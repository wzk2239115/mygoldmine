#!/bin/bash
# check-task.sh
# 检查任务完成情况
#
# 用法：
#   check-task.sh <tasks_json_path> [--show-pending] [--show-failed]
#
# 参数：
#   tasks_json_path: tasks.json 文件的路径（必需）
#   --show-pending: 显示待处理的任务列表
#   --show-failed: 显示失败的任务列表

set -euo pipefail

# 检查参数
if [ $# -lt 1 ]; then
    echo "错误: 缺少必需参数" >&2
    echo "用法: $(basename "$0") <tasks_json_path> [--show-pending] [--show-failed]" >&2
    exit 1
fi

TASKS_JSON_PATH="$1"
shift 1

# 默认值
SHOW_PENDING=false
SHOW_FAILED=false

# 解析可选参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --show-pending)
            SHOW_PENDING=true
            shift
            ;;
        --show-failed)
            SHOW_FAILED=true
            shift
            ;;
        *)
            echo "错误: 未知参数: $1" >&2
            exit 1
            ;;
    esac
done

# 检查 jq 是否安装
if ! command -v jq &> /dev/null; then
    echo "错误: 需要安装 jq 工具来处理 JSON" >&2
    echo "安装方法: sudo apt-get install jq 或 brew install jq" >&2
    exit 1
fi

# 检查 tasks.json 是否存在
if [ ! -f "$TASKS_JSON_PATH" ]; then
    echo "错误: tasks.json 文件不存在: $TASKS_JSON_PATH" >&2
    exit 1
fi

# 读取统计信息
SUMMARY=$(jq '.summary' "$TASKS_JSON_PATH")
TOTAL=$(echo "$SUMMARY" | jq -r '.total_tasks // 0')
COMPLETED=$(echo "$SUMMARY" | jq -r '.completed // 0')
IN_PROGRESS=$(echo "$SUMMARY" | jq -r '.in_progress // 0')
PENDING=$(echo "$SUMMARY" | jq -r '.pending // 0')
FAILED=$(echo "$SUMMARY" | jq -r '.failed // 0')

# 读取 duration
DURATION=$(jq -r '.duration // 0' "$TASKS_JSON_PATH")

# 格式化 duration 为可读形式
format_duration() {
    local seconds=$1
    local days=$((seconds / 86400))
    local hours=$(((seconds % 86400) / 3600))
    local minutes=$(((seconds % 3600) / 60))
    local secs=$((seconds % 60))

    if [ $days -gt 0 ]; then
        echo "${days}天 ${hours}小时 ${minutes}分钟"
    elif [ $hours -gt 0 ]; then
        echo "${hours}小时 ${minutes}分钟"
    elif [ $minutes -gt 0 ]; then
        echo "${minutes}分钟 ${secs}秒"
    else
        echo "${secs}秒"
    fi
}

DURATION_FORMATTED=$(format_duration "$DURATION")

# 计算完成率
if [ "$TOTAL" -gt 0 ]; then
    COMPLETION_RATE=$((COMPLETED * 100 / TOTAL))
else
    COMPLETION_RATE=0
fi

# 输出统计信息
echo "任务完成情况统计"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "总任务数:     $TOTAL"
echo "已完成:       $COMPLETED"
echo "进行中:       $IN_PROGRESS"
echo "待处理:       $PENDING"
echo "失败:         $FAILED"
echo "完成率:       ${COMPLETION_RATE}%"
echo "运行时长:     $DURATION_FORMATTED"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 检查是否全部完成
if [ "$TOTAL" -eq 0 ]; then
    echo "⚠️  没有任务"
    exit 0
elif [ "$PENDING" -eq 0 ] && [ "$IN_PROGRESS" -eq 0 ] && [ "$FAILED" -eq 0 ]; then
    echo "✅ 所有任务已完成"
    exit 0
elif [ "$FAILED" -gt 0 ]; then
    echo "❌ 有 $FAILED 个任务失败"
elif [ "$IN_PROGRESS" -gt 0 ] || [ "$PENDING" -gt 0 ]; then
    REMAINING=$((IN_PROGRESS + PENDING))
    echo "⏳ 还有 $REMAINING 个任务未完成"
fi

# 显示待处理任务
if [ "$SHOW_PENDING" == "true" ] && [ "$PENDING" -gt 0 ]; then
    echo ""
    echo "待处理任务列表:"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    jq -r --arg status "pending" '.tasks[] | select(.status == $status) | "  - [\(.id)] \(.description) (类型: \(.type))"' "$TASKS_JSON_PATH"
fi

# 显示失败任务
if [ "$SHOW_FAILED" == "true" ] && [ "$FAILED" -gt 0 ]; then
    echo ""
    echo "失败任务列表:"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    jq -r --arg status "failed" '.tasks[] | select(.status == $status) | "  - [\(.id)] \(.description) (类型: \(.type))"' "$TASKS_JSON_PATH"
fi

# 根据完成情况返回退出码
if [ "$PENDING" -eq 0 ] && [ "$IN_PROGRESS" -eq 0 ] && [ "$FAILED" -eq 0 ]; then
    exit 0
elif [ "$FAILED" -gt 0 ]; then
    exit 2  # 有失败任务
else
    exit 1  # 有未完成任务
fi

