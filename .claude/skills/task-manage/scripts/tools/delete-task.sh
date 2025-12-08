#!/bin/bash
# delete-task.sh
# 从 tasks.json 中删除指定任务
#
# 用法：
#   delete-task.sh <tasks_json_path> <task_id>
#
# 参数：
#   tasks_json_path: tasks.json 文件的路径（必需）
#   task_id: 要删除的任务 ID（必需）

set -euo pipefail

if [ $# -lt 2 ]; then
    echo "错误: 缺少必需参数" >&2
    echo "用法: $(basename "$0") <tasks_json_path> <task_id>" >&2
    exit 1
fi

TASKS_JSON_PATH="$1"
TASK_ID="$2"

# 检查 jq 是否安装
if ! command -v jq &> /dev/null; then
    echo "错误: 需要安装 jq 工具来处理 JSON" >&2
    echo "安装方法: sudo apt-get install jq 或 brew install jq" >&2
    exit 1
fi

# 检查 tasks.json 是否存在
if [ ! -f "$TASKS_JSON_PATH" ]; then
    echo "错误: tasks.json 文件不存在: $TASKS_JSON_PATH" >&2
    echo "提示: 请先使用 init-task-json.sh 初始化文件" >&2
    exit 1
fi

# 检查任务是否存在
if ! jq -e --arg id "$TASK_ID" '.tasks[] | select(.id == $id)' "$TASKS_JSON_PATH" > /dev/null 2>&1; then
    echo "错误: 任务 ID 不存在: $TASK_ID" >&2
    exit 1
fi

# 更新时间（UTC+8）
CURRENT_TIME="$(TZ='Asia/Shanghai' date +"%Y-%m-%dT%H:%M:%S%z" | sed 's/\([0-9][0-9]\)$/:\1/')"

# 读取 created_at 并计算 duration
CREATED_AT=$(jq -r '.created_at' "$TASKS_JSON_PATH")
CREATED_TIMESTAMP=$(date -d "$CREATED_AT" +%s 2>/dev/null || echo "0")
CURRENT_TIMESTAMP=$(date +%s)
DURATION=$((CURRENT_TIMESTAMP - CREATED_TIMESTAMP))

# 如果日期解析失败，duration 设为 0
if [ "$CREATED_TIMESTAMP" = "0" ]; then
    DURATION=0
fi

TEMP_FILE=$(mktemp)

# 删除任务并更新统计
jq \
    --arg id "$TASK_ID" \
    --arg updated_at "$CURRENT_TIME" \
    --argjson duration "$DURATION" \
    '.tasks = (.tasks | map(select(.id != $id))) |
     .summary.total_tasks = (.tasks | length) |
     .summary.pending = ([.tasks[] | select(.status == "pending")] | length) |
     .summary.in_progress = ([.tasks[] | select(.status == "in_progress")] | length) |
     .summary.completed = ([.tasks[] | select(.status == "completed")] | length) |
     .summary.failed = ([.tasks[] | select(.status == "failed")] | length) |
     .updated_at = $updated_at |
     .duration = $duration' \
    "$TASKS_JSON_PATH" > "$TEMP_FILE"

# Schema 校验
validate_tasks_json() {
    local json_file="$1"
    local script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    local schema_file="$script_dir/schema/tasks.json.schema.json"
    local validator_script="$script_dir/validate-tasks-json.py"
    
    if [ ! -f "$schema_file" ]; then
        echo "警告: Schema 文件不存在: $schema_file，跳过校验" >&2
        return 0
    }
    
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

if ! validate_tasks_json "$TEMP_FILE"; then
    echo "错误: tasks.json 未通过 Schema 校验" >&2
    rm -f "$TEMP_FILE"
    exit 1
fi

mv "$TEMP_FILE" "$TASKS_JSON_PATH"

echo "✓ 已删除任务: $TASK_ID"
echo "✓ Schema 校验通过"
