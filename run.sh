#!/usr/bin/env bash
# 一条命令拉起 Docker + Claude Code + 360 DeepSeek，并实时渲染过程日志。
#
#   bash run.sh /path/to/source
#   bash run.sh /path/to/source --timeout 7200
#   bash run.sh --status runs/<project>/<ts>
#   bash run.sh --stop   runs/<project>/<ts>
#
# 日志：
#   runs/<project>/<ts>/claude.rendered.log   实时人读日志（tail -f）
#   runs/<project>/<ts>/raw.jsonl             原始 stream-json
#   runs/<project>/<ts>.meta/wrapper.log      容器/脚本日志
set -uo pipefail

SCRIPT_PATH="$(realpath "${BASH_SOURCE[0]}")"
REPO_ROOT="$(cd "$(dirname "$SCRIPT_PATH")" && pwd)"
MINER="$REPO_ROOT/scripts/mine/mine_one_docker.sh"
RENDERER="$REPO_ROOT/scripts/mine/render_claude_log.py"

die() { printf '[run] ERROR: %s\n' "$*" >&2; exit "${2:-1}"; }
log() { printf '[run] %s\n' "$*" >&2; }

usage() {
    cat <<'EOF'
用法:
  bash run.sh <源码路径> [选项]
  bash run.sh --status <run_dir>
  bash run.sh --stop   <run_dir>

选项:
  --timeout SECONDS   单次挖掘墙钟上限（默认 21600 = 6h）
  --model MODEL       模型（默认 360-proxy/deepseek/deepseek-v4.1-flash）
  --agent AGENT       Claude Code agent（默认 security-orchestrator）
  --run-dir DIR       自定义产物目录（默认 runs/<project>/<UTC 时间>）
  --image IMAGE       Docker 镜像（默认 mygoldmine:dev）
  --build             镜像不存在时自动构建
  --foreground        启动后前台 tail 渲染日志（Ctrl-C 只退出 tail，不停止挖掘）
  --skip-env          跳过 Phase 0 环境构建
  --env-mode MODE     Phase 0 安装模式：auto|none|editable|requirements|full（默认 auto）
  --skip-verify       跳过 Phase 4 自动验证
  --verify-max N      最多验证多少条（默认 10）
  --verify-severity L 验证的严重度（默认 critical,high）
  --verify-parallel N 并行验证数（默认 2）
  --mine-only         等价于 --skip-env --skip-verify
  --verify-only DIR   对已有挖掘产物只做 Phase 4 验证（不重新挖掘）
  -h, --help          显示帮助

鉴权:
  ANTHROPIC_AUTH_TOKEN / ANTHROPIC_API_KEY / GLM_API_KEY，
  或自动读取 ~/.config/opencode/opencode.json 的 360 key。

示例:
  bash run.sh /home/wzk/mygoldmine/targets/vllm
  bash run.sh /home/wzk/mygoldmine/targets/verl --timeout 3600
  bash run.sh --status /home/wzk/mygoldmine/runs/verl/20261027T030000Z
  bash run.sh --stop   /home/wzk/mygoldmine/runs/verl/20261027T030000Z
EOF
}

MODE="start"
TARGET=""
RUN_DIR=""
TIMEOUT="${TIMEOUT:-21600}"
MODEL="${MODEL:-360-proxy/deepseek/deepseek-v4.1-flash}"
AGENT="${AGENT:-security-orchestrator}"
IMAGE="${MYGOLDMINE_IMAGE:-mygoldmine:dev}"
PROJECT="${PROJECT:-}"
SOURCE="${SOURCE:-}"
BUILD=0
FOREGROUND=0
SKIP_ENV=0
ENV_MODE="auto"
SKIP_VERIFY=0
VERIFY_MAX=10
VERIFY_SEVERITY="critical,high"
VERIFY_PARALLEL=2

