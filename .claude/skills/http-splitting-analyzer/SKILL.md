---
name: http-splitting-analyzer
description: 专业的审计工作流程，通过静态代码分析识别和验证 HTTP 响应分割（HTTP Response Splitting）漏洞；重点关注检测 HTTP 响应头构造过程中，用户可控输入未经适当验证或过滤直接用于构造响应头字段，导致 CRLF 注入、响应头分割、响应体污染、缓存投毒、会话固定等安全问题；利用按编程语言组织的参考资料目录中的参考指南。
---

## 通用 HTTP 响应分割漏洞模式（所有项目必审）

查看详细说明：[general.md](general.md)

快速概览：CRLF 注入导致响应分割（用户输入直接拼接进响应头、未过滤 \r\n 字符）、Location 头注入（重定向 URL 未验证、CRLF 未过滤）、Set-Cookie 头注入（Cookie 值未验证、CRLF 未过滤）、Content-Disposition 头注入（文件名未验证、CRLF 未过滤）、多行响应头注入（响应头值包含换行符、未规范化处理）、响应体分割（响应头后注入额外响应体、导致响应格式错误）、缓存投毒（响应分割导致缓存键污染、恶意响应被缓存）、会话固定（Set-Cookie 头被分割、会话标识符被篡改）

**HTTP 响应分割漏洞（HTTP Response Splitting）**

**Attention**  
当项目中涉及 HTTP 响应头的构造、设置、拼接等业务逻辑时，需重点审计用户可控输入是否直接用于构造响应头字段且未过滤 CRLF（\r\n）字符。此类漏洞通常出现在用户输入直接拼接进响应头（如 Location、Set-Cookie、Content-Disposition、X-Forwarded-For 等）、响应头值未验证格式、多行响应头处理不当等场景。常见于 Web 框架的响应构造、重定向处理、Cookie 设置、文件下载、反向代理配置等模块中。

**Early exit**  
若项目完全不涉及 HTTP 响应头的构造和处理（如纯静态内容服务、无任何响应头操作逻辑），或所有响应头字段均为框架自动生成且无任何用户输入参与，或所有用户输入在用于构造响应头前都经过了严格的 CRLF 过滤和格式验证，则可快速退出对该漏洞类型的审计。

**Cases**

**Python**
Flask/Django 响应头构造时用户输入直接拼接，未过滤 CRLF 字符，详见：[Python_Response_Header_CRLF_Injection.md](Python_Response_Header_CRLF_Injection.md)，遇到 CRLF 过滤保护机制详见 [bypassTricks.md](bypassTricks.md) 中"CRLF 注入绕过"和"Python/Flask/Django 框架特定绕过"部分
Location 重定向头使用用户输入时未验证和过滤，详见：[Python_Location_Header_Unvalidated.md](Python_Location_Header_Unvalidated.md)，遇到 URL 验证保护机制详见 [bypassTricks.md](bypassTricks.md) 中"Location 头注入绕过"和"Python/Flask/Django 框架特定绕过"部分
Set-Cookie 头设置时用户输入未过滤 CRLF，详见：[Python_SetCookie_Header_CRLF.md](Python_SetCookie_Header_CRLF.md)，遇到 Cookie 值过滤保护机制详见 [bypassTricks.md](bypassTricks.md) 中"Set-Cookie 头注入绕过"和"Python/Flask/Django 框架特定绕过"部分
Content-Disposition 头构造时文件名未验证，详见：[Python_ContentDisposition_Header_Injection.md](Python_ContentDisposition_Header_Injection.md)，遇到文件名过滤保护机制详见 [bypassTricks.md](bypassTricks.md) 中"Content-Disposition 头注入绕过"和"Python/Flask/Django 框架特定绕过"部分
多行响应头处理时未规范化，详见：[Python_Multiline_Header_Unnormalized.md](Python_Multiline_Header_Unnormalized.md)，遇到多行规范化保护机制详见 [bypassTricks.md](bypassTricks.md) 中"多行响应头绕过"和"Python/Flask/Django 框架特定绕过"部分

