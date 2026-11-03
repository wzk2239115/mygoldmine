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
#   runs/<project>/<ts>/raw.jsonl             原始流式 JSON 事件
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
  bash run.sh --status <产物目录>
  bash run.sh --stop   <产物目录>

选项:
  --timeout SECONDS   单次批量审计的实际运行时间上限（默认 21600 秒，即 6 小时）
  --model MODEL       模型（默认 360-proxy/deepseek/deepseek-v4.1-flash）
  --agent AGENT       Claude Code 智能体（默认 security-orchestrator）
  --run-dir DIR       自定义产物目录（默认 runs/<project>/<UTC 时间>）
  --image IMAGE       Docker 镜像（默认 mygoldmine:dev）
  --build             镜像不存在时自动构建
  --foreground        启动后在前台持续显示渲染日志（Ctrl-C 只退出日志显示，不停止批量审计）
  --skip-env          跳过第 0 阶段环境构建
  --env-mode MODE     第 0 阶段安装模式：auto|none|editable|requirements|full（默认 auto）
  --env-agent MODE    第 0 阶段智能体构建：auto|on|off（默认 auto；auto/on 均由智能体主导）
  --env-agent-timeout SEC   每轮智能体环境构建超时（默认 1800 秒）
  --env-agent-rounds N      智能体环境构建轮数（默认 1）
  --env-timeout SEC   单次确定性环境构建超时（默认 3600 秒）
  --skip-verify       跳过第 4 阶段候选问题验证
  --verify-max N      最多验证多少条候选问题（默认 10）
  --verify-severity L 验证的严重度（默认 critical,high）
  --verify-parallel N 保留兼容：验证智能体当前串行执行
  --verify-agent-timeout SEC  每条候选问题的验证智能体超时（默认 900 秒）
  --env-model MODEL           环境构建模型（默认同审计）
  --visual-model MODEL        场景设计模型（默认同蓝队）
  --judge-model MODEL         独立审核模型（默认同蓝队）
  --verify-model MODEL        验证智能体模型（默认同 --model）
  --skip-visual       跳过图文报告和攻击场景图生成
  --visual-max N      最多生成多少张攻击场景图（默认 5）
  --visual-timeout SEC      单张图片超时（默认 300 秒）
  --visual-agent-timeout SEC 智能体辅助场景生成超时（默认 900 秒）
  --skip-redteam      跳过第 5 阶段红队验证和独立审核
  --redteam-max N     最多进入红队验证的候选问题数（默认 5）
  --redteam-model M   红队攻击模型（默认 flint）
  --redteam-base-url URL    红队模型服务
  --redteam-api-key KEY     红队模型密钥
  --redteam-build-timeout SEC  隔离验证环境构建超时（默认 1260 秒）
  --redteam-agent-timeout SEC  红队智能体超时（默认 900 秒）
  --redteam-judge-timeout SEC  独立审核超时（默认 360 秒）
  --skip-mining-repair 跳过第 6 阶段经验、候选重跑、评估和发布
  --mine-only         只进行批量审计，跳过环境、验证、红队和学习阶段
  --verify-only DIR
                  对已有基线产物执行第 4 阶段验证和第 6 阶段学习，不重新执行基线审计
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
ENV_AGENT="${ENV_AGENT:-auto}"
ENV_AGENT_TIMEOUT="${ENV_AGENT_TIMEOUT:-1800}"
ENV_AGENT_ROUNDS="${ENV_AGENT_ROUNDS:-1}"
ENV_BUILD_TIMEOUT="${ENV_BUILD_TIMEOUT:-3600}"
SKIP_VERIFY=0
VERIFY_MAX=10
VERIFY_SEVERITY="critical,high"
VERIFY_PARALLEL=2
VERIFY_AGENT_TIMEOUT="${VERIFY_AGENT_TIMEOUT:-900}"
VERIFY_MODEL="${VERIFY_MODEL:-}"
SKIP_VISUAL=0
VISUAL_MAX="${VISUAL_MAX:-5}"
VISUAL_TIMEOUT="${VISUAL_TIMEOUT:-300}"
VISUAL_AGENT_TIMEOUT="${VISUAL_AGENT_TIMEOUT:-900}"
SKIP_REDTEAM=0
REDTEAM_MAX="${REDTEAM_MAX:-5}"
REDTEAM_MODEL="${REDTEAM_MODEL:-flint}"
REDTEAM_BASE_URL="${REDTEAM_BASE_URL:-http://100.81.81.75:8081/v1}"
REDTEAM_API_KEY="${REDTEAM_API_KEY:-local}"
REDTEAM_BUILD_TIMEOUT="${REDTEAM_BUILD_TIMEOUT:-1260}"
REDTEAM_AGENT_TIMEOUT="${REDTEAM_AGENT_TIMEOUT:-900}"
REDTEAM_JUDGE_TIMEOUT="${REDTEAM_JUDGE_TIMEOUT:-360}"
SKIP_MINING_REPAIR=0
ENV_MODEL="${ENV_MODEL:-}"
VISUAL_MODEL="${VISUAL_MODEL:-}"
JUDGE_MODEL="${JUDGE_MODEL:-}"

