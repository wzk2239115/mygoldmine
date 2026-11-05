#!/usr/bin/env bash
# Phase 0 orchestration: environment-builder drives detection, build and repair.
# build_env.sh is a deterministic tool used by the agent, or an explicit fallback.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

log() { printf '[phase0] %s\n' "$*" >&2; }
die() { printf '[phase0] ERROR: %s\n' "$*" >&2; exit "${2:-3}"; }

usage() {
    cat <<'EOF'
用法: phase0_env.sh <源码路径> [选项]

选项:
  --project NAME         项目名（默认 basename）
  --mode MODE            build_env 安装模式：auto|none|editable|requirements|full
  --meta-dir DIR         日志与智能体结果快照目录（必填）
  --env-root DIR         env 产物根（默认 <repo>/env）
  --base-image IMAGE     基础镜像
  --build-timeout SEC    单次确定性构建超时（默认 3600）
  --network MODE         default|host|none
  --agent MODE           auto|on|off（默认 auto；auto/on 均由智能体主导）
  --agent-timeout SEC    每轮智能体构建超时（默认 1800 秒）
  --agent-rounds N       智能体构建轮数（默认 1）
  --model MODEL          environment-builder 使用的模型
  --claude-bin PATH      Claude Code 命令行工具（默认 claude）
  --skill FILE           environment-builder 技能文件（默认 integrations/.../initial.md）
  -h, --help             显示帮助

环境变量:
  BUILD_ENV_SCRIPT       覆盖确定性构建工具（测试用）
  BUILD_ENV_AGENT_SCRIPT 覆盖智能体启动脚本（测试用）
  ENV_SKIP_IMAGE_CHECK=1 跳过 docker image inspect（测试用）
  ENV_BUILDER_SKILL_FILE 覆盖技能文件路径

退出码: 0 ready；10 partial；20 blocked
EOF
}

SOURCE=""
PROJECT=""
MODE="auto"
META_DIR=""
ENV_ROOT="${ENV_ROOT:-$REPO_ROOT/env}"
BASE_IMAGE="${BASE_IMAGE:-mygoldmine:dev}"
BUILD_TIMEOUT="${BUILD_TIMEOUT:-3600}"
NETWORK="default"
AGENT_MODE="${ENV_AGENT:-auto}"
AGENT_TIMEOUT="${ENV_AGENT_TIMEOUT:-1800}"
AGENT_ROUNDS="${ENV_AGENT_ROUNDS:-1}"
MODEL="${ENV_BUILD_MODEL:-}"
CLAUDE_BIN="${CLAUDE_BIN:-claude}"
SKILL_FILE="${ENV_BUILDER_SKILL_FILE:-$REPO_ROOT/integrations/skillopt_env_build/skills/initial.md}"
BUILD_ENV_SCRIPT="${BUILD_ENV_SCRIPT:-$REPO_ROOT/scripts/env/build_env.sh}"
BUILD_ENV_AGENT_SCRIPT="${BUILD_ENV_AGENT_SCRIPT:-$REPO_ROOT/scripts/env/build_env_agent.sh}"

while [ "$#" -gt 0 ]; do
    case "$1" in
        --project) [ "$#" -ge 2 ] || die "--project 需要参数"; PROJECT="$2"; shift ;;
        --mode) [ "$#" -ge 2 ] || die "--mode 需要参数"; MODE="$2"; shift ;;
        --meta-dir) [ "$#" -ge 2 ] || die "--meta-dir 需要参数"; META_DIR="$2"; shift ;;
        --env-root) [ "$#" -ge 2 ] || die "--env-root 需要参数"; ENV_ROOT="$2"; shift ;;
        --base-image) [ "$#" -ge 2 ] || die "--base-image 需要参数"; BASE_IMAGE="$2"; shift ;;
        --build-timeout) [ "$#" -ge 2 ] || die "--build-timeout 需要参数"; BUILD_TIMEOUT="$2"; shift ;;
        --network) [ "$#" -ge 2 ] || die "--network 需要参数"; NETWORK="$2"; shift ;;
        --agent) [ "$#" -ge 2 ] || die "--agent 需要参数"; AGENT_MODE="$2"; shift ;;
        --agent-timeout) [ "$#" -ge 2 ] || die "--agent-timeout 需要参数"; AGENT_TIMEOUT="$2"; shift ;;
        --agent-rounds) [ "$#" -ge 2 ] || die "--agent-rounds 需要参数"; AGENT_ROUNDS="$2"; shift ;;
        --model) [ "$#" -ge 2 ] || die "--model 需要参数"; MODEL="$2"; shift ;;
        --claude-bin) [ "$#" -ge 2 ] || die "--claude-bin 需要参数"; CLAUDE_BIN="$2"; shift ;;
        --skill) [ "$#" -ge 2 ] || die "--skill 需要参数"; SKILL_FILE="$2"; shift ;;
        -h|--help) usage; exit 0 ;;
        --) shift; [ "$#" -ge 1 ] || die "缺少源码路径"; SOURCE="$1"; shift; break ;;
        -*) usage >&2; die "未知参数: $1" ;;
        *) [ -z "$SOURCE" ] || die "只能指定一个源码路径"; SOURCE="$1" ;;
    esac
    shift
