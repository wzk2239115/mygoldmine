#!/usr/bin/env bash
# 在宿主侧生成图文报告与攻击场景图。
#
# 只要产物目录中存在合法的 audit-report.json，本脚本就会：
#   1. 生成 visual-model.json
#   2. 优先由智能体生成场景（claude 可用时），失败后改用 image2 直接生成
#   3. 重新渲染 report-illustrated.md
#   4. 写出 visual-summary.json / visual-summary.md
#
# 不伪造图片。图片服务不可用时记录 blocked 状态，但仍保留已生成的报告。
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SKILL_DIR="$REPO_ROOT/.claude/skills/project-cartographer/scripts"

log() { printf '[visual_report] %s\n' "$*" >&2; }
die() { printf '[visual_report] ERROR: %s\n' "$*" >&2; exit "${2:-3}"; }

usage() {
    cat <<'EOF'
用法: visual_report.sh --project NAME --run-dir DIR [选项]

选项:
  --project NAME         项目名（必填）
  --run-dir DIR          审计产物目录，必须包含 audit-report.json（必填）
  --max N                最多为多少条严重或高危候选问题生成场景图（默认 5）
  --finding-id ID        只生成指定候选问题的场景图（自动流转用）
  --timeout SEC          单张图片生成超时（默认 300 秒）
  --agent-timeout SEC    智能体辅助场景生成超时（默认 900 秒）
  --claude-bin PATH      Claude Code 命令行工具（默认 claude）
  --model MODEL          智能体辅助场景生成使用的模型（可选）
  --output DIR           输出版本目录（默认 <产物目录>/visual-rendered）
  -h, --help             显示帮助

环境变量覆盖（测试用）:
  VISUAL_BUILD_MODEL_BIN   build_visual_model.py
  VISUAL_RENDER_BIN        render_diagrams.py
  VISUAL_IMAGES_BIN        render_attack_images.py
  VISUAL_AGENTIC_BIN       render_attack_scenes_agentic.py
  VISUAL_CLAUDE            claude 可执行文件

退出码: 0 图文报告已生成（允许场景缺失）；1 构建/渲染失败；3 输入非法
EOF
}

PROJECT=""
RUN_DIR=""
MAX=5
FOCUS_FINDING=""
TIMEOUT=300
AGENT_TIMEOUT=900
CLAUDE_BIN="${VISUAL_CLAUDE:-claude}"
MODEL=""
OUTPUT=""

while [ "$#" -gt 0 ]; do
    case "$1" in
        --project) [ "$#" -ge 2 ] || die "--project 需要参数"; PROJECT="$2"; shift ;;
        --run-dir) [ "$#" -ge 2 ] || die "--run-dir 需要参数"; RUN_DIR="$2"; shift ;;
        --max) [ "$#" -ge 2 ] || die "--max 需要参数"; MAX="$2"; shift ;;
        --finding-id) [ "$#" -ge 2 ] || die "--finding-id 需要参数"; FOCUS_FINDING="$2"; shift ;;
        --timeout) [ "$#" -ge 2 ] || die "--timeout 需要参数"; TIMEOUT="$2"; shift ;;
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
[[ "$MAX" =~ ^[1-9][0-9]*$ ]] || die "--max 必须是正整数"
[[ "$TIMEOUT" =~ ^[1-9][0-9]*$ ]] || die "--timeout 必须是正整数"
[[ "$AGENT_TIMEOUT" =~ ^[1-9][0-9]*$ ]] || die "--agent-timeout 必须是正整数"

RUN_DIR="$(realpath -m "$RUN_DIR")"
AUDIT_REPORT="$RUN_DIR/audit-report.json"
[ -f "$AUDIT_REPORT" ] || die "缺少 audit-report.json: $AUDIT_REPORT" 3
python3 - "$AUDIT_REPORT" <<'PY' || die "audit-report.json 不是合法 JSON 对象" 3
import json
import sys

