#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$REPO_ROOT"

export PYTHONPATH="$REPO_ROOT${PYTHONPATH:+:$PYTHONPATH}"

echo "== compile =="
python3 -m compileall -q \
    audit_rsi \
    rsi_version \
    integrations \
    .claude/skills/jev-triage

if command -v ruff >/dev/null 2>&1; then
    echo "== ruff =="
    ruff check \
        audit_rsi \
        rsi_version \
        integrations \
        tests/test_rsi_version.py \
        tests/test_skillopt_env_build.py \
        tests/test_audit_rsi.py \
        tests/test_jev_triage.py
else
    echo "ruff not installed; skipping"
fi

echo "== pytest (deterministic) =="
python3 -m pytest -q \
    tests/test_rsi_version.py \
    tests/test_skillopt_env_build.py \
    tests/test_audit_rsi.py \
    tests/test_jev_triage.py

echo "== shell syntax =="
for file in \
    scripts/rsi.sh \
    scripts/skillopt_env_build.sh \
    scripts/env/build_env_agent.sh \
    scripts/mine/mine_one.sh \
    scripts/mine/entrypoint.sh \
    scripts/mine/mine_one_docker.sh \
    scripts/ci/fast.sh; do
    bash -n "$file"
done

echo "== version store =="
if [ -d rsi/stages ]; then
    python3 -m rsi_version validate --root rsi
fi

echo "== dataset manifest =="
python3 -m rsi_version check-dataset \
    --dataset integrations/skillopt_env_build/datasets/env_build_v0.json

echo "== fast CI passed =="
