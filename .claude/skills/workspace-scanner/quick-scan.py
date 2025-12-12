#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""工作区结构快速检测脚本。

依据 `.claude/skills/workspace-scanner/SKILL.md` 第 20-40 行的判定项，
对给定路径执行以下检测并打印结果：
1) 包管理器工作区配置
2) 多模块项目配置
3) 目录结构特征
4) 独立子工程判定条件
"""

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple

# 判定所需的关键文件集合
WORKSPACE_FILES = {
    "pnpm-workspace": "pnpm-workspace.yaml",
    "lerna": "lerna.json",
    "rush": "rush.json",
}

# 子工程依赖配置文件集合
DEPENDENCY_FILES = {
    "package.json",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "go.mod",
    "go.work",
    "Cargo.toml",
    "requirements.txt",
    "pyproject.toml",
    "composer.json",
}

# README 判定
README_FILES = {"README", "README.md", "README.MD"}

# 常见项目结构目录（不应被视为独立子工程）
COMMON_PROJECT_DIRS = {
    # Go 项目常见目录
    "cmd", "internal", "pkg", "vendor", "testdata",
    # 通用项目目录
    "docs", "doc", "test", "tests", "spec", "specs",
    "scripts", "buildscripts", "build", "dist", "bin", "out",
    "node_modules", ".git", ".github", ".vscode", ".idea",
    "coverage", "tmp", "temp", "logs", "log",
    # 构建和部署相关
    "helm", "k8s", "kubernetes", "docker", "dockerscripts",
    "deploy", "deployment", "ci", ".ci",
}


def read_json_safe(path: Path) -> Dict:
    """安全读取 JSON，异常返回空 dict。"""
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def load_text(path: Path) -> str:
    """读取文本文件内容，失败返回空字符串。"""
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def detect_package_manager_workspace(root: Path) -> List[str]:
    """检测包管理器工作区配置。"""
    hits: List[str] = []
    pkg = root / "package.json"
    if pkg.exists():
        pkg_json = read_json_safe(pkg)
        if "workspaces" in pkg_json:
            hits.append(f"package.json 含 workspaces 字段 ({pkg})")
    for name, fname in WORKSPACE_FILES.items():
        path = root / fname
        if path.exists():
            hits.append(f"{fname} 存在 ({path})")
    return hits


def detect_multi_module_configs(root: Path) -> List[str]:
    """检测多模块项目配置。"""
    hits: List[str] = []

    pom = root / "pom.xml"
    if pom.exists() and "<modules>" in load_text(pom):
        hits.append(f"Maven pom.xml 含 <modules> ({pom})")

    for gradle_file in ("settings.gradle", "settings.gradle.kts"):
        path = root / gradle_file
        if path.exists() and re.search(r"include\s*\(", load_text(path), re.IGNORECASE):
            hits.append(f"Gradle settings 含 include 语句 ({path})")
            break

    go_work = root / "go.work"
    if go_work.exists():
        hits.append(f"go.work 存在 ({go_work})")

    sln_files = list(root.glob("*.sln"))
    for sln in sln_files:
        content = load_text(sln)
        if content:
            csproj_refs = re.findall(r"[^\\s]+\\.csproj", content, flags=re.IGNORECASE)
            if len(csproj_refs) >= 2:
                hits.append(f".sln 引用多个 .csproj ({sln})")
                break
    return hits


def has_dependency_file(path: Path) -> Tuple[bool, str]:
    """判断目录下是否存在依赖配置文件，返回 (是否存在, 文件名)。"""
    for name in DEPENDENCY_FILES:
        candidate = path / name
        if candidate.exists():
            return True, name
    for csproj in path.glob("*.csproj"):
        return True, csproj.name
    return False, ""


def detect_structural_features(root: Path) -> List[str]:
    """检测目录结构特征。"""
    hits: List[str] = []
    candidate_dirs = ["packages", "apps", "services"]

    dep_dirs = []
    for d in candidate_dirs:
        base = root / d
        if not base.is_dir():
            continue
        sub_with_dep = []
        for child in base.iterdir():
            if child.is_dir():
                has_dep, dep_name = has_dependency_file(child)
                if has_dep:
                    sub_with_dep.append(f"{child.name} ({dep_name})")
        if len(sub_with_dep) >= 2:
            dep_dirs.extend([f"{d}/{x}" for x in sub_with_dep])
    if dep_dirs:
        hits.append("packages/apps/services 下存在多个含依赖配置的子目录: " + ", ".join(dep_dirs))

    # 检测顶层多个依赖配置文件（排除 go.work，因为它已在工作区配置检测中处理）
    # 按语言分组：JavaScript/Node.js, Java, Go, Rust, Python, PHP, .NET
    config_by_lang = {
        "JavaScript/Node.js": [],
        "Java": [],
        "Go": [],
        "Rust": [],
        "Python": [],
        "PHP": [],
        ".NET": [],
    }
    
    # 分类配置文件
    java_configs = ["pom.xml", "build.gradle", "build.gradle.kts"]
    go_configs = ["go.mod"]  # go.work 已排除
    rust_configs = ["Cargo.toml"]
    python_configs = ["requirements.txt", "pyproject.toml"]
    dotnet_configs = list(root.glob("*.csproj"))
    
    if (root / "package.json").exists():
        config_by_lang["JavaScript/Node.js"].append("package.json")
    if (root / "composer.json").exists():
        config_by_lang["PHP"].append("composer.json")
    for cfg in java_configs:
        if (root / cfg).exists():
            config_by_lang["Java"].append(cfg)
    for cfg in go_configs:
        if (root / cfg).exists():
            config_by_lang["Go"].append(cfg)
    for cfg in rust_configs:
        if (root / cfg).exists():
            config_by_lang["Rust"].append(cfg)
    for cfg in python_configs:
        if (root / cfg).exists():
            config_by_lang["Python"].append(cfg)
    if dotnet_configs:
        config_by_lang[".NET"].extend([c.name for c in dotnet_configs])
    
    # 统计有配置的语言数量
    languages_with_config = [lang for lang, configs in config_by_lang.items() if configs]
    
    # 如果顶层有多个不同语言的配置文件，可能是多子工程
    # 但需要更严格的判断：至少 2 个不同语言，且每个语言有独立的配置文件
    if len(languages_with_config) >= 2:
        config_details = []
        for lang in languages_with_config:
            configs = config_by_lang[lang]
            config_details.append(f"{lang}({', '.join(configs)})")
        hits.append(f"顶层存在多个不同语言的依赖配置文件: {'; '.join(config_details)}")
    # 如果同一语言有多个配置文件（如多个 .csproj），也可能是多子工程
    elif len(languages_with_config) == 1:
        lang = languages_with_config[0]
        configs = config_by_lang[lang]
        if len(configs) > 1:
            hits.append(f"顶层存在多个 {lang} 依赖配置文件: {', '.join(configs)}")
    
    # 检测：顶层有多个一级子目录，且顶层没有依赖配置文件 -> 可能是多子工程项目
    if not has_top_level_dependency(root):
        top_level_dirs = []
        for child in root.iterdir():
            if child.is_dir() and not child.name.startswith("."):
                # 排除常见项目结构目录
                if child.name not in COMMON_PROJECT_DIRS:
                    top_level_dirs.append(child.name)
        
        if len(top_level_dirs) >= 2:
            # 限制显示数量，避免输出过长
            if len(top_level_dirs) <= 10:
                dirs_str = ", ".join(top_level_dirs)
            else:
                dirs_str = ", ".join(top_level_dirs[:10]) + f", ... (共 {len(top_level_dirs)} 个)"
            hits.append(f"顶层存在多个一级子目录且无依赖配置文件: {dirs_str}")
        elif len(top_level_dirs) == 1:
            # 如果顶层只有一个一级子目录，检查该目录是否包含多个子目录且没有配置文件
            subdir = root / top_level_dirs[0]
            if subdir.is_dir():
                # 检查该子目录是否有依赖配置文件
                has_sub_dep, _ = has_dependency_file(subdir)
                if not has_sub_dep:
                    # 统计该子目录下的子目录数量
                    subdirs = [d.name for d in subdir.iterdir() if d.is_dir() and not d.name.startswith(".")]
                    if len(subdirs) >= 2:
                        # 限制显示数量
                        if len(subdirs) <= 10:
                            subdirs_str = ", ".join(subdirs)
                        else:
                            subdirs_str = ", ".join(subdirs[:10]) + f", ... (共 {len(subdirs)} 个)"
                        hits.append(f"{top_level_dirs[0]}/ 目录下存在多个子目录且无依赖配置文件: {subdirs_str}")

    return hits


def has_top_level_dependency(root: Path) -> bool:
    """检查顶层是否存在依赖配置文件。"""
    for name in DEPENDENCY_FILES:
        if (root / name).exists():
            return True
    return len(list(root.glob("*.csproj"))) > 0


def detect_independent_subprojects(root: Path) -> List[str]:
    """检测满足任一独立子工程条件的目录。"""
    hits: List[str] = []
    
    for child in root.iterdir():
        if not child.is_dir() or child.name.startswith("."):
            continue
        
        # 排除常见项目结构目录
        if child.name in COMMON_PROJECT_DIRS:
            continue
        
        has_dep, dep_name = has_dependency_file(child)
        has_readme = any((child / name).exists() for name in README_FILES)
        
        # 判定逻辑：有独立依赖配置文件 -> 独立子工程
        if has_dep:
            # 有独立依赖配置文件，判定为独立子工程
            reasons = [f"依赖配置: {dep_name}"]
            if has_readme:
                reasons.append("独立 README/文档")
            hits.append(f"{child.name} ({'; '.join(reasons)})")
    
    return hits


def analyze_workspace(root: Path) -> Dict[str, List[str]]:
    """执行全部判定，返回结果字典。"""
    return {
        "包管理器工作区配置": detect_package_manager_workspace(root),
        "多模块项目配置": detect_multi_module_configs(root),
        "目录结构特征": detect_structural_features(root),
        "独立子工程判定": detect_independent_subprojects(root),
    }


def generate_tree(root: Path) -> str:
    """生成文件树（深度为3）。"""
    try:
        result = subprocess.run(
            ["tree", "-L", "3", str(root)],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if result.returncode == 0:
            return result.stdout
        else:
            return f"无法生成文件树（tree 命令执行失败）"
    except FileNotFoundError:
        return "无法生成文件树（未安装 tree 命令）"
    except Exception as e:
        return f"无法生成文件树（错误: {e})"


def format_output(root: Path, result: Dict[str, List[str]]) -> str:
    """格式化输出结果。"""
    lines = [""]
    # 先输出文件树
    lines.append("== 文件树（深度=3） ==")
    lines.append(generate_tree(root))
    lines.append("")
    # 然后输出匹配检测规则
    for section, items in result.items():
        if items:
            lines.append(f"[{section}]")
            for item in items:
                lines.append(f"- {item}")
    total_hits = sum(len(v) for v in result.values())
    lines.append(f"总计命中: {total_hits}")
    if total_hits == 0:
        lines.append("未检测到 Monorepo / 多子工程特征，请自主分析。")
    else:
        lines.append("检测到 Monorepo / 多子工程相关特征，请进一步验证。")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="工作区结构检测")
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="要检测的项目路径，默认当前目录",
    )
    args = parser.parse_args()
    root = Path(args.path).resolve()
    if not root.exists():
        print(f"路径不存在: {root}")
        return
    result = analyze_workspace(root)
    print(format_output(root, result))


if __name__ == "__main__":
    main()