try:
    data = json.load(open(sys.argv[1], encoding="utf-8"))
except Exception:
    raise SystemExit(1)
raise SystemExit(0 if isinstance(data, dict) else 1)
PY

OUTPUT="${OUTPUT:-$RUN_DIR/visual-rendered}"
OUTPUT="$(realpath -m "$OUTPUT")"
mkdir -p "$OUTPUT" || die "无法创建输出目录: $OUTPUT" 1

BUILD_BIN="${VISUAL_BUILD_MODEL_BIN:-$SKILL_DIR/build_visual_model.py}"
RENDER_BIN="${VISUAL_RENDER_BIN:-$SKILL_DIR/render_diagrams.py}"
IMAGES_BIN="${VISUAL_IMAGES_BIN:-$SKILL_DIR/render_attack_images.py}"
AGENTIC_BIN="${VISUAL_AGENTIC_BIN:-$SKILL_DIR/render_attack_scenes_agentic.py}"

BUILD_LOG="$OUTPUT/visual-build.log"
AGENTIC_LOG="$OUTPUT/visual-agentic.log"
IMAGES_LOG="$OUTPUT/visual-images.log"
RENDER_LOG="$OUTPUT/visual-diagrams.log"

run_script() {
    local script="$1"
    shift
    if [[ "$script" == *.py ]]; then
        python3 "$script" "$@"
    elif [ -x "$script" ]; then
        "$script" "$@"
    else
        bash "$script" "$@"
    fi
}

tail_log() {
    local file="$1"
    [ -s "$file" ] || return 0
    tail -c 1200 "$file" | tr '\n' ' ' | tr -s ' ' | cut -c1-700
}

CLAUDE_AVAILABLE=0
if command -v "$CLAUDE_BIN" >/dev/null 2>&1; then
    CLAUDE_AVAILABLE=1
fi

log "project=$PROJECT run_dir=$RUN_DIR output=$OUTPUT max=$MAX"

BUILD_RC="skipped"
if [ -f "$BUILD_BIN" ]; then
    log "build visual model"
    run_script "$BUILD_BIN" --project "$PROJECT" --run-dir "$RUN_DIR" > "$BUILD_LOG" 2>&1
    BUILD_RC=$?
else
    BUILD_RC=127
    printf 'missing build script: %s\n' "$BUILD_BIN" > "$BUILD_LOG"
fi

MODEL_PATH="$RUN_DIR/visual/visual-model.json"
if [ -s "$BUILD_LOG" ]; then
    parsed_model="$(python3 - "$BUILD_LOG" <<'PY' 2>/dev/null
import json
import sys

for line in reversed(open(sys.argv[1], encoding="utf-8", errors="replace").read().splitlines()):
    try:
        item = json.loads(line)
    except Exception:
        continue
    if isinstance(item, dict) and item.get("out"):
        print(item["out"])
        break
PY
)"
    if [ -n "$parsed_model" ] && [ -s "$parsed_model" ]; then
        MODEL_PATH="$(realpath -m "$parsed_model")"
    fi
fi

BUILD_OK=0
if [ "$BUILD_RC" -eq 0 ] && [ -s "$MODEL_PATH" ] && python3 - "$MODEL_PATH" <<'PY' >/dev/null 2>&1
import json
import sys

try:
    data = json.load(open(sys.argv[1], encoding="utf-8"))
except Exception:
    raise SystemExit(1)
raise SystemExit(0 if isinstance(data, dict) else 1)
PY
then
    BUILD_OK=1
else
    [ "$BUILD_RC" -eq 0 ] && BUILD_RC=1
    log "visual model build failed rc=$BUILD_RC model=$MODEL_PATH"
fi

AGENTIC_RC="skipped"
AGENTIC_ATTEMPTED=0
IMAGES_RC="skipped"
IMAGES_ATTEMPTED=0
RENDER_RC="skipped"
AGENTIC_REASON=""
IMAGES_REASON=""

