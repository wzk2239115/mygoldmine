#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ARGS=(watch --interval "${WATCH_INTERVAL:-300}" --window-hours "${WATCH_WINDOW_HOURS:-24}")
if [ "${WATCH_FETCH:-1}" = "1" ]; then
  ARGS+=(--fetch)
fi
if [ "${WATCH_AUTO_RUN:-1}" = "1" ]; then
  ARGS+=(--auto-run)
fi
exec python3 "$ROOT/scripts/watch/watch.py" "${ARGS[@]}"
