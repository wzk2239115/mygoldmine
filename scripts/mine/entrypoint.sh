#!/usr/bin/env bash
# mygoldmine 容器入口（T07）
#
# 职责：
#   1. 解析容器运行参数（--dry-run / --help）
#   2. 校验并规范化 TARGET_DIR / RUN_DIR / TIMEOUT / MODEL / AGENT
#   3. 准备可写工作副本 /workspace/repo 并链接 .claude
#   4. 非 dry-run 时委托 scripts/mine/mine_one.sh 执行单项目审计
#
# 安全边界：
#   - 以非 root 用户运行（Dockerfile USER miner）
#   - 不读取、不挂载 /var/run/docker.sock
#   - 密钥只从环境变量读取，不写入配置文件
set -euo pipefail

usage() {
    cat <<'EOF'
用法: entrypoint.sh [--dry-run] [--help]

环境变量:
  TARGET_DIR  目标源码目录（只读挂载，默认 /target）
  RUN_DIR     产物目录（可写挂载，默认 /runs/<project>/<utc-ts>）
  TIMEOUT     单项目墙钟超时秒数（默认 21600）
  MODEL       模型 ID（默认 360-proxy/deepseek/deepseek-v4.1-flash）
  AGENT       审计智能体（默认 security-orchestrator）
  WORK_DIR    可写工作副本（默认 /workspace/repo）
  PROJECT     项目名（默认取 TARGET_DIR 的 basename）
  MAX_ATTEMPTS 模型/代理瞬时错误重试次数（默认 2，由 mine_one.sh 使用）

选项:
  --dry-run   只打印配置与将执行的命令，不创建目录、不复制文件、不调用模型
  --help      显示本帮助
EOF
}

log() { printf '[entrypoint] %s\n' "$*" >&2; }
die() { printf '[entrypoint] ERROR: %s\n' "$*" >&2; exit "${2:-1}"; }

DRY_RUN=0
while [ "$#" -gt 0 ]; do
    case "$1" in
        --dry-run) DRY_RUN=1 ;;
        -h|--help) usage; exit 0 ;;
        *) usage >&2; die "未知参数: $1" 2 ;;
    esac
    shift
done

MYGOLDMINE_HOME="${MYGOLDMINE_HOME:-/opt/mygoldmine}"
TARGET_DIR="${TARGET_DIR:-/target}"
WORK_DIR="${WORK_DIR:-/workspace/repo}"
TIMEOUT="${TIMEOUT:-21600}"
MODEL="${MODEL:-360-proxy/deepseek/deepseek-v4.1-flash}"
AGENT="${AGENT:-security-orchestrator}"
MAX_ATTEMPTS="${MAX_ATTEMPTS:-2}"

if ! [[ "$TIMEOUT" =~ ^[1-9][0-9]*$ ]]; then
    die "TIMEOUT 必须是正整数秒，当前: $TIMEOUT" 2
fi
if ! [[ "$MAX_ATTEMPTS" =~ ^[1-9][0-9]*$ ]]; then
    die "MAX_ATTEMPTS 必须是正整数，当前: $MAX_ATTEMPTS" 2
fi

if [ -z "${PROJECT:-}" ]; then
    PROJECT="$(basename "${TARGET_DIR%/}")"
    [ -n "$PROJECT" ] || PROJECT="target"
fi
PROJECT="$(printf '%s' "$PROJECT" | tr -c 'A-Za-z0-9._-' '_')"

DEFAULT_RUN_DIR="/runs/${PROJECT}/$(date -u +%Y%m%dT%H%M%SZ)"
RUN_DIR="${RUN_DIR:-$DEFAULT_RUN_DIR}"

PROMPT_FILE="${PROMPT_FILE:-/tmp/mygoldmine-prompt.txt}"
MINE_ONE="$MYGOLDMINE_HOME/scripts/mine/mine_one.sh"
RENDERER="$MYGOLDMINE_HOME/scripts/mine/render_claude_log.py"

