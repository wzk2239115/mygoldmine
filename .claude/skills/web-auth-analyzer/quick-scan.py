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
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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


def search_patterns(
    root: Path, patterns: List[str], file_extensions: Optional[Tuple[str, ...]] = None, max_results: int = 50
) -> List[Tuple[str, str, str]]:
    """使用 ripgrep 搜索模式，返回 (文件路径, 行号, 内容) 列表。"""
    results = []
    seen = set()  # 去重
    
    if not patterns:
        return results
    
    # 测试文件模式（排除）- 使用 **/ 匹配所有子目录
    test_file_patterns = [
        "**/*_test.go", "**/*_test.py", "**/*_test.php", "**/*_test.rs",
        "**/*.test.js", "**/*.test.ts", "**/*.test.jsx", "**/*.test.tsx",
        "**/*Test.java", "**/*Tests.java",
        "**/*_spec.rb", "**/*_test.rb",
        "**/*.spec.js", "**/*.spec.ts",
        "**/*_test.scala",
    ]
    
    # 对每个模式分别搜索，避免复杂正则表达式问题
    for pattern in patterns:
        if len(results) >= max_results:
            break
        
        # 构建 ripgrep 命令
        cmd = ["rg", "-n", "--max-count", str(max_results)]
        
        # 排除测试文件（使用 ! 前缀）
        for test_pattern in test_file_patterns:
            cmd.extend(["-g", f"!{test_pattern}"])
        
        # 限制文件类型
        if file_extensions:
            for ext in file_extensions:
                cmd.extend(["-g", f"*{ext}"])
        
        cmd.append(pattern)
        cmd.append(str(root))
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            
            if result.returncode == 0 and result.stdout.strip():
                for line in result.stdout.splitlines():
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
                            
                            # 过滤测试文件（双重检查，确保排除）
                            test_suffixes = [
                                "_test.go", "_test.py", "_test.php", "_test.rs",
                                ".test.js", ".test.ts", ".test.jsx", ".test.tsx",
                                "Test.java", "Tests.java",
                                "_spec.rb", "_test.rb",
                                ".spec.js", ".spec.ts",
                                "_test.scala",
                            ]
                            if any(
                                rel_path.endswith(suffix) 
                                or f"/{suffix}" in rel_path 
                                or f"\\{suffix}" in rel_path
                                or f"_{suffix}" in rel_path
                                for suffix in test_suffixes
                            ):
                                continue
                            
                            # 过滤不相关的代码片段（内容相关性检查）
                            content_lower = content.lower()
                            
                            # 排除明显不相关的关键词（更全面的列表）
                            irrelevant_keywords = [
                                # I/O 操作
                                "skipbytes", "skip_bytes", "skip bytes", "skipfile", "skip file",
                                "ioutil", "io/util", "internal/util", "internal/ioutil",
                                "buffer", "read", "write", "copy", "stream",
                                # 数据处理
                                "len(", "length", "size", "offset", "compressed", "decompressed",
                                "metadata", "cache", "heal", "replication",
                                # 注释和文档
                                "// configured", "// also skips", "// skipping", "// should skip",
                                "// check", "// returns", "// find", "// apply",
                                # 文件操作
                                "fileinfo", "modtime", "version", "entry", "entries",
                            ]
                            
                            # 认证相关关键词（更全面的列表）
                            auth_keywords = [
                                "auth", "authentication", "authorization", "authenticate", "authorize",
                                "token", "jwt", "session", "login", "logout", "password",
                                "credential", "permission", "role", "user", "admin", "policy",
                                "oauth", "oidc", "bearer", "api_key", "secret", "key",
                                "middleware", "guard", "filter", "interceptor", "decorator",
                                "public", "anonymous", "whitelist", "bypass", "skip.*auth",
                            ]
                            
                            # 检查是否包含认证相关关键词
                            has_auth_keyword = any(kw in content_lower for kw in auth_keywords)
                            
                            # 检查是否只包含不相关关键词
                            has_irrelevant_only = any(
                                kw in content_lower 
                                for kw in irrelevant_keywords
                            ) and not has_auth_keyword
                            
                            # 如果代码片段很短且只包含不相关关键词，则跳过
                            if len(content.strip()) < 60 and has_irrelevant_only:
                                continue
                            
                            # 对于认证豁免搜索，需要更严格的检查
                            # 如果包含 skip/exclude 但没有认证上下文，则跳过
                            if any(kw in content_lower for kw in ["skip", "exclude"]) and not has_auth_keyword:
                                # 检查是否是明显的非认证上下文
                                non_auth_contexts = [
                                    "compression", "compress", "decompress",
                                    "healing", "heal", "disk",
                                    "metadata", "cache", "file",
                                    "offset", "length", "size",
                                    "buffer", "stream", "read", "write",
                                ]
                                if any(ctx in content_lower for ctx in non_auth_contexts):
                                    continue
                            
                            # 过滤超长的字符串常量（通常是错误码定义等）
                            if len(content.strip()) > 500:
                                continue
                            
                            # 过滤明显是错误码或常量定义的行
                            if content.strip().startswith("const ") and "=" in content and len(content) > 200:
                                continue
                            
                            # 去重
                            key = (rel_path, line_num, content)
                            if key not in seen:
                                seen.add(key)
                                results.append((rel_path, line_num, content))
                                
                                if len(results) >= max_results:
                                    break
            
        except (subprocess.TimeoutExpired, FileNotFoundError):
            # ripgrep 不存在或超时，继续下一个模式
            continue
        except Exception:
            continue
    
    return results[:max_results]


