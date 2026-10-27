#!/usr/bin/env bash
# mygoldmine 整夜挖掘入口（T13）
#
# 动作：
#   start    以默认配置在后台启动 5 并发、每项目 6h 的整夜挖掘
#   stop     停止编排器与所有 worker（保留日志与已完成状态）
#   status   汇总运行中 / 完成 / 失败 / 待运行项目
#   resume   只对未完成项目重新启动，已完成项目不再触碰
#
# 设计：
#   - 本脚本是 scripts/mine/parallel_mine.sh 的薄封装，默认值与 T12 对齐
#   - 状态统一写入 $STATE_DIR（默认 runs/.orchestrator），与 parallel_mine 共用
#   - start/resume 默认 --detach，可用 --foreground 前台运行；--dry-run 只打印计划
#   - 不读取、不写入任何密钥；凭据仅由子进程从环境变量继承
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PM="$SCRIPT_DIR/parallel_mine.sh"

log() { printf '[overnight] %s\n' "$*" >&2; }
die() { printf '[overnight] ERROR: %s\n' "$1" >&2; exit "${2:-1}"; }

usage() {
    cat <<'EOF'
用法: overnight.sh <start|stop|status|resume> [选项]

动作:
  start     后台启动整夜挖掘（默认 detach）
  stop      停止编排器与所有 worker
  status    查看运行中 / 完成 / 失败 / 待运行
  resume    只补未完成项目（已完成项目跳过）

默认值:
  MODEL=360-proxy/deepseek/deepseek-v4.1-flash
  MAX_PARALLEL=5
  TIMEOUT=21600 秒（6 小时/项目）
  RUNS_ROOT=<repo>/runs
  STATE_DIR=<runs-root>/.orchestrator
  EXECUTOR=<repo>/scripts/mine/mine_one_docker.sh

选项:
  --model MODEL          模型 ID（默认 $MODEL 或 360-proxy/deepseek/deepseek-v4.1-flash）
  --agent AGENT          审计智能体（默认 security-orchestrator）
  --max-parallel N       最大并发项目数（默认 5）
  --timeout SECONDS      单项目超时秒数（默认 21600）
  --retries N            失败重试次数（默认 1；超时不重试）
  --min-free-gb N        启动所需磁盘余量 GB（默认 20）
  --outer-grace SECONDS  编排层超时宽限（默认 60）
  --projects LIST        仅处理逗号分隔的项目（start 可用）
  --force                start 时忽略已完成记录，全部重跑
  --targets-dir DIR      目标根目录（默认 <repo>/targets）
  --manifest FILE        目标清单（默认 <targets-dir>/manifest.json）
  --runs-root DIR        产物根目录（默认 <repo>/runs）
  --state-dir DIR        状态目录（默认 <runs-root>/.orchestrator）
  --executor FILE        单项目执行器（默认 scripts/mine/mine_one.sh）
  --dry-run              start/resume 只打印计划，不创建目录、不调用模型
  --foreground           前台运行（默认后台 detach）
  -h, --help             显示本帮助

环境变量:
  MODEL AGENT MAX_PARALLEL TIMEOUT MAX_RETRIES MIN_FREE_GB OUTER_GRACE
  TARGETS_DIR MANIFEST RUNS_ROOT STATE_DIR EXECUTOR

示例:
  bash scripts/mine/overnight.sh start
  bash scripts/mine/overnight.sh status
  bash scripts/mine/overnight.sh resume
  bash scripts/mine/overnight.sh stop

退出码:
  0 成功；1 有项目失败；3 参数错误；7 已有实例在运行；
  8 磁盘余量不足；其他见 parallel_mine.sh
EOF
}

ACTION=""
DRY_RUN=0
FOREGROUND=0
FORCE=0
PROJECTS_FILTER=""
MODEL="${MODEL:-360-proxy/deepseek/deepseek-v4.1-flash}"
AGENT="${AGENT:-security-orchestrator}"
if [ ! -f "$REPO_ROOT/.claude/agents/${AGENT}.md" ] && [ "$AGENT" != "security-orchestrator" ]; then
    log "WARN: 未找到 agent '${AGENT}'（可能被外部环境变量污染），回退到 security-orchestrator"
    AGENT="security-orchestrator"
