#!/bin/bash
# list-tasks.sh
# 获取任务列表
#
# 用法：
#   list-tasks.sh <tasks_json_path> [--format <json|pretty>] [--status <status>] [--type <type>] [--optional] [--required]
#
# 参数：
#   tasks_json_path: tasks.json 文件的路径（必需）
#   --format <json|pretty>: 输出格式（可选，默认: pretty）
#     json: 输出原始 JSON
#     pretty: 输出格式化的可读文本
#   --status <pending|in_progress|completed|failed|skipped>: 按状态过滤任务（可选）
#   --type <task_type>: 按任务类型过滤（可选）
#   --optional: 只显示可选任务（可选）
#   --required: 只显示必需任务（可选）

set -euo pipefail

# 检查参数
if [ $# -lt 1 ]; then
    echo "错误: 缺少必需参数" >&2
    echo "用法: $(basename "$0") <tasks_json_path> [--format <json|pretty>] [--status <status>] [--type <type>] [--optional] [--required]" >&2
    exit 1
fi

TASKS_JSON_PATH="$1"
shift 1

# 默认值
OUTPUT_FORMAT="pretty"
STATUS_FILTER=""
TYPE_FILTER=""
OPTIONAL_FILTER=""

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
        --status)
            STATUS_FILTER="$2"
            if [[ ! "$STATUS_FILTER" =~ ^(pending|in_progress|completed|failed|skipped)$ ]]; then
                echo "错误: 无效的状态值: $STATUS_FILTER" >&2
                echo "有效值: pending, in_progress, completed, failed, skipped" >&2
                exit 1
            fi
            shift 2
            ;;
        --type)
            TYPE_FILTER="$2"
            shift 2
            ;;
        --optional)
            if [ -n "$OPTIONAL_FILTER" ]; then
                echo "错误: --optional 和 --required 不能同时使用" >&2
                exit 1
            fi
            OPTIONAL_FILTER="true"
            shift
            ;;
        --required)
            if [ -n "$OPTIONAL_FILTER" ]; then
                echo "错误: --optional 和 --required 不能同时使用" >&2
                exit 1
            fi
            OPTIONAL_FILTER="false"
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

# 构建 jq 过滤表达式
JQ_FILTER=".tasks[]"

# 添加状态过滤
if [ -n "$STATUS_FILTER" ]; then
    JQ_FILTER="$JQ_FILTER | select(.status == \"$STATUS_FILTER\")"
fi

# 添加类型过滤
if [ -n "$TYPE_FILTER" ]; then
    JQ_FILTER="$JQ_FILTER | select(.type == \"$TYPE_FILTER\")"
fi

# 添加可选性过滤
if [ -n "$OPTIONAL_FILTER" ]; then
    JQ_FILTER="$JQ_FILTER | select(.optional == $OPTIONAL_FILTER)"
fi

# 根据格式输出
if [ "$OUTPUT_FORMAT" == "json" ]; then
    # JSON 格式输出
    jq "[$JQ_FILTER]" "$TASKS_JSON_PATH"
else
    # 格式化输出
    TASKS=$(jq "[$JQ_FILTER]" "$TASKS_JSON_PATH")
    TASK_COUNT=$(echo "$TASKS" | jq 'length')
    
    if [ "$TASK_COUNT" -eq 0 ]; then
        echo "没有找到匹配的任务"
        exit 0
    fi
    
    # 显示任务列表
    echo "任务列表 (共 $TASK_COUNT 个任务)"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # 遍历每个任务并格式化输出
    echo "$TASKS" | jq -r '.[] |
        "[" + .id + "]\n" +
        "  类型:        " + .type + "\n" +
        "  状态:        " + .status + "\n" +
        "  描述:        " + .description + "\n" +
        "  可选:        " + (if .optional then "是" else "否" end) + "\n" +
        "  开始时间:    " + (if .start_at != null then .start_at else "未开始" end) + "\n" +
        "  更新时间:    " + (if .update_at != null then .update_at else "未更新" end) + "\n" +
        "  运行时长:    " + (if .duration != null then (.duration | tostring) + "秒" else "未开始" end) + "\n" +
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"'
fi

