#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ARGS=(watch --interval "${WATCH_INTERVAL:-300}")
if [ "${WATCH_FETCH:-1}" = "1" ]; then
  ARGS+=(--fetch)
fi
exec python3 "$ROOT/scripts/watch/watch.py" "${ARGS[@]}"