**Java**
Spring MVC 响应头构造时用户输入未过滤 CRLF，详见：[Java_Spring_Response_Header_CRLF.md](Java_Spring_Response_Header_CRLF.md)，遇到 CRLF 过滤保护机制详见 [bypassTricks.md](bypassTricks.md) 中"CRLF 注入绕过"和"Java/Spring 框架特定绕过"部分
Servlet API 中 Location 头使用用户输入未验证，详见：[Java_Location_Header_Unvalidated.md](Java_Location_Header_Unvalidated.md)，遇到 URL 验证保护机制详见 [bypassTricks.md](bypassTricks.md) 中"Location 头注入绕过"和"Java/Spring 框架特定绕过"部分
HttpServletResponse 设置 Cookie 时值未过滤，详见：[Java_SetCookie_Value_CRLF.md](Java_SetCookie_Value_CRLF.md)，遇到 Cookie 值过滤保护机制详见 [bypassTricks.md](bypassTricks.md) 中"Set-Cookie 头注入绕过"和"Java/Spring 框架特定绕过"部分
Content-Disposition 头构造时文件名未验证，详见：[Java_ContentDisposition_Filename_Injection.md](Java_ContentDisposition_Filename_Injection.md)，遇到文件名过滤保护机制详见 [bypassTricks.md](bypassTricks.md) 中"Content-Disposition 头注入绕过"和"Java/Spring 框架特定绕过"部分
多行响应头解析时未规范化处理，详见：[Java_Multiline_Header_Parsing.md](Java_Multiline_Header_Parsing.md)，遇到多行规范化保护机制详见 [bypassTricks.md](bypassTricks.md) 中"多行响应头绕过"和"Java/Spring 框架特定绕过"部分

**Go**
使用 net/http 包构造响应头时用户输入未过滤，详见：[Go_Response_Header_CRLF_Injection.md](Go_Response_Header_CRLF_Injection.md)，遇到 CRLF 过滤保护机制详见 [bypassTricks.md](bypassTricks.md) 中"CRLF 注入绕过"和"Go 框架特定绕过"部分
http.Redirect 使用用户输入时未验证 Location 头，详见：[Go_Redirect_Location_Unvalidated.md](Go_Redirect_Location_Unvalidated.md)，遇到 URL 验证保护机制详见 [bypassTricks.md](bypassTricks.md) 中"Location 头注入绕过"和"Go 框架特定绕过"部分
http.SetCookie 设置 Cookie 时值未过滤 CRLF，详见：[Go_SetCookie_Value_CRLF.md](Go_SetCookie_Value_CRLF.md)，遇到 Cookie 值过滤保护机制详见 [bypassTricks.md](bypassTricks.md) 中"Set-Cookie 头注入绕过"和"Go 框架特定绕过"部分
Content-Disposition 头构造时文件名未验证，详见：[Go_ContentDisposition_Filename_Injection.md](Go_ContentDisposition_Filename_Injection.md)，遇到文件名过滤保护机制详见 [bypassTricks.md](bypassTricks.md) 中"Content-Disposition 头注入绕过"和"Go 框架特定绕过"部分
响应头多行处理时未规范化，详见：[Go_Multiline_Header_Unnormalized.md](Go_Multiline_Header_Unnormalized.md)，遇到多行规范化保护机制详见 [bypassTricks.md](bypassTricks.md) 中"多行响应头绕过"和"Go 框架特定绕过"部分

