# Python Flask/Django 响应头CRLF注入

## 基本信息
- **难度等级：** ★★★☆☆ | **审计时间：** 20-30分钟
- **关键词搜索：** `response.headers[]`, `response['X-']`, `send_file()`, `redirect()`, `make_response()`, `HttpResponse`, `add_header()`, `set_header()`
- **快速检查：** 响应头是否直接由用户输入构造，是否存在CRLF过滤

## 漏洞成因

HTTP响应头以CRLF（`\r\n`）分隔。Python Flask/Django在构造响应头时若未对用户输入进行CRLF过滤，攻击者可注入任意头部或响应体，导致HTTP响应拆分、Cache中毒、会话固定等攻击。

### 常见漏洞模式

**Flask直接拼接用户输入到响应头**
```python
@app.route('/set-header')
def set_header():
    name = request.args.get('name')
    value = request.args.get('value')
    resp = make_response("OK")
    resp.headers[name] = value  # ✗ 直接使用用户输入
    return resp
    # 攻击: ?name=X-Test&value=test\r\nSet-Cookie:admin=1
```

**Django redirect() 直接使用用户输入**
```python
def login_view(request):
    next_url = request.GET.get('next')
    return redirect(next_url)  # ✗ Location头未验证
    # 攻击: ?next=http://evil.com%0d%0aSet-Cookie:user=hacker
```

**响应头值从参数直接取值**
```python
@app.route('/download')
def download():
    filename = request.args.get('filename')
    resp = make_response(send_file(filename))
    resp.headers['Content-Disposition'] = f'attachment;filename={filename}'
    # ✗ filename可包含\r\n注入
    return resp
```

**Django HttpResponse直接赋值**
```python
def get_data(request):
    key = request.GET.get('key')
    response = HttpResponse("data")
    response[key] = request.GET.get('value')  # ✗ 无CRLF检查
    return response
```

### 审计检查清单（按优先级）

| 优先级 | 检查项 | 审计方法 |
|--------|--------|---------|
| **P0** | **直接赋值头部** | 搜索 `resp.headers[`, `response[`, `make_response(` 后跟用户输入变量；检查变量是否来自 `request.args\|request.GET\|request.POST\|request.form\|request.values` |
| **P0** | **动态Location头** | 搜索 `redirect(`, `location=`, `Location:` 等，检查参数是否包含用户输入，尤其是 `next`, `redirect_to`, `return_to` 参数 |
| **P1** | **Content-Disposition动态值** | 搜索 `Content-Disposition`, `filename=`, `attachment;` ，检查是否包含f-string或格式化用户输入 |
| **P1** | **Content-Type动态指定** | 搜索 `Content-Type`, `MIME_TYPE`, `mimetype=` ，检查是否由参数控制 |
| **P2** | **Set-Cookie动态值** | 搜索 `Set-Cookie`, `cookie=`, `set_cookie()` ，检查值是否由请求参数构造 |
| **P3** | **自定义响应头** | 搜索 `add_header`, `X-Custom-`, `headers.add()` ，检查是否有过滤或验证 |

### 审计等级判定

| 等级 | 特征 | 审计重点 |
|------|------|---------|
| **L0** | 仅内部使用、参数白名单固定 | **跳过**，无用户输入 |
| **L1** | 有关键词但难以定位，参数多 | 全局搜索响应头相关函数，追踪参数流向 |
| **L2** | 单个文件内有明显用户输入 | **关键**: 检查所有 `request.args/GET/POST` 的使用，检查是否有过滤 |
| **L3** | 多文件、中间件处理 | 跨文件追踪参数，检查中间件是否统一过滤，模块化检查 |
| **L4** | 自定义响应处理、装饰器 | 深度追踪装饰器内的响应头处理逻辑，多层跳转 |

---

## 漏洞判定

### 确认漏洞（三个条件全部满足）
1. 响应头值直接或通过简单赋值取自用户输入（`request.args/GET/POST/values`）
2. 未进行CRLF过滤或验证（不包含 `replace('\r', '').replace('\n', '')` 或 `\x0d\x0a` 检查）
3. 支持注入CRLF字符（未禁用或框架未自动过滤）

### 典型漏洞特征（满足任一项即确认）
- ✗ `resp.headers[user_input] = user_value`
- ✗ `response[request.args.get('header')] = request.args.get('value')`
- ✗ `redirect(request.args.get('next'))`  无URL验证
- ✗ `Content-Disposition` = f-string 包含 `request` 变量
- ✗ `HttpResponse()` 直接赋值 `response[key] = value`
- ✗ 中间件处理中未验证 `environ['HTTP_*']`