done

[ -n "$SOURCE" ] || die "缺少源码路径"
SOURCE="$(realpath -e "$SOURCE" 2>/dev/null)" || die "源码路径不存在"
[ -d "$SOURCE" ] || die "不是目录: $SOURCE"
[ -n "$META_DIR" ] || die "缺少 --meta-dir"
case "$MODE" in none|editable|requirements|full|auto) ;; *) die "mode 非法: $MODE" ;; esac
case "$AGENT_MODE" in auto|on|off) ;; *) die "agent mode 非法: $AGENT_MODE" ;; esac
[[ "$AGENT_TIMEOUT" =~ ^[1-9][0-9]*$ ]] || die "agent-timeout 必须是正整数"
[[ "$AGENT_ROUNDS" =~ ^[1-9][0-9]*$ ]] || die "agent-rounds 必须是正整数"
[ -f "$BUILD_ENV_SCRIPT" ] || die "缺少 build_env 脚本: $BUILD_ENV_SCRIPT"

if [ -z "$PROJECT" ]; then PROJECT="$(basename "${SOURCE%/}")"; fi
PROJECT="$(printf '%s' "$PROJECT" | tr -c 'A-Za-z0-9._-' '_')"
ENV_DIR="$ENV_ROOT/$PROJECT"
MANIFEST="$ENV_DIR/env-manifest.json"
mkdir -p "$META_DIR" "$ENV_DIR"
META_DIR="$(realpath -m "$META_DIR")"
BEST_DIR="$META_DIR/env-agent-best"

read_manifest() {
    local field="$1"
    [ -f "$MANIFEST" ] || return 0
    jq -r --arg f "$field" '.[$f] // empty' "$MANIFEST" 2>/dev/null || true
}

image_ok() {
    local image="$1"
    [ -n "$image" ] || return 1
    if [ "${ENV_SKIP_IMAGE_CHECK:-0}" = "1" ]; then return 0; fi
    docker image inspect "$image" >/dev/null 2>&1
}

status_ok() {
    case "${1:-}" in ready|partial) return 0 ;; *) return 1 ;; esac
}

save_best() {
    rm -rf "$BEST_DIR"
    mkdir -p "$BEST_DIR"
    for f in Dockerfile build.sh run.sh test.sh env-manifest.json build.log; do
        [ -f "$ENV_DIR/$f" ] && cp -a "$ENV_DIR/$f" "$BEST_DIR/$f"
    done
}

restore_best() {
    [ -f "$BEST_DIR/env-manifest.json" ] || return 1
    for f in Dockerfile build.sh run.sh test.sh env-manifest.json build.log; do
        [ -f "$BEST_DIR/$f" ] && cp -a "$BEST_DIR/$f" "$ENV_DIR/$f"
    done
}

CLAUDE_AVAILABLE=0
SKILL_AVAILABLE=0
AGENT_SCRIPT_AVAILABLE=0
command -v "$CLAUDE_BIN" >/dev/null 2>&1 && CLAUDE_AVAILABLE=1
[ -f "$SKILL_FILE" ] && SKILL_AVAILABLE=1
[ -f "$BUILD_ENV_AGENT_SCRIPT" ] && AGENT_SCRIPT_AVAILABLE=1
AGENT_MISSING=""
[ "$CLAUDE_AVAILABLE" -eq 1 ] || AGENT_MISSING="${AGENT_MISSING}claude,"
[ "$SKILL_AVAILABLE" -eq 1 ] || AGENT_MISSING="${AGENT_MISSING}skill,"
[ "$AGENT_SCRIPT_AVAILABLE" -eq 1 ] || AGENT_MISSING="${AGENT_MISSING}agent-script,"
AGENT_MISSING="${AGENT_MISSING%,}"
log "智能体前置检查：请求模式=$AGENT_MODE Claude 可用=$CLAUDE_AVAILABLE 技能可用=$SKILL_AVAILABLE 脚本可用=$AGENT_SCRIPT_AVAILABLE"
[ -n "$AGENT_MISSING" ] && log "智能体前置检查缺少: $AGENT_MISSING"

