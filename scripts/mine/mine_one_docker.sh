#!/usr/bin/env bash
# 在 Docker 中跑单个项目的 mygoldmine 审计。
#
# 与 mine_one.sh 参数兼容，供 parallel_mine.sh / overnight.sh 直接调用。
# 容器内由 scripts/mine/entrypoint.sh -> mine_one.sh 执行 Claude Code，
# 产物写回宿主 RUN_DIR（raw.jsonl / claude.rendered.log / audit-report.* / run-meta.json）。
#
# 安全边界：
#   - 目标源码只读挂载到 /target，容器内复制到 /workspace/repo 再改
#   - 不挂载 docker.sock，cap-drop ALL，no-new-privileges
#   - 密钥只通过环境变量传入，不落盘
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

log() { printf '[mine_docker] %s\n' "$*" >&2; }
die() { printf '[mine_docker] ERROR: %s\n' "$*" >&2; exit "${2:-1}"; }

usage() {
    cat <<'EOF'
用法: mine_one_docker.sh [选项]

选项:
  --dry-run              只打印配置与 docker 命令，不创建目录、不调用模型
  --build                镜像不存在时自动 docker build
  --run-dir DIR          宿主产物目录（默认 runs/<project>/<utc-ts>）
  --target DIR           宿主目标源码目录
  --timeout SECONDS      墙钟超时（默认 21600）
  --model MODEL          模型（可写 360-proxy/deepseek/deepseek-v4.1-flash，
                         容器内会转成 deepseek/deepseek-v4.1-flash）
  --agent AGENT          Claude Code agent（默认 security-orchestrator）
  --project NAME         项目名
  --target-url URL       仅用于兼容 parallel_mine 的参数，容器内从 git 读取
  --prompt FILE          仅用于兼容；容器内自动生成提示词
  --no-network           容器使用 --network none（仅调试用，无法调模型）
  -h, --help             显示本帮助

鉴权（按顺序取第一个）:
  ANTHROPIC_AUTH_TOKEN  ANTHROPIC_API_KEY  GLM_API_KEY
  或 ~/.config/opencode/opencode.json 里 provider.360-proxy.options.apiKey

镜像:
  MYGOLDMINE_IMAGE（默认 mygoldmine:dev）
EOF
}

DRY_RUN=0
BUILD=0
NETWORK_MODE="${DOCKER_NETWORK:-bridge}"
RUN_DIR="${RUN_DIR:-}"
TARGET_DIR="${TARGET_DIR:-${WORK_DIR:-}}"
TIMEOUT="${TIMEOUT:-21600}"
MODEL="${MODEL:-360-proxy/deepseek/deepseek-v4.1-flash}"
AGENT="${AGENT:-security-orchestrator}"
PROJECT="${PROJECT:-}"
IMAGE="${MYGOLDMINE_IMAGE:-mygoldmine:dev}"

while [ "$#" -gt 0 ]; do
    case "$1" in
        --dry-run) DRY_RUN=1 ;;
        --build) BUILD=1 ;;
        --no-network) NETWORK_MODE="none" ;;
        --run-dir) [ "$#" -ge 2 ] || die "--run-dir 需要参数" 3; RUN_DIR="$2"; shift ;;
        --target) [ "$#" -ge 2 ] || die "--target 需要参数" 3; TARGET_DIR="$2"; shift ;;
        --timeout) [ "$#" -ge 2 ] || die "--timeout 需要参数" 3; TIMEOUT="$2"; shift ;;
        --model) [ "$#" -ge 2 ] || die "--model 需要参数" 3; MODEL="$2"; shift ;;
        --agent) [ "$#" -ge 2 ] || die "--agent 需要参数" 3; AGENT="$2"; shift ;;
        --project) [ "$#" -ge 2 ] || die "--project 需要参数" 3; PROJECT="$2"; shift ;;
        --target-url|--prompt) [ "$#" -ge 2 ] || die "$1 需要参数" 3; shift ;;
        -h|--help) usage; exit 0 ;;
        *) usage >&2; die "未知参数: $1" 3 ;;
    esac
    shift
done

[[ "$TIMEOUT" =~ ^[1-9][0-9]*$ ]] || die "TIMEOUT 必须是正整数秒" 3
[ -n "$TARGET_DIR" ] || die "缺少 --target" 3
[ -d "$TARGET_DIR" ] || die "目标目录不存在: $TARGET_DIR" 3
TARGET_REAL="$(realpath "$TARGET_DIR")"

if [ -z "$PROJECT" ]; then
    PROJECT="$(basename "${TARGET_REAL%/}")"
fi
PROJECT="$(printf '%s' "$PROJECT" | tr -c 'A-Za-z0-9._-' '_')"

