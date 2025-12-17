---
name: security-configuration-analyzer
description: 专业的审计工作流程，通过静态代码分析识别和验证安全配置漏洞；重点关注检测未正确设置或显式加固的安全策略、配置参数或默认行为，包括默认配置、过度宽松的权限策略、敏感信息硬编码、未启用安全机制（如 HTTPS、CSP、CORS 限制）或环境配置误用等问题；利用按编程语言组织的参考资料目录中的参考指南。
---

**Attention**  
当项目中存在身份认证、访问控制、加密通信、权限管理、日志记录或第三方服务集成等安全敏感功能时，若相关安全策略、配置参数或默认行为未被正确设置或显式加固，即可能引入安全配置漏洞。此类漏洞通常源于使用默认配置、过度宽松的权限策略、敏感信息硬编码、未启用安全机制（如 HTTPS、CSP、CORS 限制等）或环境差异（如开发/测试配置误用于生产）。

**Early exit**  
若项目为纯计算型、无网络交互、无用户权限模型、无外部依赖、无配置文件（如 JSON/YAML/.env/config 等）且完全运行于隔离可信环境（如本地 CLI 工具、无状态脚本），则可快速退出对该漏洞类型的审计。

---

## 通用安全配置漏洞模式（所有项目必审）

查看详细说明：[general.md](general.md)

