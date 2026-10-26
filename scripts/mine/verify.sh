#!/usr/bin/env bash
# mygoldmine 产物校验器（T14）
#
# 校验一次（或多次）挖掘产物的完整性：
#   1. 必需文件存在且非空：raw.jsonl / claude.rendered.log /
#      audit-report.md / audit-report.json / run-meta.json
#   2. JSON 可解析：报告、run-meta，以及 raw.jsonl 的每一行
#   3. run-meta 自洽：exit_code=0、reports_complete=true、未超时/未中断
#   4. 密钥泄漏扫描：sk-、Bearer、API key/token 赋值、云厂商 key、私钥头
#
# 用法:
#   verify.sh [选项] [RUN_DIR...]
#
# 不传 RUN_DIR 时递归扫描 $REPO_ROOT/runs 下所有含产物的目录。
# 退出码：0 全部通过；1 存在校验失败；2 参数/路径错误。
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

log() { printf '[verify] %s\n' "$*" >&2; }
die() { printf '[verify] ERROR: %s\n' "$1" >&2; exit "${2:-2}"; }

usage() {
    cat <<'EOF'
用法: verify.sh [选项] [RUN_DIR...]

选项:
  --runs-root DIR  递归扫描该目录下的产物（默认 <repo>/runs）
  --run-dir DIR    只校验指定产物目录，可重复
  --allow-failed   允许 exit_code!=0 / timed_out / reports_complete!=true
  --allow-empty    扫描目录里没有产物时不报错（用于首次启动前自检）
  --quiet          只输出失败项与最终汇总
  -h, --help       显示本帮助

必需产物:
  raw.jsonl  claude.rendered.log  audit-report.md  audit-report.json  run-meta.json

示例:
  scripts/mine/verify.sh runs/smoke/20261026T174149Z
  scripts/mine/verify.sh --runs-root runs
  scripts/mine/verify.sh --run-dir runs/vllm/20261026T180000Z
EOF
}

RUNS_ROOT="$REPO_ROOT/runs"
ALLOW_FAILED=0
ALLOW_EMPTY=0
QUIET=0
declare -a RUN_DIRS=()

while [ "$#" -gt 0 ]; do
    case "$1" in
        --runs-root)
            [ "$#" -ge 2 ] || die "--runs-root 需要参数"
            RUNS_ROOT="$2"; shift ;;
        --run-dir)
            [ "$#" -ge 2 ] || die "--run-dir 需要参数"
            RUN_DIRS+=("$2"); shift ;;
        --allow-failed) ALLOW_FAILED=1 ;;
        --allow-empty) ALLOW_EMPTY=1 ;;
        --quiet) QUIET=1 ;;
        -h|--help) usage; exit 0 ;;
        --*) die "未知选项: $1" ;;
        *) RUN_DIRS+=("$1") ;;
    esac
    shift
done

PASS_COUNT=0
FAIL_COUNT=0
CHECK_ERRORS=0

ok() { [ "$QUIET" -eq 1 ] || printf '[ok] %s\n' "$*"; }
error() {
    CHECK_ERRORS=$((CHECK_ERRORS + 1))
    printf '[FAIL] %s\n' "$*" >&2
}

check_json_file() {
    local file="$1"
    [ -s "$file" ] || return 0
    if ! jq empty "$file" >/dev/null 2>&1; then
        error "$file: JSON 无法解析"
        return 1
    fi
    return 0
}

check_raw_jsonl() {
    local file="$1" line line_no=0 bad=0
    while IFS= read -r line || [ -n "$line" ]; do
        line_no=$((line_no + 1))
        [[ "$line" =~ ^[[:space:]]*$ ]] && continue
        if ! printf '%s' "$line" | jq -e . >/dev/null 2>&1; then
            bad=$((bad + 1))
            [ "$bad" -le 3 ] && error "$file:$line_no: 非法 JSON 行"
        fi
    done < "$file"
    [ "$bad" -eq 0 ] && return 0
    [ "$bad" -gt 3 ] && error "$file: 共 $bad 行非法 JSON"
    return 1
}

check_meta() {
    local file="$1" exit_code reports_complete timed_out interrupted
    local failed=0

    if ! jq -e '(.exit_code | type) == "number"' "$file" >/dev/null 2>&1; then
        error "$file: 缺少合法的 exit_code"
        return 1
    fi
    exit_code="$(jq -r '.exit_code' "$file")"
    if ! [[ "$exit_code" =~ ^-?[0-9]+$ ]]; then
        error "$file: exit_code 不是整数: $exit_code"
        failed=1
    elif [ "$exit_code" -ne 0 ] && [ "$ALLOW_FAILED" -ne 1 ]; then
        error "$file: exit_code=$exit_code（预期 0；如需保留失败产物可加 --allow-failed）"
        failed=1
    fi

    reports_complete="$(jq -r '.reports_complete // false' "$file")"
    if [ "$reports_complete" != "true" ] && [ "$ALLOW_FAILED" -ne 1 ]; then
        error "$file: reports_complete=$reports_complete（预期 true）"
        failed=1
    fi

    timed_out="$(jq -r '.timed_out // false' "$file")"
    interrupted="$(jq -r '.interrupted // false' "$file")"
    if { [ "$timed_out" = "true" ] || [ "$interrupted" = "true" ]; } && [ "$ALLOW_FAILED" -ne 1 ]; then
        error "$file: timed_out=$timed_out interrupted=$interrupted（预期均为 false）"
        failed=1
    fi

    if ! jq -e '(.artifacts | type) == "object"' "$file" >/dev/null 2>&1; then
        error "$file: 缺少 artifacts 字段"
        failed=1
    fi

    [ "$failed" -eq 0 ] && return 0
    return 1
}

