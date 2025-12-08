#!/bin/bash
# add-task.sh
# 添加任务到 tasks.json
#
# 用法：
#   add-task.sh <tasks_json_path> <task_id> <task_type> <description> [--optional] [--before <task_id>]
#
# 参数：
#   tasks_json_path: tasks.json 文件的路径（必需）
#   task_id: 任务 ID（必需，如 "task-001"）
#   task_type: 任务类型（必需，如 "asset_discovery"）
#   description: 任务描述（必需）
#   --optional: 标记任务为可选
#   --before <task_id>: 指定新任务必须在此任务之前完成（用于控制插入顺序）

set -euo pipefail

# 检查参数
if [ $# -lt 4 ]; then
    echo "错误: 缺少必需参数" >&2
    echo "用法: $(basename "$0") <tasks_json_path> <task_id> <task_type> <description> [--optional] [--before <task_id>]" >&2
    exit 1
fi

TASKS_JSON_PATH="$1"
TASK_ID="$2"
TASK_TYPE="$3"
DESCRIPTION="$4"
shift 4

# 参数验证：task_id 不能为空或仅包含空白字符
if [ -z "$TASK_ID" ] || [ -z "${TASK_ID// }" ]; then
    echo "错误: task_id 不能为空" >&2
    exit 1
fi

# 参数验证：task_type 不能为空或仅包含空白字符
if [ -z "$TASK_TYPE" ] || [ -z "${TASK_TYPE// }" ]; then
    echo "错误: task_type 不能为空" >&2
    exit 1
fi

# 参数验证：description 不能为空或仅包含空白字符
if [ -z "$DESCRIPTION" ] || [ -z "${DESCRIPTION// }" ]; then
    echo "错误: description 不能为空" >&2
    exit 1
fi

# 默认值
STATUS="pending"
OPTIONAL=false
DETAIL="{}"
BEFORE_TASK_ID=""

# 解析可选参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --optional)
            OPTIONAL=true
            shift
            ;;
        --before)
            if [ $# -lt 2 ]; then
                echo "错误: --before 选项需要指定任务 ID" >&2
                exit 1
            fi
            BEFORE_TASK_ID="$2"
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
    echo "提示: 请先使用 init-task-json.sh 初始化文件" >&2
    exit 1
fi

# 检查任务 ID 是否已存在
if jq -e --arg id "$TASK_ID" '.tasks[] | select(.id == $id)' "$TASKS_JSON_PATH" > /dev/null 2>&1; then
    echo "错误: 任务 ID 已存在: $TASK_ID" >&2
    exit 1
fi

# 如果指定了 --before，检查目标任务是否存在
if [ -n "$BEFORE_TASK_ID" ]; then
    if ! jq -e --arg id "$BEFORE_TASK_ID" '.tasks[] | select(.id == $id)' "$TASKS_JSON_PATH" > /dev/null 2>&1; then
        echo "错误: --before 指定的任务 ID 不存在: $BEFORE_TASK_ID" >&2
        exit 1
    fi
fi

# 更新 updated_at（使用中国时区 UTC+8）
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

# 创建新任务对象
NEW_TASK=$(jq -n \
    --arg id "$TASK_ID" \
    --arg type "$TASK_TYPE" \
    --arg status "$STATUS" \
    --arg desc "$DESCRIPTION" \
    --argjson optional "$OPTIONAL" \
    --argjson detail "$DETAIL" \
    '{
        "id": $id,
        "type": $type,
        "status": $status,
        "description": $desc,
        "optional": $optional,
        "detail": $detail,
        "start_at": null,
        "update_at": null,
        "duration": null
    }')

# 添加任务到 tasks 数组
TEMP_FILE=$(mktemp)
if [ -n "$BEFORE_TASK_ID" ]; then
    # 如果指定了 --before，插入到指定任务之前
    # 使用 reduce 来构建新数组，在遇到目标任务时先插入新任务
    jq \
        --argjson new_task "$NEW_TASK" \
        --arg before_id "$BEFORE_TASK_ID" \
        --arg updated_at "$CURRENT_TIME" \
        --argjson duration "$DURATION" \
        '.tasks = (.tasks | reduce .[] as $item ([];
            if $item.id == $before_id then . + [$new_task, $item] else . + [$item] end
        )) | .updated_at = $updated_at | .duration = $duration' \
        "$TASKS_JSON_PATH" > "$TEMP_FILE"
else
    # 否则追加到末尾
    jq \
        --argjson new_task "$NEW_TASK" \
        --arg updated_at "$CURRENT_TIME" \
        --argjson duration "$DURATION" \
        '.tasks += [$new_task] | .updated_at = $updated_at | .duration = $duration' \
        "$TASKS_JSON_PATH" > "$TEMP_FILE"
fi

# 更新 summary
jq \
    --argjson new_task "$NEW_TASK" \
    '.summary.total_tasks = (.tasks | length) |
     .summary.pending = ([.tasks[] | select(.status == "pending")] | length) |
     .summary.in_progress = ([.tasks[] | select(.status == "in_progress")] | length) |
     .summary.completed = ([.tasks[] | select(.status == "completed")] | length) |
     .summary.failed = ([.tasks[] | select(.status == "failed")] | length)' \
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

echo "✓ 已添加任务: $TASK_ID"
echo "  - 类型: $TASK_TYPE"
echo "  - 状态: $STATUS"
echo "  - 描述: $DESCRIPTION"
echo "  - 可选: $OPTIONAL"
if [ -n "$BEFORE_TASK_ID" ]; then
    echo "  - 插入位置: 在任务 $BEFORE_TASK_ID 之前"
fi
echo "✓ Schema 校验通过"

