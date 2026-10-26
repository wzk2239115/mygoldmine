#!/usr/bin/env bash
# T12 测试用假执行器：不调用模型，只按参数 sleep / 失败 / 产出最小报告。
#
# 环境变量:
#   FAKE_MINE_SLEEP        每次尝试的秒数（默认 0）
#   FAKE_MINE_LOG          START/END 追加日志路径（用于验证并发上限）
#   FAKE_MINE_FAIL_FIRST   若非空，首次尝试失败并在 FAKE_MINE_MARKER 留标记
#   FAKE_MINE_MARKER       首次失败标记路径
#   FAKE_MINE_INCOMPLETE   若非空，退出 0 但不写报告（验证不完整判定）
set -uo pipefail

project=""
target=""
run_dir=""
timeout=""
while [ "$#" -gt 0 ]; do
    case "$1" in
        --project) project="$2"; shift ;;
        --target) target="$2"; shift ;;
        --run-dir) run_dir="$2"; shift ;;
        --timeout) timeout="$2"; shift ;;
        --model|--agent) shift ;;
        *) ;;
    esac
    shift
done

[ -n "$project" ] || project="fake"
[ -n "$run_dir" ] || { echo "fake_mine: missing --run-dir" >&2; exit 3; }

sleep_s="${FAKE_MINE_SLEEP:-0}"
logf="${FAKE_MINE_LOG:-/dev/null}"
started_epoch="$(date +%s)"
started_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

log_event() { printf '%s %s %s\n' "$1" "$project" "$(date +%s.%N)" >> "$logf"; }
log_event START

finish() {
    local rc="$1"
    log_event END
    exit "$rc"
}
trap 'finish 143' TERM
trap 'finish 130' INT

if [ -n "${FAKE_MINE_FAIL_FIRST:-}" ]; then
    marker="${FAKE_MINE_MARKER:-/tmp/fake-mine-first-fail}"
    if [ ! -e "$marker" ]; then
        : > "$marker"
        echo "fake_mine: intentional first-attempt failure for $project" >&2
        finish 9
    fi
fi

if [ "$sleep_s" -gt 0 ] 2>/dev/null; then
    sleep "$sleep_s"
fi

if [ -n "${FAKE_MINE_INCOMPLETE:-}" ]; then
    echo "fake_mine: skipping reports for $project" >&2
    finish 0
fi

mkdir -p "$run_dir" || finish 3
cat > "$run_dir/audit-report.md" <<EOF
# Fake audit report: $project

- target: $target
- generated_by: tests/fixtures/fake-mine-executor/fake_mine.sh
EOF
printf '{"project":"%s","findings":[],"fake":true}\n' "$project" > "$run_dir/audit-report.json"
jq -n \
    --arg project "$project" \
    --arg target "$target" \
    --arg started_at "$started_at" \
    --arg ended_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --argjson duration "$(( $(date +%s) - started_epoch ))" \
    '{
        schema_version: 1,
        project: $project,
        target_url: $target,
        commit: "fake",
        started_at: $started_at,
        ended_at: $ended_at,
        duration_seconds: $duration,
        model: "fake",
        agent: "fake",
        attempts: 1,
        exit_code: 0,
        timed_out: false,
        renderer_exit_code: 0,
        reports_complete: true,
        fake: true
    }' > "$run_dir/run-meta.json"

finish 0