fi
MAX_PARALLEL="${MAX_PARALLEL:-5}"
PROJECT_TIMEOUT="${TIMEOUT:-21600}"
MAX_RETRIES="${MAX_RETRIES:-1}"
MIN_FREE_GB="${MIN_FREE_GB:-20}"
OUTER_GRACE="${OUTER_GRACE:-60}"
TARGETS_DIR="${TARGETS_DIR:-$REPO_ROOT/targets}"
MANIFEST="${MANIFEST:-}"
RUNS_ROOT="${RUNS_ROOT:-$REPO_ROOT/runs}"
STATE_DIR="${STATE_DIR:-}"
EXECUTOR="${EXECUTOR:-$SCRIPT_DIR/mine_one_docker.sh}"

while [ "$#" -gt 0 ]; do
    case "$1" in
        start|stop|status|resume)
            [ -z "$ACTION" ] || die "只能指定一个动作（已有: $ACTION，又遇到: $1）" 3
            ACTION="$1"
            ;;
        --model) [ "$#" -ge 2 ] || die "--model 需要参数" 3; MODEL="$2"; shift ;;
        --agent) [ "$#" -ge 2 ] || die "--agent 需要参数" 3; AGENT="$2"; shift ;;
        --max-parallel) [ "$#" -ge 2 ] || die "--max-parallel 需要参数" 3; MAX_PARALLEL="$2"; shift ;;
        --timeout) [ "$#" -ge 2 ] || die "--timeout 需要参数" 3; PROJECT_TIMEOUT="$2"; shift ;;
        --retries) [ "$#" -ge 2 ] || die "--retries 需要参数" 3; MAX_RETRIES="$2"; shift ;;
        --min-free-gb) [ "$#" -ge 2 ] || die "--min-free-gb 需要参数" 3; MIN_FREE_GB="$2"; shift ;;
        --outer-grace) [ "$#" -ge 2 ] || die "--outer-grace 需要参数" 3; OUTER_GRACE="$2"; shift ;;
        --projects) [ "$#" -ge 2 ] || die "--projects 需要参数" 3; PROJECTS_FILTER="$2"; shift ;;
        --targets-dir) [ "$#" -ge 2 ] || die "--targets-dir 需要参数" 3; TARGETS_DIR="$2"; shift ;;
        --manifest) [ "$#" -ge 2 ] || die "--manifest 需要参数" 3; MANIFEST="$2"; shift ;;
        --runs-root) [ "$#" -ge 2 ] || die "--runs-root 需要参数" 3; RUNS_ROOT="$2"; shift ;;
        --state-dir) [ "$#" -ge 2 ] || die "--state-dir 需要参数" 3; STATE_DIR="$2"; shift ;;
        --executor) [ "$#" -ge 2 ] || die "--executor 需要参数" 3; EXECUTOR="$2"; shift ;;
        --dry-run) DRY_RUN=1 ;;
        --foreground) FOREGROUND=1 ;;
        --force) FORCE=1 ;;
        -h|--help) usage; exit 0 ;;
        *) usage >&2; die "未知参数: $1" 3 ;;
    esac
    shift
done

[ -n "$ACTION" ] || { usage >&2; die "缺少动作: start|stop|status|resume" 3; }

[[ "$MAX_PARALLEL" =~ ^[1-9][0-9]*$ ]] || die "MAX_PARALLEL 必须是正整数，当前: $MAX_PARALLEL" 3
[[ "$PROJECT_TIMEOUT" =~ ^[1-9][0-9]*$ ]] || die "TIMEOUT 必须是正整数秒，当前: $PROJECT_TIMEOUT" 3
[[ "$MAX_RETRIES" =~ ^[0-9]+$ ]] || die "MAX_RETRIES 必须是非负整数，当前: $MAX_RETRIES" 3

