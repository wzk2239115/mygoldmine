#!/bin/bash
# update-task.sh
# 更新 tasks.json 中的任务
#
# 用法：
#   update-task.sh <tasks_json_path> <task_id> --status <status> [--detail <json>] [--optional <true|false>]
#
# 参数：
#   tasks_json_path: tasks.json 文件的路径（必需）
#   task_id: 要更新的任务 ID（必需）
#   --status <status>: 更新任务状态（必需，可选值: pending, in_progress, completed, failed, skipped）
#   --detail <json>: 更新任务详情 JSON 字符串（可选）
#   --optional <true|false>: 更新任务是否可选（可选）
#
# 注意：description 字段只能在 init-task-json 或 add-task/add-tasks 时设置，不能通过此命令更新

set -euo pipefail

# 检查参数
if [ $# -lt 4 ]; then
    echo "错误: 缺少必需参数" >&2
    echo "用法: $(basename "$0") <tasks_json_path> <task_id> --status <status> [--detail <json>] [--optional <true|false>]" >&2
    exit 1
fi

TASKS_JSON_PATH="$1"
TASK_ID="$2"
shift 2

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
if ! jq -e --arg id "$TASK_ID" '.tasks[] | select(.id == $id)' "$TASKS_JSON_PATH" > /dev/null 2>&1; then
    echo "错误: 任务 ID 不存在: $TASK_ID" >&2
    exit 1
fi

# 解析参数
UPDATE_STATUS=""
UPDATE_DETAIL=""
UPDATE_OPTIONAL=""

# 检查第一个参数是否为 --status（必需）
if [ "$1" != "--status" ]; then
    echo "错误: --status 是必需参数，必须作为第一个参数提供" >&2
    echo "用法: $(basename "$0") <tasks_json_path> <task_id> --status <status> [--detail <json>] [--optional <true|false>]" >&2
    exit 1
fi

while [[ $# -gt 0 ]]; do
    case $1 in
        --status)
            UPDATE_STATUS="$2"
            if [[ ! "$UPDATE_STATUS" =~ ^(pending|in_progress|completed|failed|skipped)$ ]]; then
                echo "错误: 无效的状态值: $UPDATE_STATUS" >&2
                echo "有效值: pending, in_progress, completed, failed, skipped" >&2
                exit 1
            fi
            shift 2
            ;;
        --detail)
            UPDATE_DETAIL="$2"
            # 验证 detail JSON
            if ! echo "$UPDATE_DETAIL" | jq . > /dev/null 2>&1; then
                echo "错误: 无效的 JSON 格式: $UPDATE_DETAIL" >&2
                exit 1
            fi
            shift 2
            ;;
        --optional)
            UPDATE_OPTIONAL="$2"
            if [[ ! "$UPDATE_OPTIONAL" =~ ^(true|false)$ ]]; then
                echo "错误: --optional 必须是 true 或 false" >&2
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

# 检查 status 是否已提供（必需）
if [ -z "$UPDATE_STATUS" ]; then
    echo "错误: --status 是必需参数" >&2
    echo "用法: $(basename "$0") <tasks_json_path> <task_id> --status <status> [--detail <json>] [--optional <true|false>]" >&2
    exit 1
fi

# 检查：当状态为 completed 时，detail 为必填
if [[ "$UPDATE_STATUS" == "completed" ]]; then
    if [ -z "$UPDATE_DETAIL" ]; then
        echo "错误: 当任务状态为 'completed' 时，--detail 是必需参数" >&2
        echo "用法: $(basename "$0") <tasks_json_path> <task_id> --status completed --detail <json> [--optional <true|false>]" >&2
        exit 1
    fi
fi

# 更新 updated_at（使用中国时区 UTC+8）
CURRENT_TIME="$(TZ='Asia/Shanghai' date +"%Y-%m-%dT%H:%M:%S%z" | sed 's/\([0-9][0-9]\)$/:\1/')"

# 读取 created_at 并计算全局 duration
CREATED_AT=$(jq -r '.created_at' "$TASKS_JSON_PATH")
CREATED_TIMESTAMP=$(date -d "$CREATED_AT" +%s 2>/dev/null || echo "0")
CURRENT_TIMESTAMP=$(date +%s)
GLOBAL_DURATION=$((CURRENT_TIMESTAMP - CREATED_TIMESTAMP))

# 如果日期解析失败，duration 设为 0
if [ "$CREATED_TIMESTAMP" = "0" ]; then
    GLOBAL_DURATION=0
fi

# 读取当前任务的状态和start_at
CURRENT_TASK_STATUS=$(jq -r --arg id "$TASK_ID" '.tasks[] | select(.id == $id) | .status // "pending"' "$TASKS_JSON_PATH")
CURRENT_TASK_START_AT=$(jq -r --arg id "$TASK_ID" '.tasks[] | select(.id == $id) | .start_at // "null"' "$TASKS_JSON_PATH")

# 检查：禁止从 pending 状态直接切换到 completed 状态
if [[ "$CURRENT_TASK_STATUS" == "pending" && "$UPDATE_STATUS" == "completed" ]]; then
    echo "错误: 任务不能从 'pending' 状态直接切换到 'completed' 状态" >&2
    echo "请先将任务状态设置为 'in_progress'，再设置为 'completed'" >&2
    exit 1
