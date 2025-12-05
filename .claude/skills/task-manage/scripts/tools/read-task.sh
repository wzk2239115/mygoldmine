#!/bin/bash
# read-task.sh
# 获取任务详情
#
# 用法：
#   read-task.sh <tasks_json_path> <task_id> [--format <json|pretty>]
#
# 参数：
#   tasks_json_path: tasks.json 文件的路径（必需）
#   task_id: 任务 ID（必需）
#   --format <json|pretty>: 输出格式（可选，默认: pretty）
#     json: 输出原始 JSON
#     pretty: 输出格式化的可读文本

set -euo pipefail

# 检查参数
if [ $# -lt 2 ]; then
    echo "错误: 缺少必需参数" >&2
    echo "用法: $(basename "$0") <tasks_json_path> <task_id> [--format <json|pretty>]" >&2
    exit 1
fi

TASKS_JSON_PATH="$1"
TASK_ID="$2"
shift 2

# 默认值
OUTPUT_FORMAT="pretty"

# 解析可选参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --format)
            OUTPUT_FORMAT="$2"
            if [[ ! "$OUTPUT_FORMAT" =~ ^(json|pretty)$ ]]; then
                echo "错误: 无效的格式值: $OUTPUT_FORMAT" >&2
                echo "有效值: json, pretty" >&2
                exit 1
            fi
            shift 2
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

# 检查任务是否存在
TASK=$(jq -e --arg id "$TASK_ID" '.tasks[] | select(.id == $id)' "$TASKS_JSON_PATH" 2>/dev/null)

if [ -z "$TASK" ]; then
    echo "错误: 任务 ID 不存在: $TASK_ID" >&2
    exit 1
fi

# 根据格式输出
if [ "$OUTPUT_FORMAT" == "json" ]; then
    echo "$TASK" | jq .
else
    # 格式化输出
    echo "任务详情:"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "ID:          $(echo "$TASK" | jq -r '.id')"
    echo "类型:        $(echo "$TASK" | jq -r '.type')"
    echo "状态:        $(echo "$TASK" | jq -r '.status')"
    echo "描述:        $(echo "$TASK" | jq -r '.description')"
    echo "可选:        $(echo "$TASK" | jq -r 'if .optional then "是" else "否" end')"
    echo "详情:"
    echo "$TASK" | jq -r '.detail' | jq .
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
fi