**PHP**
header() 函数使用用户输入时未过滤 CRLF，详见：[PHP_Header_Function_CRLF_Injection.md](PHP_Header_Function_CRLF_Injection.md)，遇到 CRLF 过滤保护机制详见 [bypassTricks.md](bypassTricks.md) 中"CRLF 注入绕过"和"PHP 框架特定绕过"部分
Location 重定向头使用用户输入未验证，详见：[PHP_Location_Header_Unvalidated.md](PHP_Location_Header_Unvalidated.md)，遇到 URL 验证保护机制详见 [bypassTricks.md](bypassTricks.md) 中"Location 头注入绕过"和"PHP 框架特定绕过"部分
setcookie() 函数设置 Cookie 时值未过滤，详见：[PHP_SetCookie_Value_CRLF.md](PHP_SetCookie_Value_CRLF.md)，遇到 Cookie 值过滤保护机制详见 [bypassTricks.md](bypassTricks.md) 中"Set-Cookie 头注入绕过"和"PHP 框架特定绕过"部分
Content-Disposition 头构造时文件名未验证，详见：[PHP_ContentDisposition_Filename_Injection.md](PHP_ContentDisposition_Filename_Injection.md)，遇到文件名过滤保护机制详见 [bypassTricks.md](bypassTricks.md) 中"Content-Disposition 头注入绕过"和"PHP 框架特定绕过"部分
多行响应头处理时未规范化，详见：[PHP_Multiline_Header_Unnormalized.md](PHP_Multiline_Header_Unnormalized.md)，遇到多行规范化保护机制详见 [bypassTricks.md](bypassTricks.md) 中"多行响应头绕过"和"PHP 框架特定绕过"部分

**JavaScript / TypeScript (Node.js)**
Express/Koa 响应头设置时用户输入未过滤，详见：[NodeJS_Response_Header_CRLF_Injection.md](NodeJS_Response_Header_CRLF_Injection.md)，遇到 CRLF 过滤保护机制详见 [bypassTricks.md](bypassTricks.md) 中"CRLF 注入绕过"和"Node.js/Express 框架特定绕过"部分
res.redirect() 使用用户输入时未验证 Location 头，详见：[NodeJS_Redirect_Location_Unvalidated.md](NodeJS_Redirect_Location_Unvalidated.md)，遇到 URL 验证保护机制详见 [bypassTricks.md](bypassTricks.md) 中"Location 头注入绕过"和"Node.js/Express 框架特定绕过"部分
res.cookie() 设置 Cookie 时值未过滤 CRLF，详见：[NodeJS_SetCookie_Value_CRLF.md](NodeJS_SetCookie_Value_CRLF.md)，遇到 Cookie 值过滤保护机制详见 [bypassTricks.md](bypassTricks.md) 中"Set-Cookie 头注入绕过"和"Node.js/Express 框架特定绕过"部分
Content-Disposition 头构造时文件名未验证，详见：[NodeJS_ContentDisposition_Filename_Injection.md](NodeJS_ContentDisposition_Filename_Injection.md)，遇到文件名过滤保护机制详见 [bypassTricks.md](bypassTricks.md) 中"Content-Disposition 头注入绕过"和"Node.js/Express 框架特定绕过"部分
多行响应头处理时未规范化，详见：[NodeJS_Multiline_Header_Unnormalized.md](NodeJS_Multiline_Header_Unnormalized.md)，遇到多行规范化保护机制详见 [bypassTricks.md](bypassTricks.md) 中"多行响应头绕过"和"Node.js/Express 框架特定绕过"部分