BASE_STATUS="not_run"
BASE_IMAGE_ID=""
BASE_RC=null
AGENT_STATUS="off"
AGENT_RC=""
AGENT_ROUNDS_RUN=0
AGENT_REASON=""
BEST_STATUS=""
USE_AGENT=0

if [ "$AGENT_MODE" = "off" ]; then
    AGENT_REASON="disabled"
elif [ "$MODE" = "none" ]; then
    AGENT_REASON="mode_none"
elif [ "$CLAUDE_AVAILABLE" -ne 1 ] || [ "$SKILL_AVAILABLE" -ne 1 ] || [ "$AGENT_SCRIPT_AVAILABLE" -ne 1 ]; then
    AGENT_STATUS="skipped_unavailable"
    AGENT_REASON="missing_prerequisites"
    log "智能体不可用，使用确定性备用方案；缺少: ${AGENT_MISSING:-unknown}"
else
    USE_AGENT=1
fi

if [ "$USE_AGENT" -eq 1 ]; then
    for round in $(seq 1 "$AGENT_ROUNDS"); do
        AGENT_ROUNDS_RUN="$round"
        log "智能体主导构建第 $round/$AGENT_ROUNDS 轮: environment-builder"
        env \
            ENV_BUILDER_SKILL_FILE="$SKILL_FILE" \
            ENV_BUILD_PROJECT="$PROJECT" \
            ENV_BUILD_REPO="$SOURCE" \
            ENV_BUILD_COMMIT="$(git -C "$SOURCE" rev-parse --short HEAD 2>/dev/null || echo nogit)" \
            ENV_BUILD_MODE="$MODE" \
            ENV_BUILD_OUT_DIR="$ENV_DIR" \
            ENV_BUILD_BASE_IMAGE="$BASE_IMAGE" \
            ENV_BUILD_TIMEOUT="$BUILD_TIMEOUT" \
            ENV_BUILD_AGENT_TIMEOUT="$AGENT_TIMEOUT" \
            ENV_BUILD_NETWORK="$NETWORK" \
            ENV_BUILD_MODEL="$MODEL" \
            CLAUDE_BIN="$CLAUDE_BIN" \
            timeout --signal=TERM --kill-after=30 "$((AGENT_TIMEOUT + BUILD_TIMEOUT + 360))" \
            bash "$BUILD_ENV_AGENT_SCRIPT" \
            > "$META_DIR/env-build-agent-$round.log" 2>&1
        AGENT_RC=$?
        if [ -f "$ENV_DIR/.build-tasks/current.json" ]; then
            "${NODE_BIN:-node}" "$REPO_ROOT/ui/server/durable-task.mjs" --wait-build "$ENV_DIR" >> "$META_DIR/env-build-agent-$round.log" 2>&1 || true
        fi
        AGENT_STATUS="$(read_manifest env_status)"
        AGENT_IMAGE="$(read_manifest image)"
        [ -n "$AGENT_STATUS" ] || AGENT_STATUS="failed"
        if [ "$AGENT_RC" -ne 0 ]; then
            AGENT_STATUS="failed"
            AGENT_REASON="agent_failed"
            log "智能体构建第 $round 轮执行失败：退出码=$AGENT_RC"
            break
        fi
        if ! { status_ok "$AGENT_STATUS" && image_ok "$AGENT_IMAGE"; }; then
            AGENT_STATUS="failed"
            AGENT_REASON="no_usable_environment"
            log "智能体构建第 $round 轮未产出可用环境：状态=$(read_manifest env_status) 镜像=${AGENT_IMAGE:-none}"
            break
        fi
        BEST_STATUS="$AGENT_STATUS"
        AGENT_REASON="agent_primary"
        save_best
        log "智能体构建第 $round 轮产出可用环境：状态=$AGENT_STATUS 镜像=$AGENT_IMAGE"
        [ "$AGENT_STATUS" = "ready" ] && break
    done
fi

FINAL_STATUS=""
FINAL_IMAGE=""
if [ "$USE_AGENT" -eq 1 ] && [ -n "$BEST_STATUS" ] && restore_best; then
    FINAL_STATUS="$(read_manifest env_status)"
    FINAL_IMAGE="$(read_manifest image)"
    log "采用智能体构建结果：状态=$BEST_STATUS"
