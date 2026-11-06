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
    scripts/audit \
    scripts/ccui \
    scripts/mine \
    scripts/redteam \
    scripts/runner \
    scripts/stages \
    scripts/workflow \
    scripts/ci/check_expression.py \
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
        scripts/mine/repair_context.py \
        tests/test_durable_recovery.py \
        tests/test_mining_repair.py \
        tests/test_mining_driver.py \
        tests/test_agentic_propose.py \
        tests/test_clean_operation.py \
        scripts/mine/check_report.py \
        scripts/audit/check_orchestration.py \
        scripts/audit/read_coverage.py \
        tests/test_audit_read_coverage.py \
        tests/test_audit_orchestration_check.py \
        scripts/runner/smoke_runner.py \
        .claude/hooks/environment-build-guard.py \
        tests/test_environment_waiting.py \
        scripts/runner/validate_requirements.py \
        tests/test_runner_tools.py \
        tests/test_redteam_harness_preflight.py \
        scripts/ci/check_expression.py \
        tests/test_expression_audit.py \
        scripts/workflow/report_quality.py \
        scripts/workflow/flow_worker.py \
        scripts/watch/watch.py \
        tests/test_report_contract.py \
        tests/test_watch_dispatch.py \
        tests/test_flow_worker.py \
        tests/test_rsi_version.py \
        tests/test_rsi_evaluation.py \
        tests/test_rsi_experience.py \
        tests/test_rsi_verification.py \
        tests/test_rsi_eval_gates.py \
        tests/test_rsi_raw_trace.py \
        scripts/stages/skillopt_adapter.py \
        tests/test_skillopt_env_build.py \
        tests/test_skillopt_stage_learning.py \
        tests/test_phase4_verify_agent.py \
        tests/test_phase5_redteam.py \
        tests/test_visual_report.py \
        tests/test_audit_rsi.py \
        tests/test_jev_triage.py
else
    echo "ruff not installed; skipping"
fi

echo "== expression coverage =="
python3 scripts/ci/check_expression.py \
    --baseline scripts/ci/expression-baseline.json \
    --allow-unreadable .claude/skills/integer-overflow-analyzer/general.md \
    --allow-unreadable .claude/skills/numeric-conversion-error-analyzer/general.md \
    --limit 5

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
    scripts/env/phase0_env.sh \
    scripts/env/sandbox.sh \
    scripts/workflow/flow_worker.sh \
    scripts/watch/daemon.sh \
    scripts/watch/heartbeat.sh \
    scripts/verify/run_verify.sh \
    scripts/verify/auto_verify.sh \
    scripts/verify/phase4_verify_agent.sh \
    scripts/redteam/phase5_redteam.sh \
    scripts/runner/build_runner.sh \
    scripts/rsi/post_validation.sh \
    scripts/mine/visual_report.sh \
    scripts/mine/mine_one.sh \
    scripts/mine/entrypoint.sh \
    scripts/mine/mine_one_docker.sh \
    scripts/mine/parallel_mine.sh \
    scripts/mine/full_audit.sh \
    scripts/clean.sh \
    scripts/ci/fast.sh; do
    bash -n "$file"
done

echo "== runner dependency repair =="
python3 -m py_compile scripts/runner/auto_repair.py
python3 scripts/runner/validate_requirements.py --json

echo "== version store =="
if [ -d rsi/stages ]; then
    python3 -m rsi_version validate --root rsi
fi

echo "== dataset manifest =="
python3 -m rsi_version check-dataset \
    --dataset integrations/skillopt_env_build/datasets/env_build_v0.json

echo "== fast CI passed =="
