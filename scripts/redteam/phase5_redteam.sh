#!/usr/bin/env bash
# Phase 5: select findings from one audit report, run the red-team batch and judge,
# then write a machine-readable summary. This wrapper never invents approvals.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PYTHON="${PYTHON:-python3}"

log() { printf '[phase5] %s\n' "$*" >&2; }
die() {
    local message="$1"
    local code="${2:-3}"
    printf '[phase5] ERROR: %s\n' "$message" >&2
    exit "$code"
}

usage() {
    cat <<'EOF'
用法: phase5_redteam.sh --project NAME --run-dir DIR [选项]

必填:
  --project NAME           项目名
  --run-dir DIR            含 audit-report.json 的批量审计产物目录

选项:
  --max N                  最多选择条数（默认 5）
  --severity LIST          逗号分隔的严重级别（默认 critical,high）
  --finding-id ID          只选择指定候选问题编号（自动流转用）
  --model MODEL            红队模型（默认 $REDTEAM_MODEL 或审计模型）
  --base-url URL           模型服务地址（默认 $REDTEAM_BASE_URL）
  --api-key KEY            模型服务密钥（默认 $REDTEAM_API_KEY 或 local）
  --build-timeout SEC      隔离验证环境构建超时（默认 1260 秒）
  --agent-timeout SEC      红队智能体超时（默认 900 秒）
  --judge-timeout SEC      独立审核超时（默认 360 秒）
  --judge-claude BIN       独立审核命令行工具（默认 claude）
  --judge-claude-model M   独立审核模型（默认空）
  --output DIR             输出目录（默认 runs/redteam/<project>/phase5-<UTC>）
  -h, --help               显示帮助

环境变量:
  REDTEAM_BATCH_PY         覆盖 batch.py 路径（测试用）
  REDTEAM_BATCH_CMD        覆盖完整 batch 命令（测试用）
  REDTEAM_BUILD_STATE_PY   覆盖 build_state.py 路径（测试用）

退出码: 0 批次完成（含 blocked/rejected）；3 配置或输入错误；4 缺少必需工具
EOF
}

PROJECT=""
RUN_DIR=""
MAX=5
SEVERITY="critical,high"
FINDING_ID_FILTER=""
MODEL="${REDTEAM_MODEL:-${MODEL:-360-proxy/deepseek/deepseek-v4.1-flash}}"
BASE_URL="${REDTEAM_BASE_URL:-}"
API_KEY="${REDTEAM_API_KEY:-}"
BUILD_TIMEOUT=1260
AGENT_TIMEOUT=900
JUDGE_TIMEOUT=360
JUDGE_CLAUDE="${REDTEAM_JUDGE_CLAUDE:-claude}"
JUDGE_CLAUDE_MODEL="${REDTEAM_JUDGE_CLAUDE_MODEL:-}"
OUTPUT=""

while [ "$#" -gt 0 ]; do
    case "$1" in
        --project) [ "$#" -ge 2 ] || die "--project 需要参数"; PROJECT="$2"; shift ;;
        --run-dir) [ "$#" -ge 2 ] || die "--run-dir 需要参数"; RUN_DIR="$2"; shift ;;
        --max) [ "$#" -ge 2 ] || die "--max 需要参数"; MAX="$2"; shift ;;
        --severity) [ "$#" -ge 2 ] || die "--severity 需要参数"; SEVERITY="$2"; shift ;;
        --finding-id) [ "$#" -ge 2 ] || die "--finding-id 需要参数"; FINDING_ID_FILTER="$2"; shift ;;
        --model) [ "$#" -ge 2 ] || die "--model 需要参数"; MODEL="$2"; shift ;;
        --base-url) [ "$#" -ge 2 ] || die "--base-url 需要参数"; BASE_URL="$2"; shift ;;
        --api-key) [ "$#" -ge 2 ] || die "--api-key 需要参数"; API_KEY="$2"; shift ;;
        --build-timeout) [ "$#" -ge 2 ] || die "--build-timeout 需要参数"; BUILD_TIMEOUT="$2"; shift ;;
        --agent-timeout) [ "$#" -ge 2 ] || die "--agent-timeout 需要参数"; AGENT_TIMEOUT="$2"; shift ;;
        --judge-timeout) [ "$#" -ge 2 ] || die "--judge-timeout 需要参数"; JUDGE_TIMEOUT="$2"; shift ;;
        --judge-claude) [ "$#" -ge 2 ] || die "--judge-claude 需要参数"; JUDGE_CLAUDE="$2"; shift ;;
        --judge-claude-model) [ "$#" -ge 2 ] || die "--judge-claude-model 需要参数"; JUDGE_CLAUDE_MODEL="$2"; shift ;;
        --output) [ "$#" -ge 2 ] || die "--output 需要参数"; OUTPUT="$2"; shift ;;
        -h|--help) usage; exit 0 ;;
        *) usage >&2; die "未知参数: $1" ;;
    esac
    shift
