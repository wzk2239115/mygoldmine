#!/usr/bin/env bash
set -euo pipefail

SCRIPT_PATH="$(realpath "${BASH_SOURCE[0]}")"
ROOT="$(cd "$(dirname "$SCRIPT_PATH")/../.." && pwd)"
UI="$ROOT/ui"

cd "$UI"

if [ ! -d node_modules ]; then
  npm install --no-audit --no-fund
fi

if [ ! -f dist/index.html ]; then
  npm run build
fi

exec node server/index.mjs "$@"
