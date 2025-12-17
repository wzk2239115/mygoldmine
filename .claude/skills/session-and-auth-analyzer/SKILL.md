---
name: session-and-auth-analyzer
description: 专业的审计工作流程，通过静态代码分析识别和验证会话管理和身份认证（Session and Authentication）漏洞；重点关注检测不安全的会话管理机制和身份认证实现，包括会话固定、会话劫持、弱会话令牌、认证绕过、密码重置漏洞、多因素认证绕过、会话超时不当、并发会话控制不足等问题；利用按编程语言组织的参考资料目录中的参考指南。
---

## 通用会话管理和身份认证漏洞模式（所有项目必审）

查看详细说明：[general.md](general.md)

快速概览：会话固定攻击（会话ID在登录前后不变、会话令牌可预测）、会话劫持风险（会话令牌未加密传输、Cookie未设置HttpOnly/Secure标志、会话令牌泄露到日志）、弱会话管理（会话令牌熵值不足、会话ID可枚举、会话令牌复用）、认证绕过（密码验证逻辑缺陷、认证状态检查缺失、权限验证绕过）、密码重置漏洞（重置令牌可预测、重置链接未过期、重置流程可被绕过）、多因素认证绕过（MFA验证可跳过、MFA状态未正确验证、MFA令牌可重放）、会话超时不当（会话永不过期、超时时间过长、超时后未清除会话数据）、并发会话控制不足（未限制并发会话数、会话冲突处理不当）、会话注销不当（注销后令牌仍有效、注销未清除服务端会话、注销后重定向到受保护页面）

**绕过技巧参考**

遇到以下保护机制时，可参考 [bypassTricks.md](bypassTricks.md) 中的对应章节：

- **会话固定保护机制**：详见 bypassTricks.md → "常见绕过技巧 - 会话固定攻击"
- **会话劫持保护机制**：详见 bypassTricks.md → "常见绕过技巧 - 会话劫持"
- **认证保护机制**：详见 bypassTricks.md → "常见绕过技巧 - 认证绕过"
- **密码重置保护机制**：详见 bypassTricks.md → "常见绕过技巧 - 密码重置绕过"
- **多因素认证保护**：详见 bypassTricks.md → "常见绕过技巧 - MFA 绕过"
- **权限验证机制**：详见 bypassTricks.md → "常见绕过技巧 - 权限绕过 (IDOR)"
- **会话ID生成与验证**：详见 bypassTricks.md → "快速审计清单 - 会话ID相关"
- **会话超时与Cookie安全**：详见 bypassTricks.md → "快速审计清单 - 会话超时"
- **并发会话控制**：详见 bypassTricks.md → "快速审计清单 - 并发会话控制"
- **语言特定的安全机制**：详见 bypassTricks.md → "语言特定的注意事项"

**会话管理和身份认证（Session and Authentication）**

**Attention**  
当项目中存在用户身份认证和会话管理功能时，若对会话令牌的生成、存储、传输、验证、过期、注销等环节处理不当，或认证逻辑存在缺陷，就可能导致会话管理和身份认证类漏洞。此类问题通常出现在用户登录、会话管理、密码重置、多因素认证、权限验证、会话注销等涉及身份认证和会话状态管理的业务模块中，需重点审计会话令牌的生命周期管理和认证流程的实现逻辑。

**Early exit**  
若项目完全不涉及用户身份认证和会话管理功能（如纯静态网站、公开API无需认证、仅提供匿名访问服务），或所有认证和会话管理均由第三方服务处理（如完全依赖OAuth2/OpenID Connect提供方、使用第三方认证服务且不自行管理会话），则可快速退出对该漏洞类型的审计。

**Cases**

**Java**  
Spring Session 中会话ID在用户登录前后保持不变，存在会话固定风险，详见：[Java_Session_Fixation_Spring.md](Java_Session_Fixation_Spring.md)  
Servlet 会话管理中使用可预测的会话ID生成算法，详见：[Java_Session_Predictable_ID.md](Java_Session_Predictable_ID.md)  
Spring Security 中认证状态检查缺失，导致认证绕过，详见：[Java_Auth_Bypass_Missing_Check.md](Java_Auth_Bypass_Missing_Check.md)  
密码重置功能中重置令牌可被枚举或预测，详见：[Java_Password_Reset_Token_Predictable.md](Java_Password_Reset_Token_Predictable.md)  
多因素认证验证逻辑可被绕过，详见：[Java_MFA_Bypass_Logic.md](Java_MFA_Bypass_Logic.md)

**Python**  
Django 会话管理中 Cookie 未设置 HttpOnly 和 Secure 标志，详见：[Python_Session_Cookie_Insecure.md](Python_Session_Cookie_Insecure.md)  
Flask 会话令牌使用弱随机数生成器，熵值不足，详见：[Python_Session_Weak_Random.md](Python_Session_Weak_Random.md)  
Django 认证中密码验证逻辑存在缺陷，允许弱密码或空密码，详见：[Python_Auth_Weak_Password_Validation.md](Python_Auth_Weak_Password_Validation.md)  
密码重置流程中重置链接未设置过期时间，详见：[Python_Password_Reset_No_Expiry.md](Python_Password_Reset_No_Expiry.md)  
会话注销后服务端会话数据未清除，详见：[Python_Session_Logout_Incomplete.md](Python_Session_Logout_Incomplete.md)

