---
name: open-redirect-analyzer
description: 专业的审计工作流程，通过静态代码分析识别和验证开放重定向（Open Redirect）漏洞；重点关注检测不安全的 URL 重定向实现，即用户可控输入（URL 参数、请求头、表单字段等）未经适当验证或过滤直接用于构造重定向目标，从而将用户重定向到攻击者控制的恶意 URL；利用按编程语言组织的参考资料目录中的参考指南。
---

## 通用开放重定向漏洞模式（所有项目必审）

查看详细说明：[general.md](general.md)

快速概览：用户输入直接用于重定向目标（URL 参数可控、请求头可控、表单字段可控）、重定向目标验证缺失或不足（未验证域名、未使用白名单、白名单可被绕过）、相对路径重定向（相对路径解析、路径遍历绕过）、协议验证缺失（未限制协议、javascript: 协议未禁止、data: 协议未禁止）、重定向链未限制（多次重定向、重定向次数未限制）、OAuth/SSO 回调重定向未验证（OAuth 回调 URL、SSO 重定向目标）、登录后重定向未验证（登录成功重定向、登出重定向）、外部链接跳转未验证（外部链接跳转、第三方服务跳转）

**开放重定向（Open Redirect）**

**Attention**  
当项目中存在将用户可控输入（如 URL 参数、请求头、表单字段等）直接用于构造重定向目标的业务逻辑时，极易引发开放重定向漏洞。此类问题通常出现在登录后重定向、OAuth/SSO 回调处理、外部链接跳转、登出重定向、密码重置后跳转等涉及 URL 重定向的业务模块中，需重点审计重定向函数的调用点，特别是用户输入未经过滤或验证直接作为重定向目标 URL 的场景。

**Early exit**  
若项目完全不涉及任何 URL 重定向功能（如纯静态页面、纯 API 服务无页面跳转、仅使用客户端路由且无服务端重定向），或所有重定向目标均为硬编码且无任何用户输入参与重定向 URL 构造，则可快速退出对该漏洞类型的审计。

**Cases**

**Python**
Flask redirect() 函数直接使用用户输入作为重定向目标，未进行域名验证，详见：[Python_Flask_Redirect_User_Input.md](Python_Flask_Redirect_User_Input.md)
Django HttpResponseRedirect 使用用户可控的 URL 参数，未实施白名单验证，详见：[Python_Django_Redirect_Unvalidated.md](Python_Django_Redirect_Unvalidated.md)
OAuth 回调处理中 redirect_uri 参数未验证，详见：[Python_OAuth_Callback_Redirect.md](Python_OAuth_Callback_Redirect.md)
登录成功后重定向到用户提供的 return_url，未校验目标域名，详见：[Python_Login_Redirect_Unvalidated.md](Python_Login_Redirect_Unvalidated.md)
相对路径重定向导致路径遍历绕过，详见：[Python_Relative_Path_Redirect.md](Python_Relative_Path_Redirect.md)