fi

# 判断是否需要设置start_at（状态变为in_progress且start_at为null）
SHOULD_SET_START_AT=false
if [ "$UPDATE_STATUS" = "in_progress" ] && [ "$CURRENT_TASK_START_AT" = "null" ]; then
    SHOULD_SET_START_AT=true
fi

# 计算任务的duration
TASK_DURATION="null"
if [ "$SHOULD_SET_START_AT" = "true" ]; then
    # 刚开始，duration为0
    TASK_DURATION="0"
elif [ "$CURRENT_TASK_START_AT" != "null" ]; then
    # 已经有start_at，计算duration
    TASK_START_TIMESTAMP=$(date -d "$CURRENT_TASK_START_AT" +%s 2>/dev/null || echo "0")
    if [ "$TASK_START_TIMESTAMP" != "0" ]; then
        TASK_DURATION=$((CURRENT_TIMESTAMP - TASK_START_TIMESTAMP))
    else
        TASK_DURATION="null"
    fi
fi

# 构建 jq 命令参数
JQ_ARGS=()
JQ_EXPR=".tasks |= map(if .id == \"$TASK_ID\" then ."

if [ -n "$UPDATE_STATUS" ]; then
    JQ_EXPR="$JQ_EXPR | .status = \"$UPDATE_STATUS\""
fi

if [ -n "$UPDATE_DETAIL" ]; then
    # 使用 --argjson 安全地传递 JSON
    JQ_ARGS+=(--argjson detail "$UPDATE_DETAIL")
    JQ_EXPR="$JQ_EXPR | .detail = \$detail"
fi

if [ -n "$UPDATE_OPTIONAL" ]; then
    JQ_EXPR="$JQ_EXPR | .optional = $UPDATE_OPTIONAL"
fi

# 设置任务的start_at
if [ "$SHOULD_SET_START_AT" = "true" ]; then
    JQ_EXPR="$JQ_EXPR | .start_at = \"$CURRENT_TIME\""
fi

# 设置任务的update_at
JQ_EXPR="$JQ_EXPR | .update_at = \"$CURRENT_TIME\""

# 设置任务的duration
if [ "$TASK_DURATION" = "null" ]; then
    JQ_EXPR="$JQ_EXPR | .duration = null"
else
    JQ_EXPR="$JQ_EXPR | .duration = $TASK_DURATION"
fi

JQ_EXPR="$JQ_EXPR else . end) | .updated_at = \"$CURRENT_TIME\" | .duration = $GLOBAL_DURATION"

# 执行更新
TEMP_FILE=$(mktemp)
if [ ${#JQ_ARGS[@]} -gt 0 ]; then
    jq "${JQ_ARGS[@]}" "$JQ_EXPR" "$TASKS_JSON_PATH" > "$TEMP_FILE"
else
    jq "$JQ_EXPR" "$TASKS_JSON_PATH" > "$TEMP_FILE"
fi

# 更新 summary
jq \
    '.summary.total_tasks = (.tasks | length) |
     .summary.pending = ([.tasks[] | select(.status == "pending")] | length) |
     .summary.in_progress = ([.tasks[] | select(.status == "in_progress")] | length) |
     .summary.completed = ([.tasks[] | select(.status == "completed")] | length) |
     .summary.failed = ([.tasks[] | select(.status == "failed")] | length) |
     .summary.skipped = ([.tasks[] | select(.status == "skipped")] | length)' \
    "$TEMP_FILE" > "$TASKS_JSON_PATH"

rm -f "$TEMP_FILE"

# Schema 校验
validate_tasks_json() {
    local json_file="$1"
    local script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    local schema_file="$script_dir/schema/tasks.json.schema.json"
    local validator_script="$script_dir/validate-tasks-json.py"
    
    if [ ! -f "$schema_file" ]; then
        echo "警告: Schema 文件不存在: $schema_file，跳过校验" >&2
        return 0
    fi
    
    # 尝试使用 Python 脚本进行校验
    if command -v python3 &> /dev/null; then
        if [ -f "$validator_script" ]; then
            python3 "$validator_script" "$json_file" "$schema_file" 2>&1
        local validation_result=$?
        if [ $validation_result -ne 0 ]; then
            return $validation_result
            fi
        else
            echo "警告: 验证脚本不存在: $validator_script，跳过校验" >&2
        fi
    else
        echo "警告: Python3 未安装，跳过 Schema 校验" >&2
    fi
}

# 执行校验
if ! validate_tasks_json "$TASKS_JSON_PATH"; then
    echo "错误: tasks.json 未通过 Schema 校验" >&2
    exit 1
fi

echo "✓ 已更新任务: $TASK_ID"
if [ -n "$UPDATE_STATUS" ]; then
    echo "  - 状态: $UPDATE_STATUS"
fi
if [ -n "$UPDATE_DETAIL" ]; then
    echo "  - 详情: 已更新"
fi
if [ -n "$UPDATE_OPTIONAL" ]; then
    echo "  - 可选: $UPDATE_OPTIONAL"
fi
echo "✓ Schema 校验通过"

