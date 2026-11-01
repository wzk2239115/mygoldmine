#!/usr/bin/env bash
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ACTION="${1:-status}"
[ "$#" -gt 0 ] && shift

PROJECT=""
RUN_DIR=""
SOURCE=""
IMAGE=""
NETWORK="bridge"

log() { printf '[sandbox] %s\n' "$*" >&2; }
die() { printf '[sandbox] ERROR: %s\n' "$*" >&2; exit "${2:-1}"; }

usage() {
    cat <<'EOF'
用法: sandbox.sh <start|status|exec|shell|isolate|connect|stop|remove> [选项] [-- command]

选项:
  --project NAME    项目名（必填）
  --run-dir DIR    对应挖掘 run；沙箱按 run 隔离并复用
  --source DIR     原始源码；start 时默认读 env-manifest.json
  --image IMAGE    环境镜像；start 时默认读 env-manifest.json
  --network MODE   start/connect 的网络（默认 bridge）

start 后工作副本保留在 /workspace/repo；stop 只停容器，remove 才删除容器。
exec/shell 可在同一工作副本中继续探索；isolate 断开所有网络后再做离线验证。
EOF
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --project) [ "$#" -ge 2 ] || die "--project 需要参数" 3; PROJECT="$2"; shift ;;
        --run-dir) [ "$#" -ge 2 ] || die "--run-dir 需要参数" 3; RUN_DIR="$2"; shift ;;
        --source) [ "$#" -ge 2 ] || die "--source 需要参数" 3; SOURCE="$2"; shift ;;
        --image) [ "$#" -ge 2 ] || die "--image 需要参数" 3; IMAGE="$2"; shift ;;
        --network) [ "$#" -ge 2 ] || die "--network 需要参数" 3; NETWORK="$2"; shift ;;
        --) shift; break ;;
        -h|--help) usage; exit 0 ;;
        *) break ;;
    esac
    shift
done

[ -n "$PROJECT" ] || die "缺少 --project" 3
[ -n "$RUN_DIR" ] || die "缺少 --run-dir" 3
PROJECT="$(printf '%s' "$PROJECT" | tr -c 'A-Za-z0-9._-' '_')"
RUN_DIR="$(realpath -m "$RUN_DIR")"
RUN_ID="$(basename "$RUN_DIR" | tr -c 'A-Za-z0-9._-' '_')"
NAME="mygoldmine-sandbox-${PROJECT}-${RUN_ID}"
MANIFEST="$REPO_ROOT/env/$PROJECT/env-manifest.json"
META="$RUN_DIR.meta"
STATE="$META/sandbox.json"

container_state() {
    docker container inspect "$NAME" --format '{{.State.Status}}' 2>/dev/null || true
}

require_running() {
    [ "$(container_state)" = "running" ] || die "沙箱未运行: $NAME（先执行 start）" 4
}

start() {
    if [ -z "$SOURCE" ] && [ -f "$MANIFEST" ]; then SOURCE="$(jq -r '.source // empty' "$MANIFEST")"; fi
    if [ -z "$IMAGE" ] && [ -f "$MANIFEST" ]; then IMAGE="$(jq -r '.image // empty' "$MANIFEST")"; fi
    [ -n "$SOURCE" ] && [ -d "$SOURCE" ] || die "源码目录无效: ${SOURCE:-<empty>}" 3
    [ -n "$IMAGE" ] || die "缺少环境镜像" 4
    SOURCE="$(realpath -e "$SOURCE")"
    docker image inspect "$IMAGE" >/dev/null 2>&1 || die "镜像不存在: $IMAGE" 4

    local state
    state="$(container_state)"
    if [ "$state" = "running" ]; then
        printf '%s\n' "$NAME"
        return 0
    fi
    if [ -n "$state" ]; then
        docker start "$NAME" >/dev/null || die "无法启动已有沙箱: $NAME" 5
    else
        mkdir -p "$RUN_DIR" "$META"
        docker run -d --name "$NAME" \
            --network "$NETWORK" \
            --cap-drop ALL --security-opt no-new-privileges \
            --pids-limit 1024 --tmpfs /tmp:rw,exec,size=1g \
            --mount "type=bind,src=$SOURCE,dst=/target,readonly" \
            --mount "type=bind,src=$RUN_DIR,dst=$RUN_DIR" \
            --mount "type=bind,src=$REPO_ROOT/scripts,dst=/opt/mygoldmine/scripts,readonly" \
            --mount "type=bind,src=$REPO_ROOT/.claude,dst=/opt/mygoldmine/.claude,readonly" \
            --mount "type=bind,src=$REPO_ROOT/knowledge,dst=/opt/mygoldmine/knowledge,readonly" \
            -e MYGOLDMINE_HOME=/opt/mygoldmine \
            -e TARGET_DIR=/target -e WORK_DIR=/workspace/repo \
            -e RUN_DIR="$RUN_DIR" -e PROJECT="$PROJECT" \
            --workdir /workspace/repo \
            --entrypoint /bin/bash \
            "$IMAGE" -lc 'cp -a /target/. /workspace/repo/ && exec tail -f /dev/null' >/dev/null \
            || die "沙箱创建失败: $NAME" 5
    fi
    mkdir -p "$META"
    jq -n \
        --arg schema_version "1" --arg project "$PROJECT" --arg run_dir "$RUN_DIR" \
        --arg container "$NAME" --arg image "$IMAGE" --arg source "$SOURCE" \
        --arg created_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
        '{schema_version:$schema_version,project:$project,run_dir:$run_dir,container:$container,image:$image,source:$source,created_at:$created_at}' \
        > "$STATE"
    printf '%s\n' "$NAME"
}

status() {
    local state networks
    state="$(container_state)"
    [ -n "$state" ] || state="absent"
    networks="$(docker container inspect "$NAME" --format '{{json .NetworkSettings.Networks}}' 2>/dev/null | jq -c 'keys' 2>/dev/null || echo '[]')"
    printf 'container=%s\nstate=%s\nnetworks=%s\nworkspace=/workspace/repo\nstate_file=%s\n' "$NAME" "$state" "$networks" "$STATE"
}

isolate() {
    require_running
    local network
    while IFS= read -r network; do
        [ -n "$network" ] && docker network disconnect "$network" "$NAME" >/dev/null 2>&1 || true
    done < <(docker container inspect "$NAME" --format '{{json .NetworkSettings.Networks}}' | jq -r 'keys[]')
    log "已断开 $NAME 的全部网络"
}

connect() {
    require_running
    docker network connect "$NETWORK" "$NAME" 2>/dev/null || true
    log "已连接 $NAME 到 $NETWORK"
}

case "$ACTION" in
    start) start ;;
    status) status ;;
    isolate) isolate ;;
    connect) connect ;;
    exec)
        require_running
        [ "$#" -gt 0 ] || die "exec 缺少命令" 3
        docker exec --workdir /workspace/repo "$NAME" "$@"
        ;;
    shell)
        require_running
        docker exec -it --workdir /workspace/repo "$NAME" /bin/bash
        ;;
    stop)
        [ -z "$(container_state)" ] || docker stop --time 20 "$NAME" >/dev/null
        log "已停止并保留沙箱: $NAME"
        ;;
    remove)
        [ -z "$(container_state)" ] || docker rm -f "$NAME" >/dev/null
        rm -f "$STATE"
        log "已删除沙箱: $NAME"
        ;;
    -h|--help|help) usage ;;
    *) usage >&2; die "未知动作: $ACTION" 3 ;;
esac
