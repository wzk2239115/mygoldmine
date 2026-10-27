#!/usr/bin/env bash
# mygoldmine 并行编排器（T12）
#
# 职责：
#   1. 按 targets/manifest.json 选择目标，最多 MAX_PARALLEL 个项目并发挖掘
#   2. 每项目独立 run 目录与日志，失败重试 1 次（超时不重试）
#   3. 断点续跑：已有 reports_complete=true 的项目默认跳过
#   4. 单实例锁（flock）、启动前磁盘余量检查、--stop、--status
#   5. --detach 时用 setsid + nohup 脱离终端，并记录 PID
#
# 安全边界：
#   - 不在实现阶段启动真实 6h 挖掘；测试用 --executor 指向假执行器
#   - 不把密钥写入任何产物；子进程只从环境变量继承凭据
#   - 默认只读取 targets/manifest.json 中 status=ok 的项目
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SCRIPT_PATH="$SCRIPT_DIR/$(basename "${BASH_SOURCE[0]}")"

log() { printf '[parallel_mine] %s\n' "$*" >&2; }
die() { printf '[parallel_mine] ERROR: %s\n' "$*" >&2; exit "${2:-1}"; }

usage() {
    cat <<'EOF'
用法: parallel_mine.sh [选项]

动作:
  --status               查看编排状态（不启动、不加锁）
  --stop                 停止正在运行的编排器与所有 worker
  --dry-run              只打印计划，不创建目录、不调用模型
  --detach               后台运行（setsid + nohup），打印 PID 后返回
  --foreground           前台运行（默认；供 --detach 内部使用）

编排参数:
  --max-parallel N       最大并发项目数（默认 $MAX_PARALLEL 或 5）
  --timeout SECONDS      单项目墙钟超时（默认 $TIMEOUT 或 21600）
  --retries N            失败后重试次数（默认 $MAX_RETRIES 或 1；超时不重试）
  --outer-grace SECONDS  编排层超时相对项目的宽限（默认 $OUTER_GRACE 或 60）
  --min-free-gb N        启动所需磁盘余量 GB（默认 $MIN_FREE_GB 或 20）
  --projects LIST        仅处理逗号分隔的项目，如 vllm,sglang
  --force                忽略已完成记录，全部重跑

路径与执行:
  --targets-dir DIR      目标根目录（默认 $TARGETS_DIR 或 <repo>/targets）
  --manifest FILE        目标清单（默认 <targets-dir>/manifest.json）
  --runs-root DIR        产物根目录（默认 $RUNS_ROOT 或 <repo>/runs）
  --state-dir DIR        状态/锁/日志目录（默认 $RUNS_ROOT/.orchestrator）
  --executor FILE        单项目执行器（默认 $EXECUTOR 或 scripts/mine/mine_one.sh）
  --model MODEL          模型 ID（默认 $MODEL 或 360-proxy/deepseek/deepseek-v4.1-flash）
  --agent AGENT          审计智能体（默认 $AGENT 或 security-orchestrator）
  --help                 显示本帮助

环境变量:
  MAX_PARALLEL TIMEOUT MAX_RETRIES OUTER_GRACE MIN_FREE_GB
  TARGETS_DIR MANIFEST RUNS_ROOT STATE_DIR EXECUTOR MODEL AGENT

状态目录:
  run-info.json          编排器整体状态与项目列表
  projects/<name>.json   单项目状态（pending/running/success/failed/timeout/skipped/stopped）
  workers/<name>.pid     worker 进程组 PID
  logs/<name>.log        单项目执行器日志
  orchestrator.lock      单实例 flock 锁
  orchestrator.pid       编排器 PID
  STOP                   停止标记

退出码:
  0 全部成功或已完成跳过；1 有项目失败；3 参数错误；4 执行器不可用；
  7 已有实例在运行；8 磁盘余量不足；130/143 被停止
EOF
}

ACTION="run"
DRY_RUN=0
DETACH=0
FOREGROUND=0
WORKER=0
FORCE=0
PROJECTS_FILTER=""
MAX_PARALLEL="${MAX_PARALLEL:-5}"
PROJECT_TIMEOUT="${TIMEOUT:-21600}"
MAX_RETRIES="${MAX_RETRIES:-1}"
OUTER_GRACE="${OUTER_GRACE:-60}"
MIN_FREE_GB="${MIN_FREE_GB:-20}"
TARGETS_DIR="${TARGETS_DIR:-$REPO_ROOT/targets}"
MANIFEST="${MANIFEST:-}"
RUNS_ROOT="${RUNS_ROOT:-$REPO_ROOT/runs}"
STATE_DIR="${STATE_DIR:-}"
EXECUTOR="${EXECUTOR:-$SCRIPT_DIR/mine_one_docker.sh}"
MODEL="${MODEL:-360-proxy/deepseek/deepseek-v4.1-flash}"
AGENT="${AGENT:-security-orchestrator}"
if [ ! -f "$REPO_ROOT/.claude/agents/${AGENT}.md" ] && [ "$AGENT" != "security-orchestrator" ]; then
    echo "[parallel_mine] WARN: 未找到 agent '${AGENT}'，回退到 security-orchestrator" >&2
    AGENT="security-orchestrator"
