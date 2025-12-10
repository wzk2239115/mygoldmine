#!/bin/bash
# .claude/skills/task-manage/scripts/install.sh
# 自动安装/卸载 task-manage 工具集
#
# 用法：
#   安装：
#     bash install.sh [--no-interactive]
#     ./install.sh [--no-interactive]
#
#   卸载：
#     bash install.sh --uninstall [--no-interactive]
#     ./install.sh --uninstall [--no-interactive]
#
# 选项：
#   --uninstall: 卸载模式，删除符号链接和 PATH 配置
#   --no-interactive: 非交互模式，自动跳过需要用户确认的步骤

set -euo pipefail

# 检测终端是否支持颜色（当输出被重定向时不使用颜色）
if [[ -t 1 ]] && command -v tput &> /dev/null && tput colors &> /dev/null; then
    USE_COLOR=true
else
    USE_COLOR=false
fi

# 颜色定义（使用 $'...' 语法确保转义序列被正确解析）
if [ "$USE_COLOR" = true ]; then
    RED=$'\033[0;31m'
    GREEN=$'\033[0;32m'
    YELLOW=$'\033[1;33m'
    BLUE=$'\033[0;34m'
    NC=$'\033[0m' # No Color
else
    RED=''
    GREEN=''
    YELLOW=''
    BLUE=''
    NC=''
fi

# 解析参数
UNINSTALL=false
NO_INTERACTIVE=false

for arg in "$@"; do
    case "$arg" in
        --uninstall)
            UNINSTALL=true
            ;;
        --no-interactive)
            NO_INTERACTIVE=true
            ;;
        *)
            echo "未知参数: $arg" >&2
            echo "用法: $0 [--uninstall] [--no-interactive]" >&2
            exit 1
            ;;
    esac
done

# 获取脚本所在目录的绝对路径
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
TOOLS_DIR="$SCRIPT_DIR/tools"
SCRIPTS=("init-task-json" "add-task" "update-task" "read-task" "list-tasks" "check-task" "delete-task")
INSTALL_ERROR=0

# ==================== 卸载功能 ====================

uninstall_symlinks() {
    echo -e "${BLUE}【步骤 1/2】删除符号链接${NC}"
    echo ""
    
    local removed_count=0
    for script in "${SCRIPTS[@]}"; do
        local link_file="$TOOLS_DIR/${script}"
        
        if [ -L "$link_file" ]; then
            local target=$(readlink "$link_file")
            if [ "$target" = "${script}.sh" ]; then
                if rm "$link_file" 2>/dev/null; then
                    echo -e "  ${GREEN}✓${NC} 已删除: $script"
                    removed_count=$((removed_count + 1))
                else
                    echo -e "  ${RED}✗${NC} 删除失败: $script"
                fi
            else
                echo -e "  ${YELLOW}⚠${NC} $script 指向不同目标，跳过"
            fi
        elif [ -e "$link_file" ]; then
            echo -e "  ${YELLOW}⚠${NC} $script 不是符号链接，跳过"
        else
            echo -e "  ${YELLOW}⚠${NC} $script 不存在，跳过"
        fi
    done
    
    echo ""
    echo -e "${GREEN}✓ 符号链接删除完成 (${removed_count}/${#SCRIPTS[@]})${NC}"
    echo ""
}

