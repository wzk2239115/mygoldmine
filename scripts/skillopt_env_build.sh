#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MODE="${1:-train}"
shift || true
SKILLOPT_ROOT="${SKILLOPT_ROOT:-$HOME/SkillOpt}"
export SKILLOPT_ROOT
TEMPLATE="$REPO_ROOT/integrations/skillopt_env_build/configs/env_build.template.yaml"
CONFIG="$REPO_ROOT/integrations/skillopt_env_build/configs/env_build.generated.yaml"

if [ ! -f "$SKILLOPT_ROOT/scripts/train.py" ]; then
    echo "SkillOpt not found at $SKILLOPT_ROOT; set SKILLOPT_ROOT" >&2
    exit 2
fi

sed -e "s#@SKILLOPT_ROOT@#$SKILLOPT_ROOT#g" \
    -e "s#@REPO_ROOT@#$REPO_ROOT#g" \
    "$TEMPLATE" > "$CONFIG"

if [ "${RUNNER_MODE:-existing}" = "command" ]; then
    sed -i.bak 's/^  runner_mode: existing/  runner_mode: command/' "$CONFIG"
    rm -f "$CONFIG.bak"
fi

case "$MODE" in
    train)
        exec python3 "$REPO_ROOT/integrations/skillopt_env_build/run_train.py" \
            --config "$CONFIG" "$@"
        ;;
    eval)
        exec python3 "$REPO_ROOT/integrations/skillopt_env_build/run_eval.py" \
            --config "$CONFIG" "$@"
        ;;
    *)
        echo "usage: $0 train|eval [args]" >&2
        exit 2
        ;;
esac
