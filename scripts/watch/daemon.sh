#!/usr/bin/env bash
# 后台常驻“自动狩猎”进程管理。
#
# 启动后会立刻执行一次轮询：先 fetch，再审查最近 WATCH_WINDOW_HOURS 小时内
# （默认 24 小时）的新提交，因此刚启动就能看到前一天的更新。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PIDFILE="$ROOT/runs/watch/watchd.pid"
LOG="$ROOT/runs/watch/watchd.log"
INTERVAL="${WATCH_INTERVAL:-300}"
WINDOW="${WATCH_WINDOW_HOURS:-24}"
LIMIT="${WATCH_LIMIT:-50}"
DEPTH="${WATCH_FETCH_DEPTH:-50}"
FETCH="${WATCH_FETCH:-1}"
AUTO_RUN="${WATCH_AUTO_RUN:-1}"

build_args() {
    local out=(watch --interval "$INTERVAL" --window-hours "$WINDOW" --limit "$LIMIT" --fetch-depth "$DEPTH")
    if [ "$FETCH" = "1" ]; then
        out+=(--fetch)
    fi
    if [ "$AUTO_RUN" = "1" ]; then
        out+=(--auto-run)
    fi
    printf '%s\n' "${out[@]}"
}

start() {
    mkdir -p "$(dirname "$PIDFILE")"
    if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE" 2>/dev/null)" 2>/dev/null; then
        echo "[watch] already running pid=$(cat "$PIDFILE")"
        return 0
    fi
    mapfile -t ARGS < <(build_args)
    setsid nohup python3 "$ROOT/scripts/watch/watch.py" "${ARGS[@]}" \
        >> "$LOG" 2>&1 < /dev/null &
    echo $! > "$PIDFILE"
    echo "[watch] started pid=$(cat "$PIDFILE") interval=${INTERVAL}s window=${WINDOW}h fetch=$FETCH auto_run=$AUTO_RUN"
}

stop() {
    if [ -f "$PIDFILE" ]; then
        pid="$(cat "$PIDFILE" 2>/dev/null || true)"
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
        fi
        rm -f "$PIDFILE"
    fi
    echo "[watch] stopped"
}

status() {
    if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE" 2>/dev/null)" 2>/dev/null; then
        echo "[watch] running pid=$(cat "$PIDFILE") interval=${INTERVAL}s window=${WINDOW}h fetch=$FETCH"
    else
        echo "[watch] not running"
    fi
    python3 "$ROOT/scripts/watch/watch.py" status
}

case "${1:-status}" in
    start) start ;;
    stop) stop ;;
    status) status ;;
    once)
        ARGS=(poll --fetch --window-hours "$WINDOW" --limit "$LIMIT" --fetch-depth "$DEPTH")
        [ "$AUTO_RUN" = "1" ] && ARGS+=(--auto-run)
        python3 "$ROOT/scripts/watch/watch.py" "${ARGS[@]}"
        ;;
    *) echo "用法: $0 {start|stop|status|once}" >&2; exit 2 ;;
esac
