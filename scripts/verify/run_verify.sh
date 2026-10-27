#!/usr/bin/env bash
# Phase 4: 在隔离容器中验证一条 finding。
#
# 约定：
#   - 输入 finding（JSON/Markdown）+ harness（可执行脚本，推荐 .sh/.py）
#   - harness 可用环境变量：
#       VERIFY_DIR=/verify  EVIDENCE_DIR=/verify/evidence
#       TARGET_DIR=/opt/target  SOURCE_DIR=/source-ro
#       FINDING_FILE=/verify/finding.<ext>  PROJECT=<project>
#   - harness 写 /verify/verdict.json:
#       {"verdict":"confirmed|rejected|inconclusive|blocked","reason":"...","evidence":["..."],"limitations":["..."]}
#     也可用退出码：0 confirmed / 10 rejected / 20 inconclusive / 30 blocked
#
# 产物：
#   verify-report.md / verify-report.json
#   harness/ finding.* harness.stdout.log harness.stderr.log evidence/
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

log() { printf '[verify] %s\n' "$*" >&2; }
die() { printf '[verify] ERROR: %s\n' "$*" >&2; exit "${2:-3}"; }

usage() {
    cat <<'EOF'
用法: run_verify.sh --project NAME --image IMAGE --finding FILE --harness FILE [选项]

必填:
  --project NAME       项目名
  --image IMAGE        环境镜像（建议 mygoldmine/env:<project>-<commit>）
  --finding FILE       finding 文件（JSON/Markdown）
  --harness FILE       验证脚本（.sh/.py 或带 shebang 的可执行文件）

选项:
  --run-dir DIR        产物目录（默认 runs/<project>/verify/<id>-<ts>）
  --source DIR         原始源码（只读挂载到 /source-ro）
  --env-manifest FILE  env-manifest.json（默认 env/<project>/env-manifest.json）
  --timeout SECONDS    验证超时（默认 300）
  --network MODE       none|bridge（默认 none）
  --memory LIMIT       容器内存（默认 4g）
  --cpus N             容器 CPU（默认 2）
  --keep-container     失败时保留容器（排障用）
  -h, --help           显示帮助

退出码: 0 confirmed；10 rejected；20 inconclusive；30 blocked；3 参数错误
EOF
}

PROJECT=""
IMAGE=""
FINDING=""
HARNESS=""
RUN_DIR=""
SOURCE=""
ENV_MANIFEST=""
TIMEOUT="${TIMEOUT:-300}"
NETWORK="none"
MEMORY="4g"
CPUS="2"
KEEP=0

while [ "$#" -gt 0 ]; do
    case "$1" in
        --project) [ "$#" -ge 2 ] || die "--project 需要参数"; PROJECT="$2"; shift ;;
        --image) [ "$#" -ge 2 ] || die "--image 需要参数"; IMAGE="$2"; shift ;;
        --finding) [ "$#" -ge 2 ] || die "--finding 需要参数"; FINDING="$2"; shift ;;
        --harness) [ "$#" -ge 2 ] || die "--harness 需要参数"; HARNESS="$2"; shift ;;
        --run-dir) [ "$#" -ge 2 ] || die "--run-dir 需要参数"; RUN_DIR="$2"; shift ;;
        --source) [ "$#" -ge 2 ] || die "--source 需要参数"; SOURCE="$2"; shift ;;
        --env-manifest) [ "$#" -ge 2 ] || die "--env-manifest 需要参数"; ENV_MANIFEST="$2"; shift ;;
        --timeout) [ "$#" -ge 2 ] || die "--timeout 需要参数"; TIMEOUT="$2"; shift ;;
        --network) [ "$#" -ge 2 ] || die "--network 需要参数"; NETWORK="$2"; shift ;;
        --memory) [ "$#" -ge 2 ] || die "--memory 需要参数"; MEMORY="$2"; shift ;;
        --cpus) [ "$#" -ge 2 ] || die "--cpus 需要参数"; CPUS="$2"; shift ;;
        --keep-container) KEEP=1 ;;
        -h|--help) usage; exit 0 ;;
        *) usage >&2; die "未知参数: $1" ;;
    esac
    shift
