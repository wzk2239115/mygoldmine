#!/usr/bin/env bash
# Phase 4: invoke the real verify-agent for selected findings.
#
# For every selected finding this wrapper:
#   1. materializes the finding under <output>/inputs/<id>/finding.json
#   2. runs `claude --agent verify-agent ...` from the repo root
#   3. lets the deterministic runner scripts/verify/run_verify.sh execute the
#      agent-written harness in an isolated container (--network none)
#   4. records honest verdicts, including blocked/inconclusive failures.
#
# It never falls back to auto_verify.sh and never synthesizes `confirmed`.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

log() { printf '[phase4] %s\n' "$*" >&2; }
die() { printf '[phase4] ERROR: %s\n' "$*" >&2; exit "${2:-3}"; }

usage() {
    cat <<'EOF'
用法:
  bash scripts/verify/phase4_verify_agent.sh \
    --project NAME --run-dir DIR --image IMAGE --source DIR [选项]

必填:
  --project NAME       项目名
  --run-dir DIR        批量审计产物目录（需含 audit-report.json）
  --image IMAGE        环境镜像
  --source DIR         原始源码目录（只读挂载）

选项:
  --max N              最多选择多少条（默认 10）
  --severity LIST      逗号分隔的严重度（默认 critical,high）
  --finding-id ID      只处理指定候选问题编号（自动流转用）
  --occurrence-id ID   写入候选问题和报告的单次观测身份字段
  --semantic-id ID     写入候选问题和报告的同源聚合身份字段
  --run-id ID          覆盖写入报告的 run_id（默认取产物目录名）
  --timeout SEC        每条候选问题的验证脚本超时（默认 300 秒）
  --agent-timeout SEC  验证智能体超时（默认 900 秒）
  --claude-bin PATH    Claude Code 命令行工具（默认 claude）
  --model MODEL        验证智能体使用的模型
  --output DIR         输出目录（默认 <产物目录>/verify/agent-<UTC 时间>）
  -h, --help           显示帮助

环境变量:
  VERIFY_RUNNER        覆盖确定性 runner 路径（测试用）

退出码:
  0  完成（即使有条目为 blocked/inconclusive）
  3  参数/输入/配置错误
  4  claude CLI 不可用
EOF
}

PROJECT=""
RUN_DIR=""
IMAGE=""
SOURCE=""
MAX=10
SEVERITY="critical,high"
VERIFY_TIMEOUT=300
AGENT_TIMEOUT=900
CLAUDE_BIN="${CLAUDE_BIN:-claude}"
MODEL="${MODEL:-}"
OUTPUT=""
FINDING_ID_FILTER=""
OCCURRENCE_ID=""
SEMANTIC_ID=""
RUN_ID_OVERRIDE=""
VERIFY_RUNNER="${VERIFY_RUNNER:-$REPO_ROOT/scripts/verify/run_verify.sh}"

while [ "$#" -gt 0 ]; do
    case "$1" in
        --project) [ "$#" -ge 2 ] || die "--project 需要参数"; PROJECT="$2"; shift ;;
        --run-dir) [ "$#" -ge 2 ] || die "--run-dir 需要参数"; RUN_DIR="$2"; shift ;;
        --image) [ "$#" -ge 2 ] || die "--image 需要参数"; IMAGE="$2"; shift ;;
        --source) [ "$#" -ge 2 ] || die "--source 需要参数"; SOURCE="$2"; shift ;;
        --max) [ "$#" -ge 2 ] || die "--max 需要参数"; MAX="$2"; shift ;;
        --severity) [ "$#" -ge 2 ] || die "--severity 需要参数"; SEVERITY="$2"; shift ;;
        --finding-id) [ "$#" -ge 2 ] || die "--finding-id 需要参数"; FINDING_ID_FILTER="$2"; shift ;;
        --occurrence-id) [ "$#" -ge 2 ] || die "--occurrence-id 需要参数"; OCCURRENCE_ID="$2"; shift ;;
        --semantic-id) [ "$#" -ge 2 ] || die "--semantic-id 需要参数"; SEMANTIC_ID="$2"; shift ;;
        --run-id) [ "$#" -ge 2 ] || die "--run-id 需要参数"; RUN_ID_OVERRIDE="$2"; shift ;;
        --timeout) [ "$#" -ge 2 ] || die "--timeout 需要参数"; VERIFY_TIMEOUT="$2"; shift ;;
        --agent-timeout) [ "$#" -ge 2 ] || die "--agent-timeout 需要参数"; AGENT_TIMEOUT="$2"; shift ;;
        --claude-bin) [ "$#" -ge 2 ] || die "--claude-bin 需要参数"; CLAUDE_BIN="$2"; shift ;;
        --model) [ "$#" -ge 2 ] || die "--model 需要参数"; MODEL="$2"; shift ;;
        --output) [ "$#" -ge 2 ] || die "--output 需要参数"; OUTPUT="$2"; shift ;;
        -h|--help) usage; exit 0 ;;
        *) usage >&2; die "未知参数: $1" ;;
    esac
    shift