while [ "$#" -gt 0 ]; do
    case "$1" in
        --supervise) MODE="supervise" ;;
        --status) MODE="status"; [ "$#" -ge 2 ] || die "--status 需要 run_dir" 3; RUN_DIR="$2"; shift ;;
        --stop)   MODE="stop";   [ "$#" -ge 2 ] || die "--stop 需要 run_dir" 3;   RUN_DIR="$2"; shift ;;
        --timeout) [ "$#" -ge 2 ] || die "--timeout 需要参数" 3; TIMEOUT="$2"; shift ;;
        --target)  [ "$#" -ge 2 ] || die "--target 需要参数" 3;  TARGET="$2"; shift ;;
        --model)   [ "$#" -ge 2 ] || die "--model 需要参数" 3;   MODEL="$2"; shift ;;
        --agent)   [ "$#" -ge 2 ] || die "--agent 需要参数" 3;   AGENT="$2"; shift ;;
        --run-dir) [ "$#" -ge 2 ] || die "--run-dir 需要参数" 3; RUN_DIR="$2"; shift ;;
        --image)   [ "$#" -ge 2 ] || die "--image 需要参数" 3;   IMAGE="$2"; shift ;;
        --project) [ "$#" -ge 2 ] || die "--project 需要参数" 3; PROJECT="$2"; shift ;;
        --source) [ "$#" -ge 2 ] || die "--source 需要参数" 3; SOURCE="$(realpath -e "$2" 2>/dev/null || true)"; shift ;;
        --build) BUILD=1 ;;
        --foreground) FOREGROUND=1 ;;
        --skip-env) SKIP_ENV=1 ;;
        --env-mode) [ "$#" -ge 2 ] || die "--env-mode 需要参数" 3; ENV_MODE="$2"; shift ;;
        --skip-verify) SKIP_VERIFY=1 ;;
        --verify-max) [ "$#" -ge 2 ] || die "--verify-max 需要参数" 3; VERIFY_MAX="$2"; shift ;;
        --verify-severity) [ "$#" -ge 2 ] || die "--verify-severity 需要参数" 3; VERIFY_SEVERITY="$2"; shift ;;
        --verify-parallel) [ "$#" -ge 2 ] || die "--verify-parallel 需要参数" 3; VERIFY_PARALLEL="$2"; shift ;;
        --mine-only) SKIP_ENV=1; SKIP_VERIFY=1 ;;
        --verify-only) MODE="verify"; [ "$#" -ge 2 ] || die "--verify-only 需要 run_dir" 3; RUN_DIR="$2"; shift ;;
        -h|--help) usage; exit 0 ;;
        --) shift; [ "$#" -ge 1 ] || die "缺少源码路径" 3; TARGET="$1"; shift; break ;;
        -*) usage >&2; die "未知参数: $1" 3 ;;
        *) [ -z "$TARGET" ] || die "只能指定一个源码路径" 3; TARGET="$1" ;;
    esac
    shift
done

if [ ! -f "$REPO_ROOT/.claude/agents/${AGENT}.md" ] && [ "$AGENT" != "security-orchestrator" ]; then
    [ "${AGENT}" != "1" ] && log "WARN: 未找到 agent '${AGENT}'，回退到 security-orchestrator"
    AGENT="security-orchestrator"
fi

if [ "$MODE" = "verify" ]; then
    RUN_DIR="$(realpath -e "$RUN_DIR" 2>/dev/null)" || die "run_dir 不存在: $RUN_DIR" 4
    [ -s "$RUN_DIR/audit-report.json" ] || die "缺少 audit-report.json: $RUN_DIR" 4
    if [ -z "$PROJECT" ]; then
        PROJECT="$(basename "$(dirname "$RUN_DIR")")"
    fi
    MANIFEST="$REPO_ROOT/env/$PROJECT/env-manifest.json"
    if [ -z "$IMAGE" ] && [ -f "$MANIFEST" ]; then
        IMAGE="$(jq -r '.image // empty' "$MANIFEST")"
    fi
    if [ -z "$SOURCE" ] && [ -f "$MANIFEST" ]; then
        SOURCE="$(jq -r '.source // empty' "$MANIFEST")"
    fi
    [ -n "$IMAGE" ] || die "缺少环境镜像（先 build_env，或传 --image）" 4
    [ -n "$SOURCE" ] || die "缺少源码路径（manifest 中没有 source，或传 --source）" 4
    log "Phase 4 only: project=$PROJECT run_dir=$RUN_DIR image=$IMAGE"
    bash "$REPO_ROOT/scripts/verify/auto_verify.sh" \
        --project "$PROJECT" --run-dir "$RUN_DIR" \
        --image "$IMAGE" --source "$SOURCE" \
        --max "$VERIFY_MAX" --severity "$VERIFY_SEVERITY" \
        --parallel "$VERIFY_PARALLEL" \
        --output "$RUN_DIR/verify/auto"
    exit $?
fi