快速概览：
- **敏感信息硬编码或明文存储**（凭证密钥硬编码、配置文件明文存储），绕过技巧详见：[bypassTricks.md - 默认凭证和配置](bypassTricks.md#默认凭证和配置)
- **TLS/SSL 配置不安全**（证书验证被禁用、弱加密套件、缺少HSTS），绕过技巧详见：[bypassTricks.md - HTTPS配置不当](bypassTricks.md#https配置不当)
- **CORS 配置过于宽松**，绕过技巧详见：[bypassTricks.md - CORS配置漏洞](bypassTricks.md#cors配置漏洞)
- **HTTP 安全响应头缺失**，绕过技巧详见：[bypassTricks.md - 缺少安全头](bypassTricks.md#缺少安全头)
- **会话管理配置不安全**
- **身份认证和授权配置缺陷**（JWT/OAuth配置错误、密码策略不当）
- **默认配置和凭证使用**，绕过技巧详见：[bypassTricks.md - 默认密码](bypassTricks.md#默认密码)
- **访问控制和权限配置不当**（文件权限过宽、RBAC配置过宽），绕过技巧详见：[bypassTricks.md - 权限配置错误](bypassTricks.md#权限配置错误)
- **数据库和缓存配置不安全**
- **第三方服务集成配置不当**
- **环境配置混用或泄露**，绕过技巧详见：[bypassTricks.md - 错误处理和信息泄露](bypassTricks.md#错误处理和信息泄露)
- **不安全的 Git 配置参数验证**（Git Hook 注入、恶意配置路径），绕过技巧详见：[bypassTricks.md - Git和版本控制暴露](bypassTricks.md#git和版本控制暴露)
- **正则表达式拒绝服务（ReDoS）**，绕过技巧详见：[bypassTricks.md - ReDoS](bypassTricks.md#redos-正则表达式拒绝服务---cwe-1333)

**关于 Git 配置注入**：若项目中集成或调用 Git 功能（如版本控制、自动化工作流），需特别关注用户输入是否直接传递给 Git 配置参数。攻击者可通过设置危险的配置项（如 `core.hooksPath`）导致远程代码执行，详见：[general_Git_Configuration_Injection.md](general_Git_Configuration_Injection.md)

---

**语言特定实现（根据项目语言选择性审计）**

以下漏洞场景与具体编程语言的安全配置实现方式相关。根据项目所使用的编程语言，仅需审计对应语言章节中的漏洞模式。

**Java**
常出现在 Spring Security 配置、Web 容器（如 Tomcat）安全策略、JWT 验证逻辑、日志脱敏设置等业务逻辑实现中，包括但不限于禁用 CSRF 保护、宽松 CORS 策略、未校验签名算法等方式，详见：
- Spring Security 配置中使用弱安全策略或过度开放权限，详见：[java_Weak_Spring_Security_Config.md](java_Weak_Spring_Security_Config.md)，绕过技巧详见：[bypassTricks.md - 权限配置错误](bypassTricks.md#权限配置错误)
- 在 Web 应用中禁用 CSRF 防护机制，详见：[java_Disabled_CSRF_Protection.md](java_Disabled_CSRF_Protection.md)
- JWT 令牌验证时未正确校验签名算法或密钥，详见：[java_Insecure_JWT_Verification.md](java_Insecure_JWT_Verification.md)

**Python**
常出现在 Flask/Django 安全中间件配置、数据库连接参数、环境变量加载、调试模式启用等场景中，包括但不限于 debug=True 暴露敏感信息、SECRET_KEY 硬编码、ALLOWED_HOSTS 过宽等方式，详见：
- 在生产环境中启用调试模式导致敏感信息泄露，详见：[python_Debug_Mode_Enabled.md](python_Debug_Mode_Enabled.md)，绕过技巧详见：[bypassTricks.md - 调试界面暴露](bypassTricks.md#调试界面暴露)
- 在代码中硬编码 SECRET_KEY 或其他密钥配置，详见：[python_Hardcoded_Secret_Key.md](python_Hardcoded_Secret_Key.md)，绕过技巧详见：[bypassTricks.md - 默认凭证和配置](bypassTricks.md#默认凭证和配置)
- CORS 配置过于宽松允许任意来源访问，详见：[python_Overly_Permissive_CORS.md](python_Overly_Permissive_CORS.md)，绕过技巧详见：[bypassTricks.md - CORS配置漏洞](bypassTricks.md#cors配置漏洞)

**Go**
常出现在 HTTP 服务初始化、TLS 配置、RBAC 策略定义、第三方库默认行为覆盖等逻辑中，包括但不限于跳过证书验证、未限制请求来源、使用默认密钥等方式，详见：
- TLS 客户端配置中跳过证书验证导致中间人攻击风险，详见：[go_Skip_TLS_Verify.md](go_Skip_TLS_Verify.md)，绕过技巧详见：[bypassTricks.md - HTTPS配置不当](bypassTricks.md#https配置不当)
- 使用默认或过于宽松的 RBAC 权限控制规则，详见：[go_Default_RBAC_Rules.md](go_Default_RBAC_Rules.md)，绕过技巧详见：[bypassTricks.md - 权限配置错误](bypassTricks.md#权限配置错误)
- CORS 配置未限制请求来源允许任意跨域访问，详见：[go_Unrestricted_CORS.md](go_Unrestricted_CORS.md)，绕过技巧详见：[bypassTricks.md - CORS配置漏洞](bypassTricks.md#cors配置漏洞)

**PHP**
常出现在 .htaccess 配置、ini 设置、会话管理、错误报告级别等 Web 安全相关模块中，包括但不限于 display_errors=On、session.cookie_httponly=Off、allow_url_include=On 等方式，详见：
- 错误报告配置过于详细导致敏感信息泄露，详见：[php_Excessive_Error_Disclosure.md](php_Excessive_Error_Disclosure.md)，绕过技巧详见：[bypassTricks.md - Stack trace泄露](bypassTricks.md#stack-trace泄露)
- 会话配置不安全（如缺少 HttpOnly、Secure 标志），详见：[php_Insecure_Session_Config.md](php_Insecure_Session_Config.md)
- 启用远程文件包含功能导致代码注入风险，详见：[php_Remote_File_Inclusion_Enabled.md](php_Remote_File_Inclusion_Enabled.md)
- 内容安全策略（CSP）配置缺陷，详见：[php_csp_policy_bypass.md](php_csp_policy_bypass.md)
- HTTP Security Headers 缺失配置，详见：[php_http_security_headers.md](php_http_security_headers.md)，绕过技巧详见：[bypassTricks.md - 缺少安全头](bypassTricks.md#缺少安全头)
- OAuth/OpenID Connect 配置错误，详见：[php_oauth_misconfiguration.md](php_oauth_misconfiguration.md)
- 正则表达式拒绝服务（ReDoS）风险，绕过技巧详见：[bypassTricks.md - ReDoS](bypassTricks.md#redos-正则表达式拒绝服务---cwe-1333)

**JavaScript / TypeScript**
常出现在前端 CSP 策略、CORS 设置、OAuth 重定向 URI 验证、环境配置加载等逻辑中，包括但不限于 unsafe-inline 脚本、通配符 origin、未校验 redirect_uri 等方式，详见：
- 内容安全策略（CSP）配置过弱或包含不安全指令，详见：[js_Weak_CSP_Policy.md](js_Weak_CSP_Policy.md)，绕过技巧详见：[bypassTricks.md - 缺少安全头](bypassTricks.md#缺少安全头)
- OAuth 流程中未正确验证重定向 URI 导致授权劫持，详见：[ts_Insecure_OAuth_Redirect.md](ts_Insecure_OAuth_Redirect.md)
- CORS 配置使用通配符允许任意来源访问，详见：[js_Wildcard_CORS_Origin.md](js_Wildcard_CORS_Origin.md)，绕过技巧详见：[bypassTricks.md - CORS配置漏洞](bypassTricks.md#cors配置漏洞)
- 正则表达式拒绝服务（ReDoS）风险，绕过技巧详见：[bypassTricks.md - ReDoS](bypassTricks.md#redos-正则表达式拒绝服务---cwe-1333)

**C/C++**
常出现在网络服务初始化、TLS/SSL 上下文配置、文件权限设置、环境变量解析等安全相关功能中，包括但不限于硬编码密钥、未验证证书、宽松的文件访问模式等方式，详见：
- TLS/SSL 配置中禁用证书验证或使用不安全的加密套件，详见：[cpp_Insecure_TLS_Config.md](cpp_Insecure_TLS_Config.md)，绕过技巧详见：[bypassTricks.md - HTTPS配置不当](bypassTricks.md#https配置不当)
- 在源代码中硬编码敏感凭证或密钥信息，详见：[c_Hardcoded_Credentials.md](c_Hardcoded_Credentials.md)，绕过技巧详见：[bypassTricks.md - 默认凭证和配置](bypassTricks.md#默认凭证和配置)
- 文件创建或操作时使用过于宽松的权限设置，详见：[cpp_Permissive_File_Permissions.md](cpp_Permissive_File_Permissions.md)，绕过技巧详见：[bypassTricks.md - 文件权限不当](bypassTricks.md#文件权限不当)

**Rust**
常出现在使用 reqwest、tokio-tls、actix-web 等库构建服务时的安全选项配置中，包括但不限于禁用证书验证、未启用 HTTPS 强制跳转、使用不安全的随机源等方式，详见：
- HTTP 客户端配置中禁用 TLS 证书验证，详见：[rust_Disable_TLS_Verification.md](rust_Disable_TLS_Verification.md)，绕过技巧详见：[bypassTricks.md - HTTPS配置不当](bypassTricks.md#https配置不当)
- Web 服务未配置 HSTS 响应头导致降级攻击风险，详见：[rust_Missing_HSTS_Header.md](rust_Missing_HSTS_Header.md)，绕过技巧详见：[bypassTricks.md - 缺少安全头](bypassTricks.md#缺少安全头)
- 随机数生成配置不安全或使用不可靠的随机源，详见：[rust_Insecure_Random_Config.md](rust_Insecure_Random_Config.md)

# 输出要求

确认漏洞后，加载 `bug-report` 技能获取标准化报告格式，生成漏洞报告文件。

**加载技能**：`bug-report`

**输出路径**：`.workspace/findings/BUG-sec-config-{file}-L{line}-{source}-{sink}.md`

**约束**：
- 每个漏洞必须生成独立的 BUG 文件，禁止合并或省略
- 漏洞报告格式严格遵循 `bug-report` 技能定义的模板