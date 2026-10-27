#!/usr/bin/env bash
# mygoldmine 单项目挖掘脚本（T08）
#
# 职责：
#   1. 在目标工作副本中链接 mygoldmine 的 .claude
#   2. 以 stream-json 模式调用 Claude Code + security-orchestrator
#   3. 产出 raw.jsonl / claude.rendered.log / audit-report.md|json / run-meta.json
#   4. 超时或收到 TERM/INT 时先保留日志、渲染、写元信息，再退出
#
# 设计依据：docs/docker-claude-mining.md 第 7-9 节
# 安全边界：
#   - 不写任何密钥到产物；run-meta.json 写入前做 sk-/Bearer 模式扫描
#   - 目标 URL 中的 userinfo 会被剥离
#   - 不接受真实武器化 exploit，仅运行审计提示词
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

log() { printf '[mine_one] %s\n' "$*" >&2; }
die() { printf '[mine_one] ERROR: %s\n' "$*" >&2; exit "${2:-1}"; }

usage() {
    cat <<'EOF'
用法: mine_one.sh [选项]

选项:
  --dry-run              只打印配置与将执行的命令，不创建目录、不调用模型
  --run-dir DIR          产物目录（默认 $RUN_DIR 或 ./runs/<project>/<utc-ts>）
  --target DIR           目标工作副本（默认 $TARGET_DIR 或 $WORK_DIR）
  --prompt FILE          提示词文件（默认 $PROMPT_FILE；缺省时自动生成到 /tmp）
  --timeout SECONDS      墙钟超时（默认 $TIMEOUT 或 21600）
  --model MODEL          模型 ID（默认 $MODEL 或 360-proxy/deepseek/deepseek-v4.1-flash）
  --agent AGENT          审计智能体（默认 $AGENT 或 security-orchestrator）
  --project NAME         项目名（默认目标目录 basename）
  --target-url URL       目标仓库 URL（默认从 git remote origin 读取）
  --help                 显示本帮助

  环境变量:
  RUN_DIR TARGET_DIR WORK_DIR TIMEOUT MODEL AGENT PROJECT PROMPT_FILE
  MAX_ATTEMPTS           模型/代理瞬时错误重试次数（默认 2）
  RETRY_DELAY            重试前等待秒数（默认 60，测试可设 0）
  MYGOLDMINE_HOME        mygoldmine 骨架目录（默认仓库根目录）
  JEV_TRIAGE             审计前跑 Jev 初筛（默认 1；0 关闭）
  JEV_PROFILE            Jev profile（默认 infra）
  JEV_MAX_FILES          Jev 最大 unit 数（默认 1500）
  JEV_WORKERS            Jev 并发请求数（默认 8）
  JEV_TIMEOUT            Jev 预跑超时秒数（默认 600）

产物:
  raw.jsonl              原始 stream-json（每行一个事件）
  claude.rendered.log    人读过程日志
  claude.stderr.log      Claude CLI stderr（排障用）
  audit-report.md/json   由 security-orchestrator 写入
  run-meta.json          运行元信息（不含密钥）

退出码:
  0 成功且报告齐全；2 无有效报告；124 超时；130/143 被信号中断；
  3 输入校验失败；4 缺少 claude CLI；5 缺少依赖/脚本；6 产物目录非空
EOF
}

DRY_RUN=0
RUN_DIR="${RUN_DIR:-}"
TARGET_DIR="${TARGET_DIR:-${WORK_DIR:-}}"
PROMPT_FILE="${PROMPT_FILE:-}"
TIMEOUT="${TIMEOUT:-21600}"
MODEL="${MODEL:-360-proxy/deepseek/deepseek-v4.1-flash}"
AGENT="${AGENT:-security-orchestrator}"
PROJECT="${PROJECT:-}"
TARGET_URL="${TARGET_URL:-}"
MAX_ATTEMPTS="${MAX_ATTEMPTS:-2}"
RETRY_DELAY="${RETRY_DELAY:-60}"
MYGOLDMINE_HOME="${MYGOLDMINE_HOME:-$REPO_ROOT}"
JEV_TRIAGE="${JEV_TRIAGE:-1}"
JEV_PROFILE="${JEV_PROFILE:-infra}"
JEV_MAX_FILES="${JEV_MAX_FILES:-1500}"
JEV_WORKERS="${JEV_WORKERS:-8}"
JEV_TIMEOUT="${JEV_TIMEOUT:-600}"

