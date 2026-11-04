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
BASE_IMAGE="${ENV_BUILD_BASE_IMAGE:-mygoldmine:dev}"
BUILD_TIMEOUT="${ENV_BUILD_TIMEOUT:-3600}"
NETWORK="${ENV_BUILD_NETWORK:-default}"
MODEL="${ENV_BUILD_MODEL:-}"
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
case "$MODEL" in
    360-proxy/*) MODEL="${MODEL#360-proxy/}" ;;
    opencode/*) MODEL="${MODEL#opencode/}" ;;
esac
export ANTHROPIC_BASE_URL="${ANTHROPIC_BASE_URL:-${GLM_ANTHROPIC_BASE:-https://api.360.cn}}"
export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1
if [ -n "$MODEL" ]; then
    export ANTHROPIC_MODEL="$MODEL"
    export ANTHROPIC_DEFAULT_OPUS_MODEL="$MODEL"
    export ANTHROPIC_DEFAULT_SONNET_MODEL="$MODEL"
    export ANTHROPIC_DEFAULT_HAIKU_MODEL="$MODEL"
    export ANTHROPIC_SMALL_FAST_MODEL="$MODEL"
    export CLAUDE_CODE_SUBAGENT_MODEL="$MODEL"
fi
if [ -z "${ANTHROPIC_AUTH_TOKEN:-}" ] && [ -z "${ANTHROPIC_API_KEY:-}" ]; then
    if [ -n "${GLM_API_KEY:-}" ]; then
        export ANTHROPIC_AUTH_TOKEN="$GLM_API_KEY"
    else
        OPENCODE_CFG="${OPENCODE_CONFIG:-$HOME/.config/opencode/opencode.json}"
        if [ -f "$OPENCODE_CFG" ] && command -v jq >/dev/null 2>&1; then
            AUTH_VALUE="$(jq -r '.provider["360-proxy"].options.apiKey // empty' "$OPENCODE_CFG" 2>/dev/null)"
            [ -z "$AUTH_VALUE" ] || export ANTHROPIC_AUTH_TOKEN="$AUTH_VALUE"
        fi
    fi
fi
mkdir -p "$OUT_DIR"
cd "$REPO_ROOT"

LANGUAGE_DIRECTIVE="$(python3 "$REPO_ROOT/scripts/config/language.py" --prompt 2>/dev/null || true)"
PROMPT="${LANGUAGE_DIRECTIVE}

Build a reproducible Docker environment for the source below.

project: ${PROJECT}
source: ${SOURCE}
commit: ${COMMIT}
mode: ${MODE}
env_dir: ${OUT_DIR}
base_image: ${BASE_IMAGE}
build_timeout_seconds: ${BUILD_TIMEOUT}
docker_network: ${NETWORK}

You own detection, build decisions, failure diagnosis, repair and runtime checks.
Use scripts/env/build_env.sh as a build tool with --env-dir ${OUT_DIR}, not as a
substitute for your own inspection and decisions. Do not stop after a dry-run.
Do not fake ready. Finish by writing ${OUT_DIR}/env-manifest.json with an honest
env_status after an actual build, verified reuse, or an explicit blocked result."

CLAUDE_ARGS=(
    --mcp-config "$(python3 "$REPO_ROOT/scripts/stages/submission.py" config --stage environment --root "$OUT_DIR")"
    --agent environment-builder
    --setting-sources project,local
    --output-format stream-json
    --verbose
    --permission-mode=bypassPermissions
    --disallowed-tools WebSearch,WebFetch
    --append-system-prompt "$(cat "$SKILL_FILE")
$(python3 "$REPO_ROOT/scripts/stages/submission.py" instruction --stage environment --root "$OUT_DIR")"
)
[ -n "$MODEL" ] && CLAUDE_ARGS+=(--model "$MODEL")
CLAUDE_ARGS+=(-p "$PROMPT")

exec "$CLAUDE_BIN" "${CLAUDE_ARGS[@]}"
