#!/usr/bin/env bash
# 对一份 audit-report.json 做“简单自动验证”：
#   1. 归一化不同报告 schema 的 findings
#   2. 按 severity 选 Top-N
#   3. 为每条生成源码级 harness（引用文件 + sink 模式）
#   4. 并行调用 run_verify.sh，只输出静态线索（不作为 confirmed）
#
# 这是启发式预筛，不替代 verify-agent 的专用 harness。
# 关键词命中不是漏洞证明；本脚本不再输出 confirmed/rejected 结论。
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

log() { printf '[auto_verify] %s\n' "$*" >&2; }
die() { printf '[auto_verify] ERROR: %s\n' "$*" >&2; exit "${2:-3}"; }

usage() {
    cat <<'EOF'
用法: auto_verify.sh --project NAME --run-dir DIR [选项]

必填:
  --project NAME       项目名
  --run-dir DIR        挖掘产物目录（需含 audit-report.json）

选项:
  --image IMAGE        环境镜像（默认读 env/<project>/env-manifest.json 的 image）
  --source DIR         源码目录（默认读 env-manifest.json 的 source）
  --max N              最多验证多少条（默认 10）
  --severity LIST      逗号分隔，默认 critical,high
  --parallel N         并行验证数（默认 2）
  --output DIR         输出目录（默认 runs/<project>/verify/auto-<ts>）
  -h, --help           显示帮助

产物:
  <output>/<finding-id>/verify-report.md|json
  <output>/summary.md / summary.json

退出码: 0 全部跑完（无论 verdict）；3 参数/报告错误
EOF
}

PROJECT=""
RUN_DIR=""
IMAGE=""
SOURCE=""
MAX=10
SEVERITY="critical,high"
PARALLEL=2
OUTPUT=""

while [ "$#" -gt 0 ]; do
    case "$1" in
        --project) [ "$#" -ge 2 ] || die "--project 需要参数"; PROJECT="$2"; shift ;;
        --run-dir) [ "$#" -ge 2 ] || die "--run-dir 需要参数"; RUN_DIR="$2"; shift ;;
        --image) [ "$#" -ge 2 ] || die "--image 需要参数"; IMAGE="$2"; shift ;;
        --source) [ "$#" -ge 2 ] || die "--source 需要参数"; SOURCE="$2"; shift ;;
        --max) [ "$#" -ge 2 ] || die "--max 需要参数"; MAX="$2"; shift ;;
        --severity) [ "$#" -ge 2 ] || die "--severity 需要参数"; SEVERITY="$2"; shift ;;
        --parallel) [ "$#" -ge 2 ] || die "--parallel 需要参数"; PARALLEL="$2"; shift ;;
        --output) [ "$#" -ge 2 ] || die "--output 需要参数"; OUTPUT="$2"; shift ;;
        -h|--help) usage; exit 0 ;;
        *) usage >&2; die "未知参数: $1" ;;
    esac
    shift
done

[ -n "$PROJECT" ] || die "缺少 --project"
[ -n "$RUN_DIR" ] || die "缺少 --run-dir"
RUN_DIR="$(realpath -e "$RUN_DIR" 2>/dev/null)" || die "run-dir 不存在: $RUN_DIR"
REPORT="$RUN_DIR/audit-report.json"
[ -s "$REPORT" ] || die "缺少 audit-report.json: $REPORT"
[[ "$MAX" =~ ^[1-9][0-9]*$ ]] || die "--max 必须正整数"
[[ "$PARALLEL" =~ ^[1-9][0-9]*$ ]] || die "--parallel 必须正整数"

MANIFEST="$REPO_ROOT/env/$PROJECT/env-manifest.json"
if [ -z "$IMAGE" ] && [ -f "$MANIFEST" ]; then
    IMAGE="$(jq -r '.image // empty' "$MANIFEST")"
fi
if [ -z "$SOURCE" ] && [ -f "$MANIFEST" ]; then
    SOURCE="$(jq -r '.source // empty' "$MANIFEST")"
fi
[ -n "$IMAGE" ] || die "缺少 --image，且 manifest 中没有 image"
[ -n "$SOURCE" ] && [ -d "$SOURCE" ] || die "源码目录无效: ${SOURCE:-<empty>}"

if [ -z "$OUTPUT" ]; then
    OUTPUT="$REPO_ROOT/runs/$PROJECT/verify/auto-$(date -u +%Y%m%dT%H%M%SZ)"
fi
OUTPUT="$(realpath -m "$OUTPUT")"
mkdir -p "$OUTPUT/inputs" "$OUTPUT/logs"