while [ "$#" -gt 0 ]; do
    case "$1" in
        --dry-run) DRY_RUN=1 ;;
        --run-dir) [ "$#" -ge 2 ] || die "--run-dir 需要参数" 3; RUN_DIR="$2"; shift ;;
        --target) [ "$#" -ge 2 ] || die "--target 需要参数" 3; TARGET_DIR="$2"; shift ;;
        --prompt) [ "$#" -ge 2 ] || die "--prompt 需要参数" 3; PROMPT_FILE="$2"; shift ;;
        --timeout) [ "$#" -ge 2 ] || die "--timeout 需要参数" 3; TIMEOUT="$2"; shift ;;
        --model) [ "$#" -ge 2 ] || die "--model 需要参数" 3; MODEL="$2"; shift ;;
        --agent) [ "$#" -ge 2 ] || die "--agent 需要参数" 3; AGENT="$2"; shift ;;
        --project) [ "$#" -ge 2 ] || die "--project 需要参数" 3; PROJECT="$2"; shift ;;
        --target-url) [ "$#" -ge 2 ] || die "--target-url 需要参数" 3; TARGET_URL="$2"; shift ;;
        -h|--help) usage; exit 0 ;;
        *) usage >&2; die "未知参数: $1" 3 ;;
    esac
    shift
done

# 环境中的通用变量（如 AGENT=1）可能被其他工具占用；仅接受已存在的 agent
if [ ! -f "$MYGOLDMINE_HOME/.claude/agents/${AGENT}.md" ] && [ "$AGENT" != "security-orchestrator" ]; then
    log "WARN: 未找到 agent '${AGENT}'，回退到 security-orchestrator"
    AGENT="security-orchestrator"
fi

[[ "$TIMEOUT" =~ ^[1-9][0-9]*$ ]] || die "TIMEOUT 必须是正整数秒，当前: $TIMEOUT" 3
[[ "$MAX_ATTEMPTS" =~ ^[1-9][0-9]*$ ]] || die "MAX_ATTEMPTS 必须是正整数，当前: $MAX_ATTEMPTS" 3
[[ "$RETRY_DELAY" =~ ^[0-9]+$ ]] || die "RETRY_DELAY 必须是非负整数，当前: $RETRY_DELAY" 3

[ -n "$TARGET_DIR" ] || die "缺少 --target 或 TARGET_DIR/WORK_DIR" 3
[ -d "$TARGET_DIR" ] || die "目标目录不存在: $TARGET_DIR" 3
TARGET_REAL="$(realpath "$TARGET_DIR")"

if [ -z "$PROJECT" ]; then
    PROJECT="$(basename "${TARGET_REAL%/}")"
fi
[ -n "$PROJECT" ] || PROJECT="target"
PROJECT="$(printf '%s' "$PROJECT" | tr -c 'A-Za-z0-9._-' '_')"

if [ -z "$RUN_DIR" ]; then
    RUN_DIR="$REPO_ROOT/runs/${PROJECT}/$(date -u +%Y%m%dT%H%M%SZ)"
fi

CLAUDE_BIN="${CLAUDE_BIN:-claude}"
RENDERER="$REPO_ROOT/scripts/mine/render_claude_log.py"
RAW="$RUN_DIR/raw.jsonl"
RENDERED="$RUN_DIR/claude.rendered.log"
ERR_LOG="$RUN_DIR/claude.stderr.log"
META="$RUN_DIR/run-meta.json"
REPORT_MD="$RUN_DIR/audit-report.md"
REPORT_JSON="$RUN_DIR/audit-report.json"
CLAUDE_SOURCE="$MYGOLDMINE_HOME/.claude"
REPO_REAL="$(realpath "$REPO_ROOT")"