# 第三方代理模型：同步全部模型别名，避免子任务回落到默认模型
export ANTHROPIC_MODEL="$MODEL"
export ANTHROPIC_DEFAULT_OPUS_MODEL="$MODEL"
export ANTHROPIC_DEFAULT_SONNET_MODEL="$MODEL"
export ANTHROPIC_DEFAULT_HAIKU_MODEL="$MODEL"
export ANTHROPIC_SMALL_FAST_MODEL="$MODEL"
export CLAUDE_CODE_SUBAGENT_MODEL="$MODEL"
export TARGET_DIR WORK_DIR RUN_DIR TIMEOUT MODEL AGENT MAX_ATTEMPTS PROJECT

build_prompt() {
    cat <<EOF
你是 mygoldmine 的安全审计执行者。请对当前工作目录中的目标源码做安全审计。

## 目标
- 原始只读源码: ${TARGET_DIR}
- 可写工作副本: ${WORK_DIR}
- 产物目录: ${RUN_DIR}

## 要求
1. 使用 ${AGENT} 智能体执行完整审计流程（项目画像、路由/认证分析、按语言与框架的漏洞分析、报告生成）。
2. 只分析本地源码，不访问公网，不读取 ${TARGET_DIR} 之外的宿主路径。
3. 只做漏洞定位、根因分析、最小复现思路与修复建议；不要编写可直接武器化的 exploit。
4. 必须把面向人的报告写到 ${RUN_DIR}/audit-report.md。
5. 必须把机器可读报告写到 ${RUN_DIR}/audit-report.json。
6. 引用证据时给出具体文件路径与行号；无法核实的 CVE 编号标记为 unverified，不得编造。
7. 发现密钥时只报告位置与类型，不得把密钥原文写入任何报告或日志。

## 交付
- ${RUN_DIR}/audit-report.md
- ${RUN_DIR}/audit-report.json
EOF
}

print_dry_run() {
    local target_exists="false"
    [ -d "$TARGET_DIR" ] && target_exists="true"
    local mine_one_exists="false"
    [ -x "$MINE_ONE" ] && mine_one_exists="true"
    local renderer_exists="false"
    [ -f "$RENDERER" ] && renderer_exists="true"
    local claude_version="unknown"
    if command -v claude >/dev/null 2>&1; then
        claude_version="$(claude --version 2>/dev/null | head -n 1 || true)"
    fi

    echo "=== mygoldmine container dry-run ==="
    echo "DRY_RUN=1"
    echo "MYGOLDMINE_HOME=$MYGOLDMINE_HOME"
    echo "TARGET_DIR=$TARGET_DIR"
    echo "TARGET_EXISTS=$target_exists"
    echo "WORK_DIR=$WORK_DIR"
    echo "RUN_DIR=$RUN_DIR"
    echo "PROJECT=$PROJECT"
    echo "TIMEOUT=$TIMEOUT"
    echo "MODEL=$MODEL"
    echo "AGENT=$AGENT"
    echo "MAX_ATTEMPTS=$MAX_ATTEMPTS"
    echo "PROMPT_FILE=$PROMPT_FILE"
    echo "CLAUDE_CODE=$claude_version"
    echo "MINE_ONE=$MINE_ONE (exists=$mine_one_exists)"
    echo "RENDERER=$RENDERER (exists=$renderer_exists)"
    if [ -S /var/run/docker.sock ]; then
        echo "DOCKER_SOCKET=mounted=true (拒绝运行，除非 ALLOW_DOCKER_SOCKET=1)"
    else
        echo "DOCKER_SOCKET=mounted=false"
    fi
    echo "NETWORK_MODE=${MYGOLDMINE_NETWORK_MODE:-unknown}"
    echo
    echo "--- prompt preview ---"
    build_prompt
    echo "--- end prompt preview ---"
    echo
    echo "--- workspace preparation ---"
    echo "cp -a ${TARGET_DIR}/. ${WORK_DIR}/"
    echo "[ -e ${WORK_DIR}/.claude ] && mv ${WORK_DIR}/.claude ${WORK_DIR}/.claude.upstream"
    echo "ln -sfn ${MYGOLDMINE_HOME}/.claude ${WORK_DIR}/.claude"
    echo
    echo "--- audit command ---"
    echo "cd ${WORK_DIR}"
    echo "timeout --signal=TERM --kill-after=60 ${TIMEOUT} \\"
    echo "  claude --verbose --output-format=stream-json \\"
    echo "        --permission-mode=bypassPermissions \\"
    echo "        --disallowed-tools WebSearch,WebFetch \\"
    echo "        --agent ${AGENT} \\"
    echo "  < ${PROMPT_FILE} | tee -a ${RUN_DIR}/raw.jsonl"
    echo
    echo "--- delegation ---"
    if [ "$mine_one_exists" = "true" ]; then
        echo "exec ${MINE_ONE} --run-dir ${RUN_DIR} --target ${WORK_DIR}"
    else
        echo "exec ${MINE_ONE} (尚未实现，属于 T08；当前仅支持 --dry-run)"
    fi
    echo
    echo "=== dry-run complete: no files created, no model calls ==="
}

