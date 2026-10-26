#!/usr/bin/env bash
# mygoldmine 目标克隆脚本（T11）
#
# 职责：
#   1. 浅克隆/更新 5 个目标仓库：codex、deepseek-harness、vLLM、SGLang、verl
#   2. 单个项目失败不阻塞其他项目
#   3. 把 url / commit / clone_time / action 写入 targets/manifest.json
#
# 安全边界：
#   - 只访问公开 GitHub 仓库，不访问生产系统
#   - URL 中的 userinfo 写入 manifest 前会被剥离
#   - GIT_TERMINAL_PROMPT=0，避免交互式认证卡住
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

log() { printf '[clone_targets] %s\n' "$*" >&2; }
die() { printf '[clone_targets] ERROR: %s\n' "$*" >&2; exit "${2:-1}"; }

usage() {
    cat <<'EOF'
用法: clone_targets.sh [选项] [项目...]

项目（默认全部 5 个）:
  codex  deepseek-harness  vllm  sglang  verl

选项:
  --dry-run              只打印克隆/更新计划，不创建目录、不访问网络
  --update               已存在的仓库执行 fetch + reset --hard
  --targets-dir DIR      目标根目录（默认 $TARGETS_DIR 或 <repo>/targets）
  --manifest FILE        manifest 路径（默认 <targets-dir>/manifest.json）
  --depth N              浅克隆深度（默认 $DEPTH 或 1）
  --full                 完整克隆（忽略 --depth）
  --timeout SECONDS      单次 git 操作超时秒数（默认 $GIT_TIMEOUT 或 600）
  --only LIST            仅处理逗号分隔的项目，如 --only vllm,sglang
  --help                 显示本帮助

环境变量:
  TARGETS_DIR MANIFEST DEPTH GIT_TIMEOUT
  GIT_SSH_COMMAND        默认已设置 BatchMode，避免 SSH 交互卡住

退出码:
  0 全部成功或 dry-run；1 有项目失败；3 参数/项目名错误
EOF
}

# 项目名 -> 默认 HTTPS URL
project_url() {
    case "$1" in
        codex)            printf '%s\n' "https://github.com/openai/codex.git" ;;
        deepseek-harness) printf '%s\n' "https://github.com/deepseek-ai/deepseek-harness.git" ;;
        vllm)             printf '%s\n' "https://github.com/vllm-project/vllm.git" ;;
        sglang)           printf '%s\n' "https://github.com/sgl-project/sglang.git" ;;
        verl)             printf '%s\n' "https://github.com/volcengine/verl.git" ;;
        *) return 1 ;;
    esac
}

sanitize_url() {
    printf '%s' "$1" | sed -E 's#(https?://)[^/@]+@#\1#g'
}

DRY_RUN=0
UPDATE=0
FULL=0
PROJECTS_ARG=""
TARGETS_DIR="${TARGETS_DIR:-$REPO_ROOT/targets}"
MANIFEST="${MANIFEST:-}"
DEPTH="${DEPTH:-1}"
GIT_TIMEOUT="${GIT_TIMEOUT:-600}"

while [ "$#" -gt 0 ]; do
    case "$1" in
        --dry-run) DRY_RUN=1 ;;
        --update) UPDATE=1 ;;
        --full) FULL=1 ;;
        --targets-dir) [ "$#" -ge 2 ] || die "--targets-dir 需要参数" 3; TARGETS_DIR="$2"; shift ;;
        --manifest) [ "$#" -ge 2 ] || die "--manifest 需要参数" 3; MANIFEST="$2"; shift ;;
        --depth) [ "$#" -ge 2 ] || die "--depth 需要参数" 3; DEPTH="$2"; shift ;;
        --timeout) [ "$#" -ge 2 ] || die "--timeout 需要参数" 3; GIT_TIMEOUT="$2"; shift ;;
        --only) [ "$#" -ge 2 ] || die "--only 需要参数" 3; PROJECTS_ARG="$2"; shift ;;
        -h|--help) usage; exit 0 ;;
        -*) usage >&2; die "未知参数: $1" 3 ;;
        *) if [ -n "$PROJECTS_ARG" ]; then PROJECTS_ARG="$PROJECTS_ARG,$1"; else PROJECTS_ARG="$1"; fi ;;
    esac
    shift