fi
ORIG_ARGS=("$@")

while [ "$#" -gt 0 ]; do
    case "$1" in
        --status) ACTION="status" ;;
        --stop) ACTION="stop" ;;
        --dry-run) DRY_RUN=1 ;;
        --detach) DETACH=1 ;;
        --foreground) FOREGROUND=1 ;;
        --worker) WORKER=1 ;;
        --force) FORCE=1 ;;
        --max-parallel) [ "$#" -ge 2 ] || die "--max-parallel 需要参数" 3; MAX_PARALLEL="$2"; shift ;;
        --timeout) [ "$#" -ge 2 ] || die "--timeout 需要参数" 3; PROJECT_TIMEOUT="$2"; shift ;;
        --retries) [ "$#" -ge 2 ] || die "--retries 需要参数" 3; MAX_RETRIES="$2"; shift ;;
        --outer-grace) [ "$#" -ge 2 ] || die "--outer-grace 需要参数" 3; OUTER_GRACE="$2"; shift ;;
        --min-free-gb) [ "$#" -ge 2 ] || die "--min-free-gb 需要参数" 3; MIN_FREE_GB="$2"; shift ;;
        --projects) [ "$#" -ge 2 ] || die "--projects 需要参数" 3; PROJECTS_FILTER="$2"; shift ;;
        --targets-dir) [ "$#" -ge 2 ] || die "--targets-dir 需要参数" 3; TARGETS_DIR="$2"; shift ;;
        --manifest) [ "$#" -ge 2 ] || die "--manifest 需要参数" 3; MANIFEST="$2"; shift ;;
        --runs-root) [ "$#" -ge 2 ] || die "--runs-root 需要参数" 3; RUNS_ROOT="$2"; shift ;;
        --state-dir) [ "$#" -ge 2 ] || die "--state-dir 需要参数" 3; STATE_DIR="$2"; shift ;;
        --executor) [ "$#" -ge 2 ] || die "--executor 需要参数" 3; EXECUTOR="$2"; shift ;;
        --model) [ "$#" -ge 2 ] || die "--model 需要参数" 3; MODEL="$2"; shift ;;
        --agent) [ "$#" -ge 2 ] || die "--agent 需要参数" 3; AGENT="$2"; shift ;;
        -h|--help) usage; exit 0 ;;
        *) usage >&2; die "未知参数: $1" 3 ;;
    esac
    shift
done

[[ "$MAX_PARALLEL" =~ ^[1-9][0-9]*$ ]] || die "MAX_PARALLEL 必须是正整数，当前: $MAX_PARALLEL" 3
[[ "$PROJECT_TIMEOUT" =~ ^[1-9][0-9]*$ ]] || die "TIMEOUT 必须是正整数秒，当前: $PROJECT_TIMEOUT" 3
[[ "$MAX_RETRIES" =~ ^[0-9]+$ ]] || die "MAX_RETRIES 必须是非负整数，当前: $MAX_RETRIES" 3
[[ "$OUTER_GRACE" =~ ^[0-9]+$ ]] || die "OUTER_GRACE 必须是非负整数，当前: $OUTER_GRACE" 3
[[ "$MIN_FREE_GB" =~ ^[0-9]+$ ]] || die "MIN_FREE_GB 必须是非负整数，当前: $MIN_FREE_GB" 3

# AGENT 环境变量可能已被其他工具占用（如 AGENT=1），仅接受真实存在的 agent
if [ ! -f "$REPO_ROOT/.claude/agents/${AGENT}.md" ]; then
    # 数字形态通常是通用环境变量（如 AGENT=1），静默回退；像名字的才提示
    [[ "$AGENT" =~ [A-Za-z] ]] && [ "$AGENT" != "security-orchestrator" ] \
        && log "WARN: 未找到 agent '${AGENT}'，回退到 security-orchestrator"
    AGENT="security-orchestrator"
fi

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

LOCK_FILE="$STATE_DIR/orchestrator.lock"
INFO_FILE="$STATE_DIR/run-info.json"
PID_FILE="$STATE_DIR/orchestrator.pid"
STOP_FILE="$STATE_DIR/STOP"
PROJECTS_DIR="$STATE_DIR/projects"
WORKERS_DIR="$STATE_DIR/workers"
LOGS_DIR="$STATE_DIR/logs"
ORCH_LOG="$LOGS_DIR/orchestrator.log"
MAX_ATTEMPTS=$(( MAX_RETRIES + 1 ))
RUN_STARTED_AT=""
STOP_REQUESTED=0

utc_now() { date -u +%Y-%m-%dT%H:%M:%SZ; }
ts_run() { date -u +%Y%m%dT%H%M%SZ; }