if [ "$DRY_RUN" = "1" ]; then
    print_dry_run
    exit 0
fi

# ---------- 真实运行 ----------
[ -d "$TARGET_DIR" ] || die "TARGET_DIR 不存在或不是目录: $TARGET_DIR" 3
[ -r "$TARGET_DIR" ] || die "TARGET_DIR 不可读: $TARGET_DIR" 3

if [ -S /var/run/docker.sock ] && [ "${ALLOW_DOCKER_SOCKET:-0}" != "1" ]; then
    die "检测到 /var/run/docker.sock；默认禁止挂载（如确需请设置 ALLOW_DOCKER_SOCKET=1）" 7
fi

command -v claude >/dev/null 2>&1 || die "容器内未找到 claude CLI" 4
[ -x "$MINE_ONE" ] || die "缺少 $MINE_ONE（T08 尚未实现）；当前仅支持 --dry-run" 5

TARGET_REAL="$(realpath "$TARGET_DIR")"
WORK_REAL_PARENT="$(realpath -m "$(dirname "$WORK_DIR")")"
mkdir -p "$WORK_REAL_PARENT"
mkdir -p "$RUN_DIR"

if [ -n "$(ls -A "$RUN_DIR" 2>/dev/null || true)" ]; then
    die "RUN_DIR 非空，拒绝覆盖: $RUN_DIR" 6
fi

if [ "$TARGET_REAL" != "$(realpath -m "$WORK_DIR")" ]; then
    mkdir -p "$WORK_DIR"
    log "复制目标源码到可写工作副本: $TARGET_DIR -> $WORK_DIR"
    find "$WORK_DIR" -mindepth 1 -maxdepth 1 -exec rm -rf {} + 2>/dev/null || true
    cp -a "$TARGET_DIR/." "$WORK_DIR/"
fi

if [ -e "$WORK_DIR/.claude" ] && [ ! -L "$WORK_DIR/.claude" ]; then
    mv "$WORK_DIR/.claude" "$WORK_DIR/.claude.upstream"
fi
ln -sfn "$MYGOLDMINE_HOME/.claude" "$WORK_DIR/.claude"
log "已链接 .claude -> $MYGOLDMINE_HOME/.claude"

build_prompt > "$PROMPT_FILE"
log "提示词已写入 $PROMPT_FILE"

log "委托 mine_one.sh 执行审计（timeout=${TIMEOUT}s, model=${MODEL}, agent=${AGENT}）"
exec "$MINE_ONE" --run-dir "$RUN_DIR" --target "$WORK_DIR" --prompt "$PROMPT_FILE"
