#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

SKILL_FILE="${ENV_BUILDER_SKILL_FILE:-}"
PROJECT="${ENV_BUILD_PROJECT:-}"
SOURCE="${ENV_BUILD_REPO:-}"
COMMIT="${ENV_BUILD_COMMIT:-}"
MODE="${ENV_BUILD_MODE:-auto}"
OUT_DIR="${ENV_BUILD_OUT_DIR:-}"
CLAUDE_BIN="${CLAUDE_BIN:-claude}"

if [ -z "$SKILL_FILE" ] || [ ! -f "$SKILL_FILE" ]; then
    echo "[build_env_agent] missing ENV_BUILDER_SKILL_FILE" >&2
    exit 2
fi
if [ -z "$SOURCE" ] || [ ! -d "$SOURCE" ]; then
    echo "[build_env_agent] missing ENV_BUILD_REPO: $SOURCE" >&2
    exit 2
fi
if [ -z "$OUT_DIR" ]; then
    echo "[build_env_agent] missing ENV_BUILD_OUT_DIR" >&2
    exit 2
fi
if ! command -v "$CLAUDE_BIN" >/dev/null 2>&1; then
    echo "[build_env_agent] claude CLI not found: $CLAUDE_BIN" >&2
    exit 4
fi

SOURCE="$(realpath "$SOURCE")"
OUT_DIR="$(realpath -m "$OUT_DIR")"
mkdir -p "$OUT_DIR"
cd "$REPO_ROOT"

PROMPT="Build a reproducible Docker environment for the source below.

project: ${PROJECT}
source: ${SOURCE}
commit: ${COMMIT}
mode: ${MODE}
env_dir: ${OUT_DIR}

Use scripts/env/build_env.sh with --env-dir ${OUT_DIR}. Do not fake ready.
Finish by writing ${OUT_DIR}/env-manifest.json with an honest env_status."

exec "$CLAUDE_BIN" \
    --agent environment-builder \
    --permission-mode=bypassPermissions \
    --disallowed-tools WebSearch,WebFetch \
    --append-system-prompt "$(cat "$SKILL_FILE")" \
    -p "$PROMPT"
