# Python Location 头重定向未验证

## Details

**审计等级：L1（关键词扫描）/ L2（跳读）**

**危险函数特征：**
- `redirect(url)` - Flask 重定向
- `HttpResponseRedirect(url)` - Django
- `response.status_code = 301/302` + `response.headers['Location'] = url`
- `response.headers['Location']` 直接赋值
- `flask.abort(code, description)`
- WSGI 标准重定向模式

**快速定位核心操作：**
1. 搜索关键字：`redirect(`, `Location`, `status_code = 3`（3xx 状态码）
2. 追踪 Location 头值来源：`request.args`、`request.form`、URL 路径参数
3. 查看是否存在 URL 格式验证（`urllib.parse.urlparse`、正则检查）
4. 检查是否限制重定向到特定域名（白名单）

**快速定位保护机制：**
- URL 白名单：`if url in allowed_urls` 或 `if url.startswith(TRUSTED_DOMAIN)`
- 域名验证：`urllib.parse.urlparse(url).netloc` 只允许特定域名
- URL scheme 限制：仅允许 `http://` 和 `https://`，拒绝 `javascript://`、`data://`
- 相对 URL 检查：`not url.startswith('http')`
- 黑名单域名：检查是否含有特殊字符或已知恶意模式

**代码示例：**
```python
# 危险：Flask 直接重定向用户输入
from flask import redirect, request

@app.route('/redirect')
def do_redirect():
    url = request.args.get('url')
    return redirect(url)  # 危险：无验证

# 危险：Django 未验证 Location 头
from django.http import HttpResponseRedirect

def redirect_view(request):
    target = request.GET.get('next')
    return HttpResponseRedirect(target)  # 危险

# 危险：直接设置 Location 头
@app.route('/jump')
def jump():
    response = make_response('Redirecting...')
    response.headers['Location'] = request.args.get('dest')  # 危险
    response.status_code = 302
    return response
```

## Classify

**漏洞（High）：**
- 用户输入（查询参数、表单、Header）直接用于 Location 头
- 无任何 URL 格式或域名验证
- 允许协议跳转（如 `javascript://`、`data://`、`//evil.com`）
- 开放重定向：允许重定向到任意外部域名

**误报：**
- Location 头值完全硬编码（如固定重定向到 `/home`）
- 重定向目标仅为相对 URL（如 `/dashboard`）且使用 `url_for()` 等框架方法
- 已实现严格的域名白名单

**代码异味（Medium）：**
- 仅检查 URL 前缀（如 `startswith('http')`）但未验证域名
- 使用黑名单过滤（如过滤 `://`）但容易绕过
- 允许所有 HTTPS URL 但未限制到自身域名
- 检查不完整（如仅检查 `http://` 但未检查 `//` 协议相对）
- 输入来自配置文件或 cookie 但未验证

## Low risk

**以下情况评为低风险：**
- 使用 `url_for()` 等框架原生方法生成重定向 URL
- 严格的域名白名单（如仅允许特定的 3-5 个内部 URL）
- 明确限制为相对 URL（如 `/` 开头）并进行正则验证
- 输入完全由管理员配置（如数据库中的安全列表）
- 实现了多层校验：白名单 + URL 格式检查 + 域名校验
- 重定向仅用于特定业务场景（如登录成功后返回来源页面）且源页面受控
