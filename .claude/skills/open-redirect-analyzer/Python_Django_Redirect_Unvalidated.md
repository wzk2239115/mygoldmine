# Python Django HttpResponseRedirect 未验证的开放重定向

Django 中 `HttpResponseRedirect` 或 `redirect()` 直接使用用户可控的 URL 参数，未实施白名单验证或目标检查，导致开放重定向漏洞。

## Details

### 核心代码示例

**常见脆弱的使用场景：**

```python
# views.py - 直接使用 request 参数构造重定向
from django.shortcuts import redirect
from django.http import HttpResponseRedirect

# 情形1: 直接使用 GET/POST 参数
def login_view(request):
    if authenticate(request):
        next_url = request.GET.get('next', '/')  # 用户可控
        return redirect(next_url)

# 情形2: 使用 HttpResponseRedirect
def logout_view(request):
    return_url = request.POST.get('return_to')
    return HttpResponseRedirect(return_url)

# 情形3: 通过 referrer 构造
def go_back(request):
    referrer = request.META.get('HTTP_REFERER')
    return redirect(referrer)

# 情形4: 拼接用户可控的路径
def dynamic_redirect(request):
    category = request.GET.get('category', 'home')
    return redirect(f'/{category}/')  # 路径遍历或外链重定向
```

**核心操作快速定位 (L3:逐行读)**
- 追踪 `redirect()` 和 `HttpResponseRedirect()` 的参数来源
- 检查参数是否直接来自 `request.GET`, `request.POST`, `request.META` 等用户输入
- 关键词扫描：`request.GET.get()`, `request.POST.get()`, `request.META.get('HTTP_REFERER')`, `request.FILES`
- 识别模式：`redirect()` 的第一参数、`HttpResponseRedirect()` 的 URL 参数

**保护机制检查 (L2:跳读)**
- 检查是否存在 URL 白名单验证（`if url in ALLOWED_URLS`）
- 检查是否有 `urlparse` 或 `urllib.parse` 的 scheme/netloc 验证
- 检查是否使用 Django 的 `is_safe_url()` 或 `url_has_allowed_host_and_scheme()`
- 查找相关的 validator 或 middleware 防护
- 验证相对 URL 限制（仅允许 `/` 开头的相对路径）

## Classify

### 漏洞研判标准

**确认为漏洞的条件：**
1. 重定向目标来自用户直接可控的输入源（GET/POST 参数、Cookie、Header）
2. 未执行任何合法性检查或仅实施了绕过式防护（如 `startswith('http')`）
3. 允许任意 scheme（http/https/javascript/data）或任意外部域名
4. 缺失白名单验证或正确的 URL 解析验证

**漏洞不存在的情景：**
- 通过 `django.utils.http.is_safe_url()` 进行 Django 标准验证
- 使用 `urllib.parse.urlparse()` 验证 scheme 和 netloc，限制仅允许相对路径或白名单域名
- 指定 `allowed_hosts` 参数限制重定向目标域名
- 完整的动态白名单（如数据库中存储的有效重定向目标）

**漏洞与误报的边界：**
- 若重定向指向硬编码的内部路由（如 `redirect('/dashboard/')`）且路径不包含用户输入，视为安全
- 若使用了 Django 的 `reverse()` 函数进行路由名称反向解析，且参数来自受控范围，通常安全
- 若重定向参数来自服务端生成的值（如从数据库查询的用户资料），且未经用户输入污染，通常安全

## Low risk

### 低风险评级的情景

1. **相对路径限制**
   - 验证重定向 URL 仅为相对路径（`url.startswith('/')` 且 `not url.startswith('//')` 且无 scheme）
   - 通过 `urllib.parse.urlparse()` 验证 scheme 为空或仅为 'http'/'https'

2. **白名单验证充分**
   - 重定向目标在应用维护的静态白名单中（如 `ALLOWED_REDIRECTS` 列表）
   - 白名单采用精确匹配而非前缀匹配，避免绕过（如白名单 `example.com` 可被绕过至 `example.com.attacker.com`）

3. **框架级防护生效**
   - 正确使用 `django.utils.http.is_safe_url()` 的返回值进行条件判断
   - 在中间件层统一拦截不安全的重定向行为

4. **上下文安全的重定向场景**
   - 仅允许站内路由重定向（scheme 和 host 被限制为当前应用域名）
   - 用户无法控制重定向目标的 scheme 或主机部分（仅能控制路径或查询参数）

5. **参数来源受信**
   - 重定向参数来自经过验证的用户数据（如数据库中已存储的安全 URL）
   - 参数来自系统配置文件而非用户请求

### 审计关键点

- 优先检查认证流程相关的重定向（`next=`, `return_to=`, `redirect_uri=`）
- 关注 OAuth/SSO 回调处理，这些场景最易出现开放重定向
- 检查 referrer 依赖的跳转逻辑，referrer 由客户端完全可控
- 注意动态生成的重定向链接（如通过字符串拼接或格式化生成的 URL）
- 验证白名单实现方式是否可被绕过（如 `endswith()` 导致的子域名绕过）
