#!/bin/bash
# .claude/scripts/setup.sh
# 设置开发环境，将 tools 目录添加到 PATH
#
# 用法：
#   source .claude/scripts/setup.sh
#   或
#   . .claude/scripts/setup.sh

# 获取脚本所在目录的绝对路径
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# tools 目录与脚本在同一目录
TOOLS_DIR="$SCRIPT_DIR/tools"

# 检查 tools 目录是否存在
if [ ! -d "$TOOLS_DIR" ]; then
    echo "警告: tools 目录不存在: $TOOLS_DIR"
    echo "是否创建该目录? (y/n)"
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        mkdir -p "$TOOLS_DIR"
        echo "已创建 tools 目录: $TOOLS_DIR"
    else
        echo "跳过 PATH 设置"
        return 0 2>/dev/null || exit 0
    fi
fi

# 检查 tools 目录是否已在 PATH 中
if [[ ":$PATH:" != *":$TOOLS_DIR:"* ]]; then
    export PATH="$TOOLS_DIR:$PATH"
    echo "✓ 已将 $TOOLS_DIR 添加到 PATH"
else
    echo "✓ $TOOLS_DIR 已在 PATH 中"
fi

# 创建符号链接（不带 .sh 后缀）
SCRIPTS=("init-task-json" "add-task" "add-tasks" "update-task" "read-task" "list-tasks" "check-task")
LINK_COUNT=0

echo ""
echo "创建符号链接..."

create_symlink() {
    local script_name=$1
    local script_file="$TOOLS_DIR/${script_name}.sh"
    local link_file="$TOOLS_DIR/${script_name}"
    
    if [ ! -f "$script_file" ]; then
        echo "  ⚠ 脚本文件不存在: ${script_file}"
        return 1
    fi
    
    if [ -L "$link_file" ]; then
        local target=$(readlink "$link_file")
        if [ "$target" = "${script_name}.sh" ]; then
            echo "  ✓ $script_name -> $script_name.sh (已存在)"
            return 0
        else
            echo "  ⚠ $link_file 已存在但指向不同目标，跳过"
            return 1
        fi
    elif [ -e "$link_file" ]; then
        echo "  ⚠ $link_file 已存在但不是符号链接，跳过"
        return 1
    else
        if ln -s "${script_name}.sh" "$link_file" 2>/dev/null; then
            echo "  ✓ 创建链接: $script_name -> $script_name.sh"
            return 0
        else
            echo "  ✗ 创建链接失败: $script_name"
            return 1
        fi
    fi
}

# 为所有脚本创建符号链接
for script in "${SCRIPTS[@]}"; do
    if create_symlink "$script"; then
        LINK_COUNT=$((LINK_COUNT + 1))
    fi
done

echo "✓ 符号链接创建完成 (${LINK_COUNT}/${#SCRIPTS[@]})"
echo ""
echo "环境设置完成"
echo "当前 PATH 中的 tools 目录: $TOOLS_DIR"

