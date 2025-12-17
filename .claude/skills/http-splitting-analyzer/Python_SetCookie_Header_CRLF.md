# Python Set-Cookie 头 CRLF 注入

## Details

**审计等级：L1（关键词扫描）/ L3（逐行读）**

**危险函数特征：**
- `response.set_cookie(key, value, ...)` - Flask/WSGI
- `HttpResponse.set_cookie()` - Django
- `response.headers['Set-Cookie'] = value` 直接设置
- `response.cookie[name] = value` 赋值
- 自定义 Cookie 拼接：`f"Set-Cookie: {name}={value}"`

**快速定位核心操作：**
1. 搜索关键字：`set_cookie(`、`Set-Cookie`、`.cookie[`、`.cookies`
2. 追踪 Cookie 值来源：`request.args`、`request.form`、`request.headers`、会话数据
3. 检查是否存在 CRLF 过滤（``、`
` 的检查）
4. 追踪 Cookie 构造过程：拼接、URL 编码、格式化

**快速定位保护机制：**
- CRLF 检查：`if '' in value or '
' in value: raise ValueError()`
- 值验证：`if not re.match(r'^[a-zA-Z0-9\-_.]*$', value)`
- URL 编码：`urllib.parse.quote(value, safe='')`
- 框架内置防护：某些框架自动过滤或限制 Cookie 值格式
- 白名单值：仅接受预定义的有效值

**代码示例：**
```python
# 危险：Flask 直接从用户输入设置 Cookie
from flask import response, request, make_response

@app.route('/setcookie')
def set_cookie():
    token = request.args.get('token')
    resp = make_response('OK')
    resp.set_cookie('session_id', token)  # 危险：未过滤 CRLF
    return resp

# 危险：Django HttpResponse
from django.http import HttpResponse

def cookie_view(request):
    value = request.GET.get('val')
    response = HttpResponse('OK')
    response.set_cookie('custom', value)  # 危险
    return response

# 危险：直接拼接 Set-Cookie 头
response.headers['Set-Cookie'] = f"user={user_input}; Path=/"  # 危险
```

## Classify

**漏洞（Critical）：**
- HTTP 请求数据（Query、Form、Header、Cookie）直接用于 Set-Cookie 值
- 无 CRLF 过滤或值验证
- Cookie 值可以包含换行符，导致响应分割
- 攻击者可注入额外的 Cookie 或响应头

**误报：**
- Cookie 值完全硬编码
- 使用框架提供的加密或签名 Cookie 机制
- Cookie 值仅为系统生成的 Session ID 或 Token

**代码异味（Medium）：**
- 仅过滤 `
` 或 `` 之一
- 使用 URL 编码但未完全验证
- Cookie 值经过哈希但输入参数本身未验证
- 间接拼接：请求参数 → 临时变量 → Cookie

## Low risk

**以下情况评为低风险：**
- 使用框架的 Session 管理系统（自动处理 Cookie 安全）
- Cookie 值为系统生成的随机 Token（无用户输入）
- 实现了严格的 CRLF 过滤：显式检查 `if '\r' in value or '\n' in value`
- 白名单验证：`if value in ['valid1', 'valid2', ...]`
- 使用加密 Cookie（框架支持）
- 输入来自内部系统（数据库、配置文件）
