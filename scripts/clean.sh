#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
APPLY=0

usage() {
    cat <<'EOF'
用法：
  bash scripts/clean.sh --dry-run  仅列出将删除的历史产物
  bash scripts/clean.sh --yes      删除历史运行和学习产物

保留目标源码、环境、手工知识库、基础智能体和基础技能。
EOF
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --yes) APPLY=1 ;;
        --dry-run) APPLY=0 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "未知参数：$1" >&2; usage >&2; exit 3 ;;
    esac
    shift
done

[ "$REPO_ROOT" != "/" ] || { echo "拒绝清理根目录" >&2; exit 3; }

paths=(
    runs
    logs
    rsi/mining-repairs
    rsi/trajectories
    rsi/learning
    rsi/labeling
    rsi/artifacts
    rsi/batch1
    rsi/consensus
    rsi/stages
    rsi/worlds
    rsi/policy
    rsi/trace_pool.json
    rsi/plan.json
    rsi/plan.md
    .claude/skills/rsi-shared-experience/rules
    knowledge/project-rules
    ui/data/finding-ledger.json
    ui/data/auto-state.json
    ui/data/refine-state.json
    ui/data/refine-queue.json
    ui/data/flow-state.json
    ui/data/flow-queue.json
    ui/data/verification-shadow.json
    ui/data/report-quality.json
    ui/data/watch-state.json
)

shopt -s nullglob
for path in "${paths[@]}" "$REPO_ROOT"/rsi/verification-*.json "$REPO_ROOT"/rsi/verification-*.jsonl "$REPO_ROOT"/rsi/redteam-*.jsonl; do
    if [[ "$path" = /* ]]; then
        target="$path"
    else
        target="$REPO_ROOT/$path"
    fi
    case "$target" in
        "$REPO_ROOT"|"/"|"$HOME") echo "拒绝危险路径：$target" >&2; exit 3 ;;
    esac
    [ -e "$target" ] || continue
    if [ "$APPLY" -eq 1 ]; then
        printf '删除 %s\n' "$target"
        rm -rf -- "$target"
    else
        printf '将删除 %s\n' "$target"
    fi
done

if [ "$APPLY" -eq 1 ]; then
    mkdir -p "$REPO_ROOT/runs" "$REPO_ROOT/logs"
    printf '历史运行和学习产物已清理；源码、环境与手工知识已保留。\n'
else
    printf '未删除任何文件。确认无误后使用 --yes。\n'
fi