done

[[ "$DEPTH" =~ ^[1-9][0-9]*$ ]] || die "DEPTH 必须是正整数，当前: $DEPTH" 3
[[ "$GIT_TIMEOUT" =~ ^[1-9][0-9]*$ ]] || die "GIT_TIMEOUT 必须是正整数秒，当前: $GIT_TIMEOUT" 3
[ -n "$MANIFEST" ] || MANIFEST="$TARGETS_DIR/manifest.json"

if [ "$FULL" = "1" ]; then
    SHALLOW=0
else
    SHALLOW=1
fi

# 解析项目列表并去重
PROJECTS=()
if [ -n "$PROJECTS_ARG" ]; then
    IFS=',' read -r -a _raw <<< "$PROJECTS_ARG"
    for p in "${_raw[@]}"; do
        p="$(printf '%s' "$p" | tr -d '[:space:]')"
        [ -n "$p" ] || continue
        project_url "$p" >/dev/null 2>&1 || die "未知项目: $p（可选: codex deepseek-harness vllm sglang verl）" 3
        [[ " ${PROJECTS[*]} " == *" $p "* ]] || PROJECTS+=("$p")
    done
else
    PROJECTS=(codex deepseek-harness vllm sglang verl)
fi
[ "${#PROJECTS[@]}" -gt 0 ] || die "未选择任何项目" 3

export GIT_TERMINAL_PROMPT=0
GIT_SSH_COMMAND="${GIT_SSH_COMMAND:-ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=15}"
export GIT_SSH_COMMAND

run_git() {
    timeout --signal=TERM --kill-after=10 "$GIT_TIMEOUT" git "$@"
}

git_commit() {
    git -C "$1" rev-parse HEAD 2>/dev/null || true
}

repo_origin() {
    git -C "$1" remote get-url origin 2>/dev/null || true
}

ACTION=()
STATUS=()
COMMITS=()
URLS=()
TIMES=()
ERRORS=()

record() {
    local idx="$1" action="$2" status="$3" commit="$4" url="$5" when="$6" err="$7"
    ACTION[$idx]="$action"
    STATUS[$idx]="$status"
    COMMITS[$idx]="$commit"
    URLS[$idx]="$(sanitize_url "$url")"
    TIMES[$idx]="$when"
    ERRORS[$idx]="$(printf '%s' "$err" | tr '\n\t' '  ' | cut -c1-500)"
    return 0
}

now_utc() { date -u +%Y-%m-%dT%H:%M:%SZ; }

clone_one() {
    local name="$1" dir="$2" url="$3" idx="$4" now="$5"
    local -a args=(clone)
    if [ "$SHALLOW" = "1" ]; then
        args+=(--depth "$DEPTH" --single-branch)
    fi
    args+=("$url" "$dir")

    if [ "$SHALLOW" = "1" ]; then
        log "[$name] 浅克隆 depth=${DEPTH} ${url} -> ${dir}"
    else
        log "[$name] 完整克隆 ${url} -> ${dir}"
    fi
    local err
    if err="$(run_git "${args[@]}" 2>&1)"; then
        local commit; commit="$(git_commit "$dir")"
        record "$idx" cloned ok "$commit" "$url" "$now" ""
        log "[$name] 完成 commit=${commit:-unknown}"
    else
        rm -rf "$dir" 2>/dev/null || true
        record "$idx" clone-failed failed "" "$url" "$now" "$err"
        log "[$name] 克隆失败: $(printf '%s' "$err" | tail -n 2 | tr '\n' ' ')"
    fi
}