if [ "$MODE" = "status" ] || [ "$MODE" = "stop" ]; then
    RUN_DIR="$(realpath -m "$RUN_DIR")"
    META="$RUN_DIR.meta"
    [ -d "$META" ] || die "找不到运行元数据: $META" 4
    PROJECT_FROM_RUN="$(basename "$(dirname "$RUN_DIR")")"
    if [ "$MODE" = "status" ]; then
        [ -f "$META/status.json" ] && jq . "$META/status.json" 2>/dev/null || echo "status.json 尚未生成"
        cname="$(cat "$META/container.name" 2>/dev/null || true)"
        if [ -n "$cname" ] && docker ps --format '{{.Names}}' | grep -qx "$cname"; then
            echo "container=$cname state=running"
        else
            echo "container=${cname:-unknown} state=not-running"
        fi
        ENV_MAN="$REPO_ROOT/env/$PROJECT_FROM_RUN/env-manifest.json"
        if [ -f "$ENV_MAN" ]; then
            echo "env_status=$(jq -r '.env_status // "unknown"' "$ENV_MAN" 2>/dev/null) env_image=$(jq -r '.image // "-"' "$ENV_MAN" 2>/dev/null)"
        else
            echo "env_status=not-built"
        fi
        if [ -f "$RUN_DIR/verify/auto/summary.json" ]; then
            echo "verify_counts=$(jq -c '.counts // {}' "$RUN_DIR/verify/auto/summary.json" 2>/dev/null)"
            echo "verify_summary=$RUN_DIR/verify/auto/summary.md"
        else
            echo "verify_counts=- (not-run)"
        fi
        echo "tail -f $RUN_DIR/claude.rendered.log"
        echo "tail -f $META/wrapper.log"
        echo "tail -f $META/verify.log"
        echo "env build: $META/env-build.log"
        exit 0
    fi
    touch "$META/render.stop" 2>/dev/null || true
    cname="$(cat "$META/container.name" 2>/dev/null || true)"
    [ -n "$cname" ] && docker stop --time 20 "$cname" >/dev/null 2>&1 || true
    docker ps -q --filter "name=^mygoldmine-verify-${PROJECT_FROM_RUN}-" 2>/dev/null | xargs -r docker stop --time 10 >/dev/null 2>&1 || true
    for f in supervisor.pid wrapper.pid renderer.pid; do
        [ -f "$META/$f" ] || continue
        pid="$(cat "$META/$f" 2>/dev/null || true)"
        [[ "$pid" =~ ^[0-9]+$ ]] || continue
        if [ "$f" = "supervisor.pid" ]; then
            kill -TERM "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null || true
        else
            kill -TERM "$pid" 2>/dev/null || true
        fi
    done
    echo "[run] stopped $RUN_DIR"
    exit 0
fi

