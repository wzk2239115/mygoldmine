#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PROJECT=""
RUN_DIR=""

while [ "$#" -gt 0 ]; do
    case "$1" in
        --project) [ "$#" -ge 2 ] || exit 3; PROJECT="$2"; shift ;;
        --run-dir) [ "$#" -ge 2 ] || exit 3; RUN_DIR="$2"; shift ;;
        *) echo "未知参数: $1" >&2; exit 3 ;;
    esac
    shift
done

[ -n "$PROJECT" ] && [ -n "$RUN_DIR" ] || {
    echo "必须提供项目名和产物目录" >&2
    exit 3
}

export PYTHONPATH="$REPO_ROOT${PYTHONPATH:+:$PYTHONPATH}"
EXPERIENCE="$REPO_ROOT/rsi/verification-experience.jsonl"
LABELED="$REPO_ROOT/rsi/verification-experience-labeled.jsonl"
SEED_CANDIDATES="$REPO_ROOT/rsi/mining-repairs/seed-candidates"
AGENTIC_DIR="$REPO_ROOT/rsi/mining-repairs/agentic"
OUTPUT_DIR="$RUN_DIR/rsi"
mkdir -p "$OUTPUT_DIR"

python3 -m audit_rsi experience-build \
    --runs "$REPO_ROOT/runs" --output "$EXPERIENCE"
python3 -m audit_rsi redteam-experience \
    --runs "$REPO_ROOT/runs/redteam" \
    --output "$REPO_ROOT/rsi/redteam-experience.jsonl" \
    --steps-output "$REPO_ROOT/rsi/redteam-steps.jsonl"

ADDITIONAL=()
if [ -f "$LABELED" ]; then
    ADDITIONAL=(--additional-pool "$LABELED")
fi
python3 -m audit_rsi mining-repair-propose \
    --pool "$EXPERIENCE" "${ADDITIONAL[@]}" \
    --ledger "$REPO_ROOT/ui/data/finding-ledger.json" \
    --output "$SEED_CANDIDATES"
MODEL_ARGS=()
if [ -n "${RSI_LEARNER_MODEL:-}" ]; then
    MODEL_ARGS=(--model "$RSI_LEARNER_MODEL")
fi
PROMPT_FILE="$OUTPUT_DIR/learner-prompt.md"
cat > "$PROMPT_FILE" <<EOF
项目：$PROJECT
证据种子目录：$SEED_CANDIDATES
修复 Markdown 输出目录：$AGENTIC_DIR

请使用 mining-repair-learning 技能，阅读种子索引及其中有价值的候选，按 mining-repair-learner 的约定生成修复 Markdown。
只处理当前项目或具有共享价值的候选，不要把所有历史候选机械照搬。每个种子只能保留其原有证据和作用域。
EOF
mkdir -p "$AGENTIC_DIR"
find "$AGENTIC_DIR" -maxdepth 1 -type f -name 'mrc_*.md' -delete
timeout --signal=TERM --kill-after=30 "${RSI_LEARNER_TIMEOUT:-900}" \
    "${CLAUDE_BIN:-claude}" --agent mining-repair-learner \
    --permission-mode bypassPermissions --output-format stream-json --verbose \
    --mcp-config "$(python3 "$REPO_ROOT/scripts/stages/submission.py" config --stage learner --root "$AGENTIC_DIR")" \
    --append-system-prompt "$(python3 "$REPO_ROOT/scripts/stages/submission.py" instruction)" \
    "${MODEL_ARGS[@]}" -p "$(cat "$PROMPT_FILE")" > "$OUTPUT_DIR/learner.jsonl"
python3 -m audit_rsi mining-repair-context \
    --project "$PROJECT" --output "$OUTPUT_DIR/active-rules.md"

COUNT="$(find "$AGENTIC_DIR" -maxdepth 1 -type f -name 'mrc_*.md' | wc -l | tr -d ' ')"
jq -n \
    --arg status "completed" \
    --arg project "$PROJECT" \
    --argjson candidates "$COUNT" \
    --arg experience "$EXPERIENCE" \
    --arg candidate_index "$SEED_CANDIDATES/index.json" \
    --arg active_rules "$OUTPUT_DIR/active-rules.md" \
    '{schema_version:1,status:$status,project:$project,candidates:$candidates,
      experience:$experience,candidate_index:$candidate_index,active_rules:$active_rules,
      publication:"requires_independent_real_run_evaluation"}' \
    > "$OUTPUT_DIR/post-validation.json"