if [ "$BUILD_OK" -eq 1 ]; then
    if [ "$CLAUDE_AVAILABLE" -eq 1 ] && [ -f "$AGENTIC_BIN" ]; then
        AGENTIC_ATTEMPTED=1
        log "render attack scenes agentically (claude=$(command -v "$CLAUDE_BIN"))"
        agentic_args=(--model "$MODEL_PATH" --out-dir "$OUTPUT" --max "$MAX" --timeout "$AGENT_TIMEOUT")
        [ -n "$FOCUS_FINDING" ] && agentic_args+=(--finding "$FOCUS_FINDING")
        [ -n "$CLAUDE_BIN" ] && agentic_args+=(--claude "$CLAUDE_BIN")
        [ -n "$MODEL" ] && agentic_args+=(--claude-model "$MODEL")
        run_script "$AGENTIC_BIN" "${agentic_args[@]}" > "$AGENTIC_LOG" 2>&1
        AGENTIC_RC=$?
        if [ "$AGENTIC_RC" -ne 0 ]; then
            AGENTIC_REASON="$(tail_log "$AGENTIC_LOG")"
            log "agentic scenes failed rc=$AGENTIC_RC; falling back to image renderer"
        fi
    else
        AGENTIC_REASON="claude unavailable: $CLAUDE_BIN"
        log "agentic scenes skipped ($AGENTIC_REASON)"
    fi

    if [ "$AGENTIC_RC" != "0" ]; then
        IMAGES_ATTEMPTED=1
        if [ -f "$IMAGES_BIN" ]; then
            log "render attack images (fallback)"
            images_args=(--model "$MODEL_PATH" --out-dir "$OUTPUT" --max "$MAX" --timeout "$TIMEOUT")
            [ -n "$FOCUS_FINDING" ] && images_args+=(--finding "$FOCUS_FINDING")
            run_script "$IMAGES_BIN" "${images_args[@]}" > "$IMAGES_LOG" 2>&1
            IMAGES_RC=$?
        else
            IMAGES_RC=127
            printf 'missing image script: %s\n' "$IMAGES_BIN" > "$IMAGES_LOG"
        fi
        if [ "$IMAGES_RC" -ne 0 ]; then
            IMAGES_REASON="$(tail_log "$IMAGES_LOG")"
            log "image renderer failed rc=$IMAGES_RC"
        fi
    fi

    log "render diagrams and illustrated report"
    if [ -f "$RENDER_BIN" ]; then
        run_script "$RENDER_BIN" --model "$MODEL_PATH" --out-dir "$OUTPUT" > "$RENDER_LOG" 2>&1
        RENDER_RC=$?
    else
        RENDER_RC=127
        printf 'missing render script: %s\n' "$RENDER_BIN" > "$RENDER_LOG"
    fi
    if [ "$RENDER_RC" -eq 0 ] && [ ! -s "$OUTPUT/report-illustrated.md" ]; then
        RENDER_RC=1
        printf '\n[visual_report] render reported success but report-illustrated.md is missing\n' >> "$RENDER_LOG"
    fi
    if [ "$RENDER_RC" -ne 0 ]; then
        log "render_diagrams failed rc=$RENDER_RC"
    fi
else
    AGENTIC_REASON="visual model build failed"
    IMAGES_REASON="visual model build failed"
fi