# ---------- 项目发现 ----------
discover_projects() {
    local name path commit
    if [ -s "$MANIFEST" ] && jq -e '.projects' "$MANIFEST" >/dev/null 2>&1; then
        while IFS=$'\t' read -r name path commit; do
            [ -n "$name" ] || continue
            [ -n "$path" ] || path="$TARGETS_DIR/$name"
            path="$(abspath "$path")"
            if [ ! -d "$path" ]; then
                log "WARN: 跳过 $name，目录不存在: $path"
                continue
            fi
            printf '%s\t%s\t%s\n' "$name" "$path" "$commit"
        done < <(jq -r '.projects | to_entries[] | select((.value.status // "ok") == "ok") | [.key, (.value.path // ""), (.value.commit // "")] | @tsv' "$MANIFEST")
    else
        [ -d "$TARGETS_DIR" ] || return 0
        while IFS= read -r path; do
            [ -d "$path/.git" ] || continue
            name="$(basename "$path")"
            commit="$(git -C "$path" rev-parse HEAD 2>/dev/null || true)"
            printf '%s\t%s\t%s\n' "$name" "$path" "$commit"
        done < <(find "$TARGETS_DIR" -mindepth 1 -maxdepth 1 -type d | sort)
    fi
}

PROJECTS=()
declare -A PROJECT_PATHS=()
declare -A PROJECT_COMMITS=()

load_projects() {
    local name path commit wanted seen=","
    wanted=",${PROJECTS_FILTER},"
    while IFS=$'\t' read -r name path commit; do
        [ -n "$name" ] || continue
        if [ -n "$PROJECTS_FILTER" ] && [[ "$wanted" != *",$name,"* ]]; then
            continue
        fi
        PROJECTS+=("$name")
        PROJECT_PATHS[$name]="$path"
        PROJECT_COMMITS[$name]="$commit"
        seen="${seen}${name},"
    done < <(discover_projects)

    if [ -n "$PROJECTS_FILTER" ]; then
        local p
        IFS=',' read -ra _wanted_projects <<< "$PROJECTS_FILTER"
        for p in "${_wanted_projects[@]}"; do
            [ -n "$p" ] || continue
            [[ "$seen" == *",$p,"* ]] || die "未找到项目: $p（检查 --manifest / --targets-dir）" 3
        done
    fi
    [ "${#PROJECTS[@]}" -gt 0 ] || die "没有可运行项目（manifest=$MANIFEST, targets=$TARGETS_DIR）" 3
}

# ---------- 运行记录 ----------
latest_meta() {
    local project="$1"
    find "$RUNS_ROOT/$project" -mindepth 2 -maxdepth 2 -type f -name run-meta.json -printf '%T@\t%p\n' 2>/dev/null \
        | sort -nr | head -n1 | cut -f2-
}

run_is_complete() {
    local meta="$1"
    [ -s "$meta" ] || return 1
    jq -e '(.reports_complete == true) and ((.exit_code // 1) == 0) and ((.timed_out // false) == false)' "$meta" >/dev/null 2>&1
}

free_gb() {
    local probe="$1" avail_kb
    while [ ! -e "$probe" ]; do probe="$(dirname "$probe")"; done
    avail_kb="$(df -Pk "$probe" 2>/dev/null | awk 'NR==2 {print $4}')"
    [ -n "$avail_kb" ] || { printf '0\n'; return; }
    printf '%s\n' $(( avail_kb / 1024 / 1024 ))
}

write_status() {
    local project="$1" status="$2" attempt="$3" exit_code="$4" timed_out="$5"
    local run_dir="$6" started_at="$7" ended_at="$8" duration="$9" message="${10}" pid="${11}"
    local tmp="$PROJECTS_DIR/.${project}.json.tmp.$$"
    jq -n \
        --arg project "$project" \
        --arg status "$status" \
        --argjson attempt "$attempt" \
        --argjson exit_code "$exit_code" \
        --argjson timed_out "$timed_out" \
        --arg run_dir "$run_dir" \
        --arg started_at "$started_at" \
        --arg ended_at "$ended_at" \
        --argjson duration_seconds "$duration" \
        --arg message "$message" \
        --argjson pid "$pid" \
        --argjson max_attempts "$MAX_ATTEMPTS" \
        '{
            project: $project,
            status: $status,
            attempt: $attempt,
            max_attempts: ($max_attempts | tonumber),
            exit_code: $exit_code,
            timed_out: $timed_out,
            started_at: $started_at,
            ended_at: $ended_at,
            duration_seconds: $duration_seconds,
            run_dir: $run_dir,
            message: $message,
            pid: $pid
        }' > "$tmp" 2>/dev/null && mv -f "$tmp" "$PROJECTS_DIR/$project.json"
}

project_status_array() {
    local p
    for p in "${PROJECTS[@]}"; do
        if [ -s "$PROJECTS_DIR/$p.json" ]; then
            cat "$PROJECTS_DIR/$p.json"
        else
            jq -n --arg p "$p" '{project: $p, status: "pending", attempt: 0}'
        fi
    done | jq -s '.'
}

