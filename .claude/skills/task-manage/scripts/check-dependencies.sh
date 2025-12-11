#!/bin/bash
# .claude/plugins/code-audit/scripts/check-dependencies.sh
# 检查 code-audit 插件所需工具的安装状态
#
# 用法：
#   bash check-dependencies.sh
#   或
#   ./check-dependencies.sh

set -euo pipefail

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 统计
TOTAL=0
PASSED=0
FAILED=0
WARNING=0

# 检查函数
check_tool() {
    local tool_name=$1
    local required=${2:-"required"}  # required 或 optional
    local description=${3:-""}
    
    TOTAL=$((TOTAL + 1))
    
    if command -v "$tool_name" &> /dev/null; then
        local version=""
        local path=$(command -v "$tool_name")
        
        # 尝试获取版本信息
        case "$tool_name" in
            jq)
                version=$(jq --version 2>/dev/null | head -1 || echo "")
                ;;
            cloc)
                version=$(cloc --version 2>/dev/null | head -1 || echo "")
                ;;
            python|python3)
                version=$(python3 --version 2>/dev/null || python --version 2>/dev/null || echo "")
                ;;
            node)
                version=$(node --version 2>/dev/null || echo "")
                ;;
            npm)
                version=$(npm --version 2>/dev/null || echo "")
                ;;
            go)
                version=$(go version 2>/dev/null | awk '{print $3}' || echo "")
                ;;
            java)
                version=$(java -version 2>&1 | head -1 | awk -F'"' '{print $2}' || echo "")
                ;;
            pip)
                version=$(pip --version 2>/dev/null | awk '{print $2}' || echo "")
                ;;
            poetry)
                version=$(poetry --version 2>/dev/null || echo "")
                ;;
            yarn)
                version=$(yarn --version 2>/dev/null || echo "")
                ;;
            rg|ripgrep)
                version=$(rg --version 2>/dev/null | head -1 | awk '{print $2}' || echo "")
                ;;
            tree)
                version=$(tree --version 2>/dev/null | head -1 | awk '{print $2}' || echo "")
                ;;
        esac
        
        if [[ -n "$version" ]]; then
            echo -e "${GREEN}✓${NC} ${tool_name}${NC} ${BLUE}(${version})${NC} - ${path}"
            if [[ -n "$description" ]]; then
                echo "    ${description}"
            fi
        else
            echo -e "${GREEN}✓${NC} ${tool_name}${NC} - ${path}"
            if [[ -n "$description" ]]; then
                echo "    ${description}"
            fi
        fi
        
        PASSED=$((PASSED + 1))
        return 0
    else
        if [[ "$required" == "required" ]]; then
            echo -e "${RED}✗${NC} ${tool_name}${NC} ${RED}[必需]${NC}"
            if [[ -n "$description" ]]; then
                echo "    ${description}"
            fi
            echo "    安装方法: $(get_install_command "$tool_name")"
            FAILED=$((FAILED + 1))
            return 1
        else
            echo -e "${YELLOW}⚠${NC} ${tool_name}${NC} ${YELLOW}[可选]${NC}"
            if [[ -n "$description" ]]; then
                echo "    ${description}"
            fi
            WARNING=$((WARNING + 1))
            return 0
        fi
    fi
}

# 检查 Python 模块
check_python_module() {
    local module_name=$1
    local required=${2:-"required"}  # required 或 optional
    local description=${3:-""}
    
    TOTAL=$((TOTAL + 1))
    
    # 首先检查 Python3 是否可用
    if ! command -v python3 &> /dev/null; then
        if [[ "$required" == "required" ]]; then
            echo -e "${RED}✗${NC} ${module_name}${NC} ${RED}[必需]${NC} (需要 Python3)"
            if [[ -n "$description" ]]; then
                echo "    ${description}"
            fi
            echo "    安装方法: 先安装 Python3，然后运行: pip3 install ${module_name}"
            FAILED=$((FAILED + 1))
            return 1
        else
            echo -e "${YELLOW}⚠${NC} ${module_name}${NC} ${YELLOW}[可选]${NC} (需要 Python3)"
            if [[ -n "$description" ]]; then
                echo "    ${description}"
            fi
            WARNING=$((WARNING + 1))
            return 0
        fi
    fi
    
    # 尝试导入模块并获取版本
    local version_output
    version_output=$(python3 -c "import ${module_name}; print(getattr(${module_name}, '__version__', 'installed'))" 2>/dev/null)
    
    if [[ $? -eq 0 ]]; then
        local version="${version_output}"
        if [[ "$version" == "installed" ]]; then
            echo -e "${GREEN}✓${NC} ${module_name}${NC} ${BLUE}(已安装)${NC}"
        else
            echo -e "${GREEN}✓${NC} ${module_name}${NC} ${BLUE}(v${version})${NC}"
        fi
        if [[ -n "$description" ]]; then
            echo "    ${description}"
        fi
        PASSED=$((PASSED + 1))
        return 0
    else
        if [[ "$required" == "required" ]]; then
            echo -e "${RED}✗${NC} ${module_name}${NC} ${RED}[必需]${NC}"
            if [[ -n "$description" ]]; then
                echo "    ${description}"
            fi
            echo "    安装方法: $(get_install_command "$module_name")"
            FAILED=$((FAILED + 1))
            return 1
        else
            echo -e "${YELLOW}⚠${NC} ${module_name}${NC} ${YELLOW}[可选]${NC}"
            if [[ -n "$description" ]]; then
                echo "    ${description}"
            fi
            echo "    安装方法: $(get_install_command "$module_name")"
            WARNING=$((WARNING + 1))
            return 0
        fi
    fi
}

