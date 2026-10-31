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
    scripts/ccui \
    scripts/mine \
    scripts/redteam \
    scripts/workflow \
    .claude/skills/jev-triage

if command -v ruff >/dev/null 2>&1; then
    echo "== ruff =="
    ruff check \
        audit_rsi \
        rsi_version \
        integrations \
        scripts/ccui \
        scripts/mine/progress_guard.py \
        scripts/mine/durable_recovery.py \
        tests/test_durable_recovery.py \
        scripts/mine/check_report.py \
        scripts/workflow/report_quality.py \
        tests/test_report_contract.py \
        tests/test_rsi_version.py \
        tests/test_rsi_evaluation.py \
        tests/test_rsi_experience.py \
        tests/test_rsi_verification.py \
        tests/test_rsi_eval_gates.py \
        tests/test_rsi_raw_trace.py \
        tests/test_skillopt_env_build.py \
        tests/test_audit_rsi.py \
        tests/test_jev_triage.py
else
    echo "ruff not installed; skipping"
fi

echo "== pytest (deterministic) =="
python3 -m pytest -q tests

if command -v node >/dev/null 2>&1; then
    echo "== UI contract tests =="
    (cd ui && node --test tests/*.test.mjs)
fi

echo "== shell syntax =="
for file in \
    run.sh \
    scripts/rsi.sh \
    scripts/skillopt_env_build.sh \
    scripts/ccui/start.sh \
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