**Go**  
Gorilla Sessions 中会话令牌未加密传输，存在会话劫持风险，详见：[Go_Session_Token_Unencrypted.md](Go_Session_Token_Unencrypted.md)  
会话ID生成使用时间戳或可预测算法，详见：[Go_Session_ID_Predictable.md](Go_Session_ID_Predictable.md)  
认证中间件中权限验证逻辑可被绕过，详见：[Go_Auth_Middleware_Bypass.md](Go_Auth_Middleware_Bypass.md)  
密码重置功能中重置令牌泄露到日志或错误信息，详见：[Go_Password_Reset_Token_Leak.md](Go_Password_Reset_Token_Leak.md)  
会话超时配置不当，会话永不过期，详见：[Go_Session_No_Timeout.md](Go_Session_No_Timeout.md)

**PHP**  
PHP 原生 Session 中会话ID可被枚举，详见：[PHP_Session_ID_Enumeration.md](PHP_Session_ID_Enumeration.md)  
Laravel 会话管理中会话令牌复用，同一令牌可被多次使用，详见：[PHP_Session_Token_Reuse.md](PHP_Session_Token_Reuse.md)  
认证逻辑中用户输入直接用于数据库查询，存在SQL注入导致认证绕过，详见：[PHP_Auth_SQL_Injection.md](PHP_Auth_SQL_Injection.md)  
密码重置功能中重置流程可被绕过，未验证用户身份，详见：[PHP_Password_Reset_Bypass.md](PHP_Password_Reset_Bypass.md)  
多因素认证状态未正确验证，MFA验证可被跳过，详见：[PHP_MFA_State_Not_Verified.md](PHP_MFA_State_Not_Verified.md)

**JavaScript / TypeScript (Node.js)**  
Express Session 中会话数据存储在客户端且未签名，可被篡改，详见：[NodeJS_Session_Client_Storage.md](NodeJS_Session_Client_Storage.md)  
JWT 作为会话令牌时未设置过期时间或过期时间过长，详见：[NodeJS_Session_JWT_No_Expiry.md](NodeJS_Session_JWT_No_Expiry.md)  
认证中间件中认证状态检查顺序错误，导致认证绕过，详见：[NodeJS_Auth_Middleware_Order.md](NodeJS_Auth_Middleware_Order.md)  
密码重置功能中重置令牌可被重放攻击，详见：[NodeJS_Password_Reset_Replay.md](NodeJS_Password_Reset_Replay.md)  
并发会话控制缺失，未限制同一用户并发会话数，详见：[NodeJS_Session_No_Concurrent_Limit.md](NodeJS_Session_No_Concurrent_Limit.md)

**C/C++**  
自定义会话管理中会话令牌使用弱哈希算法，详见：[C_Session_Weak_Hash.md](C_Session_Weak_Hash.md)  
会话存储中使用不安全的随机数生成器，详见：[CPP_Session_Weak_Random.md](CPP_Session_Weak_Random.md)  
认证函数中密码比较使用字符串比较而非安全比较，存在时序攻击风险，详见：[C_Auth_Timing_Attack.md](C_Auth_Timing_Attack.md)  
会话注销后内存中的会话数据未清除，详见：[CPP_Session_Logout_Memory_Leak.md](CPP_Session_Logout_Memory_Leak.md)  
会话超时检查逻辑缺失，会话永不过期，详见：[C_Session_No_Timeout_Check.md](C_Session_No_Timeout_Check.md)

**Rust**  
Actix Session 中会话令牌生成使用可预测的随机数，详见：[Rust_Session_Predictable_Token.md](Rust_Session_Predictable_Token.md)  
会话存储中会话数据未加密，敏感信息泄露，详见：[Rust_Session_Unencrypted_Storage.md](Rust_Session_Unencrypted_Storage.md)  
认证处理中用户输入验证不足，存在认证绕过，详见：[Rust_Auth_Input_Validation.md](Rust_Auth_Input_Validation.md)
密码重置功能中重置令牌生成算法不安全，详见：[Rust_Password_Reset_Weak_Token.md](Rust_Password_Reset_Weak_Token.md)
多因素认证实现中MFA令牌验证逻辑可被绕过，详见：[Rust_MFA_Verification_Bypass.md](Rust_MFA_Verification_Bypass.md)

# 输出要求

确认漏洞后，加载 `bug-report` 技能获取标准化报告格式，生成漏洞报告文件。

**加载技能**：`bug-report`

**输出路径**：`.workspace/findings/BUG-session-auth-{file}-L{line}-{source}-{sink}.md`

**约束**：
- 每个漏洞必须生成独立的 BUG 文件，禁止合并或省略
- 漏洞报告格式严格遵循 `bug-report` 技能定义的模板