abspath() {
    if [[ "$1" = /* ]]; then printf '%s\n' "$1"; else printf '%s/%s\n' "$PWD" "$1"; fi
}

TARGETS_DIR="$(abspath "$TARGETS_DIR")"
RUNS_ROOT="$(abspath "$RUNS_ROOT")"
[ -n "$MANIFEST" ] || MANIFEST="$TARGETS_DIR/manifest.json"
MANIFEST="$(abspath "$MANIFEST")"
[ -n "$STATE_DIR" ] || STATE_DIR="$RUNS_ROOT/.orchestrator"
STATE_DIR="$(abspath "$STATE_DIR")"
EXECUTOR="$(abspath "$EXECUTOR")"

INFO_FILE="$STATE_DIR/run-info.json"
PID_FILE="$STATE_DIR/orchestrator.pid"
PROJECTS_DIR="$STATE_DIR/projects"
STOP_FILE="$STATE_DIR/STOP"

[ -x "$PM" ] || die "找不到可执行的 parallel_mine.sh: $PM" 4
[ -d "$TARGETS_DIR" ] || die "目标目录不存在: $TARGETS_DIR" 3

# ---------- 通用状态读取 ----------
utc_now() { date -u +%Y-%m-%dT%H:%M:%SZ; }

orchestrator_alive() {
    local pid
    [ -s "$PID_FILE" ] || return 1
    pid="$(cat "$PID_FILE" 2>/dev/null || true)"
    [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null
}

discover_names() {
    if [ -s "$MANIFEST" ] && jq -e '.projects' "$MANIFEST" >/dev/null 2>&1; then
        jq -r '.projects | to_entries[] | select((.value.status // "ok") == "ok") | .key' "$MANIFEST"
    elif [ -d "$TARGETS_DIR" ]; then
        find "$TARGETS_DIR" -mindepth 1 -maxdepth 1 -type d -exec test -e '{}/.git' \; -print 2>/dev/null \
            | while IFS= read -r d; do basename "$d"; done | sort
    fi
}

status_names() {
    local p
    local -A seen=()
    if [ -s "$INFO_FILE" ] && jq -e '.projects' "$INFO_FILE" >/dev/null 2>&1; then
        while IFS= read -r p; do
            [ -n "$p" ] || continue
            seen["$p"]=1
            printf '%s\n' "$p"
        done < <(jq -r '.projects[].project' "$INFO_FILE")
    elif [ -d "$PROJECTS_DIR" ] && [ -n "$(ls -A "$PROJECTS_DIR" 2>/dev/null || true)" ]; then
        while IFS= read -r p; do
            [ -n "$p" ] || continue
            seen["$p"]=1
            printf '%s\n' "$p"
        done < <(find "$PROJECTS_DIR" -mindepth 1 -maxdepth 1 -type f -name '*.json' -printf '%f\n' \
            | sed 's/\.json$//' | sort)
    fi
    # 始终补上 manifest/targets 中的项目，避免 resume 过滤后丢失其他项目
    while IFS= read -r p; do
        [ -n "$p" ] || continue
        [ -n "${seen[$p]:-}" ] && continue
        seen["$p"]=1
        printf '%s\n' "$p"
    done < <(discover_names)
}

latest_meta() {
    local project="$1"
    find "$RUNS_ROOT/$project" -mindepth 2 -maxdepth 2 -type f -name run-meta.json -printf '%T@\t%p\n' 2>/dev/null \
        | sort -nr | head -n1 | cut -f2-
}

meta_complete() {
    local meta="$1"
    [ -s "$meta" ] || return 1
    jq -e '(.reports_complete == true) and ((.exit_code // 1) == 0) and ((.timed_out // false) == false)' "$meta" >/dev/null 2>&1
}

# 输出 <status>\t<rc>\t<duration>\t<run_dir>\t<message>
project_record() {
    local name="$1"
    local f="$PROJECTS_DIR/$name.json" meta=""
    if [ -s "$f" ]; then
        jq -r '[.status // "unknown", (.exit_code // "-"), (.duration_seconds // 0), (.run_dir // "-"), (.message // "")] | @tsv' "$f" 2>/dev/null && return
    fi
    meta="$(latest_meta "$name")"
    if [ -n "$meta" ]; then
        local st="failed" rc dur
        rc="$(jq -r '.exit_code // "-"' "$meta" 2>/dev/null || echo '-')"
        dur="$(jq -r '.duration_seconds // 0' "$meta" 2>/dev/null || echo 0)"
        if meta_complete "$meta"; then
            st="success"
        elif jq -e '.timed_out == true' "$meta" >/dev/null 2>&1; then
            st="timeout"
        fi
        printf '%s\t%s\t%s\t%s\t%s\n' "$st" "$rc" "$dur" "$(dirname "$meta")" "历史运行"
    else
        printf 'pending\t-\t0\t-\t尚未运行\n'
    fi
}

# ---------- 状态汇总 ----------
ACTION_STATUS=0

show_status() {
    local alive="no" state="not-started" pid="" names=() total=0
    local running=0 completed=0 failed=0 pending=0 stopped=0
    local p rec st rc dur dir msg

    orchestrator_alive && alive="yes"
    if [ -s "$INFO_FILE" ]; then
        state="$(jq -r '.state // "unknown"' "$INFO_FILE" 2>/dev/null || echo unknown)"
        pid="$(jq -r '.pid // empty' "$INFO_FILE" 2>/dev/null || true)"
    fi

    echo "=== mygoldmine overnight status ==="
    local info_model info_parallel info_timeout
    info_model="$(jq -r '.model // empty' "$INFO_FILE" 2>/dev/null || true)"
    info_parallel="$(jq -r '.max_parallel // empty' "$INFO_FILE" 2>/dev/null || true)"
    info_timeout="$(jq -r '.project_timeout // empty' "$INFO_FILE" 2>/dev/null || true)"
    echo "model=${info_model:-$MODEL} max_parallel=${info_parallel:-$MAX_PARALLEL} timeout=${info_timeout:-$PROJECT_TIMEOUT}s"
    echo "state=$state orchestrator_alive=$alive pid=${pid:-'-'}"
    if [ "$state" = "running" ] && [ "$alive" = "no" ]; then
        echo "WARN: 状态为 running 但编排器进程已不存在（可能被 kill -9，可用 resume 续跑）"
    fi

    mapfile -t names < <(status_names)
    total="${#names[@]}"

    local -a rows=()
    for p in "${names[@]}"; do
        rec="$(project_record "$p")"
        IFS=$'\t' read -r st rc dur dir msg <<< "$rec"
        case "$st" in
            success|skipped) completed=$(( completed + 1 )) ;;
            running)
                if [ "$alive" = "yes" ]; then
                    running=$(( running + 1 ))
                else
                    failed=$(( failed + 1 ))
                    msg="进程已退出但状态仍为 running（可用 resume）"
                fi
                ;;
            failed|timeout) failed=$(( failed + 1 )) ;;
            stopped) stopped=$(( stopped + 1 )) ;;
            *) pending=$(( pending + 1 )) ;;
        esac
        rows+=("$(printf '%s\t%s\t%s\t%s\t%s\t%s' "$p" "$st" "$rc" "$dur" "$dir" "$msg")")
    done

    if [ "${#rows[@]}" -gt 0 ]; then
        printf '%s\n' "${rows[@]}" | awk -F'\t' 'BEGIN {
                printf "%-18s %-10s %-4s %-8s %-42s %s\n", "PROJECT", "STATUS", "RC", "DUR(s)", "RUN_DIR", "NOTE"
            }
            { printf "%-18s %-10s %-4s %-8s %-42s %s\n", $1, $2, $3, $4, $5, $6 }'
    else
        echo "（没有可显示的项目）"
    fi

    echo "summary: total=$total running=$running completed=$completed failed=$failed stopped=$stopped pending=$pending"
    echo "runs_root=$RUNS_ROOT"
    echo "state_dir=$STATE_DIR"
    [ -f "$STOP_FILE" ] && echo "stop_requested=yes"
    [ -d "$STATE_DIR/logs" ] && echo "project_logs=$STATE_DIR/logs/<project>.log"
    echo "报告: $RUNS_ROOT/<project>/<timestamp>/audit-report.md"
    return 0
}

# ---------- 启动参数 ----------
build_pm_args() {
    PM_ARGS=(
        --targets-dir "$TARGETS_DIR"
        --manifest "$MANIFEST"
        --runs-root "$RUNS_ROOT"
        --state-dir "$STATE_DIR"
        --executor "$EXECUTOR"
        --model "$MODEL"
        --agent "$AGENT"
        --max-parallel "$MAX_PARALLEL"
        --timeout "$PROJECT_TIMEOUT"
        --retries "$MAX_RETRIES"
        --min-free-gb "$MIN_FREE_GB"
        --outer-grace "$OUTER_GRACE"
    )
    if [ -n "$PROJECTS_FILTER" ]; then
        PM_ARGS+=(--projects "$PROJECTS_FILTER")
    fi
    if [ "$FORCE" -eq 1 ]; then
        PM_ARGS+=(--force)
    fi
    if [ "$DRY_RUN" -eq 1 ]; then
        PM_ARGS+=(--dry-run)
    elif [ "$FOREGROUND" -eq 1 ]; then
        PM_ARGS+=(--foreground)
    else
        PM_ARGS+=(--detach)
    fi
}

precheck_start() {
    local alive_pid=""
    if orchestrator_alive; then
        alive_pid="$(cat "$PID_FILE" 2>/dev/null || true)"
        die "已有实例在运行（pid=$alive_pid）。用 '$0 status' 查看，或先 '$0 stop'" 7
    fi
    if [ -s "$PID_FILE" ]; then
        log "清理过期 PID 文件: $PID_FILE"
        rm -f "$PID_FILE"
    fi
    [ -x "$EXECUTOR" ] || die "执行器不可执行: $EXECUTOR" 4
}

start_overnight() {
    precheck_start
    build_pm_args
    echo "=== overnight start ==="
    echo "model=$MODEL max_parallel=$MAX_PARALLEL timeout=${PROJECT_TIMEOUT}s retries=$MAX_RETRIES"
    echo "targets=$TARGETS_DIR manifest=$MANIFEST"
    echo "runs_root=$RUNS_ROOT state_dir=$STATE_DIR executor=$EXECUTOR"
    echo "mode=$( [ "$DRY_RUN" -eq 1 ] && echo dry-run || { [ "$FOREGROUND" -eq 1 ] && echo foreground || echo detach; } )"
    if [ "$DRY_RUN" -eq 1 ]; then
        exec bash "$PM" "${PM_ARGS[@]}"
    fi
    bash "$PM" "${PM_ARGS[@]}" || die "启动失败（见上方阶段日志与 $STATE_DIR/logs/orchestrator.log）" $?
    echo
    if [ "$FOREGROUND" -eq 1 ]; then
        echo "前台运行结束。查看结果: bash scripts/mine/overnight.sh status"
    else
        echo "启动完成。查看进度: bash scripts/mine/overnight.sh status"
        echo "停止:         bash scripts/mine/overnight.sh stop"
    fi
    echo "次日报告:     $RUNS_ROOT/<project>/<timestamp>/audit-report.md"
}

# ---------- 未完成项目计算 ----------
compute_unfinished() {
    local names=() p rec st meta
    mapfile -t names < <(status_names)
    if [ "${#names[@]}" -eq 0 ]; then
        mapfile -t names < <(discover_names)
    fi
    [ "${#names[@]}" -gt 0 ] || return 0

    UNFINISHED=()
    for p in "${names[@]}"; do
        rec="$(project_record "$p")"
        st="${rec%%$'\t'*}"
        case "$st" in
            success|skipped) continue ;;
        esac
        # 无状态文件时，用最近一次 run-meta 判断是否已完成
        if [ ! -s "$PROJECTS_DIR/$p.json" ]; then
            meta="$(latest_meta "$p")"
            if [ -n "$meta" ] && meta_complete "$meta"; then continue; fi
        fi
        UNFINISHED+=("$p")
    done
}

resume_overnight() {
    [ "$FORCE" -eq 1 ] && die "--force 只用于 start；resume 本身只补未完成项目" 3
    orchestrator_alive && die "已有实例在运行（pid=$(cat "$PID_FILE" 2>/dev/null)），请先 status/stop" 7
    compute_unfinished
    echo "=== overnight resume ==="
    if [ "${#UNFINISHED[@]}" -eq 0 ]; then
        echo "所有项目均已完成，无需 resume。"
        return 0
    fi
    precheck_start
    echo "未完成项目（${#UNFINISHED[@]}）: ${UNFINISHED[*]}"
    PROJECTS_FILTER="$(IFS=,; echo "${UNFINISHED[*]}")"
    build_pm_args
    if [ "$DRY_RUN" -eq 1 ]; then
        exec bash "$PM" "${PM_ARGS[@]}"
    fi
    bash "$PM" "${PM_ARGS[@]}" || die "resume 启动失败，见 $STATE_DIR/logs/orchestrator.log" $?
    echo
    echo "已提交 resume。查看进度: bash scripts/mine/overnight.sh status"
}

stop_overnight() {
    echo "=== overnight stop ==="
    build_pm_args
    exec bash "$PM" --stop --state-dir "$STATE_DIR"
}

case "$ACTION" in
    status)
        show_status
        exit "$ACTION_STATUS"
        ;;
    stop)
        stop_overnight
        ;;
    start)
        start_overnight
        ;;
    resume)
        resume_overnight
        ;;
    *)
        die "未知动作: $ACTION" 3
        ;;
esac
