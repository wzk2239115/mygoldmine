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

echo "环境设置完成"
echo "当前 PATH 中的 tools 目录: $TOOLS_DIR"

