#!/bin/bash
# init-task-json.sh
# 初始化 tasks.json 文件
#
# 用法：
#   init-task-json.sh <tasks_json_path> <agent_task_id> <agent_name> --description <text> [--tasks <json>]
#
# 参数：
#   tasks_json_path: tasks.json 文件的路径（必需）
#   agent_task_id: 任务列表唯一标识符，用于区分同一 agent 的不同任务列表（必需）
#   agent_name: 代理名称（必需）
#   --description <text>: 任务列表描述（必需，非空）
#   --tasks <json>: 初始任务列表的 JSON 字符串（可选）
#                   格式: '[{"id":"task-001","description":"任务描述"},{"id":"task-002","description":"任务描述2","type":"code_scan"}]'
#
# 任务格式说明：
#   每个任务对象至少需要包含：
#   - id: 任务ID（必需）
#   - description: 任务描述（必需）
#   - type: 任务类型（可选，默认: "general"）
#   - optional: 是否可选（可选，默认: false）

set -euo pipefail

# 检查参数
if [ $# -lt 3 ]; then
    echo "错误: 缺少必需参数" >&2
    echo "用法: $(basename "$0") <tasks_json_path> <agent_task_id> <agent_name> [--tasks <json>]" >&2
    exit 1
fi

TASKS_JSON_PATH="$1"
AGENT_TASK_ID="$2"
AGENT_NAME="$3"
INITIAL_TASKS_JSON=""
DESCRIPTION=""

# 解析可选参数
shift 3
while [[ $# -gt 0 ]]; do
    case $1 in
        --description)
            if [ -z "${2:-}" ]; then
                echo "错误: --description 需要提供非空字符串" >&2
                exit 1
            fi
            DESCRIPTION="$2"
            shift 2
            ;;
        --tasks)
            if [ -z "${2:-}" ]; then
                echo "错误: --tasks 需要提供 JSON 字符串" >&2
                exit 1
            fi
            INITIAL_TASKS_JSON="$2"
            shift 2
            ;;
        *)
            echo "错误: 未知参数: $1" >&2
            exit 1
            ;;
    esac
done

# 参数格式验证
# 检查 tasks_json_path 格式
if [ -z "$TASKS_JSON_PATH" ]; then
    echo "错误: tasks_json_path 不能为空" >&2
    exit 1
fi

# 检查路径是否以 .json 结尾
if [[ ! "$TASKS_JSON_PATH" =~ \.json$ ]]; then
    echo "错误: tasks_json_path 必须以 .json 结尾" >&2
    echo "  提供的路径: $TASKS_JSON_PATH" >&2
    exit 1
fi

# 检查路径中是否包含非法字符（不允许空字符和控制字符）
if [[ "$TASKS_JSON_PATH" =~ [[:cntrl:]] ]]; then
    echo "错误: tasks_json_path 包含非法字符" >&2
    exit 1
fi