done

command -v "$PYTHON" >/dev/null 2>&1 || die "缺少必需工具: $PYTHON" 4

[ -n "$PROJECT" ] || die "缺少 --project"
[ -n "$RUN_DIR" ] || die "缺少 --run-dir"
case "$PROJECT" in */*) die "--project 不能包含 /" ;; esac
[[ "$MAX" =~ ^[1-9][0-9]*$ ]] || die "--max 必须正整数"
for timeout in "$BUILD_TIMEOUT" "$AGENT_TIMEOUT" "$JUDGE_TIMEOUT"; do
    [[ "$timeout" =~ ^[1-9][0-9]*$ ]] || die "timeout 必须正整数"
done
[ -n "$SEVERITY" ] || die "--severity 不能为空"

[ -d "$RUN_DIR" ] || die "产物目录不存在: $RUN_DIR"
RUN_DIR="$(realpath -e "$RUN_DIR")" || die "无法解析产物目录: $RUN_DIR"
AUDIT_REPORT="$RUN_DIR/audit-report.json"
[ -f "$AUDIT_REPORT" ] || die "缺少 audit-report.json: $AUDIT_REPORT"
RUN_ID="$(basename "$RUN_DIR")"

if [ -z "$OUTPUT" ]; then
    OUTPUT="$ROOT/runs/redteam/$PROJECT/phase5-$(date -u +%Y%m%dT%H%M%SZ)"
fi
OUTPUT="$(realpath -m "$OUTPUT")"
mkdir -p "$OUTPUT" || die "无法创建输出目录: $OUTPUT"

CANDIDATES="$OUTPUT/candidates.json"
SELECTION="$OUTPUT/selection.json"
"$PYTHON" - "$AUDIT_REPORT" "$PROJECT" "$RUN_ID" "$MAX" "$SEVERITY" "$CANDIDATES" "$SELECTION" "$FINDING_ID_FILTER" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

report_path, project, run_id, max_raw, severity_raw, candidates_out, selection_out, only_id = sys.argv[1:9]


def fail(message):
    print(json.dumps({"error": message}, ensure_ascii=False))
    sys.exit(3)


def normalize_severity(value):
    raw = str(value or "info").strip().lower()
    if raw.startswith("critical") or raw == "crit":
        return "critical"
    if raw.startswith("high"):
        return "high"
    if raw.startswith("medium") or raw.startswith("moderate"):
        return "medium"
    if raw.startswith("low"):
        return "low"
    return "info"


try:
    maximum = int(max_raw)
except ValueError:
    fail("invalid --max")

allowed = [item.strip().lower() for item in severity_raw.split(",") if item.strip()]
valid = {"critical", "high", "medium", "low", "info"}
if not allowed or any(item not in valid for item in allowed):
    fail("invalid --severity (use critical,high,medium,low,info)")

try:
    report = json.loads(Path(report_path).read_text(encoding="utf-8"))
except (OSError, ValueError) as exc:
    fail(f"invalid audit-report.json: {exc}")
if not isinstance(report, dict):
    fail("audit-report.json must be a JSON object")

sources = []
found_source = False
for key in ("findings", "vulnerabilities"):
    value = report.get(key)
    if isinstance(value, list):
        found_source = True
        sources.extend(value)
    elif value is not None:
        fail(f"audit-report.json .{key} must be a list")
if not found_source:
    fail("audit-report.json has no findings or vulnerabilities list")

selected = []
seen = set()
matched = 0
duplicates = 0
for raw in sources:
    if not isinstance(raw, dict):
        continue
    finding_id = str(raw.get("id") or raw.get("finding_id") or "").strip()
    if not finding_id:
        continue
    if only_id and finding_id != only_id:
        continue
    severity = normalize_severity(raw.get("severity") or raw.get("severity_raw"))
    if severity not in allowed:
        continue
    matched += 1
    if finding_id in seen:
        duplicates += 1
        continue
    seen.add(finding_id)
    if len(selected) >= maximum:
        continue
    selected.append({"project": project, "id": finding_id, "run_id": run_id})

generated_at = datetime.now(timezone.utc).isoformat()
Path(candidates_out).write_text(
    json.dumps({
        "project": project,
        "run_id": run_id,
        "generated_at": generated_at,
        "candidates": selected,
    }, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
Path(selection_out).write_text(
    json.dumps({
        "report": str(report_path),
        "project": project,
        "run_id": run_id,
        "max": maximum,
        "severity": allowed,
        "finding_id": only_id,
        "total_findings": len(sources),
        "matched": matched,
        "selected": len(selected),
        "duplicates_skipped": duplicates,
        "candidates": selected,
        "generated_at": generated_at,
    }, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
PY
SELECT_RC=$?
[ "$SELECT_RC" -eq 0 ] || die "无法从 audit-report.json 选择候选问题（returncode=$SELECT_RC）" 3

SELECTED="$("$PYTHON" -c 'import json,sys; print(len(json.load(open(sys.argv[1], encoding="utf-8")).get("candidates", [])))' "$CANDIDATES")" \
    || die "无法读取 candidates.json"

write_summary() {
    local batch_summary="$1"
    local batch_rc="$2"
    local build_attempted="$3"
    local build_rc="$4"
    local final_status="$5"
    "$PYTHON" - "$batch_summary" "$OUTPUT/summary.json" "$OUTPUT/summary.md" "$SELECTION" \
        "$PROJECT" "$RUN_DIR" "$OUTPUT/batch" "$batch_rc" "$build_attempted" "$build_rc" \
        "$final_status" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

(
    batch_summary_path,
    out_json,
    out_md,
    selection_path,
    project,
    run_dir,
    batch_out,
    batch_rc,
    build_attempted,
    build_rc,
    final_status,
) = sys.argv[1:12]

try:
    selection = json.loads(Path(selection_path).read_text(encoding="utf-8"))
except (OSError, ValueError):
    selection = {}
candidates = selection.get("candidates") if isinstance(selection.get("candidates"), list) else []

batch_summary = {}
batch_error = None
if batch_summary_path != "-":
    try:
        batch_summary = json.loads(Path(batch_summary_path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        batch_error = str(exc)
if not isinstance(batch_summary, dict):
    batch_summary = {}
batch_results = batch_summary.get("results") if isinstance(batch_summary.get("results"), list) else []

normalized = []
by_key = {}
for item in batch_results:
    if not isinstance(item, dict):
        continue
    key = (str(item.get("project", "")), str(item.get("id") or item.get("finding_id") or ""))
    by_key[key] = item

used = set()
for candidate in candidates:
    key = (str(candidate.get("project", "")), str(candidate.get("id", "")))
    used.add(key)
    item = by_key.get(key)
    if item is None:
        normalized.append({**candidate, "status": "missing_result"})
    else:
        normalized.append({
            **item,
            "project": candidate.get("project"),
            "id": candidate.get("id"),
            "run_id": candidate.get("run_id", ""),
        })

for item in batch_results:
    if not isinstance(item, dict):
        continue
    key = (str(item.get("project", "")), str(item.get("id") or item.get("finding_id") or ""))
    if key not in used:
        normalized.append(item)
        used.add(key)

counts = {}
for item in normalized:
    status = str(item.get("status") or "unknown")
    counts[status] = counts.get(status, 0) + 1

try:
    batch_returncode = int(batch_rc)
except (TypeError, ValueError):
    batch_returncode = None
try:
    build_returncode = int(build_rc)
except (TypeError, ValueError):
    build_returncode = None

if final_status == "completed":
    terminal = {"judge_approved", "judge_rejected", "judge_needs_review", "flag_captured", "not_captured", "completed", "ready"}
    failures = [item for item in normalized if str(item.get("status")) not in terminal]
    if failures:
        final_status = "blocked" if len(failures) == len(normalized) else "partial"
completed = final_status in {"completed", "no_findings"}
payload = {
    "schema_version": 1,
    "phase": 5,
    "project": project,
    "run_dir": run_dir,
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "status": final_status,
    "completed": completed,
    "severity": selection.get("severity", []),
    "max": selection.get("max"),
    "selection": {
        "report": selection.get("report"),
        "total_findings": selection.get("total_findings"),
        "matched": selection.get("matched"),
        "selected": selection.get("selected"),
        "duplicates_skipped": selection.get("duplicates_skipped"),
    },
    "candidates": candidates,
    "batch": {
        "out_dir": batch_out,
        "returncode": batch_returncode,
        "summary": None if batch_summary_path == "-" else batch_summary_path,
        "error": batch_error,
    },
    "build_state": {
        "attempted": build_attempted == "true",
        "returncode": build_returncode,
        "log": str(Path(out_json).parent / "build-state.log"),
    },
    "counts": counts,
    "results": normalized,
}
Path(out_json).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def cell(value):
    return str(value if value is not None else "").replace("|", "\\|").replace("\n", " ").strip()


lines = [
    "# Phase 5 red-team summary",
    "",
    f"- Project: {cell(project)}",
    f"- Run dir: {cell(run_dir)}",
    f"- Status: {cell(final_status)}",
    f"- Selected: {cell(selection.get('selected'))} / max {cell(selection.get('max'))}",
    f"- Severity filter: {cell(','.join(selection.get('severity') or []))}",
    f"- Batch return code: {cell(batch_returncode)}",
    f"- Build state: attempted={cell(build_attempted)} returncode={cell(build_returncode)}",
    "",
]
if final_status == "no_findings":
    lines += ["No findings matched the severity filter; the batch was not run.", ""]
if batch_error:
    lines += [f"Batch summary error: {cell(batch_error)}", ""]
lines += ["## Counts", ""]
if counts:
    lines += ["| status | count |", "| --- | --- |"]
    for status in sorted(counts):
        lines.append(f"| {cell(status)} | {counts[status]} |")
else:
    lines.append("No candidate results.")
lines += ["", "## Candidates", ""]
if normalized:
    lines += ["| # | project | id | status | detail |", "| --- | --- | --- | --- | --- |"]
    for index, item in enumerate(normalized, 1):
        detail = item.get("error") or item.get("validation_status") or ""
        if not detail and item.get("status") == "build_failed":
            detail = item.get("builder_stderr") or ""
        if not detail:
            detail = item.get("judge_stderr") or ""
        lines.append(
            f"| {index} | {cell(item.get('project'))} | {cell(item.get('id'))} | "
            f"{cell(item.get('status'))} | {cell(str(detail)[:160])} |"
        )
else:
    lines.append("No candidates.")
lines.append("")
Path(out_md).write_text("\n".join(lines), encoding="utf-8")
PY
}

if [ "$SELECTED" -eq 0 ]; then
    write_summary "-" "" "false" "" "no_findings" || die "无法写入 summary"
    log "no findings matched severity=$SEVERITY; batch not run"
    exit 0
fi

if [ -n "${REDTEAM_BATCH_PY:-}" ]; then
    [ -f "$REDTEAM_BATCH_PY" ] || die "REDTEAM_BATCH_PY 不存在: $REDTEAM_BATCH_PY" 4
    BATCH_CMD=("$PYTHON" "$REDTEAM_BATCH_PY")
elif [ -n "${REDTEAM_BATCH_CMD:-}" ]; then
    read -r -a BATCH_CMD <<< "$REDTEAM_BATCH_CMD"
    [ "${#BATCH_CMD[@]}" -gt 0 ] || die "REDTEAM_BATCH_CMD 为空" 4
else
    BATCH_PY="$ROOT/scripts/redteam/batch.py"
    [ -f "$BATCH_PY" ] || die "缺少 batch.py: $BATCH_PY" 4
    BATCH_CMD=("$PYTHON" "$BATCH_PY")
fi

if [[ "$JUDGE_CLAUDE" == */* ]]; then
    [ -x "$JUDGE_CLAUDE" ] || die "独立审核命令行工具不可执行: $JUDGE_CLAUDE" 4