remove_path_config() {
    echo -e "${BLUE}【步骤 2/2】移除 PATH 配置${NC}"
    echo ""
    
    detect_shell() {
        if [ -n "${ZSH_VERSION:-}" ]; then
            echo "zsh"
        elif [ -n "${BASH_VERSION:-}" ]; then
            echo "bash"
        else
            echo "unknown"
        fi
    }
    
    get_shell_config() {
        local shell_type=$1
        case "$shell_type" in
            zsh)
                echo "$HOME/.zshrc"
                ;;
            bash)
                echo "$HOME/.bashrc"
                ;;
            *)
                echo ""
                ;;
        esac
    }
    
    SHELL_TYPE=$(detect_shell)
    SHELL_CONFIG=$(get_shell_config "$SHELL_TYPE")
    
    if [ -z "$SHELL_CONFIG" ]; then
        echo -e "  ${YELLOW}⚠${NC} 无法检测 Shell 类型，跳过 PATH 配置移除"
        echo -e "    请手动从您的 Shell 配置文件中移除以下内容："
        echo -e "    ${YELLOW}export PATH=\"\$PATH:${TOOLS_DIR}\"${NC}"
        echo ""
        return
    fi
    
    if [ ! -f "$SHELL_CONFIG" ]; then
        echo -e "  ${YELLOW}⚠${NC} 配置文件不存在: ${SHELL_CONFIG}"
        echo ""
        return
    fi
    
    # 检查配置文件中是否存在 PATH 配置
    if grep -q "PATH.*${TOOLS_DIR}" "$SHELL_CONFIG" 2>/dev/null; then
        if [ "$NO_INTERACTIVE" = true ]; then
            # 非交互模式，直接删除
            # 创建临时文件，删除包含 TOOLS_DIR 的行和注释行
            local temp_file=$(mktemp)
            grep -v "PATH.*${TOOLS_DIR}" "$SHELL_CONFIG" | grep -v "# Task-Manage tools directory" > "$temp_file" || true
            mv "$temp_file" "$SHELL_CONFIG"
            echo -e "  ${GREEN}✓${NC} 已从 ${SHELL_CONFIG} 移除 PATH 配置"
        else
            echo "是否要从 ${SHELL_CONFIG} 中移除 PATH 配置? (y/n)"
            read -r response
            if [[ "$response" =~ ^[Yy]$ ]]; then
                local temp_file=$(mktemp)
                grep -v "PATH.*${TOOLS_DIR}" "$SHELL_CONFIG" | grep -v "# Task-Manage tools directory" > "$temp_file" || true
                mv "$temp_file" "$SHELL_CONFIG"
                echo -e "  ${GREEN}✓${NC} 已从 ${SHELL_CONFIG} 移除 PATH 配置"
                echo -e "  ${YELLOW}提示:${NC} 请运行 ${BLUE}source ${SHELL_CONFIG}${NC} 或重新打开终端以使配置生效"
            else
                echo -e "  ${YELLOW}⚠${NC} 跳过 PATH 配置移除"
            fi
        fi
    else
        echo -e "  ${YELLOW}⚠${NC} PATH 配置不存在于 ${SHELL_CONFIG}"
    fi
    
    echo ""
}

# ==================== 主程序 ====================

# 如果是卸载模式，直接执行卸载并退出
if [ "$UNINSTALL" = true ]; then
    echo "=========================================="
    echo "  Task-Manage 工具集卸载程序"
    echo "=========================================="
    echo ""
    
    uninstall_symlinks
    remove_path_config
    
    echo "=========================================="
    echo -e "  卸载完成"
    echo "=========================================="
    echo ""
    echo -e "${GREEN}✓${NC} 符号链接已删除"
    echo -e "${GREEN}✓${NC} PATH 配置已移除"
    echo ""
    echo "提示："
    echo "  - 工具脚本文件 (.sh) 未被删除，仍保留在 ${TOOLS_DIR} 目录"
    echo "  - 如需完全删除，请手动删除 ${TOOLS_DIR} 目录"
    echo ""
    exit 0
fi

# 安装模式
echo "=========================================="
echo "  Task-Manage 工具集安装程序"
echo "=========================================="
echo ""

# 步骤 1: 检查依赖
echo -e "${BLUE}【步骤 1/4】检查依赖工具${NC}"
echo ""

check_dependency() {
    local tool=$1
    local install_cmd=$2
    
    if command -v "$tool" &> /dev/null; then
        local version=""
        case "$tool" in
            jq)
                version=$(jq --version 2>/dev/null | head -1 || echo "")
                ;;
            python3)
                version=$(python3 --version 2>/dev/null || echo "")
                ;;
        esac
        
        if [[ -n "$version" ]]; then
            echo -e "  ${GREEN}✓${NC} $tool ${BLUE}(${version})${NC}"
        else
            echo -e "  ${GREEN}✓${NC} $tool"
        fi
        return 0
    else
        echo -e "  ${RED}✗${NC} $tool ${RED}[缺失]${NC}"
        echo -e "    安装命令: ${YELLOW}${install_cmd}${NC}"
        return 1
    fi
}