if [ -z "$TARGET_URL" ]; then
    TARGET_URL="$(git -C "$TARGET_REAL" remote get-url origin 2>/dev/null || true)"
fi
# 剥离 URL 中的 userinfo，避免把凭据写入 run-meta.json
TARGET_URL="$(printf '%s' "$TARGET_URL" | sed -E 's#(https?://)[^/@]+@#\1#')"
COMMIT="$(git -C "$TARGET_REAL" rev-parse HEAD 2>/dev/null || true)"

build_prompt() {
    cat <<EOF
你是 mygoldmine 的安全审计执行者。请对当前工作目录中的目标源码做安全审计。

## 目标
- 原始只读源码: ${TARGET_REAL}
- 可写工作副本: ${TARGET_REAL}
- 产物目录: ${RUN_DIR}

## 要求
1. 使用 ${AGENT} 智能体执行完整审计流程（项目画像、路由/认证分析、按语言与框架的漏洞分析、报告生成）。
2. 只分析本地源码，不访问公网，不读取目标目录之外的宿主路径。
3. 只做漏洞定位、根因分析、最小复现思路与修复建议；不要编写可直接武器化的 exploit。
4. 开始分析后尽快创建 ${REPORT_MD} 骨架，每完成一个子任务就增量更新；
   不要等所有子任务结束才写。接近超时时先落盘当前结论再退出。
5. 必须把机器可读报告写到 ${REPORT_JSON}，至少包含阶段性 findings。
6. 引用证据时给出具体文件路径与行号；无法核实的 CVE 编号标记为 unverified，不得编造。
7. 发现密钥时只报告位置与类型，不得把密钥原文写入任何报告或日志。
8. 若存在 ${RUN_DIR}/triage/jev-infra.json，先读取其中 priority>=0.6、低置信度、
   或 flags 与 mitigations 冲突的单元；Jev 只做召回，不作为 finding。

## 交付
- ${REPORT_MD}
- ${REPORT_JSON}
EOF
    local plan="${RSI_PLAN_FILE:-$MYGOLDMINE_HOME/rsi/plan.md}"
    if [ -f "$plan" ]; then
        printf '\n## 优先审计计划（audit-rsi replay policy）\n'
        cat "$plan"
        printf '\n'
    fi
}

