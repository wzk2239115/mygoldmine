#!/bin/bash
# add-tasks.sh
# 批量添加任务到 tasks.json
#
# 用法：
#   add-tasks.sh <tasks_json_path> [--before <task_id>] <tasks_json_file>
#   add-tasks.sh <tasks_json_path> [--before <task_id>] --json <tasks_json_string>
#
# 参数：
#   tasks_json_path: tasks.json 文件的路径（必需）
#   tasks_json_file: 包含任务数组的 JSON 文件路径
#   --before <task_id>: 将所有新增任务插入到指定任务之前（若单个任务内含 before 字段，则优先使用该字段）
#   --json <tasks_json_string>: 直接提供任务数组的 JSON 字符串
#
# 任务 JSON 格式：
#   [
#     {
#       "id": "task-001",
#       "type": "asset_discovery",
#       "description": "识别资产位置",
#       "optional": false,
#       "before": "task-002"  // 可选，指定插入位置
#     },
#     {
#       "id": "task-002",
#       "type": "code_scan",
#       "description": "扫描代码",
#       "optional": true
#     }
#   ]

set -euo pipefail

# 检查参数
if [ $# -lt 2 ]; then
    echo "错误: 缺少必需参数" >&2
    echo "用法: $(basename "$0") <tasks_json_path> [--before <task_id>] <tasks_json_file>" >&2
    echo "用法: $(basename "$0") <tasks_json_path> [--before <task_id>] --json <tasks_json_string>" >&2
    exit 1
fi

TASKS_JSON_PATH="$1"
shift

# 解析全局 --before
GLOBAL_BEFORE=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --before)
            if [ $# -lt 2 ]; then
                echo "错误: --before 选项需要指定任务 ID" >&2
                exit 1
            fi
            GLOBAL_BEFORE="$2"
            shift 2
            ;;
        *)
            break
            ;;
    esac
done

# 确保仍有任务数据参数
if [ $# -lt 1 ]; then
    echo "错误: 缺少任务数据参数" >&2
    echo "用法: $(basename "$0") <tasks_json_path> [--before <task_id>] <tasks_json_file>" >&2
    echo "用法: $(basename "$0") <tasks_json_path> [--before <task_id>] --json <tasks_json_string>" >&2
    exit 1
fi

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

# 解析任务数据
TASKS_DATA=""
if [ "$1" = "--json" ]; then
    if [ $# -lt 2 ]; then
        echo "错误: --json 选项需要提供 JSON 字符串" >&2
        exit 1
    fi
    TASKS_DATA="$2"
    # 验证 JSON 格式
    if ! echo "$TASKS_DATA" | jq . > /dev/null 2>&1; then
        echo "错误: 无效的 JSON 格式" >&2
        exit 1
    fi
else
    TASKS_FILE="$1"
    if [ ! -f "$TASKS_FILE" ]; then
        echo "错误: 任务文件不存在: $TASKS_FILE" >&2
        exit 1
    fi
    # 验证 JSON 格式
    if ! jq . "$TASKS_FILE" > /dev/null 2>&1; then
        echo "错误: 无效的 JSON 格式: $TASKS_FILE" >&2
        exit 1
    fi
    TASKS_DATA=$(cat "$TASKS_FILE")
fi

# 验证任务数组格式
if ! echo "$TASKS_DATA" | jq 'type == "array"' > /dev/null 2>&1; then
    echo "错误: 任务数据必须是数组格式" >&2
    exit 1
fi

# 获取脚本目录（用于调用 add-task.sh）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ADD_TASK_SCRIPT="$SCRIPT_DIR/add-task.sh"

# 检查 add-task.sh 是否存在
if [ ! -f "$ADD_TASK_SCRIPT" ]; then
    echo "错误: add-task.sh 不存在: $ADD_TASK_SCRIPT" >&2
    exit 1
fi

# 统计信息
TOTAL_TASKS=$(echo "$TASKS_DATA" | jq 'length')
SUCCESS_COUNT=0
FAILED_COUNT=0
FAILED_TASKS=()

# 遍历每个任务并添加
TASK_INDEX=0
while [ $TASK_INDEX -lt $TOTAL_TASKS ]; do
    TASK=$(echo "$TASKS_DATA" | jq -r ".[$TASK_INDEX]")
    
    # 提取任务字段
    TASK_ID=$(echo "$TASK" | jq -r '.id // empty')
    TASK_TYPE=$(echo "$TASK" | jq -r '.type // empty')
    DESCRIPTION=$(echo "$TASK" | jq -r '.description // empty')
    OPTIONAL=$(echo "$TASK" | jq -r '.optional // false')
    BEFORE_TASK_ID=$(echo "$TASK" | jq -r '.before // empty')
    if [ -z "$BEFORE_TASK_ID" ] && [ -n "$GLOBAL_BEFORE" ]; then
        BEFORE_TASK_ID="$GLOBAL_BEFORE"
    fi
    
    # 验证必需字段
    if [ -z "$TASK_ID" ] || [ -z "$TASK_TYPE" ] || [ -z "$DESCRIPTION" ]; then
        echo "警告: 跳过任务 #$((TASK_INDEX + 1))，缺少必需字段 (id, type, description)" >&2
        FAILED_COUNT=$((FAILED_COUNT + 1))
        FAILED_TASKS+=("任务 #$((TASK_INDEX + 1))")
        TASK_INDEX=$((TASK_INDEX + 1))
        continue
    fi
    
    # 构建 add-task.sh 命令
    CMD="$ADD_TASK_SCRIPT \"$TASKS_JSON_PATH\" \"$TASK_ID\" \"$TASK_TYPE\" \"$DESCRIPTION\""
    
    if [ "$OPTIONAL" = "true" ]; then
        CMD="$CMD --optional"
    fi
    
    if [ -n "$BEFORE_TASK_ID" ] && [ "$BEFORE_TASK_ID" != "null" ]; then
        CMD="$CMD --before \"$BEFORE_TASK_ID\""
    fi
    
    # 执行添加任务
    if eval "$CMD" > /dev/null 2>&1; then
        SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
        echo "✓ [$((TASK_INDEX + 1))/$TOTAL_TASKS] 已添加任务: $TASK_ID"
    else
        FAILED_COUNT=$((FAILED_COUNT + 1))
        FAILED_TASKS+=("$TASK_ID")
        echo "✗ [$((TASK_INDEX + 1))/$TOTAL_TASKS] 添加任务失败: $TASK_ID" >&2
    fi
    
    TASK_INDEX=$((TASK_INDEX + 1))
done

# 输出统计信息
echo ""
echo "批量添加完成:"
echo "  - 总计: $TOTAL_TASKS"
echo "  - 成功: $SUCCESS_COUNT"
echo "  - 失败: $FAILED_COUNT"

if [ $FAILED_COUNT -gt 0 ]; then
    echo "  - 失败的任务: ${FAILED_TASKS[*]}"
    exit 1
fi