else
    command -v "$JUDGE_CLAUDE" >/dev/null 2>&1 || die "缺少独立审核命令行工具: $JUDGE_CLAUDE" 4
fi

BATCH_OUT="$OUTPUT/batch"
mkdir -p "$BATCH_OUT" || die "无法创建 batch 输出目录: $BATCH_OUT"

log "selected=$SELECTED running batch -> $BATCH_OUT"
"${BATCH_CMD[@]}" \
    --report "$AUDIT_REPORT" \
    --candidates "$CANDIDATES" \
    --out-dir "$BATCH_OUT" \
    --model "$MODEL" \
    --base-url "$BASE_URL" \
    --api-key "$API_KEY" \
    --build-timeout "$BUILD_TIMEOUT" \
    --agent-timeout "$AGENT_TIMEOUT" \
    --judge-timeout "$JUDGE_TIMEOUT" \
    --judge-claude "$JUDGE_CLAUDE" \
    --judge-claude-model "$JUDGE_CLAUDE_MODEL"
BATCH_RC=$?

if [ "$BATCH_RC" -eq 127 ]; then
    die "batch 命令不存在" 4
fi
if [ ! -f "$BATCH_OUT/summary.json" ]; then
    write_summary "-" "$BATCH_RC" "false" "" "batch_failed" || true
    die "batch 未写出 summary.json (returncode=$BATCH_RC)" 3
fi
if [ "$BATCH_RC" -ne 0 ]; then
    write_summary "$BATCH_OUT/summary.json" "$BATCH_RC" "false" "" "batch_failed" || true
    die "batch 执行失败 (returncode=$BATCH_RC)" 3
fi

BUILD_ATTEMPTED=false
BUILD_RC=""
BUILD_STATE_PY="${REDTEAM_BUILD_STATE_PY:-$ROOT/scripts/workflow/build_state.py}"
if [ -f "$BUILD_STATE_PY" ]; then
    BUILD_ATTEMPTED=true
    if "$PYTHON" "$BUILD_STATE_PY" >"$OUTPUT/build-state.log" 2>&1; then
        BUILD_RC=0
    else
        BUILD_RC=$?
        log "build_state 失败 (returncode=$BUILD_RC)，已记录并继续"
    fi
fi

write_summary "$BATCH_OUT/summary.json" "$BATCH_RC" "$BUILD_ATTEMPTED" "$BUILD_RC" "completed" \
    || die "无法写入 summary"

log "completed -> $OUTPUT/summary.json"
exit 0