done

[ -n "$PROJECT" ] || die "缺少 --project"
[ -n "$IMAGE" ] || die "缺少 --image"
[ -n "$FINDING" ] || die "缺少 --finding"
[ -n "$HARNESS" ] || die "缺少 --harness"
[ -f "$FINDING" ] || die "finding 不存在: $FINDING"
[ -f "$HARNESS" ] || die "harness 不存在: $HARNESS"
case "$NETWORK" in none|bridge) ;; *) die "network 非法: $NETWORK" ;; esac
[[ "$TIMEOUT" =~ ^[1-9][0-9]*$ ]] || die "timeout 必须正整数"

PROJECT="$(printf '%s' "$PROJECT" | tr -c 'A-Za-z0-9._-' '_')"
FINDING="$(realpath "$FINDING")"
HARNESS="$(realpath "$HARNESS")"
[ -n "$SOURCE" ] && SOURCE="$(realpath -e "$SOURCE" 2>/dev/null)" || true
if [ -z "$ENV_MANIFEST" ]; then
    ENV_MANIFEST="$REPO_ROOT/env/$PROJECT/env-manifest.json"
fi

FINDING_ID=""
case "$FINDING" in
    *.json)
        if jq -e . "$FINDING" >/dev/null 2>&1; then
            FINDING_ID="$(jq -r '.id // .finding_id // .title // empty' "$FINDING" 2>/dev/null | head -1)"
        fi ;;
esac
[ -n "$FINDING_ID" ] || FINDING_ID="$(basename "${FINDING%.*}")"
FINDING_ID="$(printf '%s' "$FINDING_ID" | tr -c 'A-Za-z0-9._-' '_' | cut -c1-80)"

if [ -z "$RUN_DIR" ]; then
    RUN_DIR="$REPO_ROOT/runs/$PROJECT/verify/${FINDING_ID}-$(date -u +%Y%m%dT%H%M%SZ)"
fi
RUN_DIR="$(realpath -m "$RUN_DIR")"
if [ -d "$RUN_DIR" ] && [ -n "$(ls -A "$RUN_DIR" 2>/dev/null || true)" ]; then
    die "RUN_DIR 非空: $RUN_DIR" 6
fi
mkdir -p "$RUN_DIR/evidence" "$RUN_DIR/harness"

docker image inspect "$IMAGE" >/dev/null 2>&1 || die "镜像不存在: $IMAGE" 4
IMAGE_ID="$(docker image inspect "$IMAGE" --format '{{.Id}}' 2>/dev/null || true)"

FEXT="${FINDING##*.}"
[ "$FEXT" = "$FINDING" ] && FEXT="txt"
cp "$FINDING" "$RUN_DIR/finding.$FEXT"
HNAME="$(basename "$HARNESS")"
cp "$HARNESS" "$RUN_DIR/harness/$HNAME"
chmod +x "$RUN_DIR/harness/$HNAME" 2>/dev/null || true

STARTED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
START_EPOCH="$(date +%s)"
CNAME="mygoldmine-verify-${PROJECT}-$$"
STDOUT_LOG="$RUN_DIR/harness.stdout.log"
STDERR_LOG="$RUN_DIR/harness.stderr.log"
: > "$STDOUT_LOG"; : > "$STDERR_LOG"

ENV_STATUS="unknown"
if [ -f "$ENV_MANIFEST" ] && jq -e . "$ENV_MANIFEST" >/dev/null 2>&1; then
    ENV_STATUS="$(jq -r '.env_status // "unknown"' "$ENV_MANIFEST")"
fi

