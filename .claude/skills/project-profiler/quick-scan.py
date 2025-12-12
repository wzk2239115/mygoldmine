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


def detect_vtr(root: Path) -> Tuple[bool, List[str]]:
    """检测是否为安全测试靶场。"""
    evidence = []

    # 方法一：检查 README 文件
    readme_files = ["README.md", "README", "README.txt"]
    for readme_file in readme_files:
        readme_path = root / readme_file
        if readme_path.exists():
            content = load_text(readme_path).lower()
            for keyword in VTR_KEYWORDS:
                if keyword.lower() in content:
                    evidence.append(f"{readme_file} 包含关键词: {keyword}")
                    return True, evidence

    # 方法二：检查目录结构（包含多个漏洞示例目录）
    # 这里简化处理，检查是否有明显的漏洞相关目录
    suspicious_dirs = ["vulnerable", "vulnerability", "exploit", "challenge", "lab", "benchmark"]
    found_dirs = []
    for child in root.iterdir():
        if child.is_dir() and not child.name.startswith("."):
            for sus_dir in suspicious_dirs:
                if sus_dir.lower() in child.name.lower():
                    found_dirs.append(child.name)
    if len(found_dirs) >= 2:
        evidence.append(f"目录结构包含多个可疑目录: {', '.join(found_dirs[:5])}")
        return True, evidence

    return False, evidence


def count_code_files(root: Path) -> Tuple[int, int]:
    """使用 cloc 命令统计代码文件数量和代码行数。"""
    try:
        # 使用 cloc 的 JSON 输出格式
        result = subprocess.run(
            ["cloc", "--json", "--quiet", str(root)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            cloc_data = json.loads(result.stdout)
            # cloc JSON 格式包含 SUM 字段
            if "SUM" in cloc_data:
                file_count = cloc_data["SUM"].get("nFiles", 0)
                line_count = cloc_data["SUM"].get("code", 0)
                return file_count, line_count
    except FileNotFoundError:
        # cloc 命令不存在，返回 0
        return 0, 0
    except (subprocess.TimeoutExpired, json.JSONDecodeError, KeyError, ValueError):
        # cloc 执行失败或输出格式异常，返回 0
        return 0, 0
    except Exception:
        # 其他异常，返回 0
        return 0, 0

    return 0, 0


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
    is_vtr: bool,
    file_count: int,
    line_count: int,
    entry_files: List[str],
    router_files: List[str],
    router_snippets: List[str],
    main_dirs: List[str],
    backend_evidence: List[str],
    frontend_evidence: List[str],
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
        if not is_backend and not is_frontend:
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


def main() -> None:
    parser = argparse.ArgumentParser(description="项目基本信息快速收集")
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

    # 检测技术栈
    language, framework, package_manager = detect_language(root)

    # 检测项目分类
    is_backend, backend_evidence = detect_backend_service(root, language)
    is_frontend, frontend_evidence = detect_frontend_app(root)
    is_vtr, vtr_evidence = detect_vtr(root)

    # 如果检测为靶场，则互斥其他分类
    if is_vtr:
        is_backend = False
        is_frontend = False

    # 统计代码
    file_count, line_count = count_code_files(root)

    # 查找入口点（传递语言和框架信息用于路由检测）
    entry_files, router_files, router_snippets = find_entry_points(root, language, framework)

    # 获取主要目录
    main_dirs = get_main_dirs(root)

    # 格式化输出
    output = format_output(
        root,
        language,
        framework,
        package_manager,
        is_backend,
        is_frontend,
        is_vtr,
        file_count,
        line_count,
        entry_files,
        router_files,
        router_snippets,
        main_dirs,
        backend_evidence,
        frontend_evidence,
        vtr_evidence,
    )
    print(output)


if __name__ == "__main__":
    main()