# 已知 token 前缀 + 引号包裹的 key 赋值 + .env 风格赋值 + 私钥头。
# 不匹配裸关键词（例如报告里的 "api_key" 说明文字），以降低误报。
SECRET_RE="sk-[A-Za-z0-9_-]{8,}|Bearer[[:space:]]+[A-Za-z0-9._-]{8,}|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{20,}|-----BEGIN ([A-Z]+ )?PRIVATE KEY-----|[A-Za-z0-9_]*(api[_-]?key|secret[_-]?key|access[_-]?token|password)[A-Za-z0-9_]*[\"']?[[:space:]]*[:=][[:space:]]*[\"'][^\"']{8,}[\"']|[A-Za-z0-9_]*(api[_-]?key|secret[_-]?key|access[_-]?token|password)[A-Za-z0-9_]*=[^[:space:]\"']{8,}"

check_secrets() {
    local dir="$1" hit
    while IFS= read -r hit; do
        [ -z "$hit" ] && continue
        error "疑似密钥泄漏: $hit"
    done < <(grep -RInaiE --binary-files=without-match "$SECRET_RE" "$dir" 2>/dev/null || true)
}

verify_dir() {
    local dir="$1"
    local before="$CHECK_ERRORS"
    local file

    if [ ! -d "$dir" ]; then
        error "$dir: 目录不存在"
        FAIL_COUNT=$((FAIL_COUNT + 1))
        return 1
    fi

    for file in raw.jsonl claude.rendered.log audit-report.md audit-report.json run-meta.json; do
        if [ ! -f "$dir/$file" ]; then
            error "$dir: 缺少必需产物 $file"
        elif [ ! -s "$dir/$file" ]; then
            error "$dir: 产物为空 $file"
        fi
    done

    check_json_file "$dir/audit-report.json" || true
    if [ -s "$dir/run-meta.json" ] && check_json_file "$dir/run-meta.json"; then
        check_meta "$dir/run-meta.json" || true
    fi
    [ -s "$dir/raw.jsonl" ] && { check_raw_jsonl "$dir/raw.jsonl" || true; }

    check_secrets "$dir"

    if [ "$CHECK_ERRORS" -eq "$before" ]; then
        ok "$dir"
        PASS_COUNT=$((PASS_COUNT + 1))
        return 0
    fi
    printf '[FAIL] %s: %d 项校验失败\n' "$dir" "$((CHECK_ERRORS - before))" >&2
    FAIL_COUNT=$((FAIL_COUNT + 1))
    return 1
}

if [ "${#RUN_DIRS[@]}" -eq 0 ]; then
    if [ ! -d "$RUNS_ROOT" ]; then
        if [ "$ALLOW_EMPTY" -eq 1 ]; then
            log "扫描目录不存在，按 --allow-empty 跳过: $RUNS_ROOT"
            exit 0
        fi
        die "扫描目录不存在: $RUNS_ROOT（可加 --allow-empty）" 1
    fi
    mapfile -d '' -t RUN_DIRS < <(
        find "$RUNS_ROOT" -type f \
            \( -name raw.jsonl -o -name claude.rendered.log \
               -o -name audit-report.md -o -name audit-report.json \
               -o -name run-meta.json \) \
            -printf '%h\0' 2>/dev/null | sort -zu
    )
fi

if [ "${#RUN_DIRS[@]}" -eq 0 ]; then
    if [ "$ALLOW_EMPTY" -eq 1 ]; then
        log "未发现产物目录，按 --allow-empty 跳过: $RUNS_ROOT"
        exit 0
    fi
    die "未发现任何产物目录: $RUNS_ROOT（可加 --allow-empty）" 1
fi

log "待校验目录: ${#RUN_DIRS[@]}"
for dir in "${RUN_DIRS[@]}"; do
    verify_dir "$dir"
done

printf '[verify] 通过=%d 失败=%d 错误项=%d\n' "$PASS_COUNT" "$FAIL_COUNT" "$CHECK_ERRORS"
if [ "$FAIL_COUNT" -gt 0 ] || [ "$CHECK_ERRORS" -gt 0 ]; then
    exit 1
fi
exit 0