update_one() {
    local name="$1" dir="$2" url="$3" idx="$4" now="$5"
    local orig; orig="$(repo_origin "$dir")"
    [ -n "$orig" ] || orig="$url"

    local -a fetch_args=(-C "$dir" fetch)
    if [ "$SHALLOW" = "1" ]; then
        fetch_args+=(--depth "$DEPTH")
    fi

    log "[$name] 更新 ${dir}（origin=${orig}）"
    local err
    if err="$(run_git "${fetch_args[@]}" origin HEAD 2>&1)"; then
        if err="$(run_git -C "$dir" reset --hard FETCH_HEAD 2>&1)"; then
            local commit; commit="$(git_commit "$dir")"
            record "$idx" updated ok "$commit" "$orig" "$now" ""
            log "[$name] 更新完成 commit=${commit:-unknown}"
            return
        fi
        record "$idx" update-failed failed "$(git_commit "$dir")" "$orig" "$now" "$err"
        log "[$name] reset 失败: $(printf '%s' "$err" | tail -n 2 | tr '\n' ' ')"
        return
    fi

    # origin 可能是 SSH 且当前环境无密钥；回退到公开 HTTPS URL
    local first_err="$err"
    if [ "$orig" != "$url" ]; then
        log "[$name] origin fetch 失败，回退 HTTPS: ${url}"
        local -a fallback=(-C "$dir" fetch)
        if [ "$SHALLOW" = "1" ]; then
            fallback+=(--depth "$DEPTH")
        fi
        if err="$(run_git "${fallback[@]}" "$url" HEAD 2>&1)" \
            && err="$(run_git -C "$dir" reset --hard FETCH_HEAD 2>&1)"; then
            local commit; commit="$(git_commit "$dir")"
            record "$idx" updated ok "$commit" "$url" "$now" ""
            log "[$name] 通过 HTTPS 更新完成 commit=${commit:-unknown}"
            return
        fi
    fi
    record "$idx" update-failed failed "$(git_commit "$dir")" "$url" "$now" "${first_err} | ${err:-}"
    log "[$name] 更新失败: $(printf '%s' "${first_err}" | tail -n 2 | tr '\n' ' ')"
}

# ---------- 计划 ----------
if [ "$DRY_RUN" = "1" ]; then
    echo "=== mygoldmine clone_targets dry-run ==="
    echo "DRY_RUN=1"
    echo "TARGETS_DIR=$TARGETS_DIR"
    echo "MANIFEST=$MANIFEST"
    echo "SHALLOW=$SHALLOW"
    echo "DEPTH=$DEPTH"
    echo "GIT_TIMEOUT=$GIT_TIMEOUT"
    echo "UPDATE=$UPDATE"
    echo
    for name in "${PROJECTS[@]}"; do
        url="$(project_url "$name")"
        dir="$TARGETS_DIR/$name"
        if [ -d "$dir/.git" ]; then
            if [ "$UPDATE" = "1" ]; then
                action="update"
            else
                action="skip-existing"
            fi
            existing_commit="$(git_commit "$dir")"
        elif [ -e "$dir" ]; then
            action="fail (exists but not a git repo)"
            existing_commit="-"
        else
            action="clone"
            existing_commit="-"
        fi
        echo "--- $name ---"
        echo "url=$url"
        echo "dir=$dir"
        echo "action=$action"
        echo "current_commit=${existing_commit:-unknown}"
        if [ "$action" = "clone" ]; then
            if [ "$SHALLOW" = "1" ]; then
                echo "cmd=timeout ${GIT_TIMEOUT}s git clone --depth ${DEPTH} --single-branch ${url} ${dir}"
            else
                echo "cmd=timeout ${GIT_TIMEOUT}s git clone ${url} ${dir}"
            fi
        elif [ "$action" = "update" ]; then
            if [ "$SHALLOW" = "1" ]; then
                echo "cmd=timeout ${GIT_TIMEOUT}s git -C ${dir} fetch --depth ${DEPTH} origin HEAD && git -C ${dir} reset --hard FETCH_HEAD"
            else
                echo "cmd=timeout ${GIT_TIMEOUT}s git -C ${dir} fetch origin HEAD && git -C ${dir} reset --hard FETCH_HEAD"
            fi
        fi
    done
    echo
    echo "manifest=$MANIFEST (dry-run 不写入)"
    echo "=== dry-run complete: no network, no files created ==="
    exit 0
fi