# 检查 jq
if ! check_dependency "jq" "sudo apt-get install jq 或 brew install jq"; then
    INSTALL_ERROR=1
fi

# 检查 python3
if ! check_dependency "python3" "sudo apt-get install python3 或 brew install python3"; then
    INSTALL_ERROR=1
fi

# 检查 jsonschema Python 模块
echo ""
echo "检查 Python 模块..."
if command -v python3 &> /dev/null; then
    if python3 -c "import jsonschema" 2>/dev/null; then
        version=$(python3 -c "import jsonschema; print(jsonschema.__version__)" 2>/dev/null || echo "已安装")
        echo -e "  ${GREEN}✓${NC} jsonschema ${BLUE}(v${version})${NC}"
    else
        echo -e "  ${RED}✗${NC} jsonschema ${RED}[缺失]${NC}"
        echo -e "    安装命令: ${YELLOW}pip3 install jsonschema${NC}"
        INSTALL_ERROR=1
    fi
else
    echo -e "  ${RED}✗${NC} jsonschema ${RED}[需要 Python3]${NC}"
    INSTALL_ERROR=1
fi

if [ $INSTALL_ERROR -eq 1 ]; then
    echo ""
    echo -e "${RED}❌ 发现缺失的依赖，请先安装上述工具后再运行安装脚本。${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}✓ 所有依赖检查通过${NC}"
echo ""

# 步骤 2: 创建符号链接
echo -e "${BLUE}【步骤 2/4】创建符号链接${NC}"
echo ""

create_symlink() {
    local script_name=$1
    local script_file="$TOOLS_DIR/${script_name}.sh"
    local link_file="$TOOLS_DIR/${script_name}"
    
    if [ ! -f "$script_file" ]; then
        echo -e "  ${YELLOW}⚠${NC} 脚本文件不存在: ${script_file}"
        return 1
    fi
    
    if [ -L "$link_file" ]; then
        local target=$(readlink "$link_file")
        if [ "$target" = "${script_name}.sh" ]; then
            echo -e "  ${GREEN}✓${NC} $script_name -> $script_name.sh (已存在)"
            return 0
        else
            echo -e "  ${YELLOW}⚠${NC} $link_file 已存在但指向不同目标，跳过"
            return 1
        fi
    elif [ -e "$link_file" ]; then
        echo -e "  ${YELLOW}⚠${NC} $link_file 已存在但不是符号链接，跳过"
        return 1
    else
        if ln -s "${script_name}.sh" "$link_file" 2>/dev/null; then
            echo -e "  ${GREEN}✓${NC} 创建链接: $script_name -> $script_name.sh"
            return 0
        else
            echo -e "  ${RED}✗${NC} 创建链接失败: $script_name"
            return 1
        fi
    fi
}

# 创建所有脚本的符号链接
LINK_COUNT=0

for script in "${SCRIPTS[@]}"; do
    if create_symlink "$script"; then
        LINK_COUNT=$((LINK_COUNT + 1))
    fi
done

echo ""
echo -e "${GREEN}✓ 符号链接创建完成 (${LINK_COUNT}/${#SCRIPTS[@]})${NC}"
echo ""

# 步骤 3: 设置 PATH
echo -e "${BLUE}【步骤 3/4】配置 PATH 环境变量${NC}"
echo ""

detect_shell() {
    if [ -n "${ZSH_VERSION:-}" ]; then
        echo "zsh"
    elif [ -n "${BASH_VERSION:-}" ]; then
        echo "bash"
    else
        echo "unknown"
    fi
}

get_shell_config() {
    local shell_type=$1
    case "$shell_type" in
        zsh)
            echo "$HOME/.zshrc"
            ;;
        bash)
            echo "$HOME/.bashrc"
            ;;
        *)
            echo ""
            ;;
    esac
}

SHELL_TYPE=$(detect_shell)
SHELL_CONFIG=$(get_shell_config "$SHELL_TYPE")

if [ -z "$SHELL_CONFIG" ]; then
    echo -e "  ${YELLOW}⚠${NC} 无法检测 Shell 类型，跳过 PATH 配置"
    echo -e "    请手动将以下内容添加到您的 Shell 配置文件中："
    echo -e "    ${YELLOW}export PATH=\"\$PATH:${TOOLS_DIR}\"${NC}"
    echo ""
