# Python - 用户可控 URL 请求（SSRF）

## Details

### 典型代码示例

**requests 库：**
```python
import requests
url = request.args.get('url')
response = requests.get(url)  # 直接使用用户输入
```

**urllib 库：**
```python
from urllib.request import urlopen
target = request.form['target']
data = urlopen(target).read()  # 未过滤协议和地址
```

**aiohttp 库：**
```python
import aiohttp
async def fetch(session, url):
    async with session.get(url) as resp:  # 异步请求用户URL
        return await resp.text()
```

**httpx 库：**
```python
import httpx
r = httpx.get(user_input_url)  # 同步/异步均存在风险
```

### 快速定位核心操作（L1: 关键词扫描）

**关键库导入：**
- `import requests` / `from requests import`
- `import urllib` / `from urllib.request import urlopen`
- `import aiohttp` / `import httpx`
- `import http.client` / `from http.client import`

**危险函数调用：**
- `requests.{get|post|put|delete|request}(url_var)`
- `urlopen(url_var)` / `urllib.request.Request(url_var)`
- `session.{get|post}(url_var)` (aiohttp)
- `httpx.{get|post}(url_var)`
- `http.client.HTTPConnection(host_var)`

**数据流追踪（L3: 逐行读）：**
- 从 `request.args/form/json/GET/POST` 获取参数
- 跟踪变量名：`url`, `target`, `endpoint`, `callback`, `proxy`, `webhook`, `fetch_url`
- 注意字符串拼接：`base_url + user_input` 或 `f"http://{domain}/api"`

### 快速定位保护机制（L2: 跳读）

**URL 白名单检查：**
```python
ALLOWED_DOMAINS = ['api.example.com']
if not any(url.startswith(d) for d in ALLOWED_DOMAINS):
```

**协议限制：**
```python
if not url.startswith(('http://', 'https://')):
    raise ValueError
```

**IP 地址黑名单：**
```python
import ipaddress
ip = socket.gethostbyname(hostname)
if ipaddress.ip_address(ip).is_private:  # 检查私有IP
```

**审计技巧（L3: 逐行读）：**
- 检查保护逻辑是否在请求**之前**执行
- 验证白名单是否使用 `startswith`（可被绕过：`http://evil.com?target=safe.com`）
- 确认是否同时过滤了重定向（`allow_redirects=False`）
- 查找 DNS 解析后是否二次验证（TOCTOU 问题）

**跨模块保护（L4: 跨模块追踪）：**
- 检查装饰器：`@require_internal_access` / `@validate_url`
- 中间件过滤：Flask/Django 请求钩子中的全局验证
- 配置文件：`ALLOWED_HOSTS` / `TRUSTED_PROXIES` 设置项

## Classify

### 确认为漏洞
- 用户输入直接传递给 HTTP 请求函数，无任何过滤
- 保护机制存在明显绕过方式（如仅检查协议，未限制目标地址）
- 可访问内网地址（127.0.0.1, 192.168.x.x, 169.254.x.x）或云元数据（169.254.169.254）
- 白名单实现错误（使用 `in` 判断而非域名解析验证）

### 误报场景
- URL 来自配置文件或数据库硬编码，非用户直接控制
- 存在严格的域名白名单且实现正确（解析后验证 + 禁用重定向）
- 请求发生在隔离网络环境（容器无权访问宿主或内网）
- 仅允许公网且已验证的第三方 API（如 OAuth 回调已预注册）

### 代码异味
- 白名单过于宽泛（如允许整个 `.com` 顶级域）
- 存在保护但未覆盖所有代码路径（如仅保护 GET 未保护 POST）
- 依赖客户端验证而非服务端强制
- 日志记录不足，无法追踪异常请求来源

## Low risk

### 降级为低风险的情况
- **受限访问范围**：应用部署在 DMZ 区且无法访问核心内网资源
- **只读操作**：仅 GET 请求，无法触发内部系统状态变更
- **需要高权限**：触发点需要管理员账户且有严格鉴权
- **有效超时限制**：设置了极短的 `timeout`（<1秒）限制盲打探测
- **响应不可见**：请求结果不返回给用户，仅记录日志（需确认无时间盲注可能）
- **二次确认机制**：请求需要通过邮件/OTP 二次授权才会实际发起
- **业务限制**：严格的 Rate Limit 使大规模扫描不可行

### 需要额外评估的因素
- 目标服务是否运行敏感服务（Redis/Elasticsearch/Kubelet API）
- 云环境中是否可访问元数据服务获取凭证
- 是否可利用协议走私（file://, gopher://, dict://）
- 内网是否存在未授权访问的管理后台