write_info() {
    local state="$1" ended_at="${2:-}" tmp="$INFO_FILE.tmp.$$"
    project_status_array | jq \
        --arg state "$state" \
        --arg pid "$$" \
        --arg started_at "$RUN_STARTED_AT" \
        --arg ended_at "$ended_at" \
        --arg model "$MODEL" \
        --arg agent "$AGENT" \
        --arg executor "$EXECUTOR" \
        --arg runs_root "$RUNS_ROOT" \
        --arg state_dir "$STATE_DIR" \
        --arg manifest "$MANIFEST" \
        --argjson max_parallel "$MAX_PARALLEL" \
        --argjson project_timeout "$PROJECT_TIMEOUT" \
        --argjson max_attempts "$MAX_ATTEMPTS" \
        '{
            schema_version: 1,
            state: $state,
            pid: ($pid | tonumber),
            started_at: $started_at,
            ended_at: (if $ended_at == "" then null else $ended_at end),
            model: $model,
            agent: $agent,
            executor: $executor,
            runs_root: $runs_root,
            state_dir: $state_dir,
            manifest: $manifest,
            max_parallel: $max_parallel,
            project_timeout: $project_timeout,
            max_attempts: $max_attempts,
            projects: .
        }' > "$tmp" && mv -f "$tmp" "$INFO_FILE"
}

# ---------- 单项目 worker ----------
CURRENT_CHILD=""

worker_on_signal() {
    local sig="$1" rc="$2" f tmp
    STOP_REQUESTED=1
    log "worker $WORKER_PROJECT 收到信号 $sig，终止子进程"
    if [ -n "$CURRENT_CHILD" ] && kill -0 "$CURRENT_CHILD" 2>/dev/null; then
        kill -TERM "$CURRENT_CHILD" 2>/dev/null || true
        sleep 1
        kill -KILL "$CURRENT_CHILD" 2>/dev/null || true
    fi
    # 只把仍在 running 的项目改为 stopped，避免覆盖已完成的 success
    f="$PROJECTS_DIR/$WORKER_PROJECT.json"
    if [ -s "$f" ]; then
        tmp="$f.tmp.$$"
        jq --arg ended "$(utc_now)" --argjson rc "$rc" \
            'if .status == "running" then
                .status = "stopped" | .ended_at = $ended | .exit_code = $rc |
                .timed_out = false | .message = "收到停止指令"
             else . end' "$f" > "$tmp" 2>/dev/null && mv -f "$tmp" "$f"
    fi
    rm -f "$WORKERS_DIR/$WORKER_PROJECT.pid"
    exit "$rc"
}

run_project() {
    local project="$1" target="$2"
    local started_at started_epoch ended_at duration attempts=0 rc=0 timed=0 complete=0
    local run_dir="" logf="$LOGS_DIR/$project.log" child="" outer_timeout

    started_at="$(utc_now)"
    started_epoch="$(date +%s)"
    : > "$logf"
    printf '%s\n' "=== $(utc_now) project=$project target=$target ===" >> "$logf"
    echo "$$" > "$WORKERS_DIR/$project.pid"

    while :; do
        attempts=$(( attempts + 1 ))
        run_dir="$RUNS_ROOT/$project/$(ts_run)"
        [ "$attempts" -gt 1 ] && run_dir="${run_dir}-r${attempts}"
        write_status "$project" "running" "$attempts" "null" "false" "$run_dir" "$started_at" "" 0 "执行中" "$$"
        printf '%s\n' "--- attempt $attempts/$MAX_ATTEMPTS -> $run_dir ---" >> "$logf"

        outer_timeout=$(( PROJECT_TIMEOUT + OUTER_GRACE ))
        local -a cmd=(
            "$EXECUTOR"
            --target "$target"
            --project "$project"
            --run-dir "$run_dir"
            --timeout "$PROJECT_TIMEOUT"
            --model "$MODEL"
            --agent "$AGENT"
        )

        (
            cd "$REPO_ROOT" || exit 3
            export MODEL AGENT TIMEOUT="$PROJECT_TIMEOUT"
            exec timeout --signal=TERM --kill-after=60 "$outer_timeout" "${cmd[@]}"
        ) >> "$logf" 2>&1 &
        child=$!
        CURRENT_CHILD="$child"
        rc=0
        wait "$child" || rc=$?
        CURRENT_CHILD=""

        timed=0
        if [ "$rc" -eq 124 ] || [ "$rc" -eq 137 ]; then
            timed=1
        elif [ -s "$run_dir/run-meta.json" ] && jq -e '.timed_out == true' "$run_dir/run-meta.json" >/dev/null 2>&1; then
            timed=1
        fi

        complete=0
        if [ "$rc" -eq 0 ]; then
            if run_is_complete "$run_dir/run-meta.json"; then
                complete=1
            elif [ -s "$run_dir/audit-report.md" ] && [ -s "$run_dir/audit-report.json" ]; then
                complete=1
            fi
        fi

        if [ "$complete" -eq 1 ]; then
            rc=0
            break
        fi
        [ "$rc" -eq 0 ] && rc=2

        if [ -f "$STOP_FILE" ] || [ "$STOP_REQUESTED" = "1" ]; then
            break
        fi
        if [ "$timed" -eq 1 ]; then
            log "$project 超时（rc=$rc），按设计不原地重试"
            break
        fi
        if [ "$attempts" -ge "$MAX_ATTEMPTS" ]; then
            break
        fi
        log "$project 失败（rc=$rc），准备第 $((attempts + 1)) 次尝试"
        sleep 2
    done

    ended_at="$(utc_now)"
    duration=$(( $(date +%s) - started_epoch ))
    local status message
    if [ "$complete" -eq 1 ]; then
        status="success"; message="报告齐全"
    elif [ -f "$STOP_FILE" ] || [ "$STOP_REQUESTED" = "1" ]; then
        status="stopped"; message="收到停止指令"
    elif [ "$timed" -eq 1 ]; then
        status="timeout"; message="超时，日志已保留"
    else
        status="failed"; message="尝试 ${attempts} 次后仍失败"
    fi
    write_status "$project" "$status" "$attempts" "$rc" "$( [ "$timed" -eq 1 ] && echo true || echo false )" \
        "$run_dir" "$started_at" "$ended_at" "$duration" "$message" "$$"
    rm -f "$WORKERS_DIR/$project.pid"
    printf '%s\n' "=== $(utc_now) project=$project status=$status attempts=$attempts rc=$rc ===" >> "$logf"
    log "$project: status=$status attempts=$attempts rc=$rc run_dir=$run_dir"
    [ "$status" = "success" ] && return 0
    [ "$status" = "stopped" ] && return 143
    return 1
}