export VR_PROJECT="$PROJECT"
export VR_RUN_DIR="$RUN_DIR"
export VR_OUTPUT="$OUTPUT"
export VR_MODEL_PATH="$MODEL_PATH"
export VR_MAX="$MAX"
export VR_BUILD_RC="$BUILD_RC"
export VR_AGENTIC_RC="$AGENTIC_RC"
export VR_IMAGES_RC="$IMAGES_RC"
export VR_RENDER_RC="$RENDER_RC"
export VR_BUILD_OK="$BUILD_OK"
export VR_CLAUDE_AVAILABLE="$CLAUDE_AVAILABLE"
export VR_AGENTIC_ATTEMPTED="$AGENTIC_ATTEMPTED"
export VR_IMAGES_ATTEMPTED="$IMAGES_ATTEMPTED"
export VR_AGENTIC_REASON="$AGENTIC_REASON"
export VR_IMAGES_REASON="$IMAGES_REASON"
export VR_FOCUS_FINDING="$FOCUS_FINDING"
export VR_BUILD_LOG="$BUILD_LOG"
export VR_AGENTIC_LOG="$AGENTIC_LOG"
export VR_IMAGES_LOG="$IMAGES_LOG"
export VR_RENDER_LOG="$RENDER_LOG"

python3 - <<'PY'
import json
import os
from pathlib import Path

out = Path(os.environ["VR_OUTPUT"])
run_dir = Path(os.environ["VR_RUN_DIR"])
model_path = Path(os.environ["VR_MODEL_PATH"])
report_path = out / "report-illustrated.md"
max_scenes = int(os.environ["VR_MAX"])


def rc(value):
    return None if value in ("", "skipped") else int(value)


build_rc = rc(os.environ.get("VR_BUILD_RC", ""))
agentic_rc = rc(os.environ.get("VR_AGENTIC_RC", ""))
images_rc = rc(os.environ.get("VR_IMAGES_RC", ""))
render_rc = rc(os.environ.get("VR_RENDER_RC", ""))

all_ids = []
if model_path.exists():
    try:
        model = json.loads(model_path.read_text(encoding="utf-8"))
    except Exception:
        model = {}
    for attack in (model.get("trees") or {}).get("attacks") or []:
        finding_id = attack.get("finding_id") or str(attack.get("id") or "").split(":")[-1]
        severity = str(attack.get("status") or attack.get("severity") or "").lower()
        if severity and severity not in ("critical", "high"):
            continue
        finding_id = str(finding_id or "").strip()
        if finding_id and finding_id not in all_ids:
            all_ids.append(finding_id)

focus = os.environ.get("VR_FOCUS_FINDING", "").strip()
selected_ids = [focus] if focus else all_ids[:max_scenes]
scene_count = len(list(out.glob("scene-*.webp")))
missing_all = [fid for fid in all_ids if not (out / f"scene-{fid}.webp").exists()]
missing_selected = [fid for fid in selected_ids if not (out / f"scene-{fid}.webp").exists()]

build_ok = os.environ.get("VR_BUILD_OK") == "1" and model_path.exists()
report_ok = render_rc == 0 and report_path.exists()
reasons = []

if not build_ok:
    reasons.append(f"build_visual_model failed (rc={build_rc})")
elif not all_ids:
    reasons.append("no critical/high findings require scene images")
if os.environ.get("VR_CLAUDE_AVAILABLE") != "1" and all_ids:
    reasons.append(f"claude unavailable; used image renderer ({os.environ.get('VR_AGENTIC_REASON') or 'not found'})")
if agentic_rc not in (None, 0):
    detail = os.environ.get("VR_AGENTIC_REASON") or "no detail"
    reasons.append(f"agentic scene generation failed (rc={agentic_rc}); fallback attempted: {detail}")
if images_rc not in (None, 0):
    detail = os.environ.get("VR_IMAGES_REASON") or "no detail"
    reasons.append(f"image generation failed (rc={images_rc}): {detail}")
if missing_all:
    reasons.append("missing critical/high scene images: " + ", ".join(missing_all))
if not report_ok:
    reasons.append(f"render_diagrams failed (rc={render_rc}) or report-illustrated.md missing")

if not build_ok or not report_ok:
    status = "blocked"
elif missing_all:
    status = "partial"
else:
    status = "ready"

if not build_ok:
    scene_status = "blocked"