while [ "$#" -gt 0 ]; do
    case "$1" in
        --supervise) MODE="supervise" ;;
        --status) MODE="status"; [ "$#" -ge 2 ] || die "--status 需要产物目录" 3; RUN_DIR="$2"; shift ;;
        --stop)   MODE="stop";   [ "$#" -ge 2 ] || die "--stop 需要产物目录" 3;   RUN_DIR="$2"; shift ;;
        --timeout) [ "$#" -ge 2 ] || die "--timeout 需要参数" 3; TIMEOUT="$2"; shift ;;
        --target)  [ "$#" -ge 2 ] || die "--target 需要参数" 3;  TARGET="$2"; shift ;;
        --env-model) [ "$#" -ge 2 ] || die "--env-model 需要参数" 3; ENV_MODEL="$2"; shift ;;
        --visual-model) [ "$#" -ge 2 ] || die "--visual-model 需要参数" 3; VISUAL_MODEL="$2"; shift ;;
        --judge-model) [ "$#" -ge 2 ] || die "--judge-model 需要参数" 3; JUDGE_MODEL="$2"; shift ;;
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
        --env-agent) [ "$#" -ge 2 ] || die "--env-agent 需要参数" 3; ENV_AGENT="$2"; shift ;;
        --env-agent-timeout) [ "$#" -ge 2 ] || die "--env-agent-timeout 需要参数" 3; ENV_AGENT_TIMEOUT="$2"; shift ;;
        --env-agent-rounds) [ "$#" -ge 2 ] || die "--env-agent-rounds 需要参数" 3; ENV_AGENT_ROUNDS="$2"; shift ;;
        --env-timeout) [ "$#" -ge 2 ] || die "--env-timeout 需要参数" 3; ENV_BUILD_TIMEOUT="$2"; shift ;;
        --skip-verify) SKIP_VERIFY=1 ;;
        --verify-max) [ "$#" -ge 2 ] || die "--verify-max 需要参数" 3; VERIFY_MAX="$2"; shift ;;
        --verify-severity) [ "$#" -ge 2 ] || die "--verify-severity 需要参数" 3; VERIFY_SEVERITY="$2"; shift ;;
        --verify-parallel) [ "$#" -ge 2 ] || die "--verify-parallel 需要参数" 3; VERIFY_PARALLEL="$2"; shift ;;
        --verify-agent-timeout) [ "$#" -ge 2 ] || die "--verify-agent-timeout 需要参数" 3; VERIFY_AGENT_TIMEOUT="$2"; shift ;;
        --verify-model) [ "$#" -ge 2 ] || die "--verify-model 需要参数" 3; VERIFY_MODEL="$2"; shift ;;
        --skip-visual) SKIP_VISUAL=1 ;;
        --visual-max) [ "$#" -ge 2 ] || die "--visual-max 需要参数" 3; VISUAL_MAX="$2"; shift ;;
        --visual-timeout) [ "$#" -ge 2 ] || die "--visual-timeout 需要参数" 3; VISUAL_TIMEOUT="$2"; shift ;;
        --visual-agent-timeout) [ "$#" -ge 2 ] || die "--visual-agent-timeout 需要参数" 3; VISUAL_AGENT_TIMEOUT="$2"; shift ;;
        --skip-redteam) SKIP_REDTEAM=1 ;;
        --redteam-max) [ "$#" -ge 2 ] || die "--redteam-max 需要参数" 3; REDTEAM_MAX="$2"; shift ;;
        --redteam-model) [ "$#" -ge 2 ] || die "--redteam-model 需要参数" 3; REDTEAM_MODEL="$2"; shift ;;
        --redteam-base-url) [ "$#" -ge 2 ] || die "--redteam-base-url 需要参数" 3; REDTEAM_BASE_URL="$2"; shift ;;
        --redteam-api-key) [ "$#" -ge 2 ] || die "--redteam-api-key 需要参数" 3; REDTEAM_API_KEY="$2"; shift ;;
        --redteam-build-timeout) [ "$#" -ge 2 ] || die "--redteam-build-timeout 需要参数" 3; REDTEAM_BUILD_TIMEOUT="$2"; shift ;;
        --redteam-agent-timeout) [ "$#" -ge 2 ] || die "--redteam-agent-timeout 需要参数" 3; REDTEAM_AGENT_TIMEOUT="$2"; shift ;;
        --redteam-judge-timeout) [ "$#" -ge 2 ] || die "--redteam-judge-timeout 需要参数" 3; REDTEAM_JUDGE_TIMEOUT="$2"; shift ;;
        --skip-mining-repair) SKIP_MINING_REPAIR=1 ;;
        --mine-only) SKIP_ENV=1; SKIP_VERIFY=1; SKIP_VISUAL=1; SKIP_REDTEAM=1; SKIP_MINING_REPAIR=1 ;;
        --verify-only) MODE="verify"; [ "$#" -ge 2 ] || die "--verify-only 需要产物目录" 3; RUN_DIR="$2"; shift ;;
        -h|--help) usage; exit 0 ;;
        --) shift; [ "$#" -ge 1 ] || die "缺少源码路径" 3; TARGET="$1"; shift; break ;;
        -*) usage >&2; die "未知参数: $1" 3 ;;
        *) [ -z "$TARGET" ] || die "只能指定一个源码路径" 3; TARGET="$1" ;;
    esac
    shift
done