write_report() {
    local verdict="$1" reason="$2" rc="$3" timed_out="$4"
    local ended_at duration
    ended_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    duration=$(( $(date +%s) - START_EPOCH ))
    local evidence_json limits_json
    evidence_json="$(find "$RUN_DIR/evidence" -type f -printf '%f\n' 2>/dev/null | jq -R . | jq -s 'map(select(length>0))')"
    limits_json="[]"
    if [ -f "$ENV_MANIFEST" ]; then
        limits_json="$(jq -c '.limitations // []' "$ENV_MANIFEST" 2>/dev/null || echo '[]')"
    fi
    local harness_verdict_json="{}"
    if [ -f "$RUN_DIR/verdict.json" ] && jq -e . "$RUN_DIR/verdict.json" >/dev/null 2>&1; then
        harness_verdict_json="$(jq -c . "$RUN_DIR/verdict.json")"
    fi
    jq -n \
        --arg schema_version "1" \
        --arg project "$PROJECT" \
        --arg finding_id "$FINDING_ID" \
        --arg finding_file "$RUN_DIR/finding.$FEXT" \
        --arg image "$IMAGE" \
        --arg image_id "$IMAGE_ID" \
        --arg env_manifest "$ENV_MANIFEST" \
        --arg env_status "$ENV_STATUS" \
        --arg harness "$RUN_DIR/harness/$HNAME" \
        --arg network "$NETWORK" \
        --arg started_at "$STARTED_AT" \
        --arg ended_at "$ended_at" \
        --argjson duration_seconds "$duration" \
        --argjson exit_code "$rc" \
        --argjson timed_out "$timed_out" \
        --arg verdict "$verdict" \
        --arg reason "$reason" \
        --argjson evidence "$evidence_json" \
        --argjson limitations "$limits_json" \
        --argjson harness_verdict "$harness_verdict_json" \
        '{
            schema_version: $schema_version,
            project: $project,
            finding_id: $finding_id,
            finding_file: $finding_file,
            image: $image,
            image_id: $image_id,
            env_manifest: $env_manifest,
            env_status: $env_status,
            harness: $harness,
            network: $network,
            started_at: $started_at,
            ended_at: $ended_at,
            duration_seconds: $duration_seconds,
            exit_code: $exit_code,
            timed_out: $timed_out,
            verdict: $verdict,
            reason: $reason,
            evidence: $evidence,
            limitations: $limitations,
            harness_verdict: $harness_verdict,
            artifacts: {
                stdout: "harness.stdout.log",
                stderr: "harness.stderr.log",
                report_md: "verify-report.md",
                report_json: "verify-report.json"
            }
        }' > "$RUN_DIR/verify-report.json"

    {
        echo "# Verification Report — $FINDING_ID"
        echo
        echo "- Project: \`$PROJECT\`"
        echo "- Verdict: **$verdict**"
        echo "- Reason: $reason"
        echo "- Image: \`$IMAGE\` (\`$IMAGE_ID\`)"
        echo "- Env status: \`$ENV_STATUS\`"
        echo "- Network: \`$NETWORK\`"
        echo "- Duration: ${duration}s"
        echo "- Exit code: $rc$([ "$timed_out" = "true" ] && echo " (timeout)")"
        echo
        echo "## Evidence"
        if [ "$evidence_json" = "[]" ]; then
            echo "- 无（harness 未写 evidence/）"
        else
            echo "$evidence_json" | jq -r '.[] | "- evidence/\(.)"'
        fi
        echo
        echo "## Limitations"
        if [ "$limits_json" = "[]" ]; then
            echo "- 无"
        else
            echo "$limits_json" | jq -r '.[] | "- \(.)"'
        fi
        echo
        echo "## Logs"
        echo '```text'
        tail -n 40 "$STDOUT_LOG" 2>/dev/null || true
        echo '```'
        if [ -s "$STDERR_LOG" ]; then
            echo
            echo "stderr:"
            echo '```text'
            tail -n 40 "$STDERR_LOG" 2>/dev/null || true
            echo '```'
        fi
    } > "$RUN_DIR/verify-report.md"
}

if [ "$ENV_STATUS" = "blocked" ]; then
    write_report "blocked" "环境构建状态为 blocked，无法验证" 30 "false"
    log "env blocked，直接返回 blocked: $RUN_DIR/verify-report.md"
    exit 30