elif not all_ids or not missing_all:
    scene_status = "ready"
elif not missing_selected:
    scene_status = "partial"
else:
    produced_any = any((out / f"scene-{fid}.webp").exists() for fid in selected_ids)
    generation_failed = agentic_rc not in (None, 0) and images_rc not in (None, 0)
    if generation_failed or not produced_any:
        scene_status = "blocked"
    else:
        scene_status = "partial"

steps = {
    "build_visual_model": {
        "returncode": build_rc,
        "ok": build_ok,
        "log": os.environ.get("VR_BUILD_LOG"),
    },
    "render_attack_scenes_agentic": {
        "attempted": os.environ.get("VR_AGENTIC_ATTEMPTED") == "1",
        "returncode": agentic_rc,
        "ok": agentic_rc == 0,
        "log": os.environ.get("VR_AGENTIC_LOG"),
    },
    "render_attack_images": {
        "attempted": os.environ.get("VR_IMAGES_ATTEMPTED") == "1",
        "returncode": images_rc,
        "ok": images_rc == 0,
        "log": os.environ.get("VR_IMAGES_LOG"),
    },
    "render_diagrams": {
        "returncode": render_rc,
        "ok": report_ok,
        "log": os.environ.get("VR_RENDER_LOG"),
    },
}
returncodes = {
    "build_visual_model": build_rc,
    "render_attack_scenes_agentic": agentic_rc,
    "render_attack_images": images_rc,
    "render_diagrams": render_rc,
}

summary = {
    "project": os.environ.get("VR_PROJECT"),
    "run_dir": str(run_dir),
    "output_dir": str(out),
    "model_path": str(model_path),
    "visual_model": str(model_path),
    "illustrated_report_path": str(report_path),
    "illustrated_report": str(report_path),
    "max_scenes": max_scenes,
    "scene_count": scene_count,
    "critical_high_scene_ids": all_ids,
    "critical_high_count": len(all_ids),
    "selected_scene_ids": selected_ids,
    "missing_critical_high_scene_ids": missing_all,
    "missing_scene_ids": missing_all,
    "missing_selected_scene_ids": missing_selected,
    "steps": steps,
    "returncodes": returncodes,
    "status": status,
    "scene_status": scene_status,
    "reasons": reasons,
}

(out / "visual-summary.json").write_text(
    json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)

lines = [
    f"# Visual report summary — {summary['project']}",
    "",
    f"- status: `{status}`",
    f"- scene status: `{scene_status}`",
    f"- model: `{model_path}`",
    f"- illustrated report: `{report_path}`",
    f"- scenes: {scene_count}/{len(selected_ids)} selected ({len(all_ids)} critical/high)",
    f"- missing critical/high scene ids: {', '.join(missing_all) if missing_all else 'none'}",
    "",
    "## Steps",
    "",
    "| step | attempted | rc | ok |",
    "|---|---|---|---|",
]
for name, step in steps.items():
    attempted = step.get("attempted", True)
    lines.append(f"| {name} | {str(attempted).lower()} | {step.get('returncode')} | {str(step.get('ok')).lower()} |")
lines += ["", "## Reasons", ""]
if reasons:
    lines += [f"- {reason}" for reason in reasons]
else:
    lines.append("- none")
lines.append("")
(out / "visual-summary.md").write_text("\n".join(lines), encoding="utf-8")

if status == "ready":
    print(f"[visual_report] ready: {report_path}")
elif status == "partial":
    print(f"[visual_report] partial: {report_path} (missing {len(missing_all)} critical/high scene(s))")
else:
    print(f"[visual_report] blocked: see {out / 'visual-summary.md'}")
raise SystemExit(0 if build_ok and report_ok else 1)
PY

SUMMARY_RC=$?
log "summary: $OUTPUT/visual-summary.json (rc=$SUMMARY_RC)"
exit "$SUMMARY_RC"