# 获取安装命令
get_install_command() {
    local tool=$1
    case "$tool" in
        jsonschema)
            echo "pip3 install jsonschema"
            echo "    或: pip install jsonschema"
            echo "    或: python3 -m pip install jsonschema"
            ;;
        jq)
            if [[ "$OSTYPE" == "darwin"* ]]; then
                echo "brew install jq"
            elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
                echo "sudo apt-get install jq  # Debian/Ubuntu"
                echo "    sudo yum install jq  # CentOS/RHEL"
            else
                echo "请访问 https://stedolan.github.io/jq/download/"
            fi
            ;;
        cloc)
            if [[ "$OSTYPE" == "darwin"* ]]; then
                echo "brew install cloc"
            elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
                echo "sudo apt-get install cloc  # Debian/Ubuntu"
                echo "    sudo yum install cloc  # CentOS/RHEL"
            else
                echo "请访问 https://github.com/AlDanial/cloc"
            fi
            ;;
        python|python3)
            if [[ "$OSTYPE" == "darwin"* ]]; then
                echo "brew install python3"
            elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
                echo "sudo apt-get install python3  # Debian/Ubuntu"
                echo "    sudo yum install python3  # CentOS/RHEL"
            else
                echo "请访问 https://www.python.org/downloads/"
            fi
            ;;
        node|npm)
            echo "请访问 https://nodejs.org/ 或使用 nvm: curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash"
            ;;
        go)
            echo "请访问 https://go.dev/dl/"
            ;;
        java)
            echo "请访问 https://adoptium.net/ 或使用包管理器安装 OpenJDK"
            ;;
        pip)
            echo "通常随 Python 一起安装，或使用: python3 -m ensurepip --upgrade"
            ;;
        poetry)
            echo "curl -sSL https://install.python-poetry.org | python3 -"
            ;;
        yarn)
            echo "npm install -g yarn 或访问 https://yarnpkg.com/getting-started/install"
            ;;
        rg|ripgrep)
            if [[ "$OSTYPE" == "darwin"* ]]; then
                echo "brew install ripgrep"
            elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
                echo "sudo apt-get install ripgrep  # Debian/Ubuntu"
                echo "    sudo yum install ripgrep  # CentOS/RHEL"
                echo "    或从 GitHub 下载: https://github.com/BurntSushi/ripgrep/releases"
            else
                echo "请访问 https://github.com/BurntSushi/ripgrep/releases"
            fi
            ;;
        tree)
            if [[ "$OSTYPE" == "darwin"* ]]; then
                echo "brew install tree"
            elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
                echo "sudo apt-get install tree  # Debian/Ubuntu"
                echo "    sudo yum install tree  # CentOS/RHEL"
            else
                echo "请访问 http://mama.indstate.edu/users/ice/tree/"
            fi
            ;;
        *)
            echo "请查阅相关文档"
            ;;
    esac
}

# 主函数
main() {
    echo "=========================================="
    echo "  Code-Audit 插件依赖检查工具"
    echo "=========================================="
    echo ""
    
    # 必需工具
    echo -e "${BLUE}【必需工具】${NC}"
    echo "这些工具是插件运行所必需的："
    echo ""
    
    check_tool "jq" "required" "JSON 处理工具，所有智能体都需要"
    check_tool "cloc" "required" "代码行数统计工具（project-analyzer 需要）"
    check_tool "rg" "required" "ripgrep - 快速文本搜索工具（grep 的高性能替代品）"
    check_tool "python3" "required" "Python 解释器（threat-modeler 可选，用于生成 Markdown）"
    check_python_module "jsonschema" "required" "JSON Schema 验证库（tasks.json 工具需要，用于 Schema 校验）"
    check_tool "tree" "optional" "目录树显示工具（workspace-scanner 需要，用于生成文件树）"
    
    echo ""
    echo "=========================================="
    echo -e "  检查结果统计"
    echo "=========================================="
    echo -e "总计: ${TOTAL}"
    echo -e "${GREEN}通过: ${PASSED}${NC}"
    echo -e "${RED}失败: ${FAILED}${NC}"
    echo -e "${YELLOW}警告: ${WARNING}${NC}"
    echo ""
    
    if [[ $FAILED -gt 0 ]]; then
        echo -e "${RED}❌ 发现 ${FAILED} 个必需工具缺失，请先安装这些工具！${NC}"
        echo ""
        exit 1
    elif [[ $WARNING -gt 0 ]]; then
        echo -e "${YELLOW}⚠️  有 ${WARNING} 个可选工具未安装，某些功能可能受限。${NC}"
        echo ""
        exit 0
    else
        echo -e "${GREEN}✅ 所有工具检查通过！${NC}"
        echo ""
        exit 0
    fi
}

# 运行主函数
main "$@"