print_dry_run() {
    local prompt_exists="false" claude_exists="false" renderer_exists="false"
    [ -n "$PROMPT_FILE" ] && [ -f "$PROMPT_FILE" ] && prompt_exists="true"
    command -v "$CLAUDE_BIN" >/dev/null 2>&1 && claude_exists="true"
    [ -f "$RENDERER" ] && renderer_exists="true"
    local target_claude="absent"
    if [ -L "$TARGET_REAL/.claude" ]; then
        target_claude="symlink -> $(readlink "$TARGET_REAL/.claude")"
    elif [ -e "$TARGET_REAL/.claude" ]; then
        target_claude="real-dir (将改名为 .claude.upstream)"
    fi

    echo "=== mygoldmine mine_one dry-run ==="
    echo "DRY_RUN=1"
    echo "REPO_ROOT=$REPO_ROOT"
    echo "TARGET=$TARGET_REAL"
    echo "RUN_DIR=$RUN_DIR"
    echo "PROJECT=$PROJECT"
    echo "TARGET_URL=${TARGET_URL:-unknown}"
    echo "COMMIT=${COMMIT:-unknown}"
    echo "TIMEOUT=$TIMEOUT"
    echo "MODEL=$MODEL"
    echo "CLAUDE_MODEL=$CLAUDE_MODEL"
    echo "ANTHROPIC_BASE_URL=$ANTHROPIC_BASE_URL"
    echo "AUTH=${ANTHROPIC_AUTH_TOKEN:+set}${ANTHROPIC_API_KEY:+set}"
    echo "AGENT=$AGENT"
    echo "MAX_ATTEMPTS=$MAX_ATTEMPTS"
    echo "RETRY_DELAY=$RETRY_DELAY"
    echo "JEV_TRIAGE=$JEV_TRIAGE JEV_PROFILE=$JEV_PROFILE JEV_MAX_FILES=$JEV_MAX_FILES JEV_WORKERS=$JEV_WORKERS JEV_TIMEOUT=$JEV_TIMEOUT"
    echo "PROMPT_FILE=${PROMPT_FILE:-<auto>} (exists=$prompt_exists)"
    echo "CLAUDE_BIN=$CLAUDE_BIN (exists=$claude_exists)"
    echo "RENDERER=$RENDERER (exists=$renderer_exists)"
    echo "TARGET_CLAUDE=$target_claude"
    echo
    echo "--- .claude 链接 ---"
    if [ "$TARGET_REAL" = "$REPO_REAL" ]; then
        echo "skip: 目标是 mygoldmine 仓库自身，保留现有 .claude"
    else
        echo "[ -e ${TARGET_REAL}/.claude ] && mv ${TARGET_REAL}/.claude ${TARGET_REAL}/.claude.upstream"
        echo "ln -sfn ${CLAUDE_SOURCE} ${TARGET_REAL}/.claude"
    fi
    echo
    echo "--- 审计命令 ---"
    echo "cd ${TARGET_REAL}"
    echo "timeout --signal=TERM --kill-after=60 ${TIMEOUT} \\"
    echo "  ${CLAUDE_BIN} --verbose --output-format=stream-json \\"
    echo "               --permission-mode=bypassPermissions \\"
    echo "               --disallowed-tools WebSearch,WebFetch \\"
    echo "               --agent ${AGENT} \\"
    echo "  < ${PROMPT_FILE:-<auto-prompt>} >> ${RAW} 2>> ${ERR_LOG}"
    echo
    echo "--- 渲染 ---"
    if [ "$renderer_exists" = "true" ]; then
        echo "python3 ${RENDERER} --input ${RAW} --output ${RENDERED}"
    else
        echo "renderer 缺失，使用 jq fallback 渲染 ${RAW} -> ${RENDERED}"
    fi
    echo "写入 ${META}（不含密钥）"
    echo
    echo "=== dry-run complete: no files created, no model calls ==="
}

if [ "$DRY_RUN" = "1" ]; then
    print_dry_run
    exit 0
fi

# ---------- 真实运行 ----------
command -v "$CLAUDE_BIN" >/dev/null 2>&1 || die "未找到 claude CLI: $CLAUDE_BIN" 4
[ -d "$CLAUDE_SOURCE" ] || die "缺少审计骨架: $CLAUDE_SOURCE" 5

mkdir -p "$RUN_DIR" || die "无法创建 RUN_DIR: $RUN_DIR" 3
if [ -n "$(ls -A "$RUN_DIR" 2>/dev/null || true)" ]; then
    die "RUN_DIR 非空，拒绝覆盖: $RUN_DIR" 6
fi

# 提示词：外部未提供时生成临时文件，退出时清理
AUTO_PROMPT=0
if [ -z "$PROMPT_FILE" ] || [ ! -f "$PROMPT_FILE" ]; then
    PROMPT_FILE="$(mktemp /tmp/mygoldmine-prompt.XXXXXX.txt)"
    build_prompt > "$PROMPT_FILE"
    AUTO_PROMPT=1
fi

# 在目标工作副本中链接 .claude；不修改 mygoldmine 仓库自身
if [ "$TARGET_REAL" != "$REPO_REAL" ]; then
    if [ -e "$TARGET_REAL/.claude" ] && [ ! -L "$TARGET_REAL/.claude" ]; then
        if [ -e "$TARGET_REAL/.claude.upstream" ]; then
            mv "$TARGET_REAL/.claude" "$TARGET_REAL/.claude.upstream.$(date -u +%s)"
        else
            mv "$TARGET_REAL/.claude" "$TARGET_REAL/.claude.upstream"
        fi
        log "目标自带 .claude 已改名保留"
    fi
    ln -sfn "$CLAUDE_SOURCE" "$TARGET_REAL/.claude"
    log "已链接 $TARGET_REAL/.claude -> $CLAUDE_SOURCE"
