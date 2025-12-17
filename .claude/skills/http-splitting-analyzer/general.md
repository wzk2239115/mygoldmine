---
title: HTTP Response Splitting 通用缺陷审计指南
description: HTTP 响应分割类漏洞的通用审计模式及实战审计技巧
---

# 通用缺陷模式（所有项目必审）

拿到任何处理 HTTP 响应头的项目，无论使用何种编程语言，以下 HTTP Response Splitting 防护缺陷都必须进行审计。这些问题源于对用户输入的不当处理，与具体语言实现无关。

## CRLF 注入 - 响应头/体分割

### 直接用户输入拼接到响应头

最常见的缺陷是直接将用户可控的参数拼接到 HTTP 响应头中，不进行任何验证：
- 将用户输入直接用于 `Location`、`Set-Cookie`、`Content-Disposition` 等响应头
- 使用字符串拼接或格式化函数（如 `sprintf`）直接构造响应头，未检查特殊字符
- 服务器在设置响应头前未剥离或转义 `\r\n` 等 CRLF 序列；必须严格验证或转义特殊字符

**审计技巧**：在所有用户可控的参数后尝试添加 `%0d%0a`（CRLF）或 `\r\n`；观察响应头是否被注入新行；使用 Burp Suite 的 Repeater 工具逐个尝试应用处理的所有参数（GET/POST/Cookie/Header）；检查源码中是否有 `header()`、`setHeader()`、`response.addHeader()` 等函数调用与用户输入混合的地方。

## 开放重定向 - Location 头未验证

### Location 头值未验证或验证不足

重定向功能将用户输入直接用于 Location 头，允许重定向到任意外部网站：
- 使用用户提供的 URL 参数直接设置 Location 头，如 `Location: {$_GET['redirect_url']}`
- 仅进行前缀检查（如检查是否以 `/` 开头）而忽略协议部分，可用 `//attacker.com` 或 `///attacker.com` 绕过
- 允许 `javascript:` 协议 URL，在某些浏览器中可执行 JavaScript；必须限制为 `http://` 或 `https://` 协议
- 白名单验证实施不当，允许 `attacker.com.allowed-domain.com` 形式的域名欺骗

**审计技巧**：识别重定向端点（通常为 `redirect.php?url=`、`back=`、`next=`、`continue=` 等参数）；尝试 `http://attacker.com`、`https://attacker.com`、`//attacker.com`、`///attacker.com`、`javascript:alert(1)`；检查白名单实现是否使用简单的字符串匹配（如 `contains()` 而非正确的 URL 解析）。

## Set-Cookie 值注入 - 会话劫持与固定

### Cookie 值未验证

在设置 Cookie 时，未验证 Cookie 值中的 CRLF 字符，允许注入额外的 Cookie 或响应头：
- 将用户输入直接用于 Cookie 值或属性，如 `Set-Cookie: username={$_GET['username']}`
- 特别在设置 `Path`、`Domain`、`Secure`、`HttpOnly` 等属性时，可通过 CRLF 注入添加新 Cookie
- Cookie 值中的特殊字符（`\r\n`、`;`）未被转义或验证；必须严格验证字符范围或使用 URL 编码

**审计技巧**：在所有影响 Cookie 的参数后尝试添加 `%0d%0aSet-Cookie: admin=true`；观察响应头中是否有多个 Set-Cookie 头；检查 Cookie 设置的地方是否有 `setcookie()`、`response.setCookie()` 等函数与用户输入混合；尝试注入分号和空格来添加新的 Cookie 属性。

## Content-Disposition 注入 - 文件下载名篡改

### Content-Disposition 头值未验证

在提供文件下载时，将用户输入或数据库内容直接用于 `filename` 参数，未进行验证：
- 将用户上传的文件名直接用于 `Content-Disposition: attachment; filename={$uploaded_filename}`
- 允许文件名中含有 CRLF 字符，注入新的响应头；必须验证或转义特殊字符
- 允许文件名中的路径遍历序列（如 `../../etc/passwd`），虽然不执行但可混淆
- UTF-8 编码处理不当，通过 UTF-8 绕过过滤（如 `%c0%ae` 表示 `.`）

**审计技巧**：在文件下载功能中，尝试上传或修改文件名为 `test%0d%0aX-Injected-Header: value.txt`；观察响应头中是否注入了新的头；测试特殊字符 `"` 和 `;` 对头值边界的影响；查看是否存在编码转换导致的绕过。

## 多行响应头未规范化 - 缓存投毒

### 响应头处理对多行值解析不一致

不同的缓存层、代理或浏览器对多行响应头（如使用空白符继续的头）的解析可能不同，导致缓存投毒：
- HTTP/1.1 允许使用空白符（空格或制表符）实现多行响应头（folding），如 `Header: value1\r\n value2`
- 某些缓存层正规化处理不当，对同一个逻辑头进行多次解析，可导致缓存存储与客户端解析不一致
- 某些框架或代理移除或处理 `\r\n ` 序列不正确，可能允许注入新的头

**审计技巧**：使用多行头格式 `Header: value1\r\n value2` 测试，观察缓存和直接访问的响应是否不同；对 `Cache-Control`、`ETag` 等缓存相关头进行测试；检查是否存在 `\r\n ` 被保留并导致注入的情况；测试代理（如 Nginx、Apache）和浏览器缓存层的规范化行为。

---

## 审计检查清单

- [ ] 遍历所有生成 HTTP 响应头的代码位置，重点关注 `header()`、`setHeader()`、`Location`、`Set-Cookie`、`Content-Disposition`
- [ ] 检查用户输入（GET/POST/Cookie/Header）是否直接拼接到响应头中
- [ ] 验证所有响应头值是否进行了 CRLF 字符过滤或转义
- [ ] 测试所有重定向功能是否只允许安全协议（http/https），是否有充分的目标域名白名单
- [ ] 检查 Cookie 设置是否涉及用户可控数据，是否存在值或属性注入
- [ ] 审计所有涉及文件下载、文件名处理的代码，检查 Content-Disposition 值验证
- [ ] 对使用多行响应头、header folding 的代码进行特殊审查
- [ ] 测试响应包含 `%0d%0a`、`%0d`、`%0a`、`\r\n` 等 CRLF 序列的反应
- [ ] 检查是否存在编码处理（Base64、URL编码等）后的二次解码风险
- [ ] 确认缓存层（CDN、代理、浏览器）对响应头的规范化处理

---
