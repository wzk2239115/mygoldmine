#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""项目基本信息快速收集脚本。

依据 `.claude/skills/project-profiler/SKILL.md` 的判定标准，
快速收集项目基本信息并打印结果：
1) 项目分类（后端HTTP服务、前端WEB应用、安全测试靶场）
2) 技术栈（主要语言、框架、包管理器）
3) 代码统计（文件数量、代码行数、主要目录结构）
4) 入口点（主入口文件、路由入口）
"""

import argparse
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# 依赖配置文件映射到语言
DEPENDENCY_FILES = {
    "package.json": "JavaScript/TypeScript",
    "go.mod": "Go",
    "pom.xml": "Java",
    "build.gradle": "Java",
    "build.gradle.kts": "Java",
    "requirements.txt": "Python",
    "pyproject.toml": "Python",
    "composer.json": "PHP",
    "Cargo.toml": "Rust",
    "Gemfile": "Ruby",
    "build.sbt": "Scala",
}

# 后端 Web 框架关键词
BACKEND_FRAMEWORKS = {
    "JavaScript/TypeScript": ["express", "koa", "fastify", "nest", "hapi"],
    "Python": ["flask", "fastapi", "django", "tornado", "bottle", "sanic", "quart"],
    "Java": ["spring-boot", "spring-web", "springframework", "play-framework", "vertx"],
    "Go": ["gin-gonic/gin", "echo", "chi", "gorilla/mux", "fiber", "beego"],
    "PHP": ["laravel", "symfony", "codeigniter", "yii", "slim"],
    ".NET": ["AspNetCore", "Microsoft.AspNetCore"],
    "Rust": ["actix-web", "rocket", "warp", "axum"],
    "Ruby": ["rails", "sinatra", "grape"],
    "Scala": ["play-framework", "akka-http", "http4s"],
    "Kotlin": ["ktor", "spring-boot"],
}

# 前端框架关键词
FRONTEND_FRAMEWORKS = {
    "react",
    "vue",
    "angular",
    "svelte",
    "next",
    "nuxt",
    "remix",
    "gatsby",
    "vite",
}

# 路由注册模式（按框架分类）
ROUTE_PATTERNS = {
    # Express.js
    "express": [
        r"app\.(get|post|put|delete|patch|use)\(",
        r"router\.(get|post|put|delete|patch)\(",
        r"app\.use\(",
    ],
    # Koa.js
    "koa": [
        r"router\.(get|post|put|delete|patch)\(",
        r"app\.use\(",
    ],
    # Fastify
    "fastify": [
        r"fastify\.(get|post|put|delete|patch|register)\(",
    ],
    # NestJS
    "nest": [
        r"@(Get|Post|Put|Delete|Patch|Controller)\(",
        r"@Controller\(",
    ],
    # Flask
    "flask": [
        r"@app\.(route|get|post|put|delete)\(",
        r"app\.(route|get|post|put|delete)\(",
    ],
    # Django
    "django": [
        r"urlpatterns\s*=",
        r"path\(",
        r"re_path\(",
    ],
    # FastAPI
    "fastapi": [
        r"@app\.(get|post|put|delete|patch)\(",
        r"@router\.(get|post|put|delete|patch)\(",
        r"app\.(get|post|put|delete|patch)\(",
    ],
    # Spring Boot
    "spring-boot": [
        r"@(RestController|Controller)",
        r"@(GetMapping|PostMapping|PutMapping|DeleteMapping|RequestMapping)",
    ],
    # Gin
    "gin": [
        r"router\.(GET|POST|PUT|DELETE|PATCH)\(",
        r"router\.Group\(",
        r"gin\.Default\(",
    ],
    # Echo
    "echo": [
        r"e\.(GET|POST|PUT|DELETE|PATCH)\(",
        r"echo\.New\(",
    ],
    # Chi
    "chi": [
        r"r\.(Get|Post|Put|Delete|Patch)\(",
        r"chi\.NewRouter\(",
    ],
    # Go 标准库
    "go-stdlib": [
        r"router\.(Handle|HandleFunc|Path|Methods)\(",
        r"mux\.Router",
        r"http\.(HandleFunc|ServeMux)",
    ],
    # Laravel
    "laravel": [
        r"Route::(get|post|put|delete|patch|any)\(",
        r"Route::group\(",
    ],
    # Symfony
    "symfony": [
        r"Route\(",
        r"@Route\(",
    ],
    # ASP.NET Core
    "aspnetcore": [
        r"MapGet\(",
        r"MapPost\(",
        r"MapControllers\(",
        r"app\.Map\(",
    ],
    # Hapi.js
    "hapi": [
        r"server\.(route|method)\(",
        r"server\.route\(",
    ],
    # Tornado
    "tornado": [
        r"@tornado\.web\.(get|post|put|delete)\(",
        r"tornado\.web\.Application\(",
        r"\(get|post|put|delete)\(",
    ],
    # Bottle
    "bottle": [
        r"@(route|get|post|put|delete)\(",
        r"bottle\.(route|get|post|put|delete)\(",
    ],
    # Fiber (Go)
    "fiber": [
        r"app\.(Get|Post|Put|Delete|Patch)\(",
        r"fiber\.New\(",
    ],
    # CodeIgniter
    "codeigniter": [
        r"\$route\[",
        r"\$this->router->",
    ],
    # Yii
    "yii": [
        r"UrlManager",
        r"rules\s*=>\s*\[",
    ],
    # Actix (Rust)
    "actix": [
        r"web::(resource|scope|route)\(",
        r"HttpServer::new\(",
    ],
    # Rocket (Rust)
    "rocket": [
        r"#\[(get|post|put|delete|patch)\(",
        r"rocket::build\(",
    ],
    # Warp (Rust)
    "warp": [
        r"warp::(get|post|put|delete|filter)\(",
        r"warp::serve\(",
    ],
    # Rails (Ruby)
    "rails": [
        r"get\s+['\"]",
        r"post\s+['\"]",
        r"resources\s+:",
        r"Rails\.application\.routes",
    ],
    # Sinatra (Ruby)
    "sinatra": [
        r"get\s+['\"]",
        r"post\s+['\"]",
        r"Sinatra::Application",
    ],
    # Play Framework (Scala/Java)
    "play": [
        r"Routes\(",
        r"Action\s*\{",
        r"@Action",
    ],
    # Ktor (Kotlin)
    "ktor": [
        r"get\s*\{",
        r"post\s*\{",
        r"routing\s*\{",
    ],
    # Sanic (Python)
    "sanic": [
        r"@app\.(route|get|post|put|delete)\(",
        r"sanic\.Sanic\(",
    ],
    # Quart (Python)
    "quart": [
        r"@app\.(route|get|post|put|delete)\(",
        r"quart\.Quart\(",
    ],
    # Vert.x (Java)
    "vertx": [
        r"router\.(get|post|put|delete)\(",
        r"Vertx\.vertx\(",
    ],
    # Beego (Go)
    "beego": [
        r"beego\.(Router|NSRouter)\(",
        r"@router\.",
    ],
    # Slim (PHP)
    "slim": [
        r"\$app->(get|post|put|delete)\(",
        r"Slim\App",
    ],
    # Axum (Rust)
    "axum": [
        r"Router::new\(",
        r"\.route\(",
    ],
    # Grape (Ruby)
    "grape": [
        r"class\s+\w+\s+<\s+Grape::API",
        r"get\s+do",
    ],
    # Akka HTTP (Scala)
    "akka-http": [
        r"path\(",
        r"Route\.seal",
    ],
    # http4s (Scala)
    "http4s": [
        r"HttpRoutes\.of\(",
        r"GET\s*->",
    ],
}

# 入口文件
ENTRY_FILES = {
    "main.py",
    "app.py",
    "server.py",
    "main.go",
    "index.js",
    "index.ts",
    "Program.cs",
    "index.php",
    "main.rs",
}

# 安全测试靶场关键词
VTR_KEYWORDS = [
    "vulnerability",
    "vulnerable",
    "靶场",
    "靶机",
    "security test",
    "security testing",
    "penetration test",
    "pentest",
    "ctf",
    "challenge",
    "lab",
    "benchmark",
    "教学",
    "educational",
]

# 智能合约框架关键词
BLOCKCHAIN_FRAMEWORKS = {
    "JavaScript/TypeScript": ["hardhat", "truffle", "foundry", "ethers", "web3.js", "ethersjs"],
    "Solidity": ["hardhat", "truffle", "foundry"],
    "Rust": ["anchor", "solana", "substrate"],
    "Go": ["cosmos-sdk", "tendermint"],
}

# 智能合约配置文件
BLOCKCHAIN_CONFIG_FILES = [
    "hardhat.config.js",
    "hardhat.config.ts",
    "truffle-config.js",
    "truffle.js",
    "foundry.toml",
    "Anchor.toml",
]

# 智能合约源文件扩展名
BLOCKCHAIN_SOURCE_EXTENSIONS = [".sol", ".rs", ".move", ".vy", ".go"]

# 智能合约代码关键词特征
BLOCKCHAIN_CODE_KEYWORDS = [
    "pragma solidity",
    "contract {",
    "interface {",
    "library {",
    "#[program]",
    "#[derive(Accounts)]",
    "module {",
    "public fun",
]


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


EXT_LANGUAGE = {
    ".py": "Python", ".rs": "Rust", ".go": "Go",
    ".js": "JavaScript/TypeScript", ".jsx": "JavaScript/TypeScript",
    ".ts": "JavaScript/TypeScript", ".tsx": "JavaScript/TypeScript",
    ".java": "Java", ".kt": "Kotlin", ".php": "PHP", ".rb": "Ruby",
    ".cs": ".NET", ".scala": "Scala", ".sol": "Solidity",
    ".move": "Move", ".vy": "Vyper", ".c": "C/C++", ".cc": "C/C++",
    ".cpp": "C/C++", ".cxx": "C/C++", ".cu": "CUDA",
}


def detect_language_fallback(root: Path) -> Optional[str]:
    counts: Dict[str, int] = {}
    for p in _iter_scan_files(root, max_files=6000):
        lang = EXT_LANGUAGE.get(p.suffix.lower())
        if lang:
            counts[lang] = counts.get(lang, 0) + 1
    if not counts:
        return None
    return max(counts.items(), key=lambda kv: kv[1])[0]


def detect_language(root: Path) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """检测主要语言、框架和包管理器。"""
    language = None
    framework = None
    package_manager = None

    # 检测语言和包管理器
    for dep_file, lang in DEPENDENCY_FILES.items():
        if (root / dep_file).exists():
            language = lang
            if dep_file == "package.json":
                package_manager = "npm/yarn/pnpm"
            elif dep_file in ("pom.xml", "build.gradle", "build.gradle.kts"):
                package_manager = "Maven/Gradle"
            elif dep_file == "go.mod":
                package_manager = "go mod"
            elif dep_file in ("requirements.txt", "pyproject.toml"):
                package_manager = "pip/poetry"
            elif dep_file == "composer.json":
                package_manager = "composer"
            elif dep_file == "Cargo.toml":
                package_manager = "cargo"
            elif dep_file == "Gemfile":
                package_manager = "bundler"
            elif dep_file == "build.sbt":
                package_manager = "sbt"
            break

    # 检测 .NET
    if not language:
        csproj_files = list(root.glob("*.csproj"))
        if csproj_files:
            language = ".NET"
            package_manager = "NuGet"

    # 检测框架
    if language:
        if language == "JavaScript/TypeScript":
            pkg_json = read_json_safe(root / "package.json")
            deps = {**pkg_json.get("dependencies", {}), **pkg_json.get("devDependencies", {})}
            for dep_name in deps.keys():
                for fw in BACKEND_FRAMEWORKS.get(language, []):
                    if fw.lower() in dep_name.lower():
                        framework = fw
                        break
                if framework:
                    break
                # 检测前端框架
                for fw in FRONTEND_FRAMEWORKS:
                    if fw.lower() in dep_name.lower():
                        framework = fw
                        break
                if framework:
                    break
        elif language == "Python":
            for dep_file in ("requirements.txt", "pyproject.toml"):
                path = root / dep_file
                if path.exists():
                    content = load_text(path).lower()
                    for fw in BACKEND_FRAMEWORKS.get(language, []):
                        if fw.lower() in content:
                            framework = fw
                            break
                    if framework:
                        break
        elif language == "Java":
            for dep_file in ("pom.xml", "build.gradle", "build.gradle.kts"):
                path = root / dep_file
                if path.exists():
                    content = load_text(path).lower()
                    for fw in BACKEND_FRAMEWORKS.get(language, []):
                        if fw.lower() in content:
                            framework = fw
                            break
                    if framework:
                        break
        elif language == "Go":
            go_mod = root / "go.mod"
            if go_mod.exists():
                content = load_text(go_mod)
                for fw in BACKEND_FRAMEWORKS.get(language, []):
                    if fw.lower() in content.lower():
                        framework = fw.split("/")[-1]  # 提取框架名
                        break
        elif language == "PHP":
            composer_json = read_json_safe(root / "composer.json")
            deps = {**composer_json.get("require", {}), **composer_json.get("require-dev", {})}
            for dep_name in deps.keys():
                for fw in BACKEND_FRAMEWORKS.get(language, []):
                    if fw.lower() in dep_name.lower():
                        framework = fw
                        break
                if framework:
                    break
        elif language == ".NET":
            csproj_files = list(root.glob("*.csproj"))
            for csproj in csproj_files:
                content = load_text(csproj).lower()
                if "aspnetcore" in content:
                    framework = "ASP.NET Core"
                    break
        elif language == "Rust":
            cargo_toml = root / "Cargo.toml"
            if cargo_toml.exists():
                content = load_text(cargo_toml).lower()
                for fw in BACKEND_FRAMEWORKS.get(language, []):
                    if fw.lower() in content:
                        framework = fw
                        break
        elif language == "Ruby":
            gemfile = root / "Gemfile"
            if gemfile.exists():
                content = load_text(gemfile).lower()
                for fw in BACKEND_FRAMEWORKS.get(language, []):
                    if fw.lower() in content:
                        framework = fw
                        break
        elif language == "Scala":
            build_sbt = root / "build.sbt"
            if build_sbt.exists():
                content = load_text(build_sbt).lower()
                for fw in BACKEND_FRAMEWORKS.get(language, []):
                    if fw.lower() in content:
                        framework = fw
                        break
            # Scala 也可能使用 Maven/Gradle
            if not framework:
                for dep_file in ("pom.xml", "build.gradle", "build.gradle.kts"):
                    path = root / dep_file
                    if path.exists():
                        content = load_text(path).lower()
                        for fw in BACKEND_FRAMEWORKS.get(language, []):
                            if fw.lower() in content:
                                framework = fw
                                break
                        if framework:
                            break

    if not language:
        language = detect_language_fallback(root)
    return language, framework, package_manager


def detect_backend_service(root: Path, language: Optional[str]) -> Tuple[bool, List[str]]:
    """检测是否为后端HTTP服务。"""
    evidence = []

    if not language:
        return False, evidence

    # 方法一：检查依赖文件中的框架
    if language == "JavaScript/TypeScript":
        pkg_json = read_json_safe(root / "package.json")
        deps = {**pkg_json.get("dependencies", {}), **pkg_json.get("devDependencies", {})}
        for dep_name in deps.keys():
            for fw in BACKEND_FRAMEWORKS.get(language, []):
                if fw.lower() in dep_name.lower():
                    evidence.append(f"依赖文件包含后端框架: {dep_name}")
                    return True, evidence
    elif language == "Python":
        for dep_file in ("requirements.txt", "pyproject.toml"):
            path = root / dep_file
            if path.exists():
                content = load_text(path).lower()
                for fw in BACKEND_FRAMEWORKS.get(language, []):
                    if fw.lower() in content:
                        evidence.append(f"{dep_file} 包含后端框架: {fw}")
                        return True, evidence
    elif language == "Java":
        for dep_file in ("pom.xml", "build.gradle", "build.gradle.kts"):
            path = root / dep_file
            if path.exists():
                content = load_text(path).lower()
                for fw in BACKEND_FRAMEWORKS.get(language, []):
                    if fw.lower() in content:
                        evidence.append(f"{dep_file} 包含后端框架: {fw}")
                        return True, evidence
    elif language == "Go":
        go_mod = root / "go.mod"
        if go_mod.exists():
            content = load_text(go_mod)
            for fw in BACKEND_FRAMEWORKS.get(language, []):
                if fw.lower() in content.lower():
                    evidence.append(f"go.mod 包含后端框架: {fw}")
                    return True, evidence
        # Go 项目也可能使用标准库 net/http，检查代码中的 HTTP 服务器特征
        code_dirs = ["cmd", "internal", "pkg", "src", "app", "server"]
        for code_dir in code_dirs:
            code_path = root / code_dir
            if not code_path.exists():
                continue
            # 检测 HTTP 服务器相关模式
            http_patterns = [
                r"http\.Server",
                r"http\.ListenAndServe",
                r"http\.Handler",
                r"mux\.Router",
                r"router\.(Handle|HandleFunc|Path|Methods)",
            ]
            for pattern in http_patterns:
                try:
                    result = subprocess.run(
                        ["rg", "-l", pattern, str(code_path)],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    if result.returncode == 0 and result.stdout.strip():
                        evidence.append(f"代码中发现 HTTP 服务器特征: {pattern} (在 {code_dir}/)")
                        return True, evidence
                except (subprocess.TimeoutExpired, FileNotFoundError):
                    pass
    elif language == "PHP":
        composer_json = read_json_safe(root / "composer.json")
        deps = {**composer_json.get("require", {}), **composer_json.get("require-dev", {})}
        for dep_name in deps.keys():
            for fw in BACKEND_FRAMEWORKS.get(language, []):
                if fw.lower() in dep_name.lower():
                    evidence.append(f"composer.json 包含后端框架: {dep_name}")
                    return True, evidence
    elif language == ".NET":
        csproj_files = list(root.glob("*.csproj"))
        for csproj in csproj_files:
            content = load_text(csproj).lower()
            if "aspnetcore" in content:
                evidence.append(f"{csproj.name} 包含 ASP.NET Core")
                return True, evidence
    elif language == "Rust":
        cargo_toml = root / "Cargo.toml"
        if cargo_toml.exists():
            content = load_text(cargo_toml).lower()
            for fw in BACKEND_FRAMEWORKS.get(language, []):
                if fw.lower() in content:
                    evidence.append(f"Cargo.toml 包含后端框架: {fw}")
                    return True, evidence
    elif language == "Ruby":
        gemfile = root / "Gemfile"
        if gemfile.exists():
            content = load_text(gemfile).lower()
            for fw in BACKEND_FRAMEWORKS.get(language, []):
                if fw.lower() in content:
                    evidence.append(f"Gemfile 包含后端框架: {fw}")
                    return True, evidence
    elif language == "Scala":
        for dep_file in ("build.sbt", "pom.xml", "build.gradle", "build.gradle.kts"):
            path = root / dep_file
            if path.exists():
                content = load_text(path).lower()
                for fw in BACKEND_FRAMEWORKS.get(language, []):
                    if fw.lower() in content:
                        evidence.append(f"{dep_file} 包含后端框架: {fw}")
                        return True, evidence

    # 方法二：检查路由特征
    code_dirs = ["src", "app", "server", "routes", "api", "controllers"]
    # 对于 Go 项目，也检查 cmd、internal、pkg 目录
    if language == "Go":
        code_dirs.extend(["cmd", "internal", "pkg"])
    for code_dir in code_dirs:
        code_path = root / code_dir
        if not code_path.exists():
            continue

        patterns = ROUTE_PATTERNS.get(language, [])
        for pattern in patterns:
            try:
                result = subprocess.run(
                    ["rg", "-l", pattern, str(code_path)],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0 and result.stdout.strip():
                    evidence.append(f"代码中发现路由特征: {pattern} (在 {code_dir}/)")
                    return True, evidence
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass

    return False, evidence


def detect_frontend_app(root: Path) -> Tuple[bool, List[str]]:
    """检测是否为前端WEB应用。"""
    evidence = []

    # 检查 package.json
    pkg_json = read_json_safe(root / "package.json")
    deps = {**pkg_json.get("dependencies", {}), **pkg_json.get("devDependencies", {})}
    for dep_name in deps.keys():
        for fw in FRONTEND_FRAMEWORKS:
            if fw.lower() in dep_name.lower():
                evidence.append(f"依赖文件包含前端框架: {dep_name}")
                return True, evidence

    return False, evidence


def detect_smart_contract(root: Path, language: Optional[str]) -> Tuple[bool, List[str]]:
    """检测是否为智能合约项目。"""
    evidence = []

    # 方法一：检查合约配置文件
    for config_file in BLOCKCHAIN_CONFIG_FILES:
        if (root / config_file).exists():
            evidence.append(f"检测到合约配置文件: {config_file}")
            return True, evidence

    # 方法二：检查依赖/锁文件中的区块链框架关键词
    if (root / "package.json").exists():
        pkg_json = read_json_safe(root / "package.json")
        deps = {**pkg_json.get("dependencies", {}), **pkg_json.get("devDependencies", {})}
        for dep_name in deps.keys():
            if language == "JavaScript/TypeScript":
                for fw in BLOCKCHAIN_FRAMEWORKS.get("JavaScript/TypeScript", []):
                    if fw.lower() in dep_name.lower():
                        evidence.append(f"依赖文件包含区块链框架: {dep_name}")
                        return True, evidence

    # 检查其他语言的合约框架
    if language and language in BLOCKCHAIN_FRAMEWORKS:
        if (root / "Cargo.toml").exists():  # Rust
            content = load_text(root / "Cargo.toml").lower()
            for fw in BLOCKCHAIN_FRAMEWORKS.get("Rust", []):
                if fw.lower() in content:
                    evidence.append(f"Cargo.toml 包含区块链框架: {fw}")
                    return True, evidence

        if (root / "go.mod").exists():  # Go
            content = load_text(root / "go.mod").lower()
            for fw in BLOCKCHAIN_FRAMEWORKS.get("Go", []):
                if fw.lower() in content:
                    evidence.append(f"go.mod 包含区块链框架: {fw}")
                    return True, evidence

    # 方法三：检查合约源文件
    for ext in BLOCKCHAIN_SOURCE_EXTENSIONS:
        # 检查根目录及主要子目录（contracts/, src/)
        for search_dir in [root, root / "contracts", root / "src"]:
            if search_dir.exists():
                try:
                    for file in search_dir.glob(f"*{ext}"):
                        if file.is_file():
                            evidence.append(f"检测到合约源文件: {file.relative_to(root)}")
                            return True, evidence
                except Exception:
                    pass

    # 方法四：只在真正的合约扩展名中查关键词；Rust/Go 需要框架依赖才判定
    try:
        for file in root.rglob("*"):
            if not file.is_file() or any(part in SKIP_DIRS for part in file.parts):
                continue
            suffix = file.suffix.lower()
            content = load_text(file).lower()
            if suffix == ".sol":
                for keyword in ("pragma solidity", "contract {", "interface {", "library {"):
                    if keyword in content:
                        evidence.append(f"Solidity 合约特征: {file.relative_to(root)}")
                        return True, evidence
            elif suffix == ".move":
                if "module {" in content or "public fun" in content:
                    evidence.append(f"Move 合约特征: {file.relative_to(root)}")
                    return True, evidence
            elif suffix == ".vy":
                if "@external" in content or "def " in content:
                    evidence.append(f"Vyper 合约特征: {file.relative_to(root)}")
                    return True, evidence
            elif suffix == ".rs":
                if "#[program]" in content or "#[derive(accounts)]" in content:
                    cargo = root / "Cargo.toml"
                    if cargo.exists() and any(k in load_text(cargo).lower() for k in ("anchor", "solana", "cosmwasm")):
                        evidence.append(f"Rust 合约特征: {file.relative_to(root)}")
                        return True, evidence
            elif suffix == ".go":
                gomod = root / "go.mod"
                if gomod.exists() and any(k in load_text(gomod).lower() for k in ("cosmos-sdk", "tendermint")):
                    if "keeper" in content or "msgserver" in content:
                        evidence.append(f"Go 合约特征: {file.relative_to(root)}")
                        return True, evidence
    except Exception:
        pass

    return False, evidence


STRONG_VTR_PHRASES = (
    "capture the flag", "security lab", "security testing lab", "vulnerable application",
    "penetration testing lab", "pentest lab", "ctf", "靶场", "靶机", "教学靶场", "漏洞练习",
)
WEAK_VTR_KEYWORDS = ("lab", "benchmark", "challenge", "vulnerability", "vulnerable", "educational")


def _readme_text(root: Path) -> str:
    for name in ("README.md", "README", "README.txt", "readme.md"):
        p = root / name
        if p.exists():
            try:
                return p.read_text(encoding="utf-8", errors="replace").lower()
            except OSError:
                pass
    return ""


def detect_vtr(root: Path) -> Tuple[bool, List[str]]:
    """检测是否为安全测试靶场。

    单凭 README 里的 lab/benchmark 不再判定为靶场；需要多个独立信号。
    """
    evidence: List[str] = []
    score = 0
    strong = False

    content = _readme_text(root)
    if content:
        for phrase in STRONG_VTR_PHRASES:
            if phrase in content:
                score += 2
                strong = True
                evidence.append(f"README 强信号: {phrase}")
                break
        for kw in WEAK_VTR_KEYWORDS:
            if re.search(r"(?<![a-z0-9])" + re.escape(kw) + r"(?![a-z0-9])", content):
                score += 1
                evidence.append(f"README 弱信号: {kw}")
                break

    suspicious = ("vulnerable", "vulnerability", "exploit", "challenge", "ctf", "lab")
    found_dirs = []
    try:
        for child in root.iterdir():
            if child.is_dir() and not child.name.startswith("."):
                if any(s in child.name.lower() for s in suspicious):
                    found_dirs.append(child.name)
    except OSError:
        pass
    if len(found_dirs) >= 2:
        score += 2
        strong = True
        evidence.append(f"多个靶场目录: {', '.join(found_dirs[:5])}")
    elif found_dirs:
        score += 1
        evidence.append(f"疑似靶场目录: {found_dirs[0]}")

    flag_files = []
    try:
        for p in root.rglob("*"):
            if ".git" in p.parts or "node_modules" in p.parts:
                continue
            if p.is_file() and p.name.lower() in ("flag.txt", "flag", "submit.py", "submit.sh", "score.py"):
                flag_files.append(str(p.relative_to(root)))
    except OSError:
        pass
    if flag_files:
        score += 1
        strong = True
        evidence.append(f"发现 flag/submit 文件: {', '.join(flag_files[:3])}")

    if score >= 3 and strong:
        return True, evidence
    if evidence:
        evidence.append(f"评分={score}，未达到靶场阈值（需≥3且含强信号），不判定为靶场")
    return False, evidence


CODE_EXTENSIONS = {
    ".py", ".rs", ".go", ".c", ".cc", ".cpp", ".cxx", ".h", ".hpp", ".cu", ".cuh",
    ".js", ".jsx", ".ts", ".tsx", ".java", ".kt", ".php", ".rb", ".scala", ".cs",
    ".sol", ".move", ".vy", ".sh", ".bash", ".zsh",
}
SKIP_DIRS = {".git", "node_modules", "vendor", "__pycache__", ".venv", "venv", "dist", "build", ".idea", ".vscode", "third_party", "3rdparty"}
SCAN_SKIP_DIRS = SKIP_DIRS | {"tests", "test", "examples", "example", "docs", "benchmarks", "benchmark", "e2e_test"}


def _count_fallback(root: Path) -> Tuple[int, int]:
    files = 0
    lines = 0
    try:
        for p in root.rglob("*"):
            if any(part in SKIP_DIRS for part in p.parts):
                continue
            if not p.is_file() or p.suffix.lower() not in CODE_EXTENSIONS:
                continue
            files += 1
            try:
                with p.open("r", encoding="utf-8", errors="replace") as fh:
                    for _ in fh:
                        lines += 1
            except OSError:
                pass
    except OSError:
        pass
    return files, lines


def count_code_files(root: Path) -> Tuple[int, int]:
    """统计代码文件/行数；cloc 缺失或返回 0 时用纯 Python 兜底。"""
    try:
        result = subprocess.run(
            ["cloc", "--json", "--quiet", str(root)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            cloc_data = json.loads(result.stdout)
            if "SUM" in cloc_data:
                file_count = cloc_data["SUM"].get("nFiles", 0)
                line_count = cloc_data["SUM"].get("code", 0)
                if file_count or line_count:
                    return file_count, line_count
    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError, KeyError, ValueError):
        pass
    except Exception:
        pass
    return _count_fallback(root)


INFRA_SIGNALS = {
    "agent-harness": {
        "strong": ("codex-rs", "deepseek-harness", ".mcp.json", "mcp-server", "agent-harness"),
        "keywords": ("mcpservers", "approval_policy", "allow_prefix", "prefixrule", "core.hookspath",
                     "fsmonitor", "sandbox", "harness", "agent config"),
        "files": (".mcp.json", ".codex/config.toml", "AGENTS.md", "CLAUDE.md"),
    },
    "inference-engine": {
        "strong": ("vllm", "sglang", "tensorrt-llm", "llama.cpp", "text-generation-inference"),
        "keywords": ("kv cache", "kv_cache", "pagedattention", "transformers", "cuda", "triton",
                     "openai", "serving", "torch"),
        "files": ("requirements.txt", "pyproject.toml", "CMakeLists.txt"),
    },
    "training-framework": {
        "strong": ("verl", "deepspeed", "megatron", "fsdp", "grpo"),
        "keywords": ("ray", "ppo", "trainer", "checkpoint", "reward", "rollout", "actor", "critic"),
        "files": ("pyproject.toml", "requirements.txt", "Dockerfile"),
    },
    "model-serving": {
        "strong": ("triton", "model-server", "model_serving"),
        "keywords": ("uvicorn", "fastapi", "grpc", "openai", "serving", "inference"),
        "files": ("pyproject.toml", "requirements.txt", "Dockerfile"),
    },
}

NAME_HINTS = {
    "agent-harness": ("harness", "codex", "agent", "dsh", "mcp"),
    "training-framework": ("verl", "train", "training", "grpo", "ppo", "deepspeed", "megatron", "rl"),
    "inference-engine": ("vllm", "sglang", "inference", "tensorrt", "llama", "serving"),
    "model-serving": ("triton", "model-server", "model_serving"),
}

INFRA_SKILLS = {
    "agent-harness": ("agent-config-analyzer", "sandbox-boundary-analyzer",
                      "command-injection-analyzer", "path-traversal-analyzer",
                      "rpc-surface-scanner", "config-trust-scanner",
                      "ipc-serialization-analyzer"),
    "inference-engine": ("rpc-surface-scanner", "model-loading-analyzer",
                         "ipc-serialization-analyzer", "ssrf-analyzer",
                         "path-traversal-analyzer", "race-conditions-analyzer",
                         "insecure-deserialization-analyzer", "config-trust-scanner"),
    "training-framework": ("code-injection-analyzer", "insecure-deserialization-analyzer",
                           "ipc-serialization-analyzer", "dependency-analyzer",
                           "race-conditions-analyzer", "config-trust-scanner",
                           "rpc-surface-scanner", "model-loading-analyzer"),
    "model-serving": ("rpc-surface-scanner", "config-trust-scanner", "model-loading-analyzer",
                      "ipc-serialization-analyzer", "ssrf-analyzer"),
}

TRUST_BOUNDARIES = {
    "agent-harness": ("process-exec", "config", "mcp", "sandbox", "filesystem"),
    "inference-engine": ("http", "grpc", "model-file", "ipc", "network", "native"),
    "training-framework": ("config", "checkpoint", "dataset", "distributed", "process-exec"),
    "model-serving": ("http", "model-file", "auth", "network"),
}

ENTRY_PATTERNS = {
    "http": ("uvicorn.run", "fastapi(", "@app.get", "@app.post", "http.listenandserve",
             "axum::serve", "tonic::transport", "actix_web", "flask("),
    "grpc": ("grpc.server", "grpc.newserver", "tonic::transport", "add_service("),
    "ipc": ("zmq", "nng", "ray.init", "nccl", "multiprocessing.queue", "shared_memory", "msgpack"),
    "cli": ("argparse", "click.command", "typer", "command::new", "clap", "cobra"),
    "exec": ("subprocess", "os.system", "exec(", "eval(", "command::new", "shell=true"),
    "model": ("torch.load", "pickle.load", "safetensors", "from_pretrained", "trust_remote_code", "load_format"),
    "sandbox": ("seccomp", "landlock", "chroot", "bubblewrap", "sandbox", "namespace"),
}


def _iter_scan_files(root: Path, max_files: int = 4000):
    seen = 0
    for p in root.rglob("*"):
        if seen >= max_files:
            break
        if any(part in SCAN_SKIP_DIRS for part in p.parts):
            continue
        if not p.is_file():
            continue
        if p.suffix.lower() not in CODE_EXTENSIONS and p.name not in (
            "README.md", "AGENTS.md", "CLAUDE.md", "Dockerfile", "docker-compose.yml",
            "docker-compose.yaml", ".mcp.json", "pyproject.toml", "requirements.txt",
            "package.json", "Cargo.toml", "go.mod", "CMakeLists.txt",
        ):
            continue
        seen += 1
        yield p


def detect_infra(root: Path) -> Dict[str, object]:
    """检测 AI 基础设施/agent harness 类型、入口与信任边界。"""
    evidence: Dict[str, List[str]] = {k: [] for k in INFRA_SIGNALS}
    scores: Dict[str, int] = {k: 0 for k in INFRA_SIGNALS}
    strong_flag: Dict[str, bool] = {k: False for k in INFRA_SIGNALS}
    entrypoints: List[Dict[str, object]] = []
    rel_paths: List[str] = []

    key_names = {"README.md", "AGENTS.md", "CLAUDE.md", "Dockerfile", "docker-compose.yml",
                 "docker-compose.yaml", ".mcp.json", "pyproject.toml", "requirements.txt",
                 "package.json", "Cargo.toml", "go.mod", "CMakeLists.txt"}
    key_names_lower = {n.lower() for n in key_names}

    for p in _iter_scan_files(root):
        try:
            rel = str(p.relative_to(root))
        except ValueError:
            continue
        rel_lower = rel.lower()
        pname = p.name.lower()
        rel_paths.append(rel_lower)

        # 类型信号：路径/文件名 + 关键文件内容
        text = ""
        if pname in {n.lower() for n in key_names} or p.suffix.lower() in {".toml", ".json", ".yaml", ".yml"}:
            try:
                if p.stat().st_size <= 2_000_000:
                    text = p.read_text(encoding="utf-8", errors="replace").lower()
            except OSError:
                text = ""
        for ptype, cfg in INFRA_SIGNALS.items():
            if len(evidence[ptype]) < 5:
                if any(tok in rel_lower for tok in cfg["strong"]):
                    evidence[ptype].append(f"路径/文件名: {rel}")
                    scores[ptype] += 3
                    strong_flag[ptype] = True
                if pname in {f.lower() for f in cfg["files"]}:
                    evidence[ptype].append(f"配置文件: {rel}")
                    scores[ptype] += 1
                if text:
                    for tok in cfg["strong"]:
                        if tok in text:
                            evidence[ptype].append(f"{rel} 含强信号 `{tok}`")
                            scores[ptype] += 3
                            strong_flag[ptype] = True
                            break
                    for kw in cfg["keywords"]:
                        if kw in text:
                            evidence[ptype].append(f"{rel} 含 `{kw}`")
                            scores[ptype] += 1
                            break

        # 入口/汇点扫描
        if not text and p.suffix.lower() in CODE_EXTENSIONS and p.stat().st_size <= 1_500_000:
            try:
                text = p.read_text(encoding="utf-8", errors="replace").lower()
            except OSError:
                text = ""
        if text:
            for kind, patterns in ENTRY_PATTERNS.items():
                if len([e for e in entrypoints if e["kind"] == kind]) >= 8:
                    continue
                for pat in patterns:
                    pos = text.find(pat)
                    if pos >= 0:
                        line = text.count("\n", 0, pos) + 1
                        entrypoints.append({"kind": kind, "file": rel, "line": line, "evidence": pat})
                        break

    # 项目名/顶层目录是强先验：verl -> training，vllm -> inference，codex -> agent
    top_names = [root.name.lower()]
    try:
        top_names += [c.name.lower() for c in root.iterdir() if c.is_dir() and not c.name.startswith(".")]
    except OSError:
        pass
    hinted = None
    hint_token = None
    for ptype, hints in NAME_HINTS.items():
        for hint in hints:
            if any(hint in name for name in top_names):
                hinted, hint_token = ptype, hint
                break
        if hinted:
            break

    project_types: List[str] = []
    if hinted:
        project_types = [hinted]
        scores[hinted] += 20
        strong_flag[hinted] = True
        evidence[hinted].append(f"项目名/顶层目录匹配 `{hint_token}`")
    else:
        ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
        for ptype, score in ranked:
            if len(project_types) >= 2:
                break
            if strong_flag[ptype] and score >= 3:
                project_types.append(ptype)
    for ptype in evidence:
        evidence[ptype] = list(dict.fromkeys(evidence[ptype]))[:5]

    trust: List[str] = []
    skills: List[str] = []
    for ptype in project_types:
        trust.extend(TRUST_BOUNDARIES.get(ptype, ()))
        skills.extend(INFRA_SKILLS.get(ptype, ()))
    if any(e["kind"] == "http" for e in entrypoints):
        trust.append("http")
    if any(e["kind"] == "grpc" for e in entrypoints):
        trust.append("grpc")
    if any(e["kind"] == "exec" for e in entrypoints):
        trust.append("process-exec")

    return {
        "project_types": project_types,
        "types_evidence": {k: v for k, v in evidence.items() if v},
        "entrypoints": entrypoints,
        "trust_boundaries": sorted(set(trust)),
        "recommended_skills": sorted(set(skills)),
        "type_scores": scores,
    }


def format_infra(infra: Dict[str, object]) -> str:
    lines = ["", "【基础设施画像】"]
    types = infra.get("project_types") or []
    lines.append(f"项目类型: {', '.join(types) if types else '未识别'}")
    ev = infra.get("types_evidence") or {}
    if ev:
        lines.append("判定依据:")
        for ptype, items in ev.items():
            lines.append(f"  - {ptype}: {', '.join(items[:3])}")
    ents = infra.get("entrypoints") or []
    lines.append("入口/危险点:")
    if ents:
        for e in ents[:15]:
            lines.append(f"  - [{e['kind']}] {e['file']}:{e['line']} ({e['evidence']})")
    else:
        lines.append("  - 未发现")
    lines.append(f"信任边界: {', '.join(infra.get('trust_boundaries') or []) or '未识别'}")
    lines.append(f"推荐技能: {', '.join(infra.get('recommended_skills') or []) or '无'}")
    lines.append("")
    return "\n".join(lines)


def detect_framework_type(language: Optional[str], framework: Optional[str]) -> Optional[str]:
    """根据语言和框架确定框架类型（用于路由模式匹配）。"""
    if not language:
        return None
    
    if language == "JavaScript/TypeScript":
        if framework:
            fw_lower = framework.lower()
            if "express" in fw_lower:
                return "express"
            elif "koa" in fw_lower:
                return "koa"
            elif "fastify" in fw_lower:
                return "fastify"
            elif "nest" in fw_lower:
                return "nest"
            elif "hapi" in fw_lower:
                return "hapi"
    elif language == "Python":
        if framework:
            fw_lower = framework.lower()
            if "flask" in fw_lower:
                return "flask"
            elif "django" in fw_lower:
                return "django"
            elif "fastapi" in fw_lower:
                return "fastapi"
            elif "tornado" in fw_lower:
                return "tornado"
            elif "bottle" in fw_lower:
                return "bottle"
    elif language == "Java":
        if framework:
            fw_lower = framework.lower()
            if "spring" in fw_lower:
                return "spring-boot"
            elif "play" in fw_lower:
                return "play"
    elif language == "Go":
        if framework:
            fw_lower = framework.lower()
            if "gin" in fw_lower:
                return "gin"
            elif "echo" in fw_lower:
                return "echo"
            elif "chi" in fw_lower:
                return "chi"
            elif "fiber" in fw_lower:
                return "fiber"
        # Go 项目即使没有第三方框架，也可能使用标准库
        return "go-stdlib"
    elif language == "PHP":
        if framework:
            fw_lower = framework.lower()
            if "laravel" in fw_lower:
                return "laravel"
            elif "symfony" in fw_lower:
                return "symfony"
            elif "codeigniter" in fw_lower:
                return "codeigniter"
            elif "yii" in fw_lower:
                return "yii"
    elif language == ".NET":
        if framework and "aspnet" in framework.lower():
            return "aspnetcore"
    elif language == "Rust":
        if framework:
            fw_lower = framework.lower()
            if "actix" in fw_lower:
                return "actix"
            elif "rocket" in fw_lower:
                return "rocket"
            elif "warp" in fw_lower:
                return "warp"
    elif language == "Ruby":
        if framework:
            fw_lower = framework.lower()
            if "rails" in fw_lower:
                return "rails"
            elif "sinatra" in fw_lower:
                return "sinatra"
    elif language == "Scala":
        if framework:
            fw_lower = framework.lower()
            if "play" in fw_lower:
                return "play"
    # Kotlin 可能通过 Java 检测到
    if language in ("Java", "Scala") and framework and "ktor" in framework.lower():
        return "ktor"
    
    return None


def find_router_files_with_snippets(root: Path, language: Optional[str], framework: Optional[str]) -> Tuple[List[str], List[str]]:
    """根据框架类型查找路由文件并提取代码片段。
    
    返回: (文件列表, 代码片段列表)
    """
    router_files = []
    router_snippets = []
    
    # 步骤1: 确定框架类型
    framework_type = detect_framework_type(language, framework)
    if not framework_type:
        return [], []
    
    # 步骤2: 获取该框架的路由注册模式
    patterns = ROUTE_PATTERNS.get(framework_type, [])
    if not patterns:
        return [], []
    
    # 步骤3: 确定代码文件扩展名和搜索目录
    code_extensions_map = {
        "express": (".js", ".ts"),
        "koa": (".js", ".ts"),
        "fastify": (".js", ".ts"),
        "nest": (".ts", ".js"),
        "hapi": (".js", ".ts"),
        "flask": (".py",),
        "django": (".py",),
        "fastapi": (".py",),
        "tornado": (".py",),
        "bottle": (".py",),
        "spring-boot": (".java",),
        "play": (".java", ".scala"),
        "gin": (".go",),
        "echo": (".go",),
        "chi": (".go",),
        "fiber": (".go",),
        "go-stdlib": (".go",),
        "laravel": (".php",),
        "symfony": (".php",),
        "codeigniter": (".php",),
        "yii": (".php",),
        "aspnetcore": (".cs",),
        "actix": (".rs",),
        "rocket": (".rs",),
        "warp": (".rs",),
        "rails": (".rb",),
        "sinatra": (".rb",),
        "ktor": (".kt",),
    }
    code_extensions = code_extensions_map.get(framework_type, (".js", ".ts", ".py", ".java", ".go", ".php", ".cs", ".rs", ".rb", ".kt", ".scala"))
    
    # 确定搜索目录
    code_dirs = ["src", "app", "server", "routes", "routers", "api", "controllers", "handlers"]
    if language == "Go":
        code_dirs.extend(["cmd", "internal", "pkg"])
    elif language == "Ruby":
        code_dirs.extend(["app", "config"])
    elif language == "Rust":
        code_dirs.extend(["src", "examples"])
    elif language == "Scala":
        code_dirs.extend(["app", "src"])
    
    # 步骤4: 使用 ripgrep 搜索匹配的文件和代码片段
    for pattern in patterns:
        try:
            # 构建 ripgrep 命令，搜索所有代码目录
            search_paths = []
            for code_dir in code_dirs:
                code_path = root / code_dir
                if code_path.exists() and code_path.is_dir():
                    search_paths.append(str(code_path))
            
            if not search_paths:
                # 如果没有找到代码目录，搜索整个项目
                search_paths = [str(root)]
            
            # 使用 ripgrep 搜索，显示匹配的行和上下文
            # 由于已经限制了搜索目录，不需要额外限制文件类型
            cmd = ["rg", "-n", "-C", "1", pattern] + search_paths
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10,
            )
            
            if result.returncode == 0 and result.stdout.strip():
                # 解析 ripgrep 输出，提取文件和代码片段
                current_file = None
                for line in result.stdout.split("\n"):
                    if line.startswith("--"):
                        continue
                    # ripgrep 输出格式: file:line:content
                    if ":" in line:
                        parts = line.split(":", 2)
                        if len(parts) >= 3:
                            file_path = parts[0]
                            line_num = parts[1]
                            content = parts[2].strip()
                            
                            # 转换为相对路径
                            try:
                                rel_path = str(Path(file_path).relative_to(root))
                            except ValueError:
                                rel_path = file_path
                            
                            if rel_path not in router_files:
                                router_files.append(rel_path)
                            
                            # 提取代码片段（不限制长度，完整显示）
                            if content:
                                # 完整显示代码行，不截断
                                snippet = f"{rel_path}:{line_num}: {content}"
                                if snippet not in router_snippets:
                                    router_snippets.append(snippet)
                
                if len(router_files) >= 50:  # 只限制文件数量，不限制片段数量
                    break
                    
        except (subprocess.TimeoutExpired, FileNotFoundError):
            # ripgrep 不存在或超时，跳过
            continue
        except Exception:
            continue
    
    return router_files[:50], router_snippets  # 不限制代码片段数量


def find_entry_points(root: Path, language: Optional[str] = None, framework: Optional[str] = None) -> Tuple[List[str], List[str], List[str]]:
    """查找入口文件和路由文件。
    
    返回: (入口文件列表, 路由文件列表, 路由代码片段列表)
    """
    entry_files = []
    
    # 查找主入口文件
    for entry_file in ENTRY_FILES:
        for path in root.rglob(entry_file):
            if path.is_file():
                rel_path = str(path.relative_to(root))
                entry_files.append(rel_path)
                break
    
    # 根据框架查找路由文件和代码片段
    router_files, router_snippets = find_router_files_with_snippets(root, language, framework)
    
    return entry_files[:5], router_files, router_snippets


def get_main_dirs(root: Path) -> List[str]:
    """获取主要目录结构。"""
    main_dirs = []
    exclude_dirs = {".git", "node_modules", "vendor", "__pycache__", ".venv", "venv", "dist", "build", ".idea", ".vscode"}

    for child in root.iterdir():
        if child.is_dir() and not child.name.startswith(".") and child.name not in exclude_dirs:
            main_dirs.append(child.name)

    return sorted(main_dirs)[:10]


def format_output(
    root: Path,
    language: Optional[str],
    framework: Optional[str],
    package_manager: Optional[str],
    is_backend: bool,
    is_frontend: bool,
    is_smart_contract: bool,
    is_vtr: bool,
    file_count: int,
    line_count: int,
    entry_files: List[str],
    router_files: List[str],
    router_snippets: List[str],
    main_dirs: List[str],
    backend_evidence: List[str],
    frontend_evidence: List[str],
    smart_contract_evidence: List[str],
    vtr_evidence: List[str],
) -> str:
    """格式化输出结果。"""
    lines = [""]
    lines.append("== 项目基本信息 ==")
    lines.append("")

    # 项目分类
    lines.append("【项目分类】")
    if is_vtr:
        lines.append("✓ 安全测试靶场（互斥）")
        if vtr_evidence:
            for ev in vtr_evidence:
                lines.append(f"  - {ev}")
    else:
        if is_backend:
            lines.append("✓ 后端HTTP服务")
            if backend_evidence:
                for ev in backend_evidence:
                    lines.append(f"  - {ev}")
        if is_frontend:
            lines.append("✓ 前端WEB应用")
            if frontend_evidence:
                for ev in frontend_evidence:
                    lines.append(f"  - {ev}")
        if is_smart_contract:
            lines.append("✓ 智能合约项目")
            if smart_contract_evidence:
                for ev in smart_contract_evidence:
                    lines.append(f"  - {ev}")
        if not is_backend and not is_frontend and not is_smart_contract:
            lines.append("- 未检测到明确的分类特征")
    lines.append("")

    # 技术栈
    lines.append("【技术栈】")
    lines.append(f"主要语言: {language or '未知'}")
    lines.append(f"框架: {framework or '未知'}")
    lines.append(f"包管理器: {package_manager or '未知'}")
    lines.append("")

    # 代码统计
    lines.append("【代码统计】")
    lines.append(f"文件数量: {file_count}")
    lines.append(f"代码行数: {line_count:,}")
    if main_dirs:
        lines.append(f"主要目录: {', '.join(main_dirs)}")
    lines.append("")

    # 入口点
    lines.append("【入口点】")
    if entry_files:
        lines.append(f"主入口文件: {', '.join(entry_files)}")
    else:
        lines.append("主入口文件: 未找到")
    if router_files:
        lines.append(f"路由文件: {', '.join(router_files[:5])}")
        if len(router_files) > 5:
            lines.append(f"  ... 还有 {len(router_files) - 5} 个路由文件")
    else:
        lines.append("路由文件: 未找到")
    lines.append("")
    
    # 路由代码片段
    if router_snippets:
        lines.append("【路由代码片段】")
        for snippet in router_snippets:
            lines.append(f"  {snippet}")
        lines.append("")

    return "\n".join(lines)


def build_json_profile(root, language, framework, package_manager,
                      is_backend, is_frontend, is_smart_contract, is_vtr,
                      file_count, line_count, entry_files, router_files,
                      infra) -> Dict[str, object]:
    project_types: List[str] = []
    skills: List[str] = []
    if is_vtr:
        project_types = ["security-lab"]
        skills = ["vtr-scanner"]
    else:
        if is_backend:
            project_types.append("backend-http")
            skills.extend(("web-auth-analyzer", "sensitive-info-scanner"))
        if is_frontend:
            project_types.append("frontend-web")
        if is_smart_contract:
            project_types.append("smart-contract")
            skills.append("blockchain-goldmine-analyzer")
        project_types.extend(infra.get("project_types") or [])
        skills.extend(infra.get("recommended_skills") or [])
    return {
        "project_name": root.name,
        "project_path": str(root),
        "languages": [language] if language else [],
        "framework": framework,
        "package_manager": package_manager,
        "files": {"count": file_count, "lines": line_count},
        "classification": {
            "backend_http": is_backend,
            "frontend_web": is_frontend,
            "smart_contract": is_smart_contract,
            "security_lab": is_vtr,
        },
        "project_types": list(dict.fromkeys(project_types)),
        "entrypoints": {
            "main_files": entry_files,
            "route_files": router_files,
            "infra": infra.get("entrypoints") or [],
        },
        "trust_boundaries": infra.get("trust_boundaries") or [],
        "recommended_skills": list(dict.fromkeys(skills)),
        "infra_evidence": infra.get("types_evidence") or {},
        "type_scores": infra.get("type_scores") or {},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="项目基本信息快速收集")
    parser.add_argument("path", nargs="?", default=".", help="要检测的项目路径，默认当前目录")
    parser.add_argument("--json", action="store_true", help="输出机器可读 JSON（含基础设施画像）")
    parser.add_argument("--output", "-o", default="", help="写入文件（默认 stdout）")
    args = parser.parse_args()
    root = Path(args.path).resolve()
    if not root.exists():
        print(f"路径不存在: {root}")
        return

    language, framework, package_manager = detect_language(root)

    is_backend, backend_evidence = detect_backend_service(root, language)
    is_frontend, frontend_evidence = detect_frontend_app(root)
    is_smart_contract, smart_contract_evidence = detect_smart_contract(root, language)
    is_vtr, vtr_evidence = detect_vtr(root)

    if is_vtr:
        is_backend = False
        is_frontend = False
        is_smart_contract = False

    file_count, line_count = count_code_files(root)
    entry_files, router_files, router_snippets = find_entry_points(root, language, framework)
    main_dirs = get_main_dirs(root)
    infra = detect_infra(root)

    if args.json:
        payload = build_json_profile(
            root, language, framework, package_manager,
            is_backend, is_frontend, is_smart_contract, is_vtr,
            file_count, line_count, entry_files, router_files, infra,
        )
        text = json.dumps(payload, ensure_ascii=False, indent=2)
    else:
        text = format_output(
            root, language, framework, package_manager,
            is_backend, is_frontend, is_smart_contract, is_vtr,
            file_count, line_count, entry_files, router_files,
            router_snippets, main_dirs,
            backend_evidence, frontend_evidence,
            smart_contract_evidence, vtr_evidence,
        )
        text += format_infra(infra)

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)


if __name__ == "__main__":
    main()