if [ "$MODE" = "supervise" ]; then
    [ -n "$TARGET" ] || die "supervise 缺少 --target" 3
    [ -n "$RUN_DIR" ] || die "supervise 缺少 --run-dir" 3
    RUN_DIR="$(realpath -m "$RUN_DIR")"
    META="$RUN_DIR.meta"
    mkdir -p "$META"
    if [ -z "$PROJECT" ]; then
        PROJECT="$(basename "${RUN_DIR%/}")"
    fi
    PROJECT="$(printf '%s' "$PROJECT" | tr -c 'A-Za-z0-9._-' '_')"
    STARTED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    ENV_IMAGE=""
    ENV_STATUS="unknown"
    VERIFY_SUMMARY=""
    VERIFY_COUNTS="{}"

    write_status() {
        local state="$1" rc="$2"
        jq -n \
            --arg state "$state" \
            --arg project "$PROJECT" \
            --arg target "$TARGET" \
            --arg run_dir "$RUN_DIR" \
            --arg model "$MODEL" \
            --arg agent "$AGENT" \
            --arg image "$IMAGE" \
            --arg env_image "$ENV_IMAGE" \
            --arg env_status "$ENV_STATUS" \
            --arg verify_summary "$VERIFY_SUMMARY" \
            --arg started_at "$STARTED_AT" \
            --arg updated_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
            --arg container "$(cat "$META/container.name" 2>/dev/null || true)" \
            --argjson verify_counts "$VERIFY_COUNTS" \
            --argjson timeout "$TIMEOUT" \
            --argjson exit_code "$rc" \
            '{state:$state, project:$project, target:$target, run_dir:$run_dir,
              model:$model, agent:$agent, image:$image, env_image:$env_image,
              env_status:$env_status, verify_summary:$verify_summary,
              verify_counts:$verify_counts, timeout_seconds:$timeout,
              started_at:$started_at, updated_at:$updated_at, container:$container,
              exit_code:$exit_code}' > "$META/status.json"
    }

    write_status "starting" -1

    if [ "$SKIP_ENV" -eq 0 ]; then
        log "Phase 0: 构建环境（mode=$ENV_MODE）..."
        bash "$REPO_ROOT/scripts/env/build_env.sh" "$TARGET" \
            --project "$PROJECT" --mode "$ENV_MODE" \
            > "$META/env-build.log" 2>&1
        ENV_RC=$?
        if [ -f "$REPO_ROOT/env/$PROJECT/env-manifest.json" ]; then
            ENV_IMAGE="$(jq -r '.image // empty' "$REPO_ROOT/env/$PROJECT/env-manifest.json" 2>/dev/null || true)"
            ENV_STATUS="$(jq -r '.env_status // "unknown"' "$REPO_ROOT/env/$PROJECT/env-manifest.json" 2>/dev/null || true)"
        fi
        log "Phase 0 完成 rc=$ENV_RC status=$ENV_STATUS image=${ENV_IMAGE:-none}"
    else
        log "Phase 0 跳过（--skip-env）"
    fi
    write_status "running" -1
    log "supervisor 启动 project=$PROJECT run_dir=$RUN_DIR"

    MYGOLDMINE_IMAGE="$IMAGE" LIVE_RENDER=1 "$MINER" \
        --target "$TARGET" \
        --project "$PROJECT" \
        --run-dir "$RUN_DIR" \
        --timeout "$TIMEOUT" \
        --model "$MODEL" \
        --agent "$AGENT" \
        > "$META/wrapper.log" 2>&1 &
    WPID=$!
    echo "$WPID" > "$META/wrapper.pid"
    echo "mygoldmine-${PROJECT}-${WPID}" > "$META/container.name"

    for _ in $(seq 1 60); do
        [ -f "$RUN_DIR/raw.jsonl" ] && break
        kill -0 "$WPID" 2>/dev/null || break
        sleep 0.5
    done

    RPID=""
    if [ -f "$RUN_DIR/raw.jsonl" ]; then
        python3 "$RENDERER" --follow \
            --input "$RUN_DIR/raw.jsonl" \
            --output "$RUN_DIR/claude.rendered.log" \
            --stop-file "$META/render.stop" --quiet \
            > "$META/renderer.log" 2>&1 &
        RPID=$!
        echo "$RPID" > "$META/renderer.pid"
        write_status "running" -1
    else
        log "raw.jsonl 尚未出现，跳过实时渲染"
    fi

    wait "$WPID"
    RC=$?
    echo "$RC" > "$META/exit_code"
    touch "$META/render.stop" 2>/dev/null || true
    if [ -n "$RPID" ]; then wait "$RPID" 2>/dev/null || true; fi

    if [ -s "$RUN_DIR/raw.jsonl" ]; then
        python3 "$RENDERER" --input "$RUN_DIR/raw.jsonl" \
            --output "$RUN_DIR/claude.rendered.log" --quiet \
            >> "$META/renderer.log" 2>&1 || true
    fi

    if [ "$SKIP_VERIFY" -eq 0 ] && [ -n "$ENV_IMAGE" ] && [ -s "$RUN_DIR/audit-report.json" ]; then
        if docker image inspect "$ENV_IMAGE" >/dev/null 2>&1; then
            log "Phase 4: 自动验证（max=$VERIFY_MAX severity=$VERIFY_SEVERITY parallel=$VERIFY_PARALLEL）..."
            bash "$REPO_ROOT/scripts/verify/auto_verify.sh" \
                --project "$PROJECT" --run-dir "$RUN_DIR" \
                --image "$ENV_IMAGE" --source "$TARGET" \
                --max "$VERIFY_MAX" --severity "$VERIFY_SEVERITY" \
                --parallel "$VERIFY_PARALLEL" \
                --output "$RUN_DIR/verify/auto" \
                > "$META/verify.log" 2>&1
            VRC=$?
            if [ -f "$RUN_DIR/verify/auto/summary.json" ]; then
                VERIFY_SUMMARY="$RUN_DIR/verify/auto/summary.md"
                VERIFY_COUNTS="$(jq -c '.counts // {}' "$RUN_DIR/verify/auto/summary.json" 2>/dev/null || echo '{}')"
            fi
            log "Phase 4 完成 rc=$VRC counts=$VERIFY_COUNTS"
        else
            log "Phase 4 跳过：环境镜像不存在 $ENV_IMAGE"
            ENV_STATUS="blocked"
        fi
    else
        log "Phase 4 跳过（skip/no-report/no-env）"
    fi

    if [ "$RC" -eq 0 ]; then
        write_status "success" "$RC"
    elif [ "$RC" -eq 124 ] || [ "$RC" -eq 137 ]; then
        write_status "timeout" "$RC"
    else
        write_status "failed" "$RC"
    fi
    log "supervisor 结束 rc=$RC run_dir=$RUN_DIR"
    exit "$RC"