def detect_language(root: Path) -> Optional[str]:
    """检测项目主要语言。"""
    dep_files = {
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
    
    for dep_file, lang in dep_files.items():
        if (root / dep_file).exists():
            return lang
    
    # 检查 .NET
    if list(root.glob("*.csproj")):
        return ".NET"
    
    return None


def get_code_extensions(language: Optional[str]) -> Tuple[str, ...]:
    """根据语言返回代码文件扩展名。"""
    ext_map = {
        "JavaScript/TypeScript": (".js", ".ts", ".jsx", ".tsx"),
        "Python": (".py",),
        "Java": (".java",),
        "Go": (".go",),
        "PHP": (".php",),
        ".NET": (".cs",),
        "Rust": (".rs",),
        "Ruby": (".rb",),
        "Scala": (".scala",),
    }
    return ext_map.get(language, (".js", ".ts", ".py", ".java", ".go", ".php", ".cs", ".rs", ".rb"))


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
    
    print(f"项目路径: {root}")
    print(f"检测到语言: {language or '未知'}")
    print(f"搜索代码文件: {', '.join(code_extensions)}")
    print("=" * 80)
    
    # 1. 认证机制识别
    if args.category in ("all", "mechanism"):
        print("\n# 1. 认证机制识别")
        
        for auth_type, patterns in AUTH_MECHANISM_PATTERNS.items():
            results = search_patterns(root, patterns, code_extensions, max_results=20)
            if results:
                format_results(f"认证机制: {auth_type}", results)
        
        # 框架特定的认证模式
        if language:
            lang_lower = language.lower()
            for fw_name, patterns in FRAMEWORK_AUTH_PATTERNS.items():
                if fw_name in lang_lower or any(fw in lang_lower for fw in ["javascript", "typescript", "python", "java", "go", "php"]):
                    results = search_patterns(root, patterns, code_extensions, max_results=20)
                    if results:
                        format_results(f"框架认证模式: {fw_name}", results)
    
    # 2. 认证豁免/白名单
    if args.category in ("all", "bypass"):
        print("\n# 2. 认证豁免/白名单分析")
        results = search_patterns(root, AUTH_BYPASS_PATTERNS, code_extensions, max_results=30)
        if results:
            format_results("认证豁免配置", results)
    
    # 3. 用户角色体系
    if args.category in ("all", "role"):
        print("\n# 3. 用户角色体系分析")
        results = search_patterns(root, ROLE_PATTERNS, code_extensions, max_results=30)
        if results:
            format_results("角色定义和权限控制", results)
    
    # 4. 权限模型
    if args.category in ("all", "permission"):
        print("\n# 4. 权限模型分析")
        
        for model_type, patterns in PERMISSION_MODEL_PATTERNS.items():
            results = search_patterns(root, patterns, code_extensions, max_results=20)
            if results:
                format_results(f"权限模型: {model_type}", results)
        
        # 权限提升风险
        results = search_patterns(root, PRIVILEGE_ESCALATION_PATTERNS, code_extensions, max_results=20)
        if results:
            format_results("权限提升风险点", results)
    
    # 5. 会话管理安全
    if args.category in ("all", "session"):
        print("\n# 5. 会话管理安全分析")
        
        for sec_type, patterns in SESSION_SECURITY_PATTERNS.items():
            results = search_patterns(root, patterns, code_extensions, max_results=20)
            if results:
                format_results(f"会话安全: {sec_type}", results)
    
    # 6. Token 生命周期
    if args.category in ("all", "token"):
        print("\n# 6. Token 生命周期分析")
        results = search_patterns(root, TOKEN_LIFECYCLE_PATTERNS, code_extensions, max_results=20)
        if results:
            format_results("Token 配置", results)
    
    # 7. 认证安全风险
    if args.category in ("all", "risk"):
        print("\n# 7. 认证安全风险检测")
        
        for risk_type, patterns in AUTH_SECURITY_RISK_PATTERNS.items():
            results = search_patterns(root, patterns, code_extensions, max_results=20)
            if results:
                format_results(f"安全风险: {risk_type}", results)
    
    print("\n" + "=" * 80)
    print("搜索完成")


if __name__ == "__main__":
    main()