done

[ -n "$PROJECT" ] || die "缺少 --project"
[ -n "$RUN_DIR" ] || die "缺少 --run-dir"
[ -n "$IMAGE" ] || die "缺少 --image"
[ -n "$SOURCE" ] || die "缺少 --source"
[ -n "$SEVERITY" ] || die "--severity 不能为空"
[[ "$MAX" =~ ^[1-9][0-9]*$ ]] || die "--max 必须正整数: $MAX"
[[ "$VERIFY_TIMEOUT" =~ ^[1-9][0-9]*$ ]] || die "--timeout 必须正整数: $VERIFY_TIMEOUT"
[[ "$AGENT_TIMEOUT" =~ ^[1-9][0-9]*$ ]] || die "--agent-timeout 必须正整数: $AGENT_TIMEOUT"

command -v jq >/dev/null 2>&1 || die "缺少 jq"

RUN_DIR="$(realpath -e "$RUN_DIR" 2>/dev/null)" || die "产物目录不存在: $RUN_DIR"
RUN_ID_VALUE="${RUN_ID_OVERRIDE:-$(basename "$RUN_DIR")}"
REPORT="$RUN_DIR/audit-report.json"
[ -s "$REPORT" ] || die "缺少 audit-report.json: $REPORT"
jq -e . "$REPORT" >/dev/null 2>&1 || die "audit-report.json 不是合法 JSON: $REPORT"

SOURCE="$(realpath -e "$SOURCE" 2>/dev/null)" || die "源码目录不存在: $SOURCE"
[ -d "$SOURCE" ] || die "不是源码目录: $SOURCE"

# Check claude before creating any output so a missing tool cannot look like a
# completed (or confirmed) verification pass. There is deliberately no fallback.
if ! command -v "$CLAUDE_BIN" >/dev/null 2>&1; then
    die "Claude 命令行工具不可用: $CLAUDE_BIN（第 4 阶段需要真实验证智能体，不回退到自动预筛）" 4
fi
[ -f "$VERIFY_RUNNER" ] || die "缺少 run_verify 脚本: $VERIFY_RUNNER"

