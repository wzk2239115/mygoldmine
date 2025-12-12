#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""认证分析快速搜索脚本。

依据 `.claude/skills/web-auth-analyzer/SKILL.md` 的分析维度，
快速搜索认证相关的代码和框架：
1) 认证机制识别（JWT/Session/OAuth/API Key等）
2) 认证中间件和装饰器
3) 认证豁免/白名单配置
4) 用户角色体系
5) 权限模型（RBAC/ABAC/ACL）
6) 会话管理配置
7) 认证绕过风险点
"""

import argparse
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Tree-sitter 支持（使用 tree-sitter-language-pack）
from tree_sitter import Parser, Language, Query  # type: ignore
from tree_sitter_language_pack import get_parser  # type: ignore

# 认证机制搜索模式
AUTH_MECHANISM_PATTERNS = {
    "JWT": [
        r"jwt\.(verify|sign|decode|encode)",
        r"jsonwebtoken|express-jwt|expressjwt",
        r"JWT_SECRET|JWT_KEY|jwtSecret",
        r"jwt-go|jwt\.Parse|jwt\.Sign",
    ],
    "Session": [
        r"express-session|cookie-session",
        r"session\.(get|set|destroy|regenerate)",
        r"SESSION_|COOKIE_",
        r"sessionStore|session\.save",
    ],
    "OAuth": [
        r"oauth|OAuth",
        r"/oauth/token|grant_type|access_token",
        r"passport\.(use|authenticate)",
        r"oauth2|OAuth2",
    ],
    "OIDC": [
        r"openid|oidc|OIDC",
        r"id_token|\.well-known/openid-configuration",
        r"nonce",
    ],
    "API Key": [
        r"api[_-]?key|apikey|API_KEY",
        r"X-API-Key|Authorization.*Bearer",
    ],
    "Basic Auth": [
        r"basic[_-]?auth|BasicAuth",
        r"Authorization.*Basic",
    ],
}

# 框架特定的认证模式
FRAMEWORK_AUTH_PATTERNS = {
    "express": [
        r"passport\.(use|authenticate|serializeUser)",
        r"expressJwt|expressjwt",
        r"app\.use\(.*[Aa]uth|router\.use\(.*[Aa]uth",
    ],
    "nest": [
        r"@UseGuards\(|class.*Guard.*implements.*CanActivate",
        r"@(Public|Roles|RequireAuth|Authenticated)",
    ],
    "spring-boot": [
        r"@(PreAuthorize|Secured|RolesAllowed|EnableWebSecurity)",
        r"SecurityFilterChain|WebSecurityConfigurerAdapter|authorizeRequests",
        r"OncePerRequestFilter|doFilterInternal",
    ],
    "django": [
        r"@(login_required|permission_required|user_passes_test)",
        r"IsAuthenticated|IsAdminUser|permission_classes|authentication_classes",
        r"AUTHENTICATION_BACKENDS|MIDDLEWARE.*Auth",
    ],
    "flask": [
        r"@login_required|LoginManager|current_user",
        r"jwt_required|create_access_token|JWTManager",
    ],
    "go": [
        r"\.Use\(.*[Aa]uth|JWT\(|BasicAuth|AuthRequired",
        r"jwt-go|jwt\.Parse|jwt\.Sign",
    ],
    "laravel": [
        r"->middleware\(.*auth|'auth'|Authenticate::class",
        r"Route::(middleware|group).*auth",
    ],
    "fastapi": [
        r"Depends\(.*auth|oauth2_scheme|HTTPBearer",
        r"Security\(|get_current_user|verify_token",
    ],
}

# 认证豁免/白名单模式（更精确的匹配）
AUTH_BYPASS_PATTERNS = [
    # 白名单/豁免配置（认证上下文）
    r"(auth|middleware|route).*(whitelist|exclude|skip|public|anonymous)",
    r"(whitelist|exclude|skip|public|anonymous).*(auth|middleware|route|endpoint)",
    r"(public|anonymous).*(path|route|endpoint|access)",
    r"publicPath|publicPaths|public.*path",
    r"allowAnonymous|allow.*anonymous",
    # 认证禁用/绕过
    r"(disable|skip|bypass).*auth",
    r"no.*auth|noauth",
    # 环境变量控制
    r"(DEBUG|DEV_MODE|DISABLE_AUTH|NO_AUTH|ENABLE_AUTH).*=.*(true|false|1|0)",
    r"if.*(DEBUG|DEV_MODE|DISABLE_AUTH|NO_AUTH)",
    # 条件豁免
    r"(if|when).*(skip|bypass|disable).*auth",
    r"auth.*=.*false|auth.*disabled",
]

# 用户角色体系模式
ROLE_PATTERNS = [
    r"(enum.*Role|ROLE_|UserRole|UserType)",
    r"(role|roles|user_type|is_admin|is_staff)",
    r"@(Roles|RequireRole|hasRole)",
    r"(RoleGuard|PermissionGuard|RolesGuard)",
    r"(authorize|permissions|access_control)",
]

# 权限模型模式
PERMISSION_MODEL_PATTERNS = {
    "RBAC": [
        r"Role.*Permission|roles.*permissions|role_permissions",
    ],
    "ABAC": [
        r"policy|attributes|context.*auth|can\(|ability",
    ],
    "ACL": [
        r"acl|access.*list|owner_id|can.*access",
    ],
    "Policy Engine": [
        r"casbin|opa|cedar|enforce|policy.*engine",
    ],
}

# 权限提升风险模式
PRIVILEGE_ESCALATION_PATTERNS = [
    r"(update|set|change|modify).*(role|permission|admin)",
    r"(grant|add|assign|give).*(permission|role)",
    r"default.*(role|permission)|role.*=.*(admin|root)",
]

# 会话管理安全模式
SESSION_SECURITY_PATTERNS = {
    "cookie_attributes": [
        r"(httpOnly|secure|sameSite).*:",
        r"setHeader.*Set-Cookie",
    ],
    "session_regeneration": [
        r"(regenerate|renew|rotate).*session|session\.save",
    ],
    "session_id_generation": [
        r"Math\.random|uuid\(\)|randomBytes|SecureRandom",
    ],
    "session_timeout": [
        r"maxAge|expires|cookie\.maxAge",
    ],
}

# Token 生命周期模式
TOKEN_LIFECYCLE_PATTERNS = [
    r"expiresIn|exp|TTL|expires_in",
    r"refreshToken|refresh_expires|refresh_token",
    r"token.*revoke|blacklist|logout",
    r"localStorage\.setItem|sessionStorage",
]

# 认证安全风险模式
AUTH_SECURITY_RISK_PATTERNS = {
    "hardcoded_secret": [
        r"(secret|key|password|token).*=.*['\"][^'\"]{8,}['\"]",  # 至少8个字符的硬编码值
        r"JWT_SECRET.*=.*['\"][^'\"]+['\"]",
        r"API_KEY.*=.*['\"][^'\"]+['\"]",
    ],
    "weak_secret": [
        r"(secret|key|password).*=.*['\"](secret|password|12345|admin|test|demo)['\"]",
    ],
    "jwt_none_algorithm": [
        r"algorithm.*none|algorithm.*=.*['\"]none['\"]",
        r"alg.*=.*['\"]none['\"]",
    ],
    "default_credentials": [
        r"(username|user|login).*:.*['\"](admin|root|administrator)['\"]",
        r"(password|passwd|pwd).*:.*['\"](admin|password|12345|123456)['\"]",
        r"default.*(user|password|credential).*=.*['\"][^'\"]+['\"]",
        r"credentials.*=.*\{.*(user|username).*:.*['\"](admin|root)['\"]",
    ],
}

# 语言映射常量（用于 Tree-sitter）
# 将项目语言名称映射到 tree-sitter 语言标识符
LANGUAGE_MAP = {
    "JavaScript/TypeScript": "javascript",  # JavaScript 和 TypeScript 都使用 javascript parser
    "Python": "python",
    "Go": "go",
    "Java": "java",
    "PHP": "php",
    "Ruby": "ruby",
    "Rust": "rust",
    "C": "c",
    "C++": "cpp",
    ".NET": "csharp",
    "Swift": "swift",
    "Kotlin": "kotlin",
    "Scala": "scala",
    "Lua": "lua",
    "Bash": "bash",
    "YAML": "yaml",
    "JSON": "json",
    "HTML": "html",
    "CSS": "css",
}

# 测试文件后缀列表（统一管理）
TEST_FILE_SUFFIXES = [
    "_test.go", "_test.py", "_test.php", "_test.rs",
    ".test.js", ".test.ts", ".test.jsx", ".test.tsx",
    "Test.java", "Tests.java",
    "_spec.rb", "_test.rb",
    ".spec.js", ".spec.ts",
    "_test.scala",
]


class TreeSitterParserManager:
    """Tree-sitter 解析器管理器，使用 tree-sitter-language-pack。
    
    该包包含 160+ 种语言的解析器，支持所有常用编程语言。
    """
    
    def __init__(self):
        self.parsers: Dict[str, Parser] = {}
        self._init_parsers()
    
    def _init_parsers(self):
        """初始化解析器管理器（language-pack 不需要预先初始化）。"""
        # tree-sitter-language-pack 使用动态加载，不需要预先初始化
        pass
    
    def get_parser(self, language: str) -> Optional[Parser]:
        """获取指定语言的解析器。"""
        # 如果已缓存，直接返回
        if language in self.parsers:
            return self.parsers[language]
        
        # 使用 tree-sitter-language-pack 动态获取
        parser = get_parser(language)
        if parser:
            # 缓存解析器
            self.parsers[language] = parser
            return parser
        return None
    
    def get_language(self, language: str) -> Optional[Language]:
        """获取指定语言的 Language 对象。"""
        parser = self.get_parser(language)
        if parser:
            return parser.language
        return None
    
    def is_supported(self, language: str) -> bool:
        """检查语言是否支持。"""
        parser = self.get_parser(language)
        return parser is not None


def search_with_treesitter(
    file_path: Path, 
    language: str, 
    parser_manager: TreeSitterParserManager,
    search_keywords: Optional[List[str]] = None,
    root: Optional[Path] = None
) -> List[Tuple[str, str, str]]:
    """使用 Tree-sitter 搜索包含特定关键词的代码。
    
    Args:
        file_path: 要搜索的文件路径
        language: 语言标识符（如 'python', 'javascript'）
        parser_manager: Tree-sitter 解析器管理器
        search_keywords: 要搜索的关键词列表，如果为 None 则搜索所有认证相关关键词
    
    Returns:
        匹配结果列表，格式为 (文件路径, 行号, 代码内容)
    """
    results = []
    
    parser = parser_manager.get_parser(language)
    if not parser:
        return results
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # 跳过测试文件
        if any(test_suffix in str(file_path) for test_suffix in TEST_FILE_SUFFIXES):
            return results
        
        # 如果没有提供关键词，使用默认的认证相关关键词
        if search_keywords is None:
            search_keywords = [
                "auth", "authentication", "authorization", "authenticate", "authorize",
                "token", "jwt", "session", "login", "logout", "password",
                "credential", "permission", "role", "user", "admin", "policy",
                "oauth", "oidc", "bearer", "api_key", "secret", "key",
                "middleware", "guard", "filter", "interceptor", "decorator",
                "public", "anonymous", "whitelist", "bypass", "skip",
            ]
        
        # 首先进行简单的文本搜索，找到包含关键词的行
        lines = content.split('\n')
        matching_lines = []
        for line_num, line in enumerate(lines, 1):
            line_lower = line.lower()
            if any(keyword.lower() in line_lower for keyword in search_keywords):
                # 过滤掉明显不相关的行
                if len(line.strip()) > 0 and len(line.strip()) < 500:
                    matching_lines.append((line_num, line))
        
        # 使用 tree-sitter 解析代码，获取更精确的位置信息
        tree = parser.parse(content.encode('utf-8'))
        lang_obj = parser_manager.get_language(language)
        if not lang_obj:
            # 如果无法获取语言对象，直接返回文本搜索结果
            for line_num, line in matching_lines:
                rel_path = str(file_path.relative_to(file_path.parent.parent.parent.parent) if file_path.is_absolute() else file_path)
                results.append((rel_path, str(line_num), line.strip()))
            return results
        
        # 对于匹配的行，尝试使用 tree-sitter 获取更精确的节点信息
        for line_num, line in matching_lines:
            # 查找包含该行的 AST 节点
            root_node = tree.root_node
            node = root_node
            
            # 找到包含该行的最小节点
            for child in root_node.children:
                if child.start_point[0] <= line_num - 1 <= child.end_point[0]:
                    node = child
                    break
            
            # 提取代码片段
            code_line = line.strip()
            if code_line:
                try:
                    # 转换为相对路径
                    if root:
                        try:
                            rel_path = str(file_path.relative_to(root))
                        except ValueError:
                            rel_path = str(file_path)
                    else:
                        rel_path = str(file_path)
                    results.append((rel_path, str(line_num), code_line))
                except Exception:
                    pass
                    
    except Exception:
        # 解析失败，返回空结果
        pass
    
    return results


def search_files_with_treesitter(
    root: Path,
    language: str,
    parser_manager: TreeSitterParserManager,
    code_extensions: Tuple[str, ...],
    search_keywords: Optional[List[str]] = None,
    max_results: int = 50
) -> List[Tuple[str, str, str]]:
    """使用 Tree-sitter 在目录中搜索包含特定关键词的文件。
    
    Args:
        root: 搜索根目录
        language: 语言标识符
        parser_manager: Tree-sitter 解析器管理器
        code_extensions: 代码文件扩展名列表
        search_keywords: 要搜索的关键词列表
        max_results: 最大结果数
    
    Returns:
        匹配结果列表，格式为 (文件路径, 行号, 代码内容)
    """
    results = []
    seen = set()  # 去重
    
    if not parser_manager.is_supported(language):
        return results
    
    # 搜索所有匹配的代码文件
    for ext in code_extensions:
        if len(results) >= max_results:
            break
        for file_path in root.rglob(f"*{ext}"):
            if len(results) >= max_results:
                break
            if file_path.is_file():
                # 传递 root 参数以便计算相对路径
                file_results = search_with_treesitter(file_path, language, parser_manager, search_keywords, root)
                for result in file_results:
                    key = (result[0], result[1], result[2])
                    if key not in seen:
                        seen.add(key)
                        results.append(result)
                        if len(results) >= max_results:
                            break
    
    return results[:max_results]


def detect_language(root: Path) -> Optional[str]:
    """检测项目主要语言。"""
    dep_files = {
        # JavaScript/TypeScript
        "package.json": "JavaScript/TypeScript",
        "tsconfig.json": "JavaScript/TypeScript",
        "yarn.lock": "JavaScript/TypeScript",
        "pnpm-lock.yaml": "JavaScript/TypeScript",
        # Python
        "requirements.txt": "Python",
        "pyproject.toml": "Python",
        "setup.py": "Python",
        "Pipfile": "Python",
        # Java
        "pom.xml": "Java",
        "build.gradle": "Java",
        "build.gradle.kts": "Java",
        # Go
        "go.mod": "Go",
        "go.sum": "Go",
        # PHP
        "composer.json": "PHP",
        "composer.lock": "PHP",
        # Rust
        "Cargo.toml": "Rust",
        "Cargo.lock": "Rust",
        # Ruby
        "Gemfile": "Ruby",
        "Gemfile.lock": "Ruby",
        # Scala
        "build.sbt": "Scala",
        # Swift
        "Package.swift": "Swift",
        # Kotlin
        "build.gradle.kts": "Kotlin",  # 可能与 Java 冲突，但通常 Kotlin 项目也会用
    }
    
    for dep_file, lang in dep_files.items():
        if (root / dep_file).exists():
            return lang
    
    # 检查 .NET
    if list(root.glob("*.csproj")) or list(root.glob("*.sln")):
        return ".NET"
    
    # 检查 C/C++
    if list(root.glob("CMakeLists.txt")) or list(root.glob("Makefile")) or list(root.glob("*.c")) or list(root.glob("*.cpp")):
        # 优先检查 C++
        if list(root.glob("*.cpp")) or list(root.glob("*.hpp")) or list(root.glob("*.cc")):
            return "C++"
        return "C"
    
    return None


def get_code_extensions(language: Optional[str]) -> Tuple[str, ...]:
    """根据语言返回代码文件扩展名。"""
    ext_map = {
        "JavaScript/TypeScript": (".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs"),
        "Python": (".py", ".pyw", ".pyi"),
        "Java": (".java",),
        "Go": (".go",),
        "PHP": (".php", ".phtml", ".php3", ".php4", ".php5"),
        ".NET": (".cs", ".vb", ".fs"),
        "Rust": (".rs",),
        "Ruby": (".rb", ".rake", ".ru"),
        "Scala": (".scala", ".sc"),
        "C": (".c", ".h"),
        "C++": (".cpp", ".cxx", ".cc", ".hpp", ".hxx", ".hh", ".h"),
        "Swift": (".swift",),
        "Kotlin": (".kt", ".kts"),
        "Lua": (".lua",),
        "Bash": (".sh", ".bash", ".zsh"),
        "YAML": (".yaml", ".yml"),
        "JSON": (".json",),
        "HTML": (".html", ".htm", ".xhtml"),
        "CSS": (".css", ".scss", ".sass", ".less"),
    }
    # 如果没有匹配的语言，返回常见扩展名
    return ext_map.get(language, (".js", ".ts", ".py", ".java", ".go", ".php", ".cs", ".rs", ".rb", ".cpp", ".c", ".swift", ".kt"))


def format_results(category: str, results: List[Tuple[str, str, str]]) -> None:
    """格式化并打印搜索结果。"""
    if not results:
        return
    
    print(f"\n## {category}")
    print(f"找到 {len(results)} 个匹配项：\n")
    
    for file_path, line_num, content in results:
        print(f"  {file_path}:{line_num}: {content}")
    
    print()


def main():
    parser = argparse.ArgumentParser(description="认证分析快速搜索脚本")
    parser.add_argument("source_dir", type=str, help="项目源码目录路径")
    parser.add_argument(
        "--category",
        choices=["all", "mechanism", "bypass", "role", "permission", "session", "token", "risk"],
        default="all",
        help="搜索类别（默认：all）",
    )
    args = parser.parse_args()
    
    root = Path(args.source_dir).resolve()
    if not root.exists():
        print(f"错误：目录不存在: {root}")
        return
    
    language = detect_language(root)
    code_extensions = get_code_extensions(language)
    
    # 初始化 Tree-sitter（必须）
    parser_manager = TreeSitterParserManager()
    ts_lang = LANGUAGE_MAP.get(language)
    
    if not ts_lang:
        print(f"警告: 未检测到支持的语言（检测到: {language}）")
        print("将尝试使用通用搜索模式")
        ts_lang = "python"  # 默认使用 python
    
    if not parser_manager.is_supported(ts_lang):
        print(f"警告: 语言 {ts_lang} 在 tree-sitter-language-pack 中不支持")
        print("请检查语言标识符是否正确，或更新 tree-sitter-language-pack")
        return
    
    print(f"项目路径: {root}")
    print(f"检测到语言: {language or '未知'}")
    print(f"Tree-sitter 语言: {ts_lang}")
    print(f"搜索代码文件: {', '.join(code_extensions)}")
    print("=" * 80)
    
    # 1. 认证机制识别
    if args.category in ("all", "mechanism"):
        print("\n# 1. 认证机制识别")
        
        # 提取认证机制相关的关键词
        auth_keywords = []
        for patterns in AUTH_MECHANISM_PATTERNS.values():
            for pattern in patterns:
                # 从正则模式中提取关键词（简化处理）
                keywords = pattern.replace("\\", "").replace("(", "").replace(")", "").replace("|", " ").split()
                auth_keywords.extend([kw for kw in keywords if len(kw) > 2 and kw.isalpha()])
        
        results = search_files_with_treesitter(
            root, ts_lang, parser_manager, code_extensions, 
            search_keywords=list(set(auth_keywords)), max_results=20
        )
        if results:
            format_results("认证机制检测", results)
    
    # 2. 认证豁免/白名单
    if args.category in ("all", "bypass"):
        print("\n# 2. 认证豁免/白名单分析")
        bypass_keywords = ["whitelist", "exclude", "skip", "public", "anonymous", "bypass", "disable", "auth"]
        results = search_files_with_treesitter(
            root, ts_lang, parser_manager, code_extensions,
            search_keywords=bypass_keywords, max_results=30
        )
        if results:
            format_results("认证豁免配置", results)
    
    # 3. 用户角色体系
    if args.category in ("all", "role"):
        print("\n# 3. 用户角色体系分析")
        role_keywords = ["role", "roles", "user_type", "is_admin", "is_staff", "authorize", "permission", "access_control"]
        results = search_files_with_treesitter(
            root, ts_lang, parser_manager, code_extensions,
            search_keywords=role_keywords, max_results=30
        )
        if results:
            format_results("角色定义和权限控制", results)
    
    # 4. 权限模型
    if args.category in ("all", "permission"):
        print("\n# 4. 权限模型分析")
        
        permission_keywords = ["permission", "policy", "rbac", "abac", "acl", "casbin", "opa", "cedar"]
        results = search_files_with_treesitter(
            root, ts_lang, parser_manager, code_extensions,
            search_keywords=permission_keywords, max_results=20
        )
        if results:
            format_results("权限模型检测", results)
        
        # 权限提升风险
        escalation_keywords = ["update", "set", "change", "modify", "role", "permission", "admin", "grant", "assign"]
        results = search_files_with_treesitter(
            root, ts_lang, parser_manager, code_extensions,
            search_keywords=escalation_keywords, max_results=20
        )
        if results:
            format_results("权限提升风险点", results)
    
    # 5. 会话管理安全
    if args.category in ("all", "session"):
        print("\n# 5. 会话管理安全分析")
        
        session_keywords = ["session", "httpOnly", "secure", "sameSite", "regenerate", "maxAge", "expires", "cookie"]
        results = search_files_with_treesitter(
            root, ts_lang, parser_manager, code_extensions,
            search_keywords=session_keywords, max_results=20
        )
        if results:
            format_results("会话安全配置", results)
    
    # 6. Token 生命周期
    if args.category in ("all", "token"):
        print("\n# 6. Token 生命周期分析")
        token_keywords = ["token", "expiresIn", "exp", "TTL", "refreshToken", "revoke", "blacklist", "logout"]
        results = search_files_with_treesitter(
            root, ts_lang, parser_manager, code_extensions,
            search_keywords=token_keywords, max_results=20
        )
        if results:
            format_results("Token 配置", results)
    
    # 7. 认证安全风险
    if args.category in ("all", "risk"):
        print("\n# 7. 认证安全风险检测")
        
        risk_keywords = ["secret", "key", "password", "token", "JWT_SECRET", "API_KEY", "algorithm", "none", "default", "credential"]
        results = search_files_with_treesitter(
            root, ts_lang, parser_manager, code_extensions,
            search_keywords=risk_keywords, max_results=20
        )
        if results:
            format_results("安全风险检测", results)
    
    print("\n" + "=" * 80)
    print("搜索完成")


if __name__ == "__main__":
    main()