# 检查路径长度（避免过长的路径）
if [ ${#TASKS_JSON_PATH} -gt 4096 ]; then
    echo "错误: tasks_json_path 路径过长（超过 4096 字符）" >&2
    exit 1
fi

# 检查 agent_task_id 格式
if [ -z "$AGENT_TASK_ID" ]; then
    echo "错误: agent_task_id 不能为空" >&2
    exit 1
fi

# agent_task_id 应该只包含字母、数字、连字符和下划线
if [[ ! "$AGENT_TASK_ID" =~ ^[a-zA-Z0-9_-]+$ ]]; then
    echo "错误: agent_task_id 只能包含字母、数字、连字符(-)和下划线(_)" >&2
    echo "  提供的 ID: $AGENT_TASK_ID" >&2
    exit 1
fi

# 检查长度（合理的长度限制）
if [ ${#AGENT_TASK_ID} -gt 100 ]; then
    echo "错误: agent_task_id 过长（超过 100 字符）" >&2
    exit 1
fi

# 检查 agent_name 格式（必需字段）
if [ -z "$AGENT_NAME" ]; then
    echo "错误: agent_name 不能为空" >&2
    exit 1
fi

# agent_name 应该只包含字母、数字、连字符和下划线
if [[ ! "$AGENT_NAME" =~ ^[a-zA-Z0-9_-]+$ ]]; then
    echo "错误: agent_name 只能包含字母、数字、连字符(-)和下划线(_)" >&2
    echo "  提供的名称: $AGENT_NAME" >&2
    exit 1
fi

# 检查长度（合理的长度限制）
if [ ${#AGENT_NAME} -gt 100 ]; then
    echo "错误: agent_name 过长（超过 100 字符）" >&2
    exit 1
fi

# 不能以连字符或下划线开头或结尾
if [[ "$AGENT_NAME" =~ ^[-_] ]] || [[ "$AGENT_NAME" =~ [-_]$ ]]; then
    echo "错误: agent_name 不能以连字符(-)或下划线(_)开头或结尾" >&2
    exit 1
fi

# 校验 description（必填）
if [ -z "$DESCRIPTION" ]; then
    echo "错误: --description 不能为空" >&2
    exit 1
fi
if [[ "$DESCRIPTION" =~ [[:cntrl:]] ]]; then
    echo "错误: description 含有控制字符" >&2
    exit 1
fi
if [ ${#DESCRIPTION} -gt 1024 ]; then
    echo "错误: description 过长（超过 1024 字符）" >&2
    exit 1
fi

# 检查 jq 是否安装
if ! command -v jq &> /dev/null; then
    echo "错误: 需要安装 jq 工具来处理 JSON" >&2
    echo "安装方法: sudo apt-get install jq 或 brew install jq" >&2
    exit 1
fi

# 获取 tasks.json 的目录
TASKS_JSON_DIR="$(dirname "$TASKS_JSON_PATH")"

# 如果目录不存在，创建它
if [ ! -d "$TASKS_JSON_DIR" ]; then
    mkdir -p "$TASKS_JSON_DIR"
    echo "已创建目录: $TASKS_JSON_DIR"
fi

# 如果文件已存在，直接报错
if [ -f "$TASKS_JSON_PATH" ]; then
    echo "错误: 文件已存在: $TASKS_JSON_PATH" >&2
    echo "提示: 请删除现有文件或使用不同的路径" >&2
    exit 1
fi

# 处理初始任务列表
process_initial_tasks() {
    local tasks_json="[]"
    
    # 如果提供了 --tasks，使用提供的 JSON
    if [ -n "$INITIAL_TASKS_JSON" ]; then
        tasks_json="$INITIAL_TASKS_JSON"
    else
        # 没有初始任务，返回空数组
        echo "[]"
        return 0
    fi
    
    # 验证 JSON 格式
    if ! echo "$tasks_json" | jq . > /dev/null 2>&1; then
        echo "错误: 初始任务列表不是有效的 JSON 格式" >&2
        exit 1
    fi
    
    # 验证是否为数组
    if ! echo "$tasks_json" | jq 'type == "array"' | grep -q true; then
        echo "错误: 初始任务列表必须是 JSON 数组" >&2
        exit 1
    fi
    
    # 处理每个任务，确保包含必需字段
    echo "$tasks_json" | jq -c 'map(
        if .id == null or .id == "" then
            error("任务缺少必需的 id 字段")
        elif .description == null or .description == "" then
            error("任务缺少必需的 description 字段")
        else
            {
                id: .id,
                type: (.type // "general"),
                status: "pending",
                description: .description,
                optional: (.optional // false),
                detail: (.detail // {})
            }
        end
    )'
}

# 验证任务 ID 格式
validate_task_ids() {
    local tasks_json="$1"
    local task_ids=$(echo "$tasks_json" | jq -r '.[].id // empty')
    
    for task_id in $task_ids; do
        if [ -z "$task_id" ]; then
            echo "错误: 任务 ID 不能为空" >&2
            exit 1
        fi
        
        # 验证任务 ID 格式（字母、数字、连字符和下划线）
        if [[ ! "$task_id" =~ ^[a-zA-Z0-9_-]+$ ]]; then
            echo "错误: 任务 ID 格式无效: $task_id（只能包含字母、数字、连字符(-)和下划线(_)）" >&2
            exit 1
        fi
    done
    
    # 检查是否有重复的 ID
    local unique_count=$(echo "$tasks_json" | jq '[.[].id] | unique | length')
    local total_count=$(echo "$tasks_json" | jq 'length')
    if [ "$unique_count" -ne "$total_count" ]; then
        echo "错误: 初始任务列表中存在重复的任务 ID" >&2
        exit 1
    fi
}

# 生成当前时间戳（使用中国时区 UTC+8）
CURRENT_TIME="$(TZ='Asia/Shanghai' date +"%Y-%m-%dT%H:%M:%S%z" | sed 's/\([0-9][0-9]\)$/:\1/')"

# 处理初始任务
INITIAL_TASKS=$(process_initial_tasks)

# 验证任务 ID
if [ "$INITIAL_TASKS" != "[]" ]; then
    validate_task_ids "$INITIAL_TASKS"
fi

# 计算初始任务统计
TOTAL_TASKS=$(echo "$INITIAL_TASKS" | jq 'length')
PENDING_TASKS=$TOTAL_TASKS

# 创建初始 JSON 结构
TEMP_FILE=$(mktemp)
jq -n \
    --arg agent "$AGENT_NAME" \
    --arg agent_task_id "$AGENT_TASK_ID" \
    --arg description "$DESCRIPTION" \
    --arg created_at "$CURRENT_TIME" \
    --arg updated_at "$CURRENT_TIME" \
    --argjson tasks "$INITIAL_TASKS" \
    --argjson total_tasks "$TOTAL_TASKS" \
    --argjson pending "$PENDING_TASKS" \
    '{
        "agent": $agent,
        "agent_task_id": $agent_task_id,
        "description": $description,
        "created_at": $created_at,
        "updated_at": $updated_at,
        "tasks": $tasks,
        "summary": {
            "total_tasks": $total_tasks,
            "completed": 0,
            "in_progress": 0,
            "pending": $pending,
            "failed": 0
        }
    }' > "$TEMP_FILE"

mv "$TEMP_FILE" "$TASKS_JSON_PATH"

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

echo "✓ 已初始化 tasks.json: $TASKS_JSON_PATH"
echo "  - Agent: $AGENT_NAME"
echo "  - Agent Task ID: $AGENT_TASK_ID"
echo "  - 创建时间: $CURRENT_TIME"
if [ "$TOTAL_TASKS" -gt 0 ]; then
    echo "  - 初始任务数: $TOTAL_TASKS"
fi
echo "✓ Schema 校验通过"