if [ ! -f "$REPO_ROOT/.claude/agents/${AGENT}.md" ] && [ "$AGENT" != "security-orchestrator" ]; then
    log "WARN: 未找到 agent '${AGENT}'（可能被外部环境变量污染），回退到 security-orchestrator"
    AGENT="security-orchestrator"
fi

if [ -z "$RUN_DIR" ]; then
    RUN_DIR="$REPO_ROOT/runs/${PROJECT}/$(date -u +%Y%m%dT%H%M%SZ)"
fi
RUN_DIR="$(realpath -m "$RUN_DIR")"

CLAUDE_MODEL="$MODEL"
case "$CLAUDE_MODEL" in
    360-proxy/*) CLAUDE_MODEL="${CLAUDE_MODEL#360-proxy/}" ;;
    opencode/*)  CLAUDE_MODEL="${CLAUDE_MODEL#opencode/}" ;;
esac

ANTHROPIC_BASE_URL="${ANTHROPIC_BASE_URL:-${GLM_ANTHROPIC_BASE:-https://api.360.cn}}"
AUTH_MODE=""
AUTH_VALUE=""
if [ -n "${ANTHROPIC_AUTH_TOKEN:-}" ]; then
    AUTH_MODE="ANTHROPIC_AUTH_TOKEN"; AUTH_VALUE="$ANTHROPIC_AUTH_TOKEN"
elif [ -n "${ANTHROPIC_API_KEY:-}" ]; then
    AUTH_MODE="ANTHROPIC_API_KEY"; AUTH_VALUE="$ANTHROPIC_API_KEY"
elif [ -n "${GLM_API_KEY:-}" ]; then
    AUTH_MODE="ANTHROPIC_AUTH_TOKEN"; AUTH_VALUE="$GLM_API_KEY"
else
    cfg="${OPENCODE_CONFIG:-$HOME/.config/opencode/opencode.json}"
    if [ -f "$cfg" ] && command -v jq >/dev/null 2>&1; then
        AUTH_VALUE="$(jq -r '.provider["360-proxy"].options.apiKey // empty' "$cfg" 2>/dev/null)"
        [ -n "$AUTH_VALUE" ] && AUTH_MODE="ANTHROPIC_AUTH_TOKEN"
    fi
fi

if [ -z "$AUTH_VALUE" ] && [ "$DRY_RUN" -eq 0 ]; then
    die "缺少 360 鉴权：设置 ANTHROPIC_AUTH_TOKEN / ANTHROPIC_API_KEY / GLM_API_KEY" 8
fi

image_exists() { docker image inspect "$IMAGE" >/dev/null 2>&1; }

if ! image_exists && [ "$BUILD" -eq 0 ] && [ "$DRY_RUN" -eq 0 ]; then
    die "镜像不存在: $IMAGE（先执行 docker build -f docker/Dockerfile -t $IMAGE . 或加 --build）" 9
fi

CONTAINER_NAME="mygoldmine-${PROJECT}-$$"

docker_cmd() {
    local -a c=(docker run --rm)
    c+=(--name "$CONTAINER_NAME")
    c+=(--network "$NETWORK_MODE")
    c+=(--cap-drop ALL --security-opt no-new-privileges --pids-limit 1024)
    c+=(--tmpfs /tmp:rw,exec,size=1g)
    c+=(--mount "type=bind,src=${TARGET_REAL},dst=/target,readonly")
    c+=(--mount "type=bind,src=${RUN_DIR},dst=${RUN_DIR}")
    c+=(--mount "type=bind,src=${REPO_ROOT}/scripts,dst=/opt/mygoldmine/scripts,readonly")
    c+=(--mount "type=bind,src=${REPO_ROOT}/.claude,dst=/opt/mygoldmine/.claude,readonly")
    c+=(--mount "type=bind,src=${REPO_ROOT}/knowledge,dst=/opt/mygoldmine/knowledge")
    [ -d "$REPO_ROOT/rsi" ] && c+=(--mount "type=bind,src=${REPO_ROOT}/rsi,dst=/opt/mygoldmine/rsi,readonly")
    c+=(-e "MYGOLDMINE_HOME=/opt/mygoldmine")
    c+=(-e "TARGET_DIR=/target")
    c+=(-e "WORK_DIR=/workspace/repo")
    c+=(-e "RUN_DIR=${RUN_DIR}")
    c+=(-e "PROJECT=${PROJECT}")
    c+=(-e "TIMEOUT=${TIMEOUT}")
    c+=(-e "MODEL=${CLAUDE_MODEL}")
    c+=(-e "AGENT=${AGENT}")
    c+=(-e "ANTHROPIC_BASE_URL=${ANTHROPIC_BASE_URL}")
    c+=(-e "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1")
    c+=(-e "LIVE_RENDER=${LIVE_RENDER:-0}")
    c+=(-e "JEV_TRIAGE=${JEV_TRIAGE:-1}")
    c+=(-e "JEV_PROFILE=${JEV_PROFILE:-infra}")
    c+=(-e "JEV_MAX_FILES=${JEV_MAX_FILES:-1500}")
    c+=(-e "JEV_WORKERS=${JEV_WORKERS:-8}")
    c+=(-e "JEV_TIMEOUT=${JEV_TIMEOUT:-600}")
    [ -n "$AUTH_MODE" ] && c+=(-e "${AUTH_MODE}=${AUTH_VALUE}")
    c+=(--label "mygoldmine.project=${PROJECT}")
    c+=("$IMAGE")
    printf '%s\0' "${c[@]}"
}

if [ "$DRY_RUN" -eq 1 ]; then
    echo "=== mygoldmine docker dry-run ==="
    echo "IMAGE=$IMAGE (exists=$(image_exists && echo yes || echo no))"
    echo "TARGET=$TARGET_REAL"
    echo "RUN_DIR=$RUN_DIR"
    echo "PROJECT=$PROJECT"
    echo "TIMEOUT=$TIMEOUT"
    echo "MODEL=$MODEL"
    echo "CLAUDE_MODEL=$CLAUDE_MODEL"
    echo "AGENT=$AGENT"
    echo "ANTHROPIC_BASE_URL=$ANTHROPIC_BASE_URL"
    echo "AUTH_MODE=${AUTH_MODE:-none}"
    echo "NETWORK=$NETWORK_MODE"
    echo
    echo "--- docker command ---"
    mapfile -d '' -t _parts < <(docker_cmd)
    for _i in "${!_parts[@]}"; do
        case "${_parts[$_i]}" in
            ANTHROPIC_AUTH_TOKEN=*|ANTHROPIC_API_KEY=*) _parts[$_i]="${_parts[$_i]%%=*}=***" ;;
        esac
    done
    printf '%q ' "${_parts[@]}"; echo
    echo
    echo "=== dry-run complete: no container started ==="
    exit 0
fi

if ! image_exists; then
    log "镜像不存在，开始构建: $IMAGE"
    docker build -f "$REPO_ROOT/docker/Dockerfile" -t "$IMAGE" "$REPO_ROOT" || die "docker build 失败" 9
fi

mkdir -p "$RUN_DIR"
if [ -n "$(ls -A "$RUN_DIR" 2>/dev/null || true)" ]; then
    die "RUN_DIR 非空，拒绝覆盖: $RUN_DIR" 6
fi

RENDERER="$REPO_ROOT/scripts/mine/render_claude_log.py"
META="$RUN_DIR.meta"
RENDER_PID=""
mkdir -p "$META"

if [ "${LIVE_RENDER:-0}" = "1" ] && [ ! -f "$RENDERER" ]; then
    LIVE_RENDER=0
    export LIVE_RENDER
fi

start_renderer() {
    [ "${LIVE_RENDER:-0}" = "1" ] || return 0
    (
        for _ in $(seq 1 240); do
            [ -s "$RUN_DIR/raw.jsonl" ] && break
            sleep 0.5
        done
        [ -f "$RUN_DIR/raw.jsonl" ] || exit 0
        exec python3 "$RENDERER" --follow \
            --input "$RUN_DIR/raw.jsonl" \
            --output "$RUN_DIR/claude.rendered.log" \
            --stop-file "$META/render.stop" --quiet \
            > "$META/renderer.log" 2>&1
    ) &
    RENDER_PID=$!
    echo "$RENDER_PID" > "$META/renderer.pid"
}

stop_renderer() {
    [ -n "${RENDER_PID:-}" ] || return 0
    touch "$META/render.stop" 2>/dev/null || true
    for _ in $(seq 1 120); do
        kill -0 "$RENDER_PID" 2>/dev/null || break
        sleep 0.5
    done
    kill "$RENDER_PID" 2>/dev/null || true
    wait "$RENDER_PID" 2>/dev/null || true
    RENDER_PID=""
    if [ -s "$RUN_DIR/raw.jsonl" ]; then
        python3 "$RENDERER" --input "$RUN_DIR/raw.jsonl" \
            --output "$RUN_DIR/claude.rendered.log" --quiet \
            >> "$META/renderer.log" 2>&1 || true
    fi
}

cleanup() {
    docker stop --time 20 "$CONTAINER_NAME" >/dev/null 2>&1 || true
    stop_renderer
}
trap cleanup INT TERM

start_renderer

log "启动容器: project=$PROJECT image=$IMAGE timeout=${TIMEOUT}s model=$CLAUDE_MODEL"
mapfile -d '' -t _cmd < <(docker_cmd)
"${_cmd[@]}"
rc=$?
stop_renderer
trap - INT TERM
log "容器退出 rc=$rc run_dir=$RUN_DIR"
exit "$rc"