fi
if ! { status_ok "$FINAL_STATUS" && image_ok "$FINAL_IMAGE"; }; then
    if [ "$USE_AGENT" -eq 1 ]; then
        log "智能体未产出可用环境，执行确定性备用方案"
    else
        log "执行确定性环境构建：项目=$PROJECT 模式=$MODE 源码=$SOURCE"
    fi
    bash "$BUILD_ENV_SCRIPT" \
        "$SOURCE" --project "$PROJECT" --mode "$MODE" --env-dir "$ENV_DIR" \
        --base-image "$BASE_IMAGE" --timeout "$BUILD_TIMEOUT" --network "$NETWORK" \
        > "$META_DIR/env-build.log" 2>&1
    BASE_RC=$?
    BASE_STATUS="$(read_manifest env_status)"
    BASE_IMAGE_ID="$(read_manifest image)"
    [ -n "$BASE_STATUS" ] || BASE_STATUS="blocked"
    FINAL_STATUS="$BASE_STATUS"
    FINAL_IMAGE="$BASE_IMAGE_ID"
    log "确定性构建完成：退出码=$BASE_RC 状态=$BASE_STATUS 镜像=${BASE_IMAGE_ID:-none}"
    if [ "$USE_AGENT" -eq 1 ] && status_ok "$BASE_STATUS" && image_ok "$BASE_IMAGE_ID"; then
        AGENT_STATUS="failed_fallback"
        AGENT_REASON="fallback_baseline"
    fi
fi

if ! { status_ok "$FINAL_STATUS" && image_ok "$FINAL_IMAGE"; }; then
    FINAL_STATUS="blocked"
    [ -n "$AGENT_REASON" ] || AGENT_REASON="no_usable_environment"
    if [ ! -f "$MANIFEST" ]; then
        jq -n --arg project "$PROJECT" --arg source "$SOURCE" --arg mode "$MODE" \
            '{project:$project,source:$source,mode:$mode,env_status:"blocked",build_exit_code:20,image:"",image_id:"",partial_reasons:["build failed before manifest"],limitations:[]}' \
            > "$MANIFEST"
    fi
fi

jq -n \
    --arg project "$PROJECT" \
    --arg source "$SOURCE" \
    --arg mode "$MODE" \
    --arg baseline_status "$BASE_STATUS" \
    --arg baseline_image "$BASE_IMAGE_ID" \
    --argjson baseline_rc "$BASE_RC" \
    --arg agent_mode "$AGENT_MODE" \
    --arg agent_status "$AGENT_STATUS" \
    --arg agent_reason "$AGENT_REASON" \
    --arg agent_rc "$AGENT_RC" \
    --argjson agent_rounds "$AGENT_ROUNDS_RUN" \
    --arg claude_bin "$CLAUDE_BIN" \
    --argjson claude_available "$CLAUDE_AVAILABLE" \
    --arg skill_path "$SKILL_FILE" \
    --argjson skill_available "$SKILL_AVAILABLE" \
    --arg agent_script "$BUILD_ENV_AGENT_SCRIPT" \
    --argjson agent_script_available "$AGENT_SCRIPT_AVAILABLE" \
    --arg agent_missing "$AGENT_MISSING" \
    --arg final_status "$FINAL_STATUS" \
    --arg final_image "$FINAL_IMAGE" \
    --argjson capabilities "$(jq -cs '(.[0] // {}) | {platform,acceptance:(.reuse_verification.checks // .acceptance // []),limitations:(.limitations // []),partial_reasons:(.partial_reasons // [])}' "$MANIFEST" 2>/dev/null || echo null)" \
    --arg env_dir "$ENV_DIR" \
    --arg manifest "$MANIFEST" \
    --arg updated_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    '{project:$project,source:$source,mode:$mode,
      baseline:{status:$baseline_status,image:$baseline_image,exit_code:$baseline_rc},
      agent:{mode:$agent_mode,status:$agent_status,reason:$agent_reason,exit_code:$agent_rc,rounds:$agent_rounds,
             prerequisites:{claude_bin:$claude_bin,claude_available:($claude_available == 1),
                            skill_path:$skill_path,skill_available:($skill_available == 1),
                            script_path:$agent_script,script_available:($agent_script_available == 1),
                            missing:($agent_missing|split(",")|map(select(length>0)))}},
      final:{status:$final_status,image:$final_image,capabilities:$capabilities},
      env_dir:$env_dir, manifest:$manifest, updated_at:$updated_at}' \
    > "$META_DIR/env-phase.json"

log "final: status=$FINAL_STATUS image=${FINAL_IMAGE:-none} agent=$AGENT_STATUS baseline=$BASE_STATUS"
case "$FINAL_STATUS" in
    ready) exit 0 ;;
    partial) exit 10 ;;
    *) exit 20 ;;
esac