fi

MOUNT_SOURCE=()
if [ -n "$SOURCE" ] && [ -d "$SOURCE" ]; then
    MOUNT_SOURCE=(--mount "type=bind,src=$SOURCE,dst=/source-ro,readonly")
fi

case "$HNAME" in
    *.sh) ENTRY=(--entrypoint /bin/bash); ARG="/verify/harness/$HNAME" ;;
    *.py) ENTRY=(--entrypoint python3); ARG="/verify/harness/$HNAME" ;;
    *) ENTRY=(--entrypoint "/verify/harness/$HNAME"); ARG="" ;;
esac

cleanup() {
    if [ "$KEEP" -eq 0 ] && docker ps -q --filter "name=^${CNAME}$" >/dev/null 2>&1; then
        docker rm -f "$CNAME" >/dev/null 2>&1 || true
    fi
}
trap cleanup EXIT INT TERM

log "验证 $FINDING_ID image=$IMAGE network=$NETWORK timeout=${TIMEOUT}s"
set +e
timeout --signal=TERM --kill-after=10 "$TIMEOUT" \
    docker run --rm --name "$CNAME" \
        --network "$NETWORK" \
        --cap-drop ALL --security-opt no-new-privileges \
        --pids-limit 512 --memory "$MEMORY" --cpus "$CPUS" \
        --tmpfs /tmp:rw,exec,size=1g \
        --mount "type=bind,src=$RUN_DIR,dst=/verify" \
        "${MOUNT_SOURCE[@]}" \
        -e VERIFY_DIR=/verify \
        -e EVIDENCE_DIR=/verify/evidence \
        -e TARGET_DIR=/opt/target \
        -e SOURCE_DIR=/source-ro \
        -e FINDING_FILE="/verify/finding.$FEXT" \
        -e PROJECT="$PROJECT" \
        --workdir /opt/target \
        "${ENTRY[@]}" \
        "$IMAGE" $ARG \
        > "$STDOUT_LOG" 2> "$STDERR_LOG"
RC=$?
set -e

TIMED_OUT="false"
if [ "$RC" -eq 124 ] || [ "$RC" -eq 137 ]; then TIMED_OUT="true"; fi

VERDICT=""
REASON=""
if [ -f "$RUN_DIR/verdict.json" ] && jq -e . "$RUN_DIR/verdict.json" >/dev/null 2>&1; then
    VERDICT="$(jq -r '.verdict // empty' "$RUN_DIR/verdict.json" 2>/dev/null)"
    REASON="$(jq -r '.reason // empty' "$RUN_DIR/verdict.json" 2>/dev/null)"
fi

if [ -z "$VERDICT" ]; then
    case "$RC" in
        0) VERDICT="confirmed"; REASON="harness 退出 0 且未写 verdict.json" ;;
        10) VERDICT="rejected"; REASON="harness 退出 10（rejected）" ;;
        20) VERDICT="inconclusive"; REASON="harness 退出 20（inconclusive）" ;;
        30) VERDICT="blocked"; REASON="harness 退出 30（blocked）" ;;
        124|137) VERDICT="blocked"; REASON="验证超时" ;;
        125|126|127) VERDICT="blocked"; REASON="容器/入口执行失败（rc=$RC）" ;;
        *) VERDICT="inconclusive"; REASON="harness 退出 $RC，未写 verdict.json" ;;
    esac
fi

case "$VERDICT" in confirmed|rejected|inconclusive|blocked) ;; *) VERDICT="inconclusive"; REASON="非法 verdict，按 inconclusive 处理" ;; esac
[ -n "$REASON" ] || REASON="未提供原因"

write_report "$VERDICT" "$REASON" "$RC" "$TIMED_OUT"
log "verdict=$VERDICT rc=$RC report=$RUN_DIR/verify-report.md"

case "$VERDICT" in
    confirmed) exit 0 ;;
    rejected) exit 10 ;;
    inconclusive) exit 20 ;;
    blocked) exit 30 ;;
esac