**遇到保护机制时**：
- 协议检查保护：详见 [bypassTricks.md - 1. 协议相关绕过](bypassTricks.md#1-协议相关绕过)
- 域名验证保护（黑名单/白名单）：详见 [bypassTricks.md - 2. 域名验证绕过](bypassTricks.md#2-域名验证绕过)
- 路径和查询参数检查：详见 [bypassTricks.md - 3. 路径和查询参数绕过](bypassTricks.md#3-路径和查询参数绕过)
- JavaScript/Data协议拦截：详见 [bypassTricks.md - 4. 数据 URL 和 JavaScript 协议绕过](bypassTricks.md#4-数据-url-和-javascript-协议绕过)
- URL编码检查：详见 [bypassTricks.md - 7. 编码绕过](bypassTricks.md#7-编码绕过)
- 特殊字符过滤：详见 [bypassTricks.md - 8. null 字节和特殊字符绕过](bypassTricks.md#8-null-字节和特殊字符绕过)
- 相对URL限制：详见 [bypassTricks.md - 9. 相对 URL 和路径遍历](bypassTricks.md#9-相对-url-和路径遍历)

**Java**
Spring MVC RedirectView 直接使用用户输入构造重定向 URL，未进行安全验证，详见：[Java_Spring_RedirectView_User_Input.md](Java_Spring_RedirectView_User_Input.md)
HttpServletResponse.sendRedirect() 使用用户可控参数，未实施白名单或域名验证，详见：[Java_HttpServletResponse_Redirect.md](Java_HttpServletResponse_Redirect.md)
OAuth2 授权服务器中 redirect_uri 参数验证不足，详见：[Java_OAuth2_Redirect_URI_Validation.md](Java_OAuth2_Redirect_URI_Validation.md)
登录后重定向到 returnUrl 参数，未校验目标地址合法性，详见：[Java_Login_ReturnUrl_Unvalidated.md](Java_Login_ReturnUrl_Unvalidated.md)
SSO 单点登录重定向目标未验证，详见：[Java_SSO_Redirect_Unvalidated.md](Java_SSO_Redirect_Unvalidated.md)

**遇到保护机制时**：
- 协议检查保护：详见 [bypassTricks.md - 1. 协议相关绕过](bypassTricks.md#1-协议相关绕过)
- 域名验证保护（黑名单/白名单）：详见 [bypassTricks.md - 2. 域名验证绕过](bypassTricks.md#2-域名验证绕过)
- 路径和查询参数检查：详见 [bypassTricks.md - 3. 路径和查询参数绕过](bypassTricks.md#3-路径和查询参数绕过)
- JavaScript/Data协议拦截：详见 [bypassTricks.md - 4. 数据 URL 和 JavaScript 协议绕过](bypassTricks.md#4-数据-url-和-javascript-协议绕过)
- URL编码检查：详见 [bypassTricks.md - 7. 编码绕过](bypassTricks.md#7-编码绕过)
- 特殊字符过滤：详见 [bypassTricks.md - 8. null 字节和特殊字符绕过](bypassTricks.md#8-null-字节和特殊字符绕过)
- 相对URL限制：详见 [bypassTricks.md - 9. 相对 URL 和路径遍历](bypassTricks.md#9-相对-url-和路径遍历)
- OAuth特定保护：详见 [bypassTricks.md - 11. OAuth 和 OIDC 特定绕过](bypassTricks.md#11-oauth-和-oidc-特定绕过)
- Spring框架保护：详见 [bypassTricks.md - 12.1 Spring Security 绕过](bypassTricks.md#121-spring-security-绕过)

**Go**
使用 http.Redirect() 直接重定向到用户输入 URL，未进行域名白名单验证，详见：[Go_HTTP_Redirect_User_Input.md](Go_HTTP_Redirect_User_Input.md)
Gin 框架 c.Redirect() 使用用户可控参数，未实施安全验证，详见：[Go_Gin_Redirect_Unvalidated.md](Go_Gin_Redirect_Unvalidated.md)
OAuth 回调处理中 redirect_uri 未验证，详见：[Go_OAuth_Redirect_URI_Validation.md](Go_OAuth_Redirect_URI_Validation.md)
登录成功后重定向到 return_url，未校验目标域名，详见：[Go_Login_Redirect_Unvalidated.md](Go_Login_Redirect_Unvalidated.md)
相对路径重定向导致安全绕过，详见：[Go_Relative_Path_Redirect.md](Go_Relative_Path_Redirect.md)

**遇到保护机制时**：
- 协议检查保护：详见 [bypassTricks.md - 1. 协议相关绕过](bypassTricks.md#1-协议相关绕过)
- 域名验证保护（黑名单/白名单）：详见 [bypassTricks.md - 2. 域名验证绕过](bypassTricks.md#2-域名验证绕过)
- 路径和查询参数检查：详见 [bypassTricks.md - 3. 路径和查询参数绕过](bypassTricks.md#3-路径和查询参数绕过)
- JavaScript/Data协议拦截：详见 [bypassTricks.md - 4. 数据 URL 和 JavaScript 协议绕过](bypassTricks.md#4-数据-url-和-javascript-协议绕过)
- URL编码检查：详见 [bypassTricks.md - 7. 编码绕过](bypassTricks.md#7-编码绕过)
- 特殊字符过滤：详见 [bypassTricks.md - 8. null 字节和特殊字符绕过](bypassTricks.md#8-null-字节和特殊字符绕过)
- 相对URL限制：详见 [bypassTricks.md - 9. 相对 URL 和路径遍历](bypassTricks.md#9-相对-url-和路径遍历)
- OAuth特定保护：详见 [bypassTricks.md - 11. OAuth 和 OIDC 特定绕过](bypassTricks.md#11-oauth-和-oidc-特定绕过)

**PHP**
使用 header('Location: ...') 直接重定向到用户输入 URL，未进行验证，详见：[PHP_Header_Location_User_Input.md](PHP_Header_Location_User_Input.md)
Laravel redirect() 辅助函数使用用户可控参数，未实施白名单验证，详见：[PHP_Laravel_Redirect_Unvalidated.md](PHP_Laravel_Redirect_Unvalidated.md)
OAuth 回调中 redirect_uri 参数验证不足，详见：[PHP_OAuth_Redirect_URI_Validation.md](PHP_OAuth_Redirect_URI_Validation.md)
登录后重定向到 return_url，未校验目标地址，详见：[PHP_Login_Redirect_Unvalidated.md](PHP_Login_Redirect_Unvalidated.md)
外部链接跳转功能未验证目标域名，详见：[PHP_External_Link_Redirect.md](PHP_External_Link_Redirect.md)

**遇到保护机制时**：
- 协议检查保护：详见 [bypassTricks.md - 1. 协议相关绕过](bypassTricks.md#1-协议相关绕过)
- 域名验证保护（黑名单/白名单）：详见 [bypassTricks.md - 2. 域名验证绕过](bypassTricks.md#2-域名验证绕过)
- 路径和查询参数检查：详见 [bypassTricks.md - 3. 路径和查询参数绕过](bypassTricks.md#3-路径和查询参数绕过)
- JavaScript/Data协议拦截：详见 [bypassTricks.md - 4. 数据 URL 和 JavaScript 协议绕过](bypassTricks.md#4-数据-url-和-javascript-协议绕过)
- URL编码检查：详见 [bypassTricks.md - 7. 编码绕过](bypassTricks.md#7-编码绕过)
- 特殊字符过滤：详见 [bypassTricks.md - 8. null 字节和特殊字符绕过](bypassTricks.md#8-null-字节和特殊字符绕过)
- 相对URL限制：详见 [bypassTricks.md - 9. 相对 URL 和路径遍历](bypassTricks.md#9-相对-url-和路径遍历)
- OAuth特定保护：详见 [bypassTricks.md - 11. OAuth 和 OIDC 特定绕过](bypassTricks.md#11-oauth-和-oidc-特定绕过)
- Laravel框架保护：详见 [bypassTricks.md - 12.2 Laravel 绕过](bypassTricks.md#122-laravel-绕过)

**JavaScript / TypeScript (Node.js)**
Express res.redirect() 直接使用用户输入作为重定向目标，未进行域名验证，详见：[NodeJS_Express_Redirect_User_Input.md](NodeJS_Express_Redirect_User_Input.md)
Koa ctx.redirect() 使用用户可控参数，未实施白名单验证，详见：[NodeJS_Koa_Redirect_Unvalidated.md](NodeJS_Koa_Redirect_Unvalidated.md)
OAuth 回调处理中 redirect_uri 未验证，详见：[NodeJS_OAuth_Redirect_URI_Validation.md](NodeJS_OAuth_Redirect_URI_Validation.md)
登录成功后重定向到 returnUrl，未校验目标域名，详见：[NodeJS_Login_Redirect_Unvalidated.md](NodeJS_Login_Redirect_Unvalidated.md)
相对路径重定向导致路径遍历，详见：[NodeJS_Relative_Path_Redirect.md](NodeJS_Relative_Path_Redirect.md)

**遇到保护机制时**：
- 协议检查保护：详见 [bypassTricks.md - 1. 协议相关绕过](bypassTricks.md#1-协议相关绕过)
- 域名验证保护（黑名单/白名单）：详见 [bypassTricks.md - 2. 域名验证绕过](bypassTricks.md#2-域名验证绕过)
- 路径和查询参数检查：详见 [bypassTricks.md - 3. 路径和查询参数绕过](bypassTricks.md#3-路径和查询参数绕过)
- JavaScript/Data协议拦截：详见 [bypassTricks.md - 4. 数据 URL 和 JavaScript 协议绕过](bypassTricks.md#4-数据-url-和-javascript-协议绕过)
- URL编码检查：详见 [bypassTricks.md - 7. 编码绕过](bypassTricks.md#7-编码绕过)
- 特殊字符过滤：详见 [bypassTricks.md - 8. null 字节和特殊字符绕过](bypassTricks.md#8-null-字节和特殊字符绕过)
- 相对URL限制：详见 [bypassTricks.md - 9. 相对 URL 和路径遍历](bypassTricks.md#9-相对-url-和路径遍历)
- OAuth特定保护：详见 [bypassTricks.md - 11. OAuth 和 OIDC 特定绕过](bypassTricks.md#11-oauth-和-oidc-特定绕过)
- Express框架保护：详见 [bypassTricks.md - 12.3 Express.js 绕过](bypassTricks.md#123-expressjs-绕过)

**C/C++**
使用 HTTP 响应头 Location 直接重定向到用户输入 URL，未进行安全验证，详见：[C_HTTP_Location_Header_User_Input.md](C_HTTP_Location_Header_User_Input.md)
自定义重定向函数使用用户可控参数，未实施域名白名单，详见：[C_Custom_Redirect_Unvalidated.md](C_Custom_Redirect_Unvalidated.md)

**遇到保护机制时**：
- 协议检查保护：详见 [bypassTricks.md - 1. 协议相关绕过](bypassTricks.md#1-协议相关绕过)
- 域名验证保护（黑名单/白名单）：详见 [bypassTricks.md - 2. 域名验证绕过](bypassTricks.md#2-域名验证绕过)
- 路径和查询参数检查：详见 [bypassTricks.md - 3. 路径和查询参数绕过](bypassTricks.md#3-路径和查询参数绕过)
- JavaScript/Data协议拦截：详见 [bypassTricks.md - 4. 数据 URL 和 JavaScript 协议绕过](bypassTricks.md#4-数据-url-和-javascript-协议绕过)
- URL编码检查：详见 [bypassTricks.md - 7. 编码绕过](bypassTricks.md#7-编码绕过)
- 特殊字符过滤：详见 [bypassTricks.md - 8. null 字节和特殊字符绕过](bypassTricks.md#8-null-字节和特殊字符绕过)
- 相对URL限制：详见 [bypassTricks.md - 9. 相对 URL 和路径遍历](bypassTricks.md#9-相对-url-和路径遍历)

**Rust**
使用 actix-web HttpResponse::Redirect 直接重定向到用户输入，未进行域名验证，详见：[Rust_Actix_Redirect_User_Input.md](Rust_Actix_Redirect_User_Input.md)
Rocket 框架 Redirect::to() 使用用户可控参数，未实施白名单验证，详见：[Rust_Rocket_Redirect_Unvalidated.md](Rust_Rocket_Redirect_Unvalidated.md)
OAuth 回调处理中 redirect_uri 验证不足，详见：[Rust_OAuth_Redirect_URI_Validation.md](Rust_OAuth_Redirect_URI_Validation.md)

**遇到保护机制时**：
- 协议检查保护：详见 [bypassTricks.md - 1. 协议相关绕过](bypassTricks.md#1-协议相关绕过)
- 域名验证保护（黑名单/白名单）：详见 [bypassTricks.md - 2. 域名验证绕过](bypassTricks.md#2-域名验证绕过)
- 路径和查询参数检查：详见 [bypassTricks.md - 3. 路径和查询参数绕过](bypassTricks.md#3-路径和查询参数绕过)
- JavaScript/Data协议拦截：详见 [bypassTricks.md - 4. 数据 URL 和 JavaScript 协议绕过](bypassTricks.md#4-数据-url-和-javascript-协议绕过)
- URL编码检查：详见 [bypassTricks.md - 7. 编码绕过](bypassTricks.md#7-编码绕过)
- 特殊字符过滤：详见 [bypassTricks.md - 8. null 字节和特殊字符绕过](bypassTricks.md#8-null-字节和特殊字符绕过)
- 相对URL限制：详见 [bypassTricks.md - 9. 相对 URL 和路径遍历](bypassTricks.md#9-相对-url-和路径遍历)
- OAuth特定保护：详见 [bypassTricks.md - 11. OAuth 和 OIDC 特定绕过](bypassTricks.md#11-oauth-和-oidc-特定绕过)

# 输出要求

确认漏洞后，加载 `bug-report` 技能获取标准化报告格式，生成漏洞报告文件。

**加载技能**：`bug-report`

**输出路径**：`.workspace/findings/BUG-open-redirect-{file}-L{line}-{source}-{sink}.md`

**约束**：
- 每个漏洞必须生成独立的 BUG 文件，禁止合并或省略
- 漏洞报告格式严格遵循 `bug-report` 技能定义的模板