# ---------- status / stop ----------
status_project_names() {
    if [ -s "$INFO_FILE" ] && jq -e '.projects' "$INFO_FILE" >/dev/null 2>&1; then
        jq -r '.projects[].project' "$INFO_FILE"
    elif [ -d "$PROJECTS_DIR" ] && [ -n "$(ls -A "$PROJECTS_DIR" 2>/dev/null || true)" ]; then
        find "$PROJECTS_DIR" -mindepth 1 -maxdepth 1 -type f -name '*.json' -printf '%f\n' | sed 's/\.json$//' | sort
    else
        discover_projects 2>/dev/null | cut -f1
    fi
}

show_status() {
    echo "=== mygoldmine parallel_mine status ==="
    if [ -s "$INFO_FILE" ]; then
        jq -r '"state=\(.state) pid=\(.pid) started_at=\(.started_at) ended_at=\(.ended_at // "-") max_parallel=\(.max_parallel) timeout=\(.project_timeout)s max_attempts=\(.max_attempts)", "model=\(.model) agent=\(.agent)", "executor=\(.executor)", "runs_root=\(.runs_root)"' "$INFO_FILE" 2>/dev/null
        local state pid alive="no"
        state="$(jq -r '.state // "unknown"' "$INFO_FILE" 2>/dev/null || echo unknown)"
        pid="$(jq -r '.pid // empty' "$INFO_FILE" 2>/dev/null || true)"
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then alive="yes"; fi
        echo "orchestrator_alive=$alive"
        if { [ "$state" = "running" ] || [ "$state" = "stopping" ]; } && [ "$alive" = "no" ]; then
            echo "WARN: 状态为 $state 但 PID $pid 已不存在（可能被 kill -9）"
        fi
    else
        echo "state=not-started (无 $INFO_FILE)"
    fi
    [ -f "$STOP_FILE" ] && echo "stop_requested=yes (存在 $STOP_FILE)" || echo "stop_requested=no"
    echo

    local names
    mapfile -t names < <(status_project_names)
    if [ "${#names[@]}" -eq 0 ]; then
        echo "（没有可显示的项目）"
        return 0
    fi

    {
        local p f meta latest
        for p in "${names[@]}"; do
            f="$PROJECTS_DIR/$p.json"
            if [ -s "$f" ]; then
                jq -r '[.project, .status, (.attempt // 0), (.exit_code // "-"), (.duration_seconds // 0), (.run_dir // "-"), (.message // "")] | @tsv' "$f"
            else
                meta="$(latest_meta "$p")"
                if [ -n "$meta" ]; then
                    local st="failed" rc="-" dur=0
                    rc="$(jq -r '.exit_code // "-"' "$meta" 2>/dev/null || echo '-')"
                    dur="$(jq -r '.duration_seconds // 0' "$meta" 2>/dev/null || echo 0)"
                    if run_is_complete "$meta"; then st="done"
                    elif jq -e '.timed_out == true' "$meta" >/dev/null 2>&1; then st="timeout"; fi
                    printf '%s\t%s\t-\t%s\t%s\t%s\t%s\n' "$p" "$st" "$rc" "$dur" "$(dirname "$meta")" "历史运行"
                else
                    printf '%s\tpending\t0\t-\t0\t-\t%s\n' "$p" "尚未运行"
                fi
            fi
        done
    } | awk -F'\t' 'BEGIN { printf "%-18s %-9s %-4s %-5s %-8s %-42s %s\n", "PROJECT", "STATUS", "TRY", "RC", "DUR(s)", "RUN_DIR", "NOTE" }
        { printf "%-18s %-9s %-4s %-5s %-8s %-42s %s\n", $1, $2, $3, $4, $5, $6, $7 }'

    echo
    if [ -d "$PROJECTS_DIR" ] && [ -n "$(ls -A "$PROJECTS_DIR" 2>/dev/null || true)" ]; then
        echo -n "summary: "
        jq -s 'group_by(.status) | map("\(.[0].status)=\(length)") | join(" ")' "$PROJECTS_DIR"/*.json 2>/dev/null || echo "n/a"
    fi
    [ -f "$ORCH_LOG" ] && echo "orchestrator_log=$ORCH_LOG"
    [ -d "$LOGS_DIR" ] && echo "project_logs=$LOGS_DIR/<project>.log"
    return 0
}

do_stop() {
    local pid="" stopped=0 p pf
    if [ -s "$PID_FILE" ]; then
        pid="$(cat "$PID_FILE" 2>/dev/null || true)"
    fi

    mkdir -p "$STATE_DIR" 2>/dev/null || true
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        : > "$STOP_FILE"
        echo "发送 TERM 到编排器 pid=$pid"
        kill -TERM "$pid" 2>/dev/null || true
        stopped=1
    fi

    if [ -d "$WORKERS_DIR" ]; then
        for pf in "$WORKERS_DIR"/*.pid; do
            [ -s "$pf" ] || continue
            pid="$(cat "$pf" 2>/dev/null || true)"
            [ -n "$pid" ] || continue
            if kill -0 "$pid" 2>/dev/null; then
                echo "发送 TERM 到 worker 进程组 -$pid ($(basename "$pf" .pid))"
                kill -TERM -- "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null || true
                stopped=1
            fi
        done
    fi

    if [ "$stopped" -eq 0 ]; then
        echo "没有正在运行的 parallel_mine 实例"
        rm -f "$STOP_FILE"
        return 0
    fi

    local wait_s="${STOP_WAIT:-30}" i
    for (( i = 0; i < wait_s; i++ )); do
        local alive=0
        if [ -s "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE" 2>/dev/null)" 2>/dev/null; then alive=1; fi
        for pf in "$WORKERS_DIR"/*.pid; do
            [ -s "$pf" ] && kill -0 "$(cat "$pf" 2>/dev/null)" 2>/dev/null && alive=1
        done
        [ "$alive" -eq 0 ] && break
        sleep 1
    done
    if [ -s "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE" 2>/dev/null)" 2>/dev/null; then
        echo "编排器未在 ${wait_s}s 内退出，发送 KILL"
        kill -KILL "$(cat "$PID_FILE" 2>/dev/null)" 2>/dev/null || true
    fi
    echo "停止请求已处理；保留 $STOP_FILE 供运行中的 worker 检查"
    return 0
}

# ---------- dry-run ----------
print_plan() {
    local now gb executor_ok=no
    now="$(ts_run)"
    gb="$(free_gb "$RUNS_ROOT")"
    [ -x "$EXECUTOR" ] && executor_ok=yes

    echo "=== mygoldmine parallel_mine dry-run ==="
    echo "DRY_RUN=1"
    echo "REPO_ROOT=$REPO_ROOT"
    echo "MANIFEST=$MANIFEST"
    echo "TARGETS_DIR=$TARGETS_DIR"
    echo "RUNS_ROOT=$RUNS_ROOT"
    echo "STATE_DIR=$STATE_DIR"
    echo "EXECUTOR=$EXECUTOR (executable=$executor_ok)"
    echo "MODEL=$MODEL"
    echo "AGENT=$AGENT"
    echo "MAX_PARALLEL=$MAX_PARALLEL"
    echo "PROJECT_TIMEOUT=$PROJECT_TIMEOUT"
    echo "MAX_RETRIES=$MAX_RETRIES (max_attempts=$MAX_ATTEMPTS)"
    echo "OUTER_GRACE=$OUTER_GRACE"
    echo "MIN_FREE_GB=$MIN_FREE_GB"
    echo "FREE_GB=$gb (disk_check=$( [ "$gb" -ge "$MIN_FREE_GB" ] && echo pass || echo fail ))"
    echo "FORCE=$FORCE"
    echo "LOCK=$LOCK_FILE"
    echo "ORCH_LOG=$ORCH_LOG"
    echo
    echo "--- 项目计划 ---"
    local p meta decision last
    for p in "${PROJECTS[@]}"; do
        meta="$(latest_meta "$p")"
        if [ -n "$meta" ] && run_is_complete "$meta" && [ "$FORCE" -ne 1 ]; then
            decision="skip（已完成）"
            last="$(dirname "$meta")"
        elif [ -n "$meta" ] && run_is_complete "$meta"; then
            decision="run（--force）"
            last="$(dirname "$meta")"
        else
            decision="run"
            last="${meta:+$(dirname "$meta")}"
            [ -n "$last" ] || last="-"
        fi
        echo "  $p"
        echo "    target=${PROJECT_PATHS[$p]}"
        echo "    commit=${PROJECT_COMMITS[$p]:-unknown}"
        echo "    decision=$decision"
        echo "    previous_run=$last"
        echo "    next_run=$RUNS_ROOT/$p/$now"
        echo "    log=$LOGS_DIR/$p.log"
    done
    echo
    echo "--- 执行命令（每项目） ---"
    echo "setsid timeout --signal=TERM --kill-after=60 $(( PROJECT_TIMEOUT + OUTER_GRACE )) \\"
    echo "  $EXECUTOR --target <target> --project <name> --run-dir <run_dir> \\"
    echo "    --timeout $PROJECT_TIMEOUT --model $MODEL --agent $AGENT"
    echo
    echo "--- 控制 ---"
    echo "status: $SCRIPT_PATH --status --runs-root $RUNS_ROOT --state-dir $STATE_DIR"
    echo "stop:   $SCRIPT_PATH --stop --state-dir $STATE_DIR"
    echo "detach: $SCRIPT_PATH --detach [同上参数]"
    echo
    echo "=== dry-run complete: no directories created, no model calls, no lock taken ==="
}

# ---------- 动作分发 ----------
if [ "$ACTION" = "status" ]; then
    show_status
    exit 0
fi
if [ "$ACTION" = "stop" ]; then
    do_stop
    exit 0
fi

if [ "$DRY_RUN" = "1" ]; then
    load_projects
    print_plan
    exit 0
fi

if [ "$WORKER" = "1" ]; then
    [ -n "${WORKER_PROJECT:-}" ] || die "worker 模式缺少 WORKER_PROJECT" 3
    [ -n "${WORKER_TARGET:-}" ] || die "worker 模式缺少 WORKER_TARGET" 3
    [ -d "$WORKER_TARGET" ] || die "worker 目标不存在: $WORKER_TARGET" 3
    mkdir -p "$PROJECTS_DIR" "$WORKERS_DIR" "$LOGS_DIR" || die "无法创建状态目录: $STATE_DIR" 5
    [ -x "$EXECUTOR" ] || die "执行器不可执行: $EXECUTOR" 4
    STOP_REQUESTED=0
    trap 'worker_on_signal TERM 143' TERM
    trap 'worker_on_signal INT 130' INT
    run_project "$WORKER_PROJECT" "$WORKER_TARGET"
    exit $?
fi

if [ "$DETACH" = "1" ]; then
    if [ -s "$PID_FILE" ]; then
        old_pid="$(cat "$PID_FILE" 2>/dev/null || true)"
        if [ -n "$old_pid" ] && kill -0 "$old_pid" 2>/dev/null; then
            die "已有 parallel_mine 实例在运行（pid=$old_pid），用 --status 查看" 7
        fi
        rm -f "$PID_FILE"
    fi
    mkdir -p "$STATE_DIR" "$LOGS_DIR" || die "无法创建状态目录: $STATE_DIR" 5
    FWD=()
    for a in "${ORIG_ARGS[@]}"; do
        [ "$a" = "--detach" ] && continue
        FWD+=("$a")
    done
    FWD+=(--foreground)
    setsid nohup bash "$SCRIPT_PATH" "${FWD[@]}" >> "$ORCH_LOG" 2>&1 < /dev/null &
    child=$!
    for _ in $(seq 1 50); do
        [ -s "$PID_FILE" ] && break
        kill -0 "$child" 2>/dev/null || break
        sleep 0.2
    done
    if [ -s "$PID_FILE" ]; then
        echo "detached pid=$(cat "$PID_FILE") log=$ORCH_LOG state=$STATE_DIR"
        exit 0
    fi
    echo "detach 失败：未生成 PID 文件，日志尾部：" >&2
    tail -n 20 "$ORCH_LOG" >&2 2>/dev/null || true
    exit 1
fi

# ---------- 前台编排 ----------
load_projects
mkdir -p "$STATE_DIR" "$PROJECTS_DIR" "$WORKERS_DIR" "$LOGS_DIR" || die "无法创建状态目录: $STATE_DIR" 5

exec 9>"$LOCK_FILE" || die "无法打开锁文件: $LOCK_FILE" 5
if ! flock -n 9; then
    die "已有 parallel_mine 实例在运行（锁: $LOCK_FILE），用 --status 查看" 7
fi

free_gb_now="$(free_gb "$RUNS_ROOT")"
if [ "$free_gb_now" -lt "$MIN_FREE_GB" ]; then
    die "磁盘余量不足：${free_gb_now}G < ${MIN_FREE_GB}G（检查 $RUNS_ROOT）" 8
fi

echo "$$" > "$PID_FILE"
rm -f "$STOP_FILE"
RUN_STARTED_AT="$(utc_now)"

cleanup() {
    if [ -s "$PID_FILE" ] && [ "$(cat "$PID_FILE" 2>/dev/null)" = "$$" ]; then
        rm -f "$PID_FILE"
    fi
}
trap cleanup EXIT

on_stop() {
    STOP_REQUESTED=1
    : > "$STOP_FILE"
    log "收到停止信号，通知所有 worker"
    local p pid
    if [ "${#WORKER_PIDS[@]}" -gt 0 ]; then
        for p in "${!WORKER_PIDS[@]}"; do
            pid="${WORKER_PIDS[$p]}"
            [ -n "$pid" ] || continue
            kill -TERM -- "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null || true
        done
    fi
}
trap 'on_stop' TERM
trap 'on_stop; exit 130' INT

# 初始化项目状态与整体状态
for p in "${PROJECTS[@]}"; do
    rm -f "$PROJECTS_DIR/$p.json" "$WORKERS_DIR/$p.pid"
done
write_info "running"

declare -A WORKER_PIDS=()
running=0

launch_worker() {
    local p="$1" target="$2"
    WORKER_PROJECT="$p" WORKER_TARGET="$target" \
        setsid bash "$SCRIPT_PATH" --worker \
            --targets-dir "$TARGETS_DIR" \
            --manifest "$MANIFEST" \
            --runs-root "$RUNS_ROOT" \
            --state-dir "$STATE_DIR" \
            --executor "$EXECUTOR" \
            --timeout "$PROJECT_TIMEOUT" \
            --retries "$MAX_RETRIES" \
            --outer-grace "$OUTER_GRACE" \
            --model "$MODEL" \
            --agent "$AGENT" \
            >> "$ORCH_LOG" 2>&1 < /dev/null &
    WORKER_PIDS[$p]=$!
    running=$(( running + 1 ))
    log "启动 $p pid=$! target=$target"
}

reap_finished() {
    local p pid
    for p in "${!WORKER_PIDS[@]}"; do
        pid="${WORKER_PIDS[$p]}"
        if ! kill -0 "$pid" 2>/dev/null; then
            wait "$pid" 2>/dev/null || true
            unset 'WORKER_PIDS[$p]'
            running=$(( running - 1 ))
            [ -s "$PROJECTS_DIR/$p.json" ] && log "$p 结束: $(jq -r '.status + " rc=" + ((.exit_code // "-")|tostring)' "$PROJECTS_DIR/$p.json" 2>/dev/null)"
        fi
    done
}

skipped=0
for p in "${PROJECTS[@]}"; do
    if [ -f "$STOP_FILE" ]; then break; fi
    meta="$(latest_meta "$p")"
    if [ "$FORCE" -ne 1 ] && [ -n "$meta" ] && run_is_complete "$meta"; then
        last_dir="$(dirname "$meta")"
        write_status "$p" "skipped" 0 0 false "$last_dir" "" "$(utc_now)" 0 "已完成，跳过（--force 可重跑）" 0
        log "跳过 $p（已完成: $last_dir）"
        skipped=$(( skipped + 1 ))
        continue
    fi

    while [ "$running" -ge "$MAX_PARALLEL" ]; do
        reap_finished
        [ "$running" -lt "$MAX_PARALLEL" ] && break
        sleep 0.2
    done
    [ -f "$STOP_FILE" ] && break
    launch_worker "$p" "${PROJECT_PATHS[$p]}"
done

while [ "$running" -gt 0 ]; do
    reap_finished
    [ "$running" -eq 0 ] && break
    sleep 0.2
done

# 停止时给 worker 一点收尾时间，超时后强杀进程组
if [ "$STOP_REQUESTED" = "1" ]; then
    local_deadline=$(( $(date +%s) + 90 ))
    while [ "$running" -gt 0 ] && [ "$(date +%s)" -lt "$local_deadline" ]; do
        reap_finished
        sleep 0.5
    done
    for p in "${!WORKER_PIDS[@]}"; do
        pid="${WORKER_PIDS[$p]}"
        kill -KILL -- "-$pid" 2>/dev/null || kill -KILL "$pid" 2>/dev/null || true
        unset 'WORKER_PIDS[$p]'
    done
fi

ENDED_AT="$(utc_now)"
final_state="finished"
[ "$STOP_REQUESTED" = "1" ] && final_state="stopped"
write_info "$final_state" "$ENDED_AT"
# 停止标记保留到下次启动时清理，便于 --status 看到

# 汇总计数并决定退出码
count_success=0 count_skipped=0 count_failed=0 count_timeout=0 count_stopped=0
for p in "${PROJECTS[@]}"; do
    st="$(jq -r '.status // "pending"' "$PROJECTS_DIR/$p.json" 2>/dev/null || echo pending)"
    case "$st" in
        success) count_success=$(( count_success + 1 )) ;;
        skipped) count_skipped=$(( count_skipped + 1 )) ;;
        timeout) count_timeout=$(( count_timeout + 1 )) ;;
        stopped) count_stopped=$(( count_stopped + 1 )) ;;
        *) count_failed=$(( count_failed + 1 )) ;;
    esac
done

echo "=== parallel_mine 完成 ==="
echo "state=$final_state success=$count_success skipped=$count_skipped failed=$count_failed timeout=$count_timeout stopped=$count_stopped"
echo "info=$INFO_FILE logs=$LOGS_DIR"

if [ "$STOP_REQUESTED" = "1" ]; then
    exit 143
fi
if [ "$count_failed" -gt 0 ] || [ "$count_timeout" -gt 0 ] || [ "$count_stopped" -gt 0 ]; then
    exit 1
fi
exit 0