### 安全排除（任一项充分）
- ✓ 使用 `werkzeug.security.safe_str_cmp()` 或白名单验证头名
- ✓ CRLF过滤：`value = value.replace('\r', '').replace('\n', '')`
- ✓ 使用Flask/Django内置安全API（如 `secure_filename()`）
- ✓ URL白名单：`next_url in ALLOWED_REDIRECTS`
- ✓ 框架自动过滤（Django HttpResponse自动拒绝CRLF）**但需验证版本**
- ✓ WAF规则：ModSecurity 规则ID 930110（CRLF检查）
- ✓ 响应头值来自代码常量，无用户输入

### 灰色判定（风险较低但需注意）
- ⚠ 仅特定头部使用用户输入（非所有头部）
- ⚠ 部分参数有过滤但不完整（仅检查 `\n` 不检查 `\r`）
- ⚠ 过滤在中间件但某些端点绕过

---

## 审计专业技巧：真实漏洞 vs 误报区分

### 误报陷阱1：框架自动防护

**Django HttpResponse的自动CRLF检查**
```python
# Django 3.0+ 会自动拒绝包含\r\n的头值
response = HttpResponse()
response['X-Custom'] = "value\r\nInjection"  # Django自动抛异常
# ValueError: Invalid header name b'X-Custom', value b'value\r\nInjection'
```

**审计建议：**
- 检查Django版本，3.0及以上版本有自动防护
- 但Flask和自定义WSGI应用没有，必须手动验证
- 搜索 `__version__` 或 `django.VERSION` 确认版本
- 即使有自动防护，仍需检查是否所有代码路径都通过HttpResponse

**误报案例：**
```python
# ✓ 虽然看起来有风险，但Django已保护
def api_view(request):
    response = HttpResponse("ok")
    user_header = request.GET.get('header')
    response[user_header] = request.GET.get('value')
    return response  # Django自动阻止CRLF注入
```

### 误报陷阱2：框架内置验证的Location头

**Flask redirect()的URL验证**
```python
from flask import redirect

# Flask 1.0+ 对redirect()进行了加强
def login(request):
    return redirect(request.args.get('next'))
    # Flask不会拒绝，但现代Flask有一定防护
```

**审计建议：**
- Flask本身不会自动过滤CRLF，但有 `url_has_allowed_host_and_scheme()` 工具
- 检查是否使用了 `werkzeug.security.safe_str_cmp()` 或URL验证
- 查找 `url_has_allowed_host_and_scheme()` 的使用
- 没有的话就是真实漏洞

**真实漏洞 vs 误报：**
```python
# ✗ 真实漏洞：直接redirect，无验证
return redirect(request.args.get('next'))

# ✓ 误报：已经过验证
from werkzeug.urls import url_has_allowed_host_and_scheme
next_url = request.args.get('next')
if url_has_allowed_host_and_scheme(next_url, {'example.com'}):
    return redirect(next_url)
```

### 误报陷阱3：部分响应头的安全属性

**某些头部天生无法注入body**
```python
# 这些头部即使有CRLF，也无法进行HTTP响应拆分
# 因为框架处理方式限制了攻击面

# ✓ 低风险：仅用于日志或跟踪ID
resp.headers['X-Request-ID'] = request.args.get('id')  # 格式: UUID

# ✓ 低风险：值被限制为特定类型
resp.headers['X-Page-Size'] = request.args.get('size')  # 格式: 数字

# ✗ 高风险：可控制Location头导致HTTP响应拆分
resp.headers['Location'] = request.args.get('url')
```

**审计建议：**
- 区分"攻击面"：Location, Set-Cookie, Content-Disposition最危险
- X-Custom-*通常低风险，除非包含重要信息（如session ID）
- Content-Type和Content-Length如果可控会影响缓存中毒

### 误报陷阱4：URL编码混淆

**正确识别CRLF注入：**
```python
# URL编码的CRLF（%0d%0a）会被解码
# ✗ 真实漏洞
redirect(request.args.get('next'))
# 攻击: ?next=http://evil.com%0d%0aSet-Cookie:admin=1
# 被解码为: http://evil.com\r\nSet-Cookie:admin=1

# ✓ 已防护（仅在特定场景）
from urllib.parse import urlparse, unquote
url = unquote(request.args.get('next'))
# 但这只是解码，未必安全，需要配合白名单
```

**审计建议：**
- 搜索 `unquote()`, `urllib.parse.unquote()` 的使用
- 检查解码后是否进行了CRLF检查
- 注意 `safe_str_cmp()` 不能替代CRLF过滤

### 误报陷阱5：中间件过滤的遗漏

**全局中间件过滤不代表所有端点安全**
```python
# middleware.py
class CRLFFilterMiddleware:
    def process_response(self, request, response):
        # 尝试过滤所有响应头中的CRLF
        for key, value in response.items():
            if '\r' in value or '\n' in value:
                response[key] = value.replace('\r', '').replace('\n', '')
        return response

# 但某些场景中间件无法拦截：
# 1. 使用了response.stream_response() 的流式响应
# 2. 使用了内置HTTP库的响应（如requests库返回）
# 3. 直接设置的原始socket响应
```