MODEL_RAW="$MODEL"
case "$MODEL" in
    360-proxy/*) MODEL="${MODEL#360-proxy/}" ;;
    opencode/*) MODEL="${MODEL#opencode/}" ;;
esac

if [ -z "$OUTPUT" ]; then
    OUTPUT="$RUN_DIR/verify/agent-$(date -u +%Y%m%dT%H%M%SZ)"
fi
OUTPUT="$(realpath -m "$OUTPUT")"
mkdir -p "$OUTPUT/inputs" "$OUTPUT/logs"

ENV_MANIFEST="$REPO_ROOT/env/$PROJECT/env-manifest.json"
ENV_MANIFEST_EXISTS=0
[ -f "$ENV_MANIFEST" ] && ENV_MANIFEST_EXISTS=1

JQ_SELECT='
def items:
  if (.findings? | type) == "array" and ((.findings | length) > 0) then .findings
  elif (.vulnerabilities? | type) == "array" then .vulnerabilities
  elif (.findings? | type) == "array" then .findings
  else [] end;
($sev | ascii_downcase | split(",") | map(gsub("^\\s+|\\s+$"; ""))) as $sevs
| [ items | to_entries[]
    | .value as $v
    | if ($v | type) != "object" then
        {malformed: true, index: .key, reason: "not-an-object", preview: ($v | tostring | .[0:200])}
      else
        ($v.severity // $v.severity_raw // $v.level // $v.cvss_severity // "unknown") as $s
        | ($s | tostring | ascii_downcase) as $norm
        | if ($sevs | index($norm)) != null then
            {index: .key,
             orig_id: (($v.id // $v.finding_id // $v.title // $v.name // "") | tostring),
             title: (($v.title // $v.name // $v.id // "") | tostring),
             severity: $norm,
             raw: $v}
          else empty
          end
      end
  ] as $rows
| {
    selected: ([$rows[] | select(.malformed != true) | select($finding_id == "" or .orig_id == $finding_id)][0:$max]),
    malformed: [$rows[] | select(.malformed == true)]
  }
'

SELECTION_FILE="$OUTPUT/.selection.json"
jq --arg sev "$SEVERITY" --arg finding_id "$FINDING_ID_FILTER" --argjson max "$MAX" "$JQ_SELECT" "$REPORT" > "$SELECTION_FILE" \
    || die "解析 audit-report.json 失败: $REPORT"

mapfile -t SELECTED < <(jq -c '.selected[]' "$SELECTION_FILE")
MALFORMED_JSON="$(jq -c '.malformed // []' "$SELECTION_FILE")"
SELECTED_COUNT="${#SELECTED[@]}"
rm -f "$SELECTION_FILE"

RECORDS_FILE="$OUTPUT/.findings.ndjson"
: > "$RECORDS_FILE"

find_harness() {
    local sid="$1"
    local hdir="$OUTPUT/$sid/harness"
    local found=""
    [ -d "$hdir" ] || return 1
    found="$(find "$hdir" -type f -perm -u+x 2>/dev/null | sort | head -n 1)"
    if [ -z "$found" ]; then
        found="$(find "$hdir" -type f \( -name '*.sh' -o -name '*.py' \) 2>/dev/null | sort | head -n 1)"
    fi
    if [ -z "$found" ]; then
        found="$(find "$hdir" -type f 2>/dev/null | sort | head -n 1)"
    fi
    [ -n "$found" ] || return 1
    printf '%s\n' "$found"
}

write_synth_report() {
    local sid="$1" verdict="$2" reason="$3" agent_rc="$4" runner_rc_json="$5" status="$6"
    local dir="$OUTPUT/$sid"
    mkdir -p "$dir"
    jq -n \
        --arg schema_version "1" \
        --arg project "$PROJECT" \
        --arg finding_id "$sid" \
        --arg occurrence_id "$OCCURRENCE_ID" \
        --arg semantic_id "$SEMANTIC_ID" \
        --arg run_id "$RUN_ID_VALUE" \
        --arg image "$IMAGE" \
        --arg source "$SOURCE" \
        --arg verdict "$verdict" \
        --arg reason "$reason" \
        --arg status "$status" \
        --arg generated_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
        --argjson agent_return_code "$agent_rc" \
        --argjson runner_return_code "$runner_rc_json" \
        '{
            schema_version: $schema_version,
            project: $project,
            finding_id: $finding_id,
            occurrence_id: (if $occurrence_id == "" then null else $occurrence_id end),
            semantic_id: (if $semantic_id == "" then null else $semantic_id end),
            run_id: (if $run_id == "" then null else $run_id end),
            image: $image,
            source: $source,
            verdict: $verdict,
            reason: $reason,
            evidence: [],
            limitations: ["wrapper synthesized this report because no valid report was produced"],
            synthesized: true,
            status: $status,
            agent_return_code: $agent_return_code,
            runner_return_code: $runner_return_code,
            generated_at: $generated_at
        }' > "$dir/verify-report.json"
    {
        echo "# Verification Report — $sid"
        echo
        echo "- Project: \`$PROJECT\`"
        echo "- Verdict: **$verdict**"
        echo "- Reason: $reason"
        echo "- Status: \`$status\`"
        echo "- Agent return code: $agent_rc"
        echo "- Runner return code: $runner_rc_json"
        echo "- Generated at: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
        echo
        echo "No valid verify-report.json was produced by verify-agent/run_verify."
        echo "This report is synthesized for auditability and does not assert a vulnerability."
    } > "$dir/verify-report.md"
}

enrich_report_identity() {
    local report="$1"
    [ -f "$report" ] && jq -e . "$report" >/dev/null 2>&1 || return 0
    local tmp="$report.identity.$$"
    jq --arg occ "$OCCURRENCE_ID" --arg sem "$SEMANTIC_ID" --arg run "$RUN_ID_VALUE" '
        (if $occ != "" then .occurrence_id = (.occurrence_id // $occ) else . end)
        | (if $sem != "" then .semantic_id = (.semantic_id // $sem) else . end)
        | (if $run != "" then .run_id = (.run_id // $run) else . end)
    ' "$report" > "$tmp" && mv "$tmp" "$report" || rm -f "$tmp"
}

report_valid() {
    local report="$1"
    [ -f "$report" ] && jq -e '.verdict' "$report" >/dev/null 2>&1
}

load_report() {
    local report="$1"
    VERDICT="$(jq -r '.verdict // empty' "$report" 2>/dev/null)"
    REASON="$(jq -r '.reason // empty' "$report" 2>/dev/null)"
    case "$VERDICT" in
        confirmed|rejected|inconclusive|blocked) return 0 ;;
        *) return 1 ;;
    esac
}

# run_verify.sh refuses a non-empty --run-dir. The agent is told to write the
# harness under <output>/<id>/harness, so move the agent artifacts aside before
# invoking the deterministic runner and restore the harness if needed.
invoke_runner() {
    local sid="$1" harness="$2"
    local run_dir="$OUTPUT/$sid"
    local stage_root="$OUTPUT/.runner-stage/$sid"
    local pass_harness="$harness"
    local moved=0
    local rel=""
    local child base

    case "$harness" in
        "$run_dir"/*)
            rel="${harness#"$run_dir"/}"
            rm -rf "$stage_root"
            mkdir -p "$stage_root"
            shopt -s dotglob nullglob
            for child in "$run_dir"/*; do
                base="$(basename "$child")"
                mv "$child" "$stage_root/$base"
            done
            shopt -u dotglob nullglob
            pass_harness="$stage_root/$rel"
            moved=1
            ;;
    esac

    (
        cd "$REPO_ROOT" || exit 3
        bash "$VERIFY_RUNNER" \
            --project "$PROJECT" \
            --image "$IMAGE" \
            --finding "$OUTPUT/inputs/$sid/finding.json" \
            --harness "$pass_harness" \
            --source "$SOURCE" \
            --run-dir "$run_dir" \
            --timeout "$VERIFY_TIMEOUT" \
            --network none
    ) > "$OUTPUT/logs/$sid.runner.log" 2>&1
    local rc=$?

    if [ "$moved" -eq 1 ]; then
        if [ ! -e "$run_dir/$rel" ] && [ -e "$stage_root/$rel" ]; then
            mkdir -p "$(dirname "$run_dir/$rel")"
            cp -a "$stage_root/$rel" "$run_dir/$rel"
        fi
        rm -rf "$stage_root"
    fi
    return "$rc"
}

build_prompt() {
    local sid="$1" finding="$2" run_dir="$3" harness_dir="$4"
    cat <<EOF
You are the Phase 4 verify-agent. Verify exactly one finding on the host and leave
an honest, auditable verdict. Do not scan for new bugs and do not write exploits.

project: $PROJECT
finding: $finding
finding_id: $sid
env_manifest: $ENV_MANIFEST
source: $SOURCE
output_run_dir: $run_dir
harness_dir: $harness_dir
timeout_seconds: $VERIFY_TIMEOUT

Steps:
1. Read the finding JSON, the env manifest if it exists, and only the relevant
   source files. If the environment is blocked, do not force a run.
2. Write a minimal, benign harness under $harness_dir (recommended .sh or .py).
   It must be safe: benign markers only, loopback-only services, no reverse
   shells, no external downloads, no public network targets, no cloud metadata
   access, and no Docker socket mounts.
3. Invoke the real deterministic runner from the repo root:

   bash $VERIFY_RUNNER \\
     --project $PROJECT \\
     --image $IMAGE \\
     --finding $finding \\
     --harness $harness_dir/<your-harness> \\
     --source $SOURCE \\
     --run-dir $run_dir \\
     --timeout $VERIFY_TIMEOUT \\
     --network none

   If the runner rejects the run directory because the harness is already there,
   leave the harness in place; the wrapper will invoke the runner once more.
4. The runner writes $run_dir/verify-report.json and verify-report.md. Never
   hand-write a confirmed verdict without runtime/source-semantic evidence.
   blocked and inconclusive are valid, honest outcomes.
EOF
}

for entry in "${SELECTED[@]}"; do
    source_index="$(jq -r '.index' <<< "$entry")"
    orig_id="$(jq -r '.orig_id // ""' <<< "$entry")"
    title="$(jq -r '.title // ""' <<< "$entry")"
    severity="$(jq -r '.severity // "unknown"' <<< "$entry")"

    base="$(printf '%s' "${orig_id:-finding-$source_index}" | tr -c 'A-Za-z0-9._-' '_' | cut -c1-80)"
    [ -n "$base" ] || base="finding-$source_index"
    sid="$base"
    suffix=2
    while [ -e "$OUTPUT/inputs/$sid" ]; do
        sid="${base}-${suffix}"
        suffix=$((suffix + 1))
    done

    input_dir="$OUTPUT/inputs/$sid"
    run_dir="$OUTPUT/$sid"
    harness_dir="$run_dir/harness"
    finding_file="$input_dir/finding.json"
    report_json="$run_dir/verify-report.json"
    agent_log="$OUTPUT/logs/$sid.agent.log"
    runner_log="$OUTPUT/logs/$sid.runner.log"
    mkdir -p "$input_dir" "$run_dir"

    jq --arg id "$sid" \
       --arg occ "$OCCURRENCE_ID" \
       --arg sem "$SEMANTIC_ID" \
       --arg run "$RUN_ID_VALUE" \
       --argjson idx "$source_index" '
        .raw as $r
        | $r + {
            id: $id,
            original_id: ($r.id // $r.finding_id // $r.title // null),
            selection_index: $idx
          }
        + (if $occ != "" then {occurrence_id: $occ} else {} end)
        + (if $sem != "" then {semantic_id: $sem} else {} end)
        + (if $run != "" then {run_id: $run} else {} end)
    ' <<< "$entry" > "$finding_file" || die "写入候选问题失败: $sid"

    log "选中 $sid (severity=$severity, index=$source_index)"
    PROMPT="$(build_prompt "$sid" "$finding_file" "$run_dir" "$harness_dir")"
    CLAUDE_ARGS=(
        --mcp-config "$(python3 "$REPO_ROOT/scripts/stages/submission.py" config --stage verify --root "$run_dir")"
        --append-system-prompt "$(python3 "$REPO_ROOT/scripts/stages/submission.py" instruction --stage verify --root "$run_dir")"
        --agent verify-agent
        --output-format stream-json
        --verbose
        --permission-mode=bypassPermissions
        --disallowed-tools WebSearch,WebFetch
    )
    [ -n "$MODEL" ] && CLAUDE_ARGS+=(--model "$MODEL")
    CLAUDE_ARGS+=(-p "$PROMPT")

    (
        cd "$REPO_ROOT" || exit 3
        PHASE4_OUTPUT="$OUTPUT" \
        PHASE4_RUN_DIR="$run_dir" \
        PHASE4_SAFE_ID="$sid" \
        PHASE4_FINDING="$finding_file" \
        PHASE4_HARNESS_DIR="$harness_dir" \
        PHASE4_ENV_MANIFEST="$ENV_MANIFEST" \
        PHASE4_RUNNER="$VERIFY_RUNNER" \
        PHASE4_PROJECT="$PROJECT" \
        PHASE4_IMAGE="$IMAGE" \
        PHASE4_SOURCE="$SOURCE" \
        PHASE4_TIMEOUT="$VERIFY_TIMEOUT" \
        VERIFY_OUTPUT="$OUTPUT" \
        VERIFY_RUN_DIR="$run_dir" \
        VERIFY_FINDING_FILE="$finding_file" \
        VERIFY_HARNESS_DIR="$harness_dir" \
        VERIFY_RUNNER="$VERIFY_RUNNER" \
        PROJECT="$PROJECT" \
        timeout --signal=TERM --kill-after=30 "$AGENT_TIMEOUT" \
            python3 "$REPO_ROOT/scripts/stages/claude_connection.py" "$MODEL_RAW" "$CLAUDE_BIN" "${CLAUDE_ARGS[@]}"
    ) > "$agent_log" 2>&1
    agent_rc=$?

    VERDICT=""
    REASON=""
    status=""
    runner_rc_json="null"
    harness_path="$(find_harness "$sid" || true)"

    if report_valid "$report_json" && load_report "$report_json"; then
        enrich_report_identity "$report_json"
        status="reported"
    else
        if [ -n "$harness_path" ]; then
            log "验证智能体未产出有效报告，包装脚本调用 run_verify: $sid"
            invoke_runner "$sid" "$harness_path"
            runner_rc=$?
            runner_rc_json="$runner_rc"
            harness_path="$(find_harness "$sid" || true)"
            if report_valid "$report_json" && load_report "$report_json"; then
                enrich_report_identity "$report_json"
                status="runner_reported"
            else
                reason="验证脚本未产出有效 verify-report.json（rc=$runner_rc）；不确认漏洞"
                write_synth_report "$sid" "inconclusive" "$reason" "$agent_rc" "$runner_rc_json" "runner_no_report"
                status="runner_no_report"
                VERDICT="inconclusive"
                REASON="$reason"
            fi
        else
            if [ "$agent_rc" -eq 124 ] || [ "$agent_rc" -eq 137 ]; then
                reason="验证智能体超时且未产出验证脚本或报告（rc=$agent_rc）"
            elif [ "$agent_rc" -ne 0 ]; then
                reason="验证智能体退出 ${agent_rc} 且未产出验证脚本或报告"
            else
                reason="验证智能体未产出验证脚本或报告"
            fi
            write_synth_report "$sid" "blocked" "$reason" "$agent_rc" "null" "agent_no_harness"
            status="agent_no_harness"
            VERDICT="blocked"
            REASON="$reason"
        fi
    fi

    [ -f "$report_json" ] || report_json=""
    jq -n \
        --arg finding_id "$sid" \
        --arg original_id "$orig_id" \
        --arg title "$title" \
        --arg severity "$severity" \
        --arg status "$status" \
        --arg verdict "${VERDICT:-unknown}" \
        --arg reason "${REASON:-}" \
        --argjson source_index "$source_index" \
        --argjson agent_return_code "$agent_rc" \
        --argjson runner_return_code "$runner_rc_json" \
        --arg finding_path "$finding_file" \
        --arg occurrence_id "$OCCURRENCE_ID" \
        --arg semantic_id "$SEMANTIC_ID" \
        --arg run_id "$RUN_ID_VALUE" \
        --arg run_dir "$run_dir" \
        --arg report_path "$report_json" \
        --arg harness_path "${harness_path:-}" \
        --arg agent_log "$agent_log" \
        --arg runner_log "$runner_log" \
        '{
            finding_id: $finding_id,
            original_id: (if $original_id == "" then null else $original_id end),
            occurrence_id: (if $occurrence_id == "" then null else $occurrence_id end),
            semantic_id: (if $semantic_id == "" then null else $semantic_id end),
            run_id: (if $run_id == "" then null else $run_id end),
            title: $title,
            severity: $severity,
            status: $status,
            verdict: $verdict,
            reason: $reason,
            source_index: $source_index,
            agent_return_code: $agent_return_code,
            runner_return_code: $runner_return_code,
            finding_path: $finding_path,
            run_dir: $run_dir,
            report_path: (if $report_path == "" then null else $report_path end),
            harness_path: (if $harness_path == "" then null else $harness_path end),
            agent_log: $agent_log,
            runner_log: $runner_log
        }' >> "$RECORDS_FILE"
done

FINDINGS_JSON="$(jq -s '.' "$RECORDS_FILE" 2>/dev/null)" || FINDINGS_JSON="[]"
[ -n "$FINDINGS_JSON" ] || FINDINGS_JSON="[]"
PROCESSED_COUNT="$(jq 'length' <<< "$FINDINGS_JSON")"

jq -n \
    --arg schema_version "1" \
    --arg project "$PROJECT" \
    --arg run_dir "$RUN_DIR" \
    --arg report "$REPORT" \
    --arg image "$IMAGE" \
    --arg source "$SOURCE" \
    --arg model "$MODEL" \
    --arg model_raw "$MODEL_RAW" \
    --arg claude_bin "$CLAUDE_BIN" \
    --arg verify_runner "$VERIFY_RUNNER" \
    --arg env_manifest "$ENV_MANIFEST" \
    --argjson env_manifest_exists "$ENV_MANIFEST_EXISTS" \
    --arg generated_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --arg output "$OUTPUT" \
    --argjson selected "$SELECTED_COUNT" \
    --argjson processed "$PROCESSED_COUNT" \
    --argjson malformed "$MALFORMED_JSON" \
    --argjson findings "$FINDINGS_JSON" \
    --argjson verify_timeout "$VERIFY_TIMEOUT" \
    --argjson agent_timeout "$AGENT_TIMEOUT" \
    '{
        schema_version: $schema_version,
        project: $project,
        run_dir: $run_dir,
        report: $report,
        image: $image,
        source: $source,
        model: $model,
        model_raw: $model_raw,
        claude_bin: $claude_bin,
        verify_runner: $verify_runner,
        env_manifest: $env_manifest,
        env_manifest_exists: ($env_manifest_exists == 1),
        generated_at: $generated_at,
        output: $output,
        selected: $selected,
        processed: $processed,
        malformed_count: ($malformed | length),
        malformed: $malformed,
        status: (if ($findings|length)==0 then "no_findings" elif all($findings[]; .verdict=="blocked") then "blocked" elif any($findings[]; .verdict=="blocked") then "partial" else "completed" end),
        counts: ($findings | group_by(.verdict) | map({key: (.[0].verdict // "unknown"), value: length}) | from_entries),
        status_counts: ($findings | group_by(.status) | map({key: (.[0].status // "unknown"), value: length}) | from_entries),
        findings: $findings,
        timeouts: {verify: $verify_timeout, agent: $agent_timeout}
    }' > "$OUTPUT/summary.json"

{
    echo "# Phase 4 Verify Agent Summary — $PROJECT"
    echo
    echo "- Report: \`$REPORT\`"
    echo "- Image: \`$IMAGE\`"
    echo "- Source: \`$SOURCE\`"
    echo "- Model: \`${MODEL:-default}\`"
    echo "- Selected: $SELECTED_COUNT (severity=$SEVERITY, max=$MAX)"
    echo "- Processed: $PROCESSED_COUNT"
    echo "- Malformed skipped: $(jq '.malformed_count' "$OUTPUT/summary.json")"
    echo "- Output: \`$OUTPUT\`"
    echo
    echo "## Counts"
    jq -r '.counts | to_entries[] | "- \(.key): \(.value)"' "$OUTPUT/summary.json" 2>/dev/null || echo "- 无"
    echo
    echo "## Findings"
    echo "| ID | Severity | Status | Verdict | Agent rc | Runner rc | Reason |"
    echo "|---|---|---|---|---|---|---|"
    jq -r '.findings[] | "| \(.finding_id) | \(.severity) | \(.status) | \(.verdict) | \(.agent_return_code) | \(if .runner_return_code == null then "-" else .runner_return_code end) | \((.reason // "") | gsub("\\|"; "/") | gsub("\n"; " ")) |"' "$OUTPUT/summary.json" 2>/dev/null || true
} > "$OUTPUT/summary.md"

rm -f "$RECORDS_FILE"
rm -rf "$OUTPUT/.runner-stage"

log "完成: $OUTPUT/summary.md"
jq -r '.counts | to_entries[] | "  \(.key)=\(.value)"' "$OUTPUT/summary.json" 2>/dev/null >&2 || true
exit 0