fi

# ---------- start ----------
[ -n "$TARGET" ] || { usage >&2; die "缺少源码路径" 3; }
TARGET="$(realpath -e "$TARGET" 2>/dev/null)" || die "源码路径不存在: $TARGET" 3
[ -d "$TARGET" ] || die "不是目录: $TARGET" 3
[[ "$TIMEOUT" =~ ^[1-9][0-9]*$ ]] || die "TIMEOUT 必须是正整数秒" 3

if [ -z "$PROJECT" ]; then
    PROJECT="$(basename "${TARGET%/}")"
fi
PROJECT="$(printf '%s' "$PROJECT" | tr -c 'A-Za-z0-9._-' '_')"

if [ -z "$RUN_DIR" ]; then
    RUN_DIR="$REPO_ROOT/runs/$PROJECT/$(date -u +%Y%m%dT%H%M%SZ)"
fi
RUN_DIR="$(realpath -m "$RUN_DIR")"
META="$RUN_DIR.meta"
mkdir -p "$META"

if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
    if [ "$BUILD" -eq 1 ]; then
        log "镜像不存在，开始构建: $IMAGE"
        docker build -f "$REPO_ROOT/docker/Dockerfile" -t "$IMAGE" "$REPO_ROOT" || die "docker build 失败" 9
    else
        die "镜像不存在: $IMAGE（先构建，或加 --build）" 9
    fi
fi

chmod +x "$MINER" "$RENDERER" 2>/dev/null || true

sup_args=(
    --target "$TARGET" --project "$PROJECT" --run-dir "$RUN_DIR"
    --timeout "$TIMEOUT" --model "$MODEL" --agent "$AGENT" --image "$IMAGE"
    --env-mode "$ENV_MODE" --verify-max "$VERIFY_MAX"
    --verify-severity "$VERIFY_SEVERITY" --verify-parallel "$VERIFY_PARALLEL"
)
[ "$SKIP_ENV" -eq 1 ] && sup_args+=(--skip-env)
[ "$SKIP_VERIFY" -eq 1 ] && sup_args+=(--skip-verify)

setsid nohup bash "$SCRIPT_PATH" --supervise "${sup_args[@]}" \
    > "$META/supervisor.log" 2>&1 < /dev/null &
SPID=$!
echo "$SPID" > "$META/supervisor.pid"

for _ in $(seq 1 30); do
    [ -f "$META/container.name" ] && [ -f "$RUN_DIR/raw.jsonl" ] && break
    kill -0 "$SPID" 2>/dev/null || break
    sleep 1
done

if [ "$FOREGROUND" -eq 1 ]; then
    echo "[run] foreground: tail -f $RUN_DIR/claude.rendered.log (Ctrl-C 只退出 tail)"
    tail -n +1 -F "$RUN_DIR/claude.rendered.log" 2>/dev/null
    exit 0
fi

cat <<EOF
[run] started
  target:    $TARGET
  project:   $PROJECT
  model:     $MODEL
  timeout:   ${TIMEOUT}s
  run_dir:   $RUN_DIR
  meta:      $META
  container: $(cat "$META/container.name" 2>/dev/null || echo pending)
  supervisor: $SPID
  runner:    $MINER
  pipeline:  Phase0 env -> mine -> Phase4 verify
  env_mode:  $ENV_MODE (skip=$SKIP_ENV)  verify: severities=$VERIFY_SEVERITY max=$VERIFY_MAX (skip=$SKIP_VERIFY)
EOF

if ! kill -0 "$SPID" 2>/dev/null; then
    echo "[run] supervisor 已退出，查看 $META/supervisor.log 和 $META/wrapper.log" >&2
    tail -n 20 "$META/supervisor.log" 2>/dev/null >&2 || true
    exit 1
fi

cat <<EOF

Phase 0 环境构建:
  tail -f "$META/env-build.log"

Phase 1/2 挖掘（实时渲染）:
  tail -f "$RUN_DIR/claude.rendered.log"
  tail -f "$RUN_DIR/raw.jsonl"
  tail -f "$META/wrapper.log"

Phase 4 自动验证:
  tail -f "$META/verify.log"
  # 完成后看：
  cat "$RUN_DIR/verify/auto/summary.md"

查看状态 / 停止:
  bash run.sh --status "$RUN_DIR"
  bash run.sh --stop "$RUN_DIR"
EOF