**审计建议：**
- 不要假设中间件保护了所有代码路径
- 检查是否有绕过中间件的响应方式
- 特别关注：WebSocket、Stream、File Download等特殊响应
- 确认中间件是否处理 `response.headers` 而非 `response['X-*']`

### 误报陷阱6：白名单的有效性

**看起来安全的白名单，实际可能有缺陷**
```python
# ✓ 真正安全的白名单
ALLOWED_HEADERS = frozenset(['X-Custom-ID', 'X-Request-ID'])
if header_name in ALLOWED_HEADERS:
    resp.headers[header_name] = value

# ✗ 不安全的白名单：字符串包含检查
UNSAFE_PATTERN = 'X-Custom'
if UNSAFE_PATTERN in header_name:  # 可被绕过
    resp.headers[header_name] = value
# 攻击: header_name = 'Evil-X-Custom'，包含但不在真正白名单内

# ✗ 不安全的白名单：大小写敏感
HEADERS = ['X-Custom-ID']
if header_name in HEADERS:  # 'x-custom-id' 无法匹配
    resp.headers[header_name] = value
```

**审计建议：**
- 检查白名单实现是否使用了 `in` 检查（容易绕过）
- 验证是否考虑了大小写问题（HTTP头名通常大小写无关）
- 理想方案：精确集合匹配，如 `frozenset().intersection()`

### 真实漏洞的五大特征检查清单

| 特征 | 检查方法 | 风险等级 |
|------|--------|---------|
| **无条件用户输入** | 搜索 `request.args/GET/POST` 后直接赋值到头部 | P0 |
| **无CRLF过滤** | 确认不存在 `replace('\r', '')` 和 `replace('\n', '')` | P0 |
| **非白名单验证** | 头名不在预定义列表中 | P0 |
| **框架版本低** | Django < 3.0 或 Flask无URL验证 | P1 |
| **多路径响应** | 除了HttpResponse外还有其他响应方式 | P1 |

### 误报常见模式（可安全跳过）

- 响应头值来自数据库固定字段，无用户输入路径
- 使用了 `secure_filename()` + `Content-Disposition`
- 已实现精确白名单 + CRLF过滤 + URL验证
- Django 3.0+ 中通过HttpResponse设置的所有头部（自动防护）
- WAF层有ModSecurity规则ID 930110激活

---

## 实现建议

### 核心防护方案

**方案1：白名单+CRLF过滤**
```python
SAFE_HEADER_NAMES = {'X-Custom', 'X-Request-ID', 'X-User-ID'}

def set_custom_header(resp, header_name, value):
    # ✓ 白名单验证头名
    if header_name not in SAFE_HEADER_NAMES:
        raise ValueError("Invalid header")

    # ✓ CRLF过滤
    safe_value = value.replace('\r', '').replace('\n', '')
    resp.headers[header_name] = safe_value
    return resp
```

**方案2：安全重定向（白名单URL）**
```python
ALLOWED_DOMAINS = {'example.com', 'app.example.com'}

def safe_redirect(next_url):
    # ✓ URL解析+域名白名单
    if not next_url:
        return redirect('/')

    parsed = urllib.parse.urlparse(next_url)
    if parsed.netloc and parsed.netloc not in ALLOWED_DOMAINS:
        return redirect('/')  # 拒绝跨域重定向

    if not parsed.scheme or parsed.scheme == 'http':
        return redirect(next_url)

    return redirect('/')  # 默认安全
```

**方案3：安全的Content-Disposition**
```python
from werkzeug.utils import secure_filename

@app.route('/download')
def download():
    filename = request.args.get('filename')
    # ✓ 使用secure_filename清理
    safe_filename = secure_filename(filename)
    if not safe_filename:
        safe_filename = 'file'

    resp = make_response(send_file(f'/uploads/{safe_filename}'))
    resp.headers['Content-Disposition'] = f'attachment;filename="{safe_filename}"'
    return resp
```

### 检查清单
- [ ] 所有用户输入的响应头使用白名单验证
- [ ] 响应头值包含CRLF过滤：`replace('\r', '').replace('\n', '')`
- [ ] 重定向URL使用域名白名单或 `urllib.parse` 验证
- [ ] `Content-Disposition` 使用 `secure_filename()`
- [ ] 测试CRLF注入：`value=test\r\nSet-Cookie:admin=1`
- [ ] 中间件统一过滤所有自定义头部

---

## 修复优先级

1. **立即修复**：添加CRLF过滤，所有用户输入响应头都需要 `replace('\r', '').replace('\n', '')`
2. **本周修复**：实现头名白名单，重定向URL验证
3. **可选加强**：CSP头配置，X-Content-Type-Options: nosniff
4. **长期优化**：框架升级到最新版本，启用自动CRLF检查