else
    # 检查是否已在 PATH 中
    if [[ ":$PATH:" == *":${TOOLS_DIR}:"* ]]; then
        echo -e "  ${GREEN}✓${NC} $TOOLS_DIR 已在当前会话的 PATH 中"
    else
        echo -e "  ${YELLOW}⚠${NC} $TOOLS_DIR 未在当前会话的 PATH 中"
    fi
    
    # 检查配置文件中是否已存在
    if [ -f "$SHELL_CONFIG" ] && grep -q "PATH.*${TOOLS_DIR}" "$SHELL_CONFIG" 2>/dev/null; then
        echo -e "  ${GREEN}✓${NC} PATH 配置已存在于 ${SHELL_CONFIG}"
    else
        echo -e "  ${YELLOW}⚠${NC} PATH 配置不存在于 ${SHELL_CONFIG}"
        echo ""
        echo "" >> "$SHELL_CONFIG"
        echo "# Task-Manage tools directory" >> "$SHELL_CONFIG"
        echo "export PATH=\"\$PATH:${TOOLS_DIR}\"" >> "$SHELL_CONFIG"
        echo -e "  ${GREEN}✓${NC} 已添加到 ${SHELL_CONFIG}"
        echo -e "  ${GREEN}→${NC} 正在重新加载配置: source ${SHELL_CONFIG}"
        # 直接重新加载配置，使 PATH 立即生效
        # 临时禁用 set -u，因为 .bashrc 中可能检查未定义的 PS1 变量
        set +u
        # shellcheck disable=SC1090
        source "$SHELL_CONFIG"
        set -u
        echo -e "  ${GREEN}✓${NC} 配置加载完成，PATH 已更新"
    fi
fi

echo ""

# 步骤 4: 验证安装
echo -e "${BLUE}【步骤 4/4】验证安装${NC}"
echo ""

verify_script() {
    local script_name=$1
    local script_path="$TOOLS_DIR/${script_name}"
    
    if [ -L "$script_path" ] || [ -f "${script_path}.sh" ]; then
        if [ -x "${script_path}.sh" ] || [ -x "$script_path" ]; then
            echo -e "  ${GREEN}✓${NC} $script_name"
            return 0
        else
            echo -e "  ${YELLOW}⚠${NC} $script_name (文件存在但不可执行)"
            return 1
        fi
    else
        echo -e "  ${RED}✗${NC} $script_name (文件不存在)"
        return 1
    fi
}

VERIFY_COUNT=0
for script in "${SCRIPTS[@]}"; do
    if verify_script "$script"; then
        VERIFY_COUNT=$((VERIFY_COUNT + 1))
    fi
done

echo ""
echo "=========================================="
echo -e "  安装完成"
echo "=========================================="
echo ""
echo -e "${GREEN}✓${NC} 依赖检查: 通过"
echo -e "${GREEN}✓${NC} 符号链接: ${LINK_COUNT}/${#SCRIPTS[@]} 个"
echo -e "${GREEN}✓${NC} 脚本验证: ${VERIFY_COUNT}/${#SCRIPTS[@]} 个"
echo ""

# 显示使用说明
echo "使用说明："
printf "  1. 如果 PATH 已更新，可以直接使用命令：\n"
printf "     ${BLUE}init-task-json${NC} <tasks_json_path> <agent_task_id> <agent_name> --description \"<text>\"\n"
printf "     ${BLUE}add-task${NC} <tasks_json_path> <task_id> <task_type> <description>\n"
printf "     ${BLUE}update-task${NC} <tasks_json_path> <task_id> --status <status>\n"
printf "     ${BLUE}read-task${NC} <tasks_json_path> <task_id>\n"
printf "     ${BLUE}list-tasks${NC} <tasks_json_path> [选项]\n"
printf "     ${BLUE}check-task${NC} <tasks_json_path> [选项]\n"
echo ""
printf "  2. 如果 PATH 未更新，可以使用完整路径：\n"
printf "     ${BLUE}${TOOLS_DIR}/init-task-json${NC} ... --description \"<text>\"\n"
echo ""
printf "  3. 查看详细文档：\n"
printf "     ${BLUE}.claude/skills/task-manage/SKILL.md${NC}\n"
echo ""