# ---------- 真实执行 ----------
mkdir -p "$TARGETS_DIR" || die "无法创建 TARGETS_DIR: $TARGETS_DIR"
mkdir -p "$(dirname "$MANIFEST")" || die "无法创建 manifest 目录: $(dirname "$MANIFEST")"

FAILED=0
for idx in "${!PROJECTS[@]}"; do
    name="${PROJECTS[$idx]}"
    url="$(project_url "$name")"
    dir="$TARGETS_DIR/$name"
    now="$(now_utc)"

    if [ -d "$dir/.git" ]; then
        if [ "$UPDATE" = "1" ]; then
            update_one "$name" "$dir" "$url" "$idx" "$now"
        else
            commit="$(git_commit "$dir")"
            actual_url="$(repo_origin "$dir")"
            [ -n "$actual_url" ] || actual_url="$url"
            record "$idx" existing ok "$commit" "$actual_url" "$now" ""
            log "[$name] 已存在，跳过（commit=${commit:-unknown}；使用 --update 可更新）"
        fi
    elif [ -e "$dir" ]; then
        record "$idx" skip-failed failed "" "$url" "$now" "$dir 已存在但不是 git 仓库"
        log "[$name] 目录已存在但不是 git 仓库: $dir"
    else
        clone_one "$name" "$dir" "$url" "$idx" "$now"
    fi

    [ "${STATUS[$idx]}" = "ok" ] || FAILED=1
done

# ---------- 写 manifest（合并已有内容） ----------
META="$(mktemp)"
trap 'rm -f "$META"' EXIT
: > "$META"
for idx in "${!PROJECTS[@]}"; do
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
        "${PROJECTS[$idx]}" \
        "$TARGETS_DIR/${PROJECTS[$idx]}" \
        "${URLS[$idx]}" \
        "${COMMITS[$idx]}" \
        "${TIMES[$idx]}" \
        "${ACTION[$idx]}" \
        "${STATUS[$idx]}" \
        "${ERRORS[$idx]}" >> "$META"
done

python3 - "$MANIFEST" "$META" "$TARGETS_DIR" "$SHALLOW" "$DEPTH" <<'PY'
import json, os, sys
from datetime import datetime, timezone

manifest_path, meta_path, targets_dir, shallow, depth = sys.argv[1:6]
projects = []
with open(meta_path, "r", encoding="utf-8") as fh:
    for line in fh:
        parts = line.rstrip("\n").split("\t")
        if len(parts) < 8:
            continue
        name, path, url, commit, when, action, status, error = parts[:8]
        entry = {
            "url": url,
            "path": path,
            "commit": commit,
            "clone_time": when,
            "action": action,
            "status": status,
        }
        if error:
            entry["error"] = error
        projects.append((name, entry))

merged = {}
if os.path.exists(manifest_path):
    try:
        with open(manifest_path, "r", encoding="utf-8") as fh:
            old = json.load(fh)
        if isinstance(old, dict) and isinstance(old.get("projects"), dict):
            merged = old["projects"]
    except (ValueError, OSError):
        merged = {}

for name, entry in projects:
    merged[name] = entry

out = {
    "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "targets_dir": targets_dir,
    "shallow": shallow == "1",
    "depth": int(depth),
    "projects": dict(sorted(merged.items())),
}

tmp = manifest_path + ".tmp"
with open(tmp, "w", encoding="utf-8") as fh:
    json.dump(out, fh, indent=2, ensure_ascii=False, sort_keys=False)
    fh.write("\n")
os.replace(tmp, manifest_path)
PY
[ "$?" -eq 0 ] || die "写入 manifest 失败: $MANIFEST" 5

log "manifest 已写入 $MANIFEST"

printf '\n=== summary ===\n'
printf '%-18s %-12s %-8s %-40s\n' "PROJECT" "ACTION" "STATUS" "COMMIT"
for idx in "${!PROJECTS[@]}"; do
    printf '%-18s %-12s %-8s %-40s\n' \
        "${PROJECTS[$idx]}" "${ACTION[$idx]}" "${STATUS[$idx]}" "${COMMITS[$idx]:--}"
done

exit "$FAILED"
