#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PY="$ROOT/scripts/workflow/flow_worker.py"
PIDFILE="$ROOT/ui/data/flow-worker.pid"
LOG="$ROOT/ui/data/flow-worker.log"
PAUSE="$ROOT/ui/data/flow.pause"
STOP="$ROOT/ui/data/flow.stop"
BATCH="${FLOW_BATCH:-1}"
INTERVAL="${FLOW_INTERVAL:-60}"

start() {
    mkdir -p "$(dirname "$PIDFILE")"
    rm -f "$STOP"
    if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE" 2>/dev/null)" 2>/dev/null; then
        echo "[flow] already running pid=$(cat "$PIDFILE")"
        return 0
    fi
    nohup python3 "$PY" --loop --batch "$BATCH" --interval "$INTERVAL" >> "$LOG" 2>&1 &
    echo $! > "$PIDFILE"
    echo "[flow] started pid=$(cat "$PIDFILE") batch=$BATCH interval=${INTERVAL}s"
}

stop() {
    touch "$STOP"
    if [ -f "$PIDFILE" ]; then
        pid="$(cat "$PIDFILE" 2>/dev/null || true)"
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
        fi
        rm -f "$PIDFILE"
    fi
    echo "[flow] stopped"
}

status() {
    if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE" 2>/dev/null)" 2>/dev/null; then
        echo "[flow] running pid=$(cat "$PIDFILE")"
    else
        echo "[flow] not running"
    fi
    if [ -f "$ROOT/ui/data/flow-queue.json" ]; then
        jq '.stats' "$ROOT/ui/data/flow-queue.json" 2>/dev/null || true
    fi
}

reset() {
    rm -f "$ROOT/ui/data/flow-state.json" "$ROOT/ui/data/flow-queue.json"
    echo "[flow] reset"
}

case "${1:-status}" in
    start) start ;;
    stop) stop ;;
    status) status ;;
    pause) touch "$PAUSE"; echo "[flow] paused" ;;
    resume) rm -f "$PAUSE"; echo "[flow] resumed" ;;
    reset) reset ;;
    once) python3 "$PY" --once --batch "${FLOW_BATCH:-1}" ;;
    *) echo "用法: $0 {start|stop|status|pause|resume|reset|once}" >&2; exit 2 ;;
esac
