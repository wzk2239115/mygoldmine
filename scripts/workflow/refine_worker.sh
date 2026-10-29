#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PY="$ROOT/scripts/workflow/refine_worker.py"
PIDFILE="$ROOT/ui/data/refine-worker.pid"
LOG="$ROOT/ui/data/refine-worker.log"
PAUSE="$ROOT/ui/data/refine.pause"
STOP="$ROOT/ui/data/refine.stop"
BATCH="${REFINE_BATCH:-20}"
INTERVAL="${REFINE_INTERVAL:-5}"

start() {
    mkdir -p "$(dirname "$PIDFILE")"
    rm -f "$STOP"
    if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE" 2>/dev/null)" 2>/dev/null; then
        echo "[refine] already running pid=$(cat "$PIDFILE")"
        return 0
    fi
    nohup python3 "$PY" --loop --batch "$BATCH" --interval "$INTERVAL" >> "$LOG" 2>&1 &
    echo $! > "$PIDFILE"
    echo "[refine] started pid=$(cat "$PIDFILE") batch=$BATCH interval=${INTERVAL}s"
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
    echo "[refine] stopped"
}

status() {
    if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE" 2>/dev/null)" 2>/dev/null; then
        echo "[refine] running pid=$(cat "$PIDFILE")"
    else
        echo "[refine] not running"
    fi
    if [ -f "$ROOT/ui/data/refine-queue.json" ]; then
        jq '.stats' "$ROOT/ui/data/refine-queue.json" 2>/dev/null || true
    fi
}

reset() {
    rm -f "$ROOT/ui/data/refine-state.json" "$ROOT/ui/data/refine-queue.json"
    echo "[refine] reset"
}

case "${1:-status}" in
    start) start ;;
    stop) stop ;;
    status) status ;;
    pause) touch "$PAUSE"; echo "[refine] paused" ;;
    resume) rm -f "$PAUSE"; echo "[refine] resumed" ;;
    reset) reset ;;
    once) python3 "$PY" --once --batch "${REFINE_BATCH:-50}" ;;
    *) echo "用法: $0 {start|stop|status|pause|resume|reset|once}" >&2; exit 2 ;;
esac