else
    log "目标是 mygoldmine 仓库自身，跳过 .claude 链接"
fi

# task-manage 的内置命令（init-task-json 等）需要在 PATH 中
TOOLS_DIR="$CLAUDE_SOURCE/skills/task-manage/scripts/tools"
[ -d "$TOOLS_DIR" ] && export PATH="$TOOLS_DIR:$PATH"

# 第三方代理：同步全部模型别名，避免子任务回落到默认模型。# opencode 的 provider 前缀（如 360-proxy/）不是合法 Anthropic 模型名，需剥离。
CLAUDE_MODEL="$MODEL"
case "$CLAUDE_MODEL" in
    360-proxy/*) CLAUDE_MODEL="${CLAUDE_MODEL#360-proxy/}" ;;
    opencode/*)  CLAUDE_MODEL="${CLAUDE_MODEL#opencode/}" ;;
esac
export ANTHROPIC_BASE_URL="${ANTHROPIC_BASE_URL:-${GLM_ANTHROPIC_BASE:-https://api.360.cn}}"
export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1
export ANTHROPIC_MODEL="$CLAUDE_MODEL"
export ANTHROPIC_DEFAULT_OPUS_MODEL="$CLAUDE_MODEL"
export ANTHROPIC_DEFAULT_SONNET_MODEL="$CLAUDE_MODEL"
export ANTHROPIC_DEFAULT_HAIKU_MODEL="$CLAUDE_MODEL"
export ANTHROPIC_SMALL_FAST_MODEL="$CLAUDE_MODEL"
export CLAUDE_CODE_SUBAGENT_MODEL="$CLAUDE_MODEL"
export RUN_DIR PROJECT TARGET_DIR TIMEOUT MODEL AGENT MAX_ATTEMPTS

START_EPOCH="$(date +%s)"
STARTED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
: > "$RAW"
: > "$ERR_LOG"

CHILD_PID=""
INTERRUPTED=0
INTERRUPT_RC=143
TIMED_OUT=0
ATTEMPTS=0
CLAUDE_RC=0
FINALIZED=0

on_signal() {
    INTERRUPTED=1
    INTERRUPT_RC="${1:-143}"
    log "收到中断信号，终止子进程并保留日志"
    if [ -n "$CHILD_PID" ] && kill -0 "$CHILD_PID" 2>/dev/null; then
        kill -TERM "$CHILD_PID" 2>/dev/null || true
        sleep 1
        kill -KILL "$CHILD_PID" 2>/dev/null || true
    fi
}
trap 'on_signal 130' INT
trap 'on_signal 143' TERM

is_transient_error() {
    [ -s "$ERR_LOG" ] || return 1
    grep -Eqi '429|rate.?limit|overloaded|5[0-9][0-9]|timed? ?out|ECONNRESET|ETIMEDOUT|temporarily unavailable' "$ERR_LOG"
}

render_log() {
    if [ "${LIVE_RENDER:-0}" = "1" ]; then
        log "LIVE_RENDER=1，跳过容器内最终渲染（由宿主 run.sh 实时渲染并收尾）"
        return 0
    fi
    local renderer_rc=0
    if [ -f "$RENDERER" ]; then
        log "渲染 stream-json -> $RENDERED"
        python3 "$RENDERER" --input "$RAW" --output "$RENDERED"
        renderer_rc=$?
        if [ "$renderer_rc" -ne 0 ]; then
            log "渲染器退出 $renderer_rc，回退到 jq fallback"
            render_fallback "$RAW" "$RENDERED" || true
        fi
    else
        log "渲染器缺失（T09），使用 jq fallback"
        render_fallback "$RAW" "$RENDERED" || true
        renderer_rc=127
    fi
    return "$renderer_rc"
}

render_fallback() {
    local raw="$1" out="$2"
    {
        printf '# fallback renderer: scripts/mine/render_claude_log.py 尚未安装（T09）\n'
        local line rendered
        while IFS= read -r line || [ -n "$line" ]; do
            [ -z "$line" ] && continue
            if ! printf '%s' "$line" | jq -e . >/dev/null 2>&1; then
                printf '%s\n' "$line"
                continue
            fi
            rendered="$(printf '%s' "$line" | jq -r '
                if .type == "system" and ((.subtype // "") == "init") then
                    "[init] model=\(.model // "?") cwd=\(.cwd // "?")"
                elif .type == "rate_limit_event" then
                    "[rate-limit] status=\(.rate_limit_info.status // "?")"
                elif .type == "assistant" then
                    (.message.content // [])[] |
                    if .type == "text" then (.text // "")
                    elif .type == "thinking" then "[thinking] \(.thinking // "")"
                    elif .type == "tool_use" then
                        "[tool:\(.name // "?")] \(.input.description // .input.command // .input.file_path // "")"
                    else empty end
                elif .type == "user" then
                    (.message.content // [])[] |
                    if .type == "tool_result" then
                        (if (.is_error // false) then "[tool-error] " else "[tool-result] " end) + ((.content // "") | tostring)
                    else empty end
                elif .type == "result" then
                    "[result] is_error=\(.is_error // false) duration_ms=\(.duration_ms // 0)"
                else empty end
            ' 2>/dev/null)"
            if [ -n "$rendered" ]; then
                printf '%s\n' "$rendered"
            fi
        done < "$raw"
    } > "$out"
}

maybe_jev_triage() {
    [ "$JEV_TRIAGE" = "1" ] || { log "JEV_TRIAGE=0，跳过 Jev 初筛"; return 0; }
    local script="$CLAUDE_SOURCE/skills/jev-triage/jev_triage.py"
    if [ ! -f "$script" ]; then
        log "WARN: 未找到 $script，跳过 Jev 初筛"
        return 0
    fi
    mkdir -p "$RUN_DIR/triage" || return 0
    local out="$RUN_DIR/triage/jev-${JEV_PROFILE}.json"
    log "Jev 初筛: profile=$JEV_PROFILE max_files=$JEV_MAX_FILES workers=$JEV_WORKERS -> $out"
    if timeout --signal=TERM --kill-after=30 "$JEV_TIMEOUT" python3 "$script" \
        --root "$TARGET_REAL" --profile "$JEV_PROFILE" \
        --max-files "$JEV_MAX_FILES" --workers "$JEV_WORKERS" \
        --cache-dir "$RUN_DIR/triage/jev-cache" --out "$out" \
        >> "$RUN_DIR/triage/jev.log" 2>&1; then
        log "Jev 初筛完成: $out"
    else
        log "WARN: Jev 初筛失败/超时，继续审计（详见 $RUN_DIR/triage/jev.log）"
    fi
}

write_meta() {
    local exit_code="$1" renderer_rc="$2" ended_at duration
    ended_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    duration=$(( $(date +%s) - START_EPOCH ))
    local timed_out_json="false" interrupted_json="false"
    [ "$TIMED_OUT" = "1" ] && timed_out_json="true"
    [ "$INTERRUPTED" = "1" ] && interrupted_json="true"
    local report_md_present="false" report_json_present="false"
    [ -s "$REPORT_MD" ] && report_md_present="true"
    [ -s "$REPORT_JSON" ] && report_json_present="true"

    local tmp="$META.tmp.$$"
    if ! jq -n \
        --arg schema_version "1" \
        --arg project "$PROJECT" \
        --arg target_url "$TARGET_URL" \
        --arg commit "$COMMIT" \
        --arg started_at "$STARTED_AT" \
        --arg ended_at "$ended_at" \
        --argjson duration_seconds "$duration" \
        --arg model "$MODEL" \
        --arg agent "$AGENT" \
        --argjson attempts "$ATTEMPTS" \
        --argjson exit_code "$exit_code" \
        --argjson timed_out "$timed_out_json" \
        --argjson interrupted "$interrupted_json" \
        --argjson renderer_exit_code "$renderer_rc" \
        --argjson report_md_present "$report_md_present" \
        --argjson report_json_present "$report_json_present" \
        '{
            schema_version: ($schema_version | tonumber),
            project: $project,
            target_url: $target_url,
            commit: $commit,
            started_at: $started_at,
            ended_at: $ended_at,
            duration_seconds: $duration_seconds,
            model: $model,
            agent: $agent,
            attempts: $attempts,
            exit_code: $exit_code,
            timed_out: $timed_out,
            interrupted: $interrupted,
            renderer_exit_code: $renderer_exit_code,
            reports_complete: ($report_md_present and $report_json_present),
            artifacts: {
                raw: "raw.jsonl",
                rendered: "claude.rendered.log",
                stderr: "claude.stderr.log",
                report_md: "audit-report.md",
                report_json: "audit-report.json"
            }
        }' > "$tmp"; then
        rm -f "$tmp"
        log "WARN: 生成 run-meta.json 失败"
        return 1
    fi

    if grep -Eq 'sk-[A-Za-z0-9_-]{16,}|Bearer[[:space:]]+[A-Za-z0-9._-]{16,}' "$tmp"; then
        rm -f "$tmp"
        log "ERROR: run-meta.json 命中密钥模式，拒绝写入"
        return 1
    fi
    mv "$tmp" "$META"
}

finalize() {
    [ "$FINALIZED" = "1" ] && return 0
    FINALIZED=1

    local renderer_rc=0
    render_log || renderer_rc=$?

    local effective_rc="$CLAUDE_RC"
    if [ "$INTERRUPTED" = "1" ]; then
        effective_rc="$INTERRUPT_RC"
    elif [ ! -s "$REPORT_MD" ] || [ ! -s "$REPORT_JSON" ]; then
        # Agent 提前退出：即使 rc=0 也视为失败
        [ "$effective_rc" -eq 0 ] && effective_rc=2
    fi

    write_meta "$effective_rc" "$renderer_rc" || true

    [ "$AUTO_PROMPT" = "1" ] && rm -f "$PROMPT_FILE"
    FINAL_CODE="$effective_rc"
    log "完成: exit_code=$effective_rc timed_out=$TIMED_OUT attempts=$ATTEMPTS run_dir=$RUN_DIR"
    return 0
}
trap 'finalize; [ -n "${FINAL_CODE:-}" ] && exit "$FINAL_CODE" || exit 1' EXIT

maybe_jev_triage

# 单次尝试；只有瞬时错误才重试，超时不原地重试
while :; do
    ATTEMPTS=$((ATTEMPTS + 1))
    if [ "$ATTEMPTS" -gt 1 ]; then
        printf '%s\n' "--- mine_one retry attempt ${ATTEMPTS} at $(date -u +%Y-%m-%dT%H:%M:%SZ) ---" >> "$RAW"
        log "第 ${ATTEMPTS} 次尝试"
    fi

    (
        cd "$TARGET_REAL" || exit 3
        exec timeout --signal=TERM --kill-after=60 "$TIMEOUT" \
            "$CLAUDE_BIN" --verbose --output-format=stream-json \
                --permission-mode=bypassPermissions \
                --disallowed-tools WebSearch,WebFetch \
                --agent "$AGENT"
    ) < "$PROMPT_FILE" >> "$RAW" 2>> "$ERR_LOG" &
    CHILD_PID=$!

    CLAUDE_RC=0
    wait "$CHILD_PID" || CLAUDE_RC=$?
    CHILD_PID=""

    [ "$INTERRUPTED" = "1" ] && break
    [ "$CLAUDE_RC" -eq 0 ] && break
    if [ "$CLAUDE_RC" -eq 124 ] || [ "$CLAUDE_RC" -eq 137 ]; then
        TIMED_OUT=1
        log "超时（rc=$CLAUDE_RC），保留日志并退出"
        break
    fi
    if [ "$ATTEMPTS" -lt "$MAX_ATTEMPTS" ] && is_transient_error; then
        log "检测到瞬时错误（rc=$CLAUDE_RC），${RETRY_DELAY}s 后重试"
        sleep "$RETRY_DELAY"
        continue
    fi
    break
done

# EXIT trap 会执行 finalize 并按 FINAL_CODE 退出
exit 0
