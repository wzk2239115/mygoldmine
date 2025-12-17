# Python 响应头 CRLF 注入

## Details

**审计等级：L1（关键词扫描）/ L3（逐行读）**

**危险函数特征：**
- `response.headers[key] = value`（Flask）
- `response[key] = value`（WSGI）
- `HttpResponse['Header'] = value`（Django）
- `make_response()` 后直接设置响应头
- `Flask.redirect()` 参数未验证
- 原生 WSGI 环境变量 `HTTP_*` 直接拼接进响应头

**快速定位核心操作：**
1. 全局搜索关键字：`response.headers`、`response[`、`make_response`、`set_header`
2. 搜索 `\r`、`\n`、`\\r`、`\\n`、`%0d`、`%0a` 的过滤逻辑
3. 追踪响应头值来源：`request.args`、`request.form`、`request.headers`、`request.GET`、`request.POST`
4. 关键点：头字段名和头字段值是否包含用户输入，是否经过验证

**快速定位保护机制：**
- CRLF 检查：`if '\r' in value or '\n' in value`
- 黑名单过滤：`value.replace('\r\n', '').replace('\r', '').replace('\n', '')`
- 白名单验证：`if re.match(r'^[a-zA-Z0-9\-_.]+$', value)`
- URL 合法性校验：`urllib.parse.urlparse()` 验证 Location 头
- 框架级防护：某些框架自动检测和拒绝 CRLF 字符

**代码示例：**
```python
# 危险：Flask 直接拼接用户输入到响应头
from flask import Flask, request, make_response

@app.route('/send')
def send_header():
    user_input = request.args.get('name')
    response = make_response(f"Hello {user_input}")
    response.headers['X-Custom'] = user_input  # 危险：未过滤 CRLF
    return response

# 危险：Django HttpResponse 直接设置
from django.http import HttpResponse

def view_func(request):
    name = request.GET.get('name')
    response = HttpResponse("content")
    response['X-Custom-Header'] = name  # 危险：未验证
    return response

# 危险：WSGI 环境直接操作
def app(environ, start_response):
    custom = environ.get('HTTP_X_CUSTOM', '')
    headers = [('X-Custom', custom)]  # 危险：未过滤
    start_response('200 OK', headers)
    return [b'OK']
```

## Classify

**漏洞（Critical）：**
- HTTP 请求头（Header、Query Parameter、Form Data、Cookie）直接拼接进响应头
- 响应头值包含 `\r\n`、`\r`、`\n` 或编码形式（`%0d%0a`、`%0d`、`%0a`）
- 无任何 CRLF 过滤或验证机制
- 多个用户输入来源叠加拼接（增加攻击面）

**误报：**
- 响应头值完全硬编码，无任何动态部分
- 响应头在框架底层自动生成，应用层无设置逻辑
- 输入已被框架自动过滤（如某些框架会自动检测和拒绝）

**代码异味（Medium）：**
- 仅过滤 `\n` 或 `\r` 之一，但未同时过滤两者
- 使用了黑名单过滤但过滤规则不完整（如只过滤 `%0d%0a` 但未过滤双重编码）
- 用户输入经过 URL 编码但未 Decode 验证
- 间接拼接：用户输入 → 临时存储 → 响应头（需追踪完整链路）

## Low risk

**以下情况评为低风险：**
- 响应头值完全由应用控制，不包含任何外部输入
- 已实现严格的 CRLF 过滤：在拼接前显式检查 `if '\r' in value or '\n' in value: raise ValueError()`
- 使用白名单验证：仅接受特定格式（如 `[a-zA-Z0-9\-_.]+`）
- 框架内置防护已启用（如 Flask 某版本自动过滤）
- 输入仅用于非关键响应头（如 `X-Custom-Debug`）且有长度限制
- 响应头来自内部系统（数据库、配置文件）且无外部输入污染