VERIFY_MODEL="${VERIFY_MODEL:-$MODEL}"
ENV_MODEL="${ENV_MODEL:-$MODEL}"
VISUAL_MODEL="${VISUAL_MODEL:-$VERIFY_MODEL}"
JUDGE_MODEL="${JUDGE_MODEL:-$VERIFY_MODEL}"
for _model_var in VISUAL_MODEL JUDGE_MODEL; do
    _value="${!_model_var}"
    case "$_value" in 360-proxy/*) _value="${_value#360-proxy/}" ;; opencode/*) _value="${_value#opencode/}" ;; esac
    printf -v "$_model_var" '%s' "$_value"
done

case "$ENV_AGENT" in auto|on|off) ;; *) die "--env-agent 必须是 auto|on|off: $ENV_AGENT" 3 ;; esac
[[ "$ENV_AGENT_TIMEOUT" =~ ^[1-9][0-9]*$ ]] || die "--env-agent-timeout 必须是正整数: $ENV_AGENT_TIMEOUT" 3
[[ "$ENV_AGENT_ROUNDS" =~ ^[1-9][0-9]*$ ]] || die "--env-agent-rounds 必须是正整数: $ENV_AGENT_ROUNDS" 3
[[ "$ENV_BUILD_TIMEOUT" =~ ^[1-9][0-9]*$ ]] || die "--env-timeout 必须是正整数: $ENV_BUILD_TIMEOUT" 3
for _num in "$VISUAL_MAX" "$VISUAL_TIMEOUT" "$VISUAL_AGENT_TIMEOUT" "$VERIFY_AGENT_TIMEOUT" \
    "$REDTEAM_MAX" "$REDTEAM_BUILD_TIMEOUT" "$REDTEAM_AGENT_TIMEOUT" "$REDTEAM_JUDGE_TIMEOUT"; do
    [[ "$_num" =~ ^[1-9][0-9]*$ ]] || die "数值参数必须是正整数: $_num" 3
done
SCENE_MAX="$VISUAL_MAX"
[ "$REDTEAM_MAX" -gt "$SCENE_MAX" ] && SCENE_MAX="$REDTEAM_MAX"

if [ ! -f "$REPO_ROOT/.claude/agents/${AGENT}.md" ] && [ "$AGENT" != "security-orchestrator" ]; then
    [ "${AGENT}" != "1" ] && log "WARN: 未找到智能体 '${AGENT}'，回退到 security-orchestrator"
    AGENT="security-orchestrator"
fi

if [ "$MODE" = "verify" ]; then
    RUN_DIR="$(realpath -e "$RUN_DIR" 2>/dev/null)" || die "产物目录不存在: $RUN_DIR" 4
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
    [ -n "$IMAGE" ] || die "缺少环境镜像（先执行 build_env，或传 --image）" 4
    [ -n "$SOURCE" ] || die "缺少源码路径（环境清单中没有 source，或传 --source）" 4
    log "仅执行第 4 阶段：项目=$PROJECT 产物目录=$RUN_DIR 镜像=$IMAGE"
    if [ "$SKIP_VISUAL" -eq 0 ]; then
        bash "$REPO_ROOT/scripts/mine/visual_report.sh" \
            --project "$PROJECT" --run-dir "$RUN_DIR" --max "$SCENE_MAX" \
            --timeout "$VISUAL_TIMEOUT" --agent-timeout "$VISUAL_AGENT_TIMEOUT" \
            --claude-bin "${CLAUDE_BIN:-claude}" --model "$VISUAL_MODEL"
    fi
    bash "$REPO_ROOT/scripts/verify/phase4_verify_agent.sh" \
        --project "$PROJECT" --run-dir "$RUN_DIR" --image "$IMAGE" --source "$SOURCE" \
        --max "$VERIFY_MAX" --severity "$VERIFY_SEVERITY" \
        --timeout 300 --agent-timeout "$VERIFY_AGENT_TIMEOUT" \
        --claude-bin "${CLAUDE_BIN:-claude}" --model "$VERIFY_MODEL" \
        --output "$RUN_DIR/verify/agent"
    VRC=$?
    if [ -f "$REPO_ROOT/scripts/workflow/build_state.py" ]; then
        python3 "$REPO_ROOT/scripts/workflow/build_state.py" || true
    fi
    if [ "$SKIP_MINING_REPAIR" -eq 0 ] && [ -f "$REPO_ROOT/scripts/rsi/post_validation.sh" ]; then
        log "第 6 阶段：构建红蓝经验并生成挖掘修复候选..."
        bash "$REPO_ROOT/scripts/rsi/post_validation.sh" \
            --project "$PROJECT" --run-dir "$RUN_DIR"
        LRC=$?
        [ "$VRC" -ne 0 ] || VRC="$LRC"
        if [ "$LRC" -eq 0 ] && [ "$VRC" -eq 0 ]; then
            PYTHONPATH="$REPO_ROOT${PYTHONPATH:+:$PYTHONPATH}" \
                python3 -m audit_rsi mining-repair-drive \
                --scope project --project "$PROJECT" --target "$SOURCE" \
                --baseline-run "$RUN_DIR" --image "$IMAGE" --miner-image "mygoldmine:dev" \
                --output "$RUN_DIR/rsi/driver.json"
            VRC=$?
        fi
    fi
    exit "$VRC"
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
        if [ -f "$META/sandbox.json" ]; then
            sandbox_name="$(jq -r '.container // empty' "$META/sandbox.json")"
            sandbox_state="$(docker container inspect "$sandbox_name" --format '{{.State.Status}}' 2>/dev/null || echo absent)"
            echo "sandbox=$sandbox_name state=$sandbox_state workspace=/workspace/repo"
            echo "shell: bash scripts/env/sandbox.sh shell --project $PROJECT_FROM_RUN --run-dir $RUN_DIR"
        fi
        ENV_MAN="$REPO_ROOT/env/$PROJECT_FROM_RUN/env-manifest.json"
        if [ -f "$ENV_MAN" ]; then
            echo "env_status=$(jq -r '.env_status // "unknown"' "$ENV_MAN" 2>/dev/null) env_image=$(jq -r '.image // "-"' "$ENV_MAN" 2>/dev/null)"
            if [ -f "$META/env-phase.json" ]; then
                echo "env_agent_status=$(jq -r '.agent.status // "unknown"' "$META/env-phase.json" 2>/dev/null) env_agent_reason=$(jq -r '.agent.reason // "unknown"' "$META/env-phase.json" 2>/dev/null) env_baseline=$(jq -r '.baseline.status // "unknown"' "$META/env-phase.json" 2>/dev/null)"
                echo "env_agent_missing=$(jq -r '(.agent.prerequisites.missing // []) | join(",")' "$META/env-phase.json" 2>/dev/null)"
            fi
        else
            echo "env_status=not-built"
        fi
        if [ -f "$RUN_DIR/verify/agent/summary.json" ]; then
            echo "verify_counts=$(jq -c '.counts // {}' "$RUN_DIR/verify/agent/summary.json" 2>/dev/null)"
            echo "verify_summary=$RUN_DIR/verify/agent/summary.md"
        else
            echo "verify_counts=- (not-run)"
        fi
        if [ -f "$META/status.json" ]; then
            echo "visual_status=$(jq -r '.visual_status // "-"' "$META/status.json" 2>/dev/null) visual_summary=$(jq -r '.visual_summary // "-"' "$META/status.json" 2>/dev/null)"
            echo "verify_agent_status=$(jq -r '.verify_agent_status // "-"' "$META/status.json" 2>/dev/null)"
            echo "redteam_status=$(jq -r '.redteam_status // "-"' "$META/status.json" 2>/dev/null) redteam_summary=$(jq -r '.redteam_summary // "-"' "$META/status.json" 2>/dev/null)"
            echo "review_ready=$(jq -r '.review_ready // 0' "$META/status.json" 2>/dev/null)"
        fi
        echo "tail -f $RUN_DIR/claude.rendered.log"
        echo "tail -f $META/wrapper.log"
        echo "tail -f $META/verify.log"
        echo "env build: $META/env-build.log"
        echo "env agent: $META/env-build-agent-*.log  summary=$META/env-phase.json"
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
    if [ -f "$META/status.json" ]; then
        tmp="$META/status.json.tmp.$$"
        jq --arg updated_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
           '.state = "stopped" | .updated_at = $updated_at' \
           "$META/status.json" > "$tmp" 2>/dev/null && mv "$tmp" "$META/status.json" || rm -f "$tmp"
    fi
    echo "[run] stopped $RUN_DIR"
    exit 0
fi

if [ "$MODE" = "supervise" ]; then
    [ -n "$TARGET" ] || die "监督模式缺少 --target" 3
    [ -n "$RUN_DIR" ] || die "监督模式缺少 --run-dir" 3
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
    ENV_AGENT_STATUS="unknown"
    ENV_AGENT_REASON="unknown"
    VERIFY_SUMMARY=""
    VERIFY_COUNTS="{}"
    VERIFY_AGENT_STATUS="pending"
    VISUAL_STATUS="pending"
    VISUAL_SUMMARY=""
    REDTEAM_STATUS="pending"
    REDTEAM_SUMMARY=""
    REVIEW_READY=0
    PIPELINE_DEGRADED=0

    write_status() {
        local state="$1" rc="$2"
        local target_commit target_branch
        target_commit="$(git -C "$TARGET" rev-parse HEAD 2>/dev/null || true)"
        target_branch="${TARGET_BRANCH:-$(git -C "$TARGET" rev-parse --abbrev-ref HEAD 2>/dev/null || true)}"
        [ -n "$target_branch" ] || target_branch="detached"
        jq -n \
            --arg state "$state" \
            --arg project "$PROJECT" \
            --arg target "$TARGET" \
            --arg commit "$target_commit" \
            --arg branch "$target_branch" \
            --arg run_dir "$RUN_DIR" \
            --arg model "$MODEL" \
            --arg env_model "$ENV_MODEL" --arg visual_model "$VISUAL_MODEL" \
            --arg verify_model "$VERIFY_MODEL" --arg redteam_model "$REDTEAM_MODEL" --arg judge_model "$JUDGE_MODEL" \
            --arg agent "$AGENT" \
            --arg image "$IMAGE" \
            --arg env_image "$ENV_IMAGE" \
            --arg env_status "$ENV_STATUS" \
            --arg env_agent_status "$ENV_AGENT_STATUS" \
            --arg env_agent_reason "$ENV_AGENT_REASON" \
            --arg verify_summary "$VERIFY_SUMMARY" \
            --arg verify_agent_status "$VERIFY_AGENT_STATUS" \
            --arg visual_status "$VISUAL_STATUS" \
            --arg visual_summary "$VISUAL_SUMMARY" \
            --arg redteam_status "$REDTEAM_STATUS" \
            --arg redteam_summary "$REDTEAM_SUMMARY" \
            --argjson review_ready "$REVIEW_READY" \
            --arg started_at "$STARTED_AT" \
            --arg updated_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
            --arg container "$(cat "$META/container.name" 2>/dev/null || true)" \
            --argjson verify_counts "$VERIFY_COUNTS" \
            --argjson timeout "$TIMEOUT" \
            --argjson exit_code "$rc" \
            '{state:$state, project:$project, target:$target, commit:$commit, branch:$branch,
              run_dir:$run_dir, model:$model,
              stage_models:{audit:$model,environment:$env_model,visual:$visual_model,verify:$verify_model,redteam:$redteam_model,judge:$judge_model},
              agent:$agent, image:$image, env_image:$env_image,
              env_status:$env_status, env_agent_status:$env_agent_status,
              env_agent_reason:$env_agent_reason, verify_summary:$verify_summary,
              verify_agent_status:$verify_agent_status, verify_counts:$verify_counts,
              visual_status:$visual_status, visual_summary:$visual_summary,
              redteam_status:$redteam_status, redteam_summary:$redteam_summary,
              review_ready:$review_ready, timeout_seconds:$timeout,
              started_at:$started_at, updated_at:$updated_at, container:$container,
              exit_code:$exit_code}' > "$META/status.json"
    }

    set_stage() {
        PIPELINE_STAGE_FILE="$META/pipeline-stage.json" python3 "$REPO_ROOT/scripts/workflow/pipeline_stage.py" "$1"
    }
    set_stage environment
    write_status "starting" -1

    if [ "$SKIP_ENV" -eq 0 ]; then
        log "第 0 阶段：智能体主导环境构建（安装模式=$ENV_MODE 智能体模式=$ENV_AGENT 轮数=$ENV_AGENT_ROUNDS）..."
        bash "$REPO_ROOT/scripts/env/phase0_env.sh" "$TARGET" \
            --project "$PROJECT" --mode "$ENV_MODE" --meta-dir "$META" \
            --agent "$ENV_AGENT" --agent-timeout "$ENV_AGENT_TIMEOUT" \
            --agent-rounds "$ENV_AGENT_ROUNDS" --build-timeout "$ENV_BUILD_TIMEOUT" \
            --base-image "$IMAGE" \
            --model "$ENV_MODEL" --claude-bin "${CLAUDE_BIN:-claude}" \
            > "$META/env-phase0.log" 2>&1
        ENV_RC=$?
        ENV_MANIFEST="$REPO_ROOT/env/$PROJECT/env-manifest.json"
        if [ -f "$ENV_MANIFEST" ]; then
            ENV_IMAGE="$(jq -r '.image // empty' "$ENV_MANIFEST" 2>/dev/null || true)"
            ENV_STATUS="$(jq -r '.env_status // "unknown"' "$ENV_MANIFEST" 2>/dev/null || true)"
        fi
        if [ -f "$META/env-phase.json" ]; then
            ENV_AGENT_STATUS="$(jq -r '.agent.status // "unknown"' "$META/env-phase.json" 2>/dev/null || true)"
            ENV_AGENT_REASON="$(jq -r '.agent.reason // "unknown"' "$META/env-phase.json" 2>/dev/null || true)"
            ENV_BASELINE_STATUS="$(jq -r '.baseline.status // "unknown"' "$META/env-phase.json" 2>/dev/null || true)"
        fi
        log "第 0 阶段完成：退出码=$ENV_RC 基线状态=${ENV_BASELINE_STATUS:-unknown} 智能体状态=${ENV_AGENT_STATUS:-unknown} 原因=${ENV_AGENT_REASON:-unknown} 环境状态=$ENV_STATUS 镜像=${ENV_IMAGE:-none}"
    else
        ENV_AGENT_STATUS="skipped_env"
        ENV_AGENT_REASON="skip_env"
        log "第 0 阶段跳过（--skip-env）"
    fi
    SANDBOX_CONTAINER=""
    if [ "$SKIP_ENV" -eq 0 ] && [ "${PERSIST_SANDBOX:-1}" = "1" ] && [ -n "$ENV_IMAGE" ]; then
        SANDBOX_CONTAINER="$(bash "$REPO_ROOT/scripts/env/sandbox.sh" start \
            --project "$PROJECT" --run-dir "$RUN_DIR" --source "$TARGET" \
            --image "$ENV_IMAGE" --network "${DOCKER_NETWORK:-bridge}" 2>> "$META/sandbox.log")"
        if [ -n "$SANDBOX_CONTAINER" ]; then
            log "持久沙箱已就绪: $SANDBOX_CONTAINER"
        else
            log "WARN: 持久沙箱创建失败，回退到一次性批量审计容器"
        fi
    fi
    set_stage orchestrator
    write_status "running" -1
    log "监督进程启动：项目=$PROJECT 产物目录=$RUN_DIR"

    SANDBOX_CONTAINER="$SANDBOX_CONTAINER" MYGOLDMINE_IMAGE="$IMAGE" LIVE_RENDER=1 "$MINER" \
        --target "$TARGET" \
        --project "$PROJECT" \
        --run-dir "$RUN_DIR" \
        --timeout "$TIMEOUT" \
        --model "$MODEL" \
        --agent "$AGENT" \
        > "$META/wrapper.log" 2>&1 &
    WPID=$!
    echo "$WPID" > "$META/wrapper.pid"
    if [ -n "$SANDBOX_CONTAINER" ]; then
        echo "$SANDBOX_CONTAINER" > "$META/container.name"
    else
        echo "mygoldmine-${PROJECT}-${WPID}" > "$META/container.name"
    fi

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

    if [ -n "$SANDBOX_CONTAINER" ]; then
        bash "$REPO_ROOT/scripts/env/sandbox.sh" isolate \
            --project "$PROJECT" --run-dir "$RUN_DIR" >> "$META/sandbox.log" 2>&1 || true
    fi

    # Structured infra runs can recover independently after a native Agent/CLI failure.
    # Each finished boundary is persisted by mine_one.sh; only missing tasks are retried.
    if [ "$RC" -ne 0 ] && [ "${AUTO_RECOVER:-1}" = "1" ] && \
        python3 - "$REPO_ROOT" "$RUN_DIR" <<'PYRECOVERY'
import sys
from pathlib import Path
sys.path.insert(0, str(Path(sys.argv[1]) / "scripts/mine"))
from durable_recovery import plan_from_trace
try:
    plan_from_trace(Path(sys.argv[2]))
except (OSError, ValueError):
    raise SystemExit(1)
PYRECOVERY
    then
        if [ "$RC" -eq 124 ] || [ "$RC" -eq 125 ] || [ "$RC" -eq 137 ]; then
            write_status "timeout" "$RC"
        else
            write_status "failed" "$RC"
        fi
        RECOVERY_RUN="${RUN_DIR}-recovery"
        log "发现可恢复的 infra 任务，保留原始运行并转入 $RECOVERY_RUN"
        python3 "$REPO_ROOT/scripts/mine/durable_recovery.py" \
            --target "$TARGET" --recover-from "$RUN_DIR" --run-dir "$RECOVERY_RUN" \
            --model "$MODEL" --idle-timeout "${AUDIT_IDLE_TIMEOUT:-180}" \
            --task-timeout "${RECOVERY_TASK_TIMEOUT:-600}" \
            --budget "${RECOVERY_BUDGET:-1800}" --max-attempts "${RECOVERY_MAX_ATTEMPTS:-2}"
        RC=$?
        RUN_DIR="$RECOVERY_RUN"
        META="$RUN_DIR.meta"
        SANDBOX_CONTAINER=""
        mkdir -p "$META"
        echo "$RC" > "$META/exit_code"
    fi

    REPORTS_COMPLETE=0
    if [ -s "$RUN_DIR/audit-report.md" ] && [ -s "$RUN_DIR/audit-report.json" ]; then
        if python3 "$REPO_ROOT/scripts/mine/check_report.py" \
            --report "$RUN_DIR/audit-report.json" --output "$RUN_DIR/report-quality.json" \
            --fail-missing --fail-language >> "$META/report-quality.log" 2>&1; then
            REPORTS_COMPLETE=1
        else
            log "报告质量合同未通过，不自动执行第 4 阶段"
        fi
    fi

    if [ "$REPORTS_COMPLETE" -eq 1 ] && [ "$SKIP_VISUAL" -eq 0 ]; then
        log "图文报告：生成报告与攻击场景图（最多 $SCENE_MAX 张）..."
        set_stage visual
        bash "$REPO_ROOT/scripts/mine/visual_report.sh" \
            --project "$PROJECT" --run-dir "$RUN_DIR" --max "$SCENE_MAX" \
            --timeout "$VISUAL_TIMEOUT" --agent-timeout "$VISUAL_AGENT_TIMEOUT" \
            --claude-bin "${CLAUDE_BIN:-claude}" --model "$VISUAL_MODEL" \
            > "$META/visual-report.log" 2>&1
        VSRC=$?
        VISUAL_SUMMARY="$RUN_DIR/visual-rendered/visual-summary.md"
        if [ -f "$RUN_DIR/visual-rendered/visual-summary.json" ]; then
            VISUAL_STATUS="$(jq -r '.status // "unknown"' "$RUN_DIR/visual-rendered/visual-summary.json" 2>/dev/null || echo unknown)"
        else
            VISUAL_STATUS="failed"
        fi
        [ "$VSRC" -eq 0 ] || PIPELINE_DEGRADED=1
        [ "$VISUAL_STATUS" = "blocked" ] && PIPELINE_DEGRADED=1
        log "图文报告完成：退出码=$VSRC 状态=$VISUAL_STATUS"
    else
        log "图文报告跳过（已禁用或没有有效报告）"
    fi

    if [ "$SKIP_VERIFY" -eq 0 ] && [ -n "$ENV_IMAGE" ] && [ "$REPORTS_COMPLETE" -eq 1 ] && [ "$ENV_STATUS" != "blocked" ]; then
        if docker image inspect "$ENV_IMAGE" >/dev/null 2>&1; then
            log "第 4 阶段：验证候选问题（最多 $VERIFY_MAX 条，严重度 $VERIFY_SEVERITY）..."
            set_stage verify
            bash "$REPO_ROOT/scripts/verify/phase4_verify_agent.sh" \
                --project "$PROJECT" --run-dir "$RUN_DIR" \
                --image "$ENV_IMAGE" --source "$TARGET" \
                --max "$VERIFY_MAX" --severity "$VERIFY_SEVERITY" \
                --timeout 300 --agent-timeout "$VERIFY_AGENT_TIMEOUT" \
                --claude-bin "${CLAUDE_BIN:-claude}" --model "$VERIFY_MODEL" \
                --output "$RUN_DIR/verify/agent" \
                > "$META/verify.log" 2>&1
            VRC=$?
            if [ -f "$RUN_DIR/verify/agent/summary.json" ]; then
                VERIFY_SUMMARY="$RUN_DIR/verify/agent/summary.md"
                VERIFY_COUNTS="$(jq -c '.counts // {}' "$RUN_DIR/verify/agent/summary.json" 2>/dev/null || echo '{}')"
                VERIFY_AGENT_STATUS="completed"
            else
                VERIFY_AGENT_STATUS="failed"
                PIPELINE_DEGRADED=1
            fi
            [ "$VRC" -eq 0 ] || { VERIFY_AGENT_STATUS="failed"; PIPELINE_DEGRADED=1; }
            log "第 4 阶段完成：退出码=$VRC 状态=$VERIFY_AGENT_STATUS 结论统计=$VERIFY_COUNTS"
        else
            log "第 4 阶段跳过：环境镜像不存在 $ENV_IMAGE"
            ENV_STATUS="blocked"
            VERIFY_AGENT_STATUS="blocked"
            PIPELINE_DEGRADED=1
        fi
    else
        if [ "$ENV_STATUS" = "blocked" ]; then
            VERIFY_AGENT_STATUS="blocked"
            PIPELINE_DEGRADED=1
            log "第 4 阶段跳过：环境构建受阻"
        else
            VERIFY_AGENT_STATUS="skipped"
            log "第 4 阶段跳过（已禁用、没有有效报告或没有环境）"
        fi
    fi

    if [ "$SKIP_REDTEAM" -eq 0 ] && [ -n "$ENV_IMAGE" ] && [ "$REPORTS_COMPLETE" -eq 1 ] && [ "$ENV_STATUS" != "blocked" ]; then
        log "第 5 阶段：红队批量验证与独立审核（最多 $REDTEAM_MAX 条，模型 $REDTEAM_MODEL）..."
        set_stage redteam-lab
        PIPELINE_STAGE_FILE="$META/pipeline-stage.json" bash "$REPO_ROOT/scripts/redteam/phase5_redteam.sh" \
            --project "$PROJECT" --run-dir "$RUN_DIR" \
            --max "$REDTEAM_MAX" --severity "$VERIFY_SEVERITY" \
            --model "$REDTEAM_MODEL" --base-url "$REDTEAM_BASE_URL" --api-key "$REDTEAM_API_KEY" \
            --build-timeout "$REDTEAM_BUILD_TIMEOUT" --agent-timeout "$REDTEAM_AGENT_TIMEOUT" \
            --judge-timeout "$REDTEAM_JUDGE_TIMEOUT" \
            --judge-claude "${CLAUDE_BIN:-claude}" --judge-claude-model "$JUDGE_MODEL" \
            --output "$RUN_DIR/redteam" \
            > "$META/redteam.log" 2>&1
        RRC=$?
        REDTEAM_SUMMARY="$RUN_DIR/redteam/summary.md"
        if [ -f "$RUN_DIR/redteam/summary.json" ]; then
            REDTEAM_STATUS="$(jq -r '.status // "unknown"' "$RUN_DIR/redteam/summary.json" 2>/dev/null || echo unknown)"
        else
            REDTEAM_STATUS="failed"
        fi
        [ "$RRC" -eq 0 ] || PIPELINE_DEGRADED=1
        case "$REDTEAM_STATUS" in completed|no_findings) ;; *) PIPELINE_DEGRADED=1 ;; esac
        log "第 5 阶段完成：退出码=$RRC 状态=$REDTEAM_STATUS"
    else
        if [ "$ENV_STATUS" = "blocked" ]; then
            REDTEAM_STATUS="blocked"
            PIPELINE_DEGRADED=1
            log "第 5 阶段跳过：环境构建受阻"
        else
            REDTEAM_STATUS="skipped"
            log "第 5 阶段跳过（已禁用、没有有效报告或没有环境）"
        fi
    fi

    if [ -f "$REPO_ROOT/scripts/workflow/build_state.py" ] && [ "$REPORTS_COMPLETE" -eq 1 ]; then
        python3 "$REPO_ROOT/scripts/workflow/build_state.py" >> "$META/workflow.log" 2>&1 || true
        if [ -f "$REPO_ROOT/ui/data/auto-state.json" ]; then
            REVIEW_READY="$(jq -r --arg p "$PROJECT" '[(.review // {}) | to_entries[] | .value | select((.project // "") == $p)] | length' "$REPO_ROOT/ui/data/auto-state.json" 2>/dev/null || echo 0)"
        fi
    fi

    if [ "$SKIP_MINING_REPAIR" -eq 0 ] && [ "$REPORTS_COMPLETE" -eq 1 ] && [ -f "$REPO_ROOT/scripts/rsi/post_validation.sh" ]; then
        log "第 6 阶段：构建红蓝经验并生成挖掘修复候选..."
        set_stage learner
        bash "$REPO_ROOT/scripts/rsi/post_validation.sh" \
            --project "$PROJECT" --run-dir "$RUN_DIR" > "$META/mining-repair.log" 2>&1
        LRC=$?
        if [ "$LRC" -ne 0 ]; then
            PIPELINE_DEGRADED=1
            log "第 6 阶段失败：退出码=$LRC，详见 $META/mining-repair.log"
        else
            log "第 6 阶段候选已生成，开始隔离重跑与仓库专属修复评估..."
            if [ "$SKIP_VERIFY" -eq 0 ] && [ "$SKIP_REDTEAM" -eq 0 ] && [ -n "$ENV_IMAGE" ] && [ "$ENV_STATUS" != "blocked" ]; then
                PYTHONPATH="$REPO_ROOT${PYTHONPATH:+:$PYTHONPATH}" \
                    python3 -m audit_rsi mining-repair-drive \
                    --scope project --project "$PROJECT" --target "$TARGET" \
                    --baseline-run "$RUN_DIR" --image "$ENV_IMAGE" --miner-image "$IMAGE" \
                    --output "$RUN_DIR/rsi/driver.json" >> "$META/mining-repair.log" 2>&1
                DRC=$?
                if [ "$DRC" -ne 0 ]; then
                    PIPELINE_DEGRADED=1
                    log "仓库专属修复的候选重跑失败：退出码=$DRC"
                else
                    log "仓库专属修复评估完成：结果见 $RUN_DIR/rsi/driver.json"
                fi
            else
                log "候选重跑跳过：红蓝验证或环境不可用，候选保持未发布"
            fi
            log "第 6 阶段完成：候选、评估与已加载规则见 $RUN_DIR/rsi/"
        fi
    fi

    if [ "$RC" -eq 124 ] || [ "$RC" -eq 125 ] || [ "$RC" -eq 137 ]; then
        write_status "timeout" "$RC"
    elif [ "$REPORTS_COMPLETE" -eq 1 ]; then
        if [ "$RC" -eq 0 ] && [ "$PIPELINE_DEGRADED" -eq 0 ]; then
            write_status "success" "$RC"
        else
            write_status "partial" "$RC"
        fi
    else
        [ "$RC" -eq 0 ] && RC=2
        write_status "failed" "$RC"
    fi
    log "监督进程结束：退出码=$RC 产物目录=$RUN_DIR"
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
    --env-model "$ENV_MODEL" --visual-model "$VISUAL_MODEL" --judge-model "$JUDGE_MODEL"
    --env-mode "$ENV_MODE" --env-agent "$ENV_AGENT"
    --env-agent-timeout "$ENV_AGENT_TIMEOUT" --env-agent-rounds "$ENV_AGENT_ROUNDS"
    --env-timeout "$ENV_BUILD_TIMEOUT" --verify-max "$VERIFY_MAX"
    --verify-severity "$VERIFY_SEVERITY" --verify-parallel "$VERIFY_PARALLEL"
    --verify-agent-timeout "$VERIFY_AGENT_TIMEOUT" --verify-model "$VERIFY_MODEL"
    --visual-max "$VISUAL_MAX" --visual-timeout "$VISUAL_TIMEOUT"
    --visual-agent-timeout "$VISUAL_AGENT_TIMEOUT"
    --redteam-max "$REDTEAM_MAX" --redteam-model "$REDTEAM_MODEL"
    --redteam-base-url "$REDTEAM_BASE_URL" --redteam-api-key "$REDTEAM_API_KEY"
    --redteam-build-timeout "$REDTEAM_BUILD_TIMEOUT" --redteam-agent-timeout "$REDTEAM_AGENT_TIMEOUT"
    --redteam-judge-timeout "$REDTEAM_JUDGE_TIMEOUT"
)
[ "$SKIP_ENV" -eq 1 ] && sup_args+=(--skip-env)
[ "$SKIP_VERIFY" -eq 1 ] && sup_args+=(--skip-verify)
[ "$SKIP_VISUAL" -eq 1 ] && sup_args+=(--skip-visual)
[ "$SKIP_REDTEAM" -eq 1 ] && sup_args+=(--skip-redteam)

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
    echo "[run] 前台显示：tail -f $RUN_DIR/claude.rendered.log（Ctrl-C 只退出日志显示）"
    tail -n +1 -F "$RUN_DIR/claude.rendered.log" 2>/dev/null
    exit 0
fi

cat <<EOF
[run] 已启动
  目标：      $TARGET
  项目：      $PROJECT
  模型：      $MODEL
  超时：      ${TIMEOUT} 秒
  产物目录：  $RUN_DIR
  元信息目录：$META
  容器：      $(cat "$META/container.name" 2>/dev/null || echo 等待中)
  监督进程：  $SPID
  执行器：    $MINER
  流程：      第 0 阶段环境构建 -> 批量审计 -> 图文报告 -> 第 4 阶段验证 -> 第 5 阶段红队验证
  环境模式：  $ENV_MODE（跳过=$SKIP_ENV）  智能体模式：$ENV_AGENT（轮数=$ENV_AGENT_ROUNDS）
  图文报告：  最多 $SCENE_MAX 张场景图（跳过=$SKIP_VISUAL）
  候选验证：  严重度 $VERIFY_SEVERITY，最多 $VERIFY_MAX 条（跳过=$SKIP_VERIFY）
  红队验证：  最多 $REDTEAM_MAX 条，模型 $REDTEAM_MODEL（跳过=$SKIP_REDTEAM）
EOF

if ! kill -0 "$SPID" 2>/dev/null; then
    echo "[run] 监督进程已退出，查看 $META/supervisor.log 和 $META/wrapper.log" >&2
    tail -n 20 "$META/supervisor.log" 2>/dev/null >&2 || true
    exit 1
fi

cat <<EOF

第 0 阶段环境构建（智能体主导与确定性备用）:
  tail -f "$META/env-build-agent-1.log"
  tail -f "$META/env-build.log"
  cat "$META/env-phase.json"

第 1/2 阶段批量审计（实时渲染）:
  tail -f "$RUN_DIR/claude.rendered.log"
  tail -f "$RUN_DIR/raw.jsonl"
  tail -f "$META/wrapper.log"

第 4 阶段自动验证:
  tail -f "$META/verify.log"
  # 完成后看：
  cat "$RUN_DIR/verify/auto/summary.md"

持久沙箱（同一工作副本继续探索）:
  bash scripts/env/sandbox.sh status --project "$PROJECT" --run-dir "$RUN_DIR"
  bash scripts/env/sandbox.sh shell --project "$PROJECT" --run-dir "$RUN_DIR"
  # stop 保留工作副本；remove 才删除容器。PERSIST_SANDBOX=0 可禁用复用。

查看状态 / 停止:
  bash run.sh --status "$RUN_DIR"
  bash run.sh --stop "$RUN_DIR"
EOF