JQ_NORM='
def norm_one:
  if type=="object" then
    ((.file // .path // "") +
     (if (.lines // .line) != null then ":" + ((.lines // .line)|tostring) else "" end))
  elif type=="string" then .
  else "" end;
def norm_files:
  if type=="array" then map(norm_one)
  elif type=="object" then [norm_one]
  elif type=="string" then [.]
  else [] end;
def files_of:
  if .files != null then (.files|norm_files)
  elif .location != null then (.location|norm_files)
  elif .verification != null then (.verification|norm_files)
  elif (.evidence != null and (.evidence|type)=="array") then (.evidence|norm_files)
  else [] end;
def text_of:
  ([.title, .root_cause, .impact, .description, .evidence, .reproduction_idea]
   | map(select(type=="string")) | join(" "));
def rank:
  if .=="critical" then 0 elif .=="high" then 1 elif .=="medium" then 2
  elif .=="low" then 3 else 4 end;
[.findings[]?
 | {
     id: (.id // .finding_id // .title // "finding"),
     title: (.title // .name // .id // "finding"),
     severity: ((.severity // .severity_raw // .level // "unknown")|ascii_downcase),
     files: (files_of | map(select(type=="string" and test("/")))),
     text: text_of
   }]
| map(.severity = (.severity|ascii_downcase))
| map(select(.severity as $s | ($sev|split(",")|map(ascii_downcase)|index($s)) != null))
| sort_by([(.severity|rank), .id])
| .[:$max]
| .[]
'

mapfile -t FINDINGS < <(jq -c --arg sev "$SEVERITY" --argjson max "$MAX" "$JQ_NORM" "$REPORT" 2>/dev/null)
N=${#FINDINGS[@]}
[ "$N" -gt 0 ] || die "没有匹配 severity=$SEVERITY 的 finding"

PATTERNS=(
    'exec(' 'eval(' 'compile(' 'pickle.load' 'pickle.loads' 'torch.load'
    'shell=True' 'os.system' 'subprocess' 'exec_module' 'load_module'
    'yaml.load' 'api_key' 'admin_api_key' 'allow_origins' 'cors'
    'verify=False' 'urlopen' 'requests.get' 'send_file' 'render_template'
    'mount(' 'innerHTML' 'dangerouslySetInnerHTML' 'readFile' 'readFileSync'
    'filePath' 'model_path' 'load_format' 'trust_remote_code'
)

HARNESS="$OUTPUT/harness-template.py"
cat > "$HARNESS" <<'PY'
#!/usr/bin/env python3
import json, os, sys
from pathlib import Path

vdir = Path(os.environ.get("VERIFY_DIR", "/verify"))
edir = Path(os.environ.get("EVIDENCE_DIR", str(vdir / "evidence")))
target = Path(os.environ.get("TARGET_DIR", "/opt/target"))
source = Path(os.environ.get("SOURCE_DIR", "/source-ro"))
edir.mkdir(parents=True, exist_ok=True)

with open(os.environ["FINDING_FILE"], encoding="utf-8") as fh:
    finding = json.load(fh)

def finish(verdict, reason, ev=None, lim=None):
    payload = {"verdict": verdict, "reason": reason,
               "evidence": ev or [], "limitations": lim or [],
               "evidence_class": "static-pattern"}
    (vdir / "verdict.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print(f"{verdict}: {reason}")
    sys.exit({"confirmed": 0, "rejected": 10, "inconclusive": 20, "blocked": 30}[verdict])

files = finding.get("files") or []
pattern = (finding.get("pattern") or "").strip()
if not files:
    finish("inconclusive", "finding 未提供可定位文件，无法自动验证",
           lim=["需要 verify-agent 生成专用 harness"])

checked, missing = [], []
for item in files:
    raw = str(item).split(":", 1)[0].strip()
    if not raw:
        continue
    p = target / raw
    if not p.exists():
        p = source / raw
    if p.exists():
        checked.append(p)
    else:
        missing.append(raw)

(edir / "files.txt").write_text(
    "checked:\n" + "\n".join(str(p) for p in checked) +
    "\nmissing:\n" + "\n".join(missing) + "\n", encoding="utf-8")

if not checked:
    finish("blocked", "引用的文件在环境镜像/源码中不存在: " + ", ".join(missing[:8]),
           ev=["files.txt"])
if not pattern:
    finish("inconclusive", "引用文件存在，但未提取到可自动检查的 sink 模式",
           ev=["files.txt"], lim=["需要 verify-agent 生成专用 harness"])

hits = []
needle = pattern.lower()
for p in checked:
    try:
        for lineno, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if needle in line.lower():
                hits.append(f"{p}:{lineno}:{line.strip()}")
    except OSError:
        pass
(edir / "grep.txt").write_text("\n".join(hits) + "\n", encoding="utf-8")

if hits:
    finish("inconclusive", f"静态模式命中 `{pattern}`，但未证明可达/可触发；不是运行时确认",
           ev=["files.txt", "grep.txt"],
           lim=["仅关键词/源码模式命中", "未启动目标程序", "需要 verify-agent 生成可达性 harness"])
finish("inconclusive", f"引用文件存在但未命中模式 `{pattern}`；关键词缺失不等于漏洞不存在",
       ev=["files.txt", "grep.txt"],
       lim=["仅关键词/源码模式检查", "未启动目标程序", "需要 verify-agent 生成可达性 harness"])
PY
chmod +x "$HARNESS"

verify_one() {
    local f="$1"
    local id sev text pattern input base
    id="$(jq -r '.id' <<< "$f" | tr -c 'A-Za-z0-9._-' '_' | cut -c1-80)"
    sev="$(jq -r '.severity' <<< "$f")"
    text="$(jq -r '.text' <<< "$f")"
    pattern=""
    for pat in "${PATTERNS[@]}"; do
        if printf '%s' "$text" | grep -Fqi -- "$pat"; then pattern="$pat"; break; fi
    done
    input="$OUTPUT/inputs/$id"
    mkdir -p "$input"
    jq --arg pattern "$pattern" '. + {pattern:$pattern}' <<< "$f" > "$input/finding.json"
    "$SCRIPT_DIR/run_verify.sh" \
        --project "$PROJECT" \
        --image "$IMAGE" \
        --finding "$input/finding.json" \
        --harness "$HARNESS" \
        --source "$SOURCE" \
        --run-dir "$OUTPUT/$id" \
        --timeout 180 --network none \
        > "$OUTPUT/logs/$id.log" 2>&1
    local rc=$?
    echo "$rc" > "$OUTPUT/$id.exit_code"
}

log "项目=$PROJECT report=$REPORT image=$IMAGE source=$SOURCE"
log "选中 $N 条（severity=$SEVERITY, max=$MAX），并行=$PARALLEL"
log "输出: $OUTPUT"

pids=()
for f in "${FINDINGS[@]}"; do
    ( verify_one "$f" ) &
    pids+=($!)
    if [ "${#pids[@]}" -ge "$PARALLEL" ]; then
        wait -n 2>/dev/null || true
        # 清理已退出 PID（简单轮询）
        alive=()
        for pid in "${pids[@]}"; do kill -0 "$pid" 2>/dev/null && alive+=("$pid"); done
        pids=("${alive[@]}")
    fi
done
wait 2>/dev/null || true

findings_json="$(for d in "$OUTPUT"/*/; do
    [ -f "$d/verify-report.json" ] || continue
    id="$(basename "$d")"
    sev="$(jq -r '.severity // "unknown"' "$OUTPUT/inputs/$id/finding.json" 2>/dev/null || echo unknown)"
    jq -c --arg sev "$sev" '{finding_id:.finding_id, severity:$sev, verdict:.verdict, reason:.reason, env_status:.env_status, image_id:.image_id}' "$d/verify-report.json"
done | jq -s 'sort_by(.finding_id)')"
[ -n "$findings_json" ] || findings_json="[]"

jq -n \
    --arg schema_version "1" \
    --arg project "$PROJECT" \
    --arg report "$REPORT" \
    --arg image "$IMAGE" \
    --arg source "$SOURCE" \
    --arg generated_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --arg output "$OUTPUT" \
    --argjson selected "$N" \
    --argjson findings "$findings_json" \
    '{
        schema_version: $schema_version,
        project: $project,
        report: $report,
        image: $image,
        source: $source,
        generated_at: $generated_at,
        output: $output,
        selected: $selected,
        counts: ($findings | group_by(.verdict) | map({key: .[0].verdict, value: length}) | from_entries),
        findings: $findings
    }' > "$OUTPUT/summary.json"

{
    echo "# Auto Verify Summary — $PROJECT"
    echo
    echo "- Report: \`$REPORT\`"
    echo "- Image: \`$IMAGE\`"
    echo "- Selected: $N (severity=$SEVERITY, max=$MAX)"
    echo "- Output: \`$OUTPUT\`"
    echo
    echo "## Counts"
    jq -r '.counts | to_entries[] | "- \(.key): \(.value)"' "$OUTPUT/summary.json" 2>/dev/null || echo "- 无"
    echo
    echo "## Findings"
    echo "| ID | Severity | Verdict | Reason |"
    echo "|---|---|---|---|"
    jq -r '.findings[] | "| \(.finding_id) | \(.severity // "-") | \(.verdict) | \(.reason | gsub("\\|"; "/")) |"' "$OUTPUT/summary.json" 2>/dev/null || true
} > "$OUTPUT/summary.md"

log "完成: $OUTPUT/summary.md"
jq -r '.counts | to_entries[] | "  \(.key)=\(.value)"' "$OUTPUT/summary.json" 2>/dev/null >&2 || true
if [ -f "$REPO_ROOT/scripts/workflow/build_state.py" ]; then
    python3 "$REPO_ROOT/scripts/workflow/build_state.py" >&2 || true
fi
exit 0