**C/C++**
HTTP 响应头构造时用户输入直接拼接，未过滤 CRLF，详见：[C_Response_Header_CRLF_Injection.md](C_Response_Header_CRLF_Injection.md)，遇到 CRLF 过滤保护机制详见 [bypassTricks.md](bypassTricks.md) 中"CRLF 注入绕过"部分
Location 头构造时用户输入未验证，详见：[C_Location_Header_Unvalidated.md](C_Location_Header_Unvalidated.md)，遇到 URL 验证保护机制详见 [bypassTricks.md](bypassTricks.md) 中"Location 头注入绕过"部分
Set-Cookie 头构造时值未过滤，详见：[C_SetCookie_Value_CRLF.md](C_SetCookie_Value_CRLF.md)，遇到 Cookie 值过滤保护机制详见 [bypassTricks.md](bypassTricks.md) 中"Set-Cookie 头注入绕过"部分
Content-Disposition 头构造时文件名未验证，详见：[C_ContentDisposition_Filename_Injection.md](C_ContentDisposition_Filename_Injection.md)，遇到文件名过滤保护机制详见 [bypassTricks.md](bypassTricks.md) 中"Content-Disposition 头注入绕过"部分
多行响应头解析时未规范化，详见：[C_Multiline_Header_Parsing.md](C_Multiline_Header_Parsing.md)，遇到多行规范化保护机制详见 [bypassTricks.md](bypassTricks.md) 中"多行响应头绕过"部分

**Rust**
使用 hyper 库设置响应头时用户输入未过滤，详见：[Rust_Hyper_Response_Header_CRLF.md](Rust_Hyper_Response_Header_CRLF.md)，遇到 CRLF 过滤保护机制详见 [bypassTricks.md](bypassTricks.md) 中"CRLF 注入绕过"部分
Location 头使用用户输入时未验证，详见：[Rust_Location_Header_Unvalidated.md](Rust_Location_Header_Unvalidated.md)，遇到 URL 验证保护机制详见 [bypassTricks.md](bypassTricks.md) 中"Location 头注入绕过"部分
Set-Cookie 头设置时值未过滤 CRLF，详见：[Rust_SetCookie_Value_CRLF.md](Rust_SetCookie_Value_CRLF.md)，遇到 Cookie 值过滤保护机制详见 [bypassTricks.md](bypassTricks.md) 中"Set-Cookie 头注入绕过"部分
Content-Disposition 头构造时文件名未验证，详见：[Rust_ContentDisposition_Filename_Injection.md](Rust_ContentDisposition_Filename_Injection.md)，遇到文件名过滤保护机制详见 [bypassTricks.md](bypassTricks.md) 中"Content-Disposition 头注入绕过"部分
多行响应头处理时未规范化，详见：[Rust_Multiline_Header_Unnormalized.md](Rust_Multiline_Header_Unnormalized.md)，遇到多行规范化保护机制详见 [bypassTricks.md](bypassTricks.md) 中"多行响应头绕过"部分

## HTTP 响应分割绕过技巧

在进行 HTTP 响应分割漏洞审计时，特别是验证防护机制的有效性，需要了解常见的绕过技巧。参考详细的绕过技巧文档：[bypassTricks.md](bypassTricks.md)

该文档包含：
- CRLF 注入绕过（换行符编码变体、替换顺序问题、Unicode 编码）
- Location 头注入绕过（URL 编码、协议混淆、相对路径）
- Set-Cookie 头注入绕过（Cookie 值编码、属性注入、多行 Cookie）
- Content-Disposition 头注入绕过（文件名编码、RFC 2047、Unicode）
- 多行响应头绕过（折叠头、续行符、空白字符）
- 响应体分割绕过（分块传输、压缩混淆）
- 缓存投毒绕过（Vary 头绕过、响应分割污染缓存）
- 特定框架绕过（Python/Flask/Django、Java/Spring、PHP、Node.js/Express、Go）

在验证防护机制时，应使用这些绕过技巧来测试防护的鲁棒性。

# 输出要求

确认漏洞后，加载 `bug-report` 技能获取标准化报告格式，生成漏洞报告文件。

**加载技能**：`bug-report`

**输出路径**：`.workspace/findings/BUG-http-splitting-{file}-L{line}-{source}-{sink}.md`

**约束**：
- 每个漏洞必须生成独立的 BUG 文件，禁止合并或省略
- 漏洞报告格式严格遵循 `bug-report` 技能定义的模板

