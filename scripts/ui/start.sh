#!/usr/bin/env bash
set -euo pipefail

SCRIPT_PATH="$(realpath "${BASH_SOURCE[0]}")"
ROOT="$(cd "$(dirname "$SCRIPT_PATH")/../.." && pwd)"
UI="$ROOT/ui"

cd "$UI"

if [ ! -d node_modules ]; then
  npm install --no-audit --no-fund
fi

needs_build=0
if [ ! -f dist/index.html ]; then
  needs_build=1
elif [ -n "$(find src index.html vite.config.js package.json -newer dist/index.html -print -quit 2>/dev/null)" ]; then
  needs_build=1
fi

if [ "${SKIP_BUILD:-0}" != "1" ] && [ "$needs_build" = "1" ]; then
  echo "[vul-ai-board] rebuilding UI..."
  npm run build
fi

if [ -f "$ROOT/scripts/workflow/build_state.py" ]; then
  python3 "$ROOT/scripts/workflow/build_state.py" || true
fi

if [ "${REFINE_WORKER:-1}" = "1" ] && [ -x "$ROOT/scripts/workflow/refine_worker.sh" ]; then
  bash "$ROOT/scripts/workflow/refine_worker.sh" start || true
fi

exec node server/index.mjs "$@"
