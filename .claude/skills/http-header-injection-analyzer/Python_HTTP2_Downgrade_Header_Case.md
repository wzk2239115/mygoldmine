# Python HTTP/2降级头字段大小写处理

## 基本信息
- **难度等级：** ★★★★☆ | **审计时间：** 30-45分钟
- **关键词搜索：** `h2`, `hyper`, `httpx`, `headers.get`, `request.headers`, `:authority`, `:method`, `lower()`, `casefold()`
- **快速检查：** 头字段比较是否大小写敏感，HTTP/2伪头字段处理是否正确

## 漏洞成因

HTTP/2协议强制所有头字段小写（如`content-type`），而HTTP/1.1传统使用多种大小写形式（如`Content-Type`）。Python Web框架处理请求头时，若使用大小写敏感比较或自定义头规范化逻辑，HTTP/2请求可能绕过安全检查。

### 常见漏洞模式

```python
# ✗ 漏洞：大小写敏感的头检查
def check_auth_header(request):
    # HTTP/2的authorization是小写，此检查可能被绕过
    if 'Authorization' in request.headers:
        return validate_token(request.headers['Authorization'])
    return False
    # HTTP/2请求的'authorization'（小写）绕过检查
```

```python
# ✗ 漏洞：黑名单使用大小写敏感匹配
BLOCKED_HEADERS = ['X-Forwarded-For', 'X-Real-IP', 'X-Forwarded-Host']

def filter_proxy_headers(headers):
    filtered = {}
    for name, value in headers.items():
        if name not in BLOCKED_HEADERS:  # 大小写敏感
            filtered[name] = value
    return filtered
    # HTTP/2的'x-forwarded-for'（小写）绕过过滤
```

```python
# ✗ 漏洞：手动字符串比较Content-Type
def is_json_request(request):
    content_type = request.headers.get('Content-Type', '')
    # HTTP/2头是小写：content-type
    return content_type.startswith('application/json')
    # HTTP/2请求使用'content-type'键，get可能返回None
```

```python
# ✗ 漏洞：自定义头规范化与框架不一致
def normalize_header_name(name):
    # 首字母大写规范化
    return '-'.join(word.capitalize() for word in name.split('-'))

def get_header_safe(request, name):
    normalized = normalize_header_name(name)
    return request.headers.get(normalized)
    # 框架可能已经小写化了头名称
```

```python
# ✓ 修复：大小写不敏感的头访问
def check_auth_header_safe(request):
    # 使用框架提供的大小写不敏感访问
    # Flask/Werkzeug的headers对象是大小写不敏感的
    auth = request.headers.get('Authorization')  # 自动处理大小写
    if auth:
        return validate_token(auth)
    return False

def filter_proxy_headers_safe(headers):
    blocked_lower = {'x-forwarded-for', 'x-real-ip', 'x-forwarded-host'}
    filtered = {}
    for name, value in headers.items():
        if name.lower() not in blocked_lower:  # 大小写不敏感
            filtered[name] = value
    return filtered
```

### 审计专业技巧与真实漏洞判断

#### 真实漏洞特征识别

**特征1：安全控制点的大小写敏感比较** ⚠️ **高风险**
- 关键证据：在身份验证、授权、防护头过滤等**安全关键路径**中使用精确比较
- 快速判断：搜索认证相关函数（`auth`, `validate`, `permission`, `token`），确认是否使用大小写敏感的头检查
- 真实案例：`if request.headers.get('Authorization') == None` 无法捕获`authorization`（HTTP/2格式）
- 误报排除：如果仅在非安全路径（日志、统计、格式转换）中使用，降低为低风险

**特征2：自定义头规范化与框架行为不一致** ⚠️ **中风险**
- 关键证据：存在自定义的`normalize_header_name()`、`standardize_header()`等函数
- 验证方法：
  1. 查看函数实现是否使用`capitalize()`, `title()`, `upper()`等可能与框架默认行为不一致的操作
  2. 跟踪该函数的使用点，检查是否应用到安全检查逻辑
  3. 对比框架默认行为：Flask/Werkzeug默认小写化，Django也是小写化
- 真实案例：`normalize_header_name('authorization')` 返回`Authorization`，但框架已返回小写形式
- 误报排除：如果函数仅用于显示目的（响应头、日志输出），非安全关键

**特征3：HTTP/2伪头与传统头处理的分支逻辑** ⚠️ **高风险**
- 关键证据：存在对`:authority`, `:method`, `:path`的特殊处理，且与`Host`, `Method`, `Path`处理逻辑不一致
- 验证方法：
  1. 搜索伪头字段`:` 前缀
  2. 检查伪头处理是否与HTTP/1.1相应头的安全检查**完全相同**
  3. 注意跨协议验证的一致性（如URL验证、主机验证）
- 真实案例：`Host`头验证过滤了恶意域名，但`:authority`伪头未被验证
- 误报排除：如果伪头与传统头验证逻辑完全一致，仅使用哪个取决于协议版本

**特征4：黑名单比较中的大小写问题** ⚠️ **中风险**
- 关键证据：`in BLOCKED_HEADERS` 或 `== blocked_value` 的精确比较
- 快速判断：
  ```python
  # 真漏洞
  BLOCKED = ['X-Forwarded-For', 'X-Real-IP']
  if header_name in BLOCKED:  # 'x-forwarded-for'会绕过

  # 误报（安全的）
  BLOCKED = ['x-forwarded-for', 'x-real-ip']
  if header_name.lower() in BLOCKED:  # 正确处理
  ```
- 真实案例：反向代理头注入，使用`x-forwarded-for`（小写）绕过过滤
- 误报排除：黑名单已全部小写，且比较使用`.lower()`

#### 常见的审计误报陷阱

**误报陷阱1：框架自动处理造成的假阳性**
- 误报现象：代码中看起来使用大小写敏感比较，但框架已自动处理
- 确认方法：
  - Flask: `request.headers` 是 `werkzeug.datastructures.Headers`，实现了`__contains__`的大小写不敏感
  - Django: `request.META` 中HTTP头都转换为大写+`HTTP_`前缀，如`HTTP_AUTHORIZATION`
  - FastAPI/Starlette: `request.headers` 是自定义MutableHeaders，支持大小写不敏感
- 验证代码：运行 `print(type(request.headers))` 确认类型

**误报陷阱2：对象级别的`.get()`方法是安全的**
- 误报现象：看到`headers.get('Authorization')`就认为是漏洞
- 真实情况：这是**安全的**，因为框架的Headers对象已实现大小写不敏感的`__getitem__`和`get()`
- 正确判断：仅当看到`dict.get()`（普通字典）或手动字符串比较才是漏洞

**误报陷阱3：仅在日志或监控中使用头名称**
- 误报现象：在日志输出中看到`'Authorization'`（大写）就认为有问题
- 真实情况：日志显示格式不影响安全性，关键是**安全检查点**
- 正确判断：只关注安全关键路径（认证、授权、防护），忽略监控/日志

**误报陷阱4：HTTP/2部分支持但未激活**
- 误报现象：代码中有HTTP/2库导入，但实际环境仅运行HTTP/1.1
- 验证方法：
  - 检查ASGI/WSGI服务器配置，是否启用HTTP/2协商
  - 常见仅支持HTTP/1.1的：`gunicorn`（默认），`uWSGI`（默认）
  - 需要HTTP/2的：`hypercorn`, `daphne`, `uvicorn`（需配置）
- 风险判定：如果生产环境仅HTTP/1.1，此类漏洞无法被触发

#### 审计检查清单（按优先级）

| 优先级 | 检查项 | 审计方法 | 误报排除条件 |
|--------|--------|---------|------------|
| **P0** | 大小写敏感的头比较 | 搜索 `in request.headers\|== 'Content-Type'`，**且在认证/授权函数内** | 验证框架Headers对象类型；检查`.get()`而非`in`操作符 |
| **P0** | 安全头黑名单 | 搜索 `BLOCKED\|filtered.*header`，检查存储和比较是否大小写敏感 | 黑名单全小写 + 使用`.lower()`比较 |
| **P1** | 自定义头规范化 | 搜索 `capitalize\|title\|upper.*header`，追踪用途 | 函数仅用于显示目的，非安全路径 |
| **P1** | HTTP/2库使用 | 搜索 `h2\|hyper\|httpx`，检查头处理 | 生产环境仅HTTP/1.1无HTTP/2协商 |
| **P2** | 伪头字段处理 | 搜索 `:authority\|:method\|:path`，对比HTTP/1.1头的验证逻辑 | 伪头验证与传统头完全一致 |
| **P2** | 中间件头处理 | 搜索 `before_request\|middleware`，检查头规范化 | 框架级别的统一规范化 |

### 审计等级判定

| 等级 | 特征 | 审计重点 |
|------|------|---------|
| **L0** | 仅使用框架默认头访问 | **跳过**，框架自动处理大小写 |
| **L1** | 使用`.get()`方法 | 关键词扫描确认无精确匹配 |
| **L2** | 存在字符串形式头操作 | 检查大小写处理 |
| **L3** | 自定义头解析或规范化 | 逐行审计处理逻辑 |
| **L4** | HTTP/2代理或协议转换 | 跨模块追踪转换全流程 |

---

## 漏洞判定

### 确认漏洞（三个条件全部满足）
1. 存在手动字符串形式的头处理
2. 使用大小写敏感比较
3. 安全功能依赖该头检查

### 典型漏洞特征（满足任一项即确认）
- ✗ `if 'Authorization' in headers` 大小写敏感检查
- ✗ `if name == 'X-Forwarded-For'` 精确字符串比较
- ✗ 自定义`capitalize()`规范化与框架行为不一致
- ✗ HTTP/2伪头`:authority`与`Host`头处理不一致

### 安全排除（任一项充分）
- ✓ 使用Flask/Django框架的`headers.get()`（自动大小写不敏感）
- ✓ 所有比较使用`name.lower()`或`casefold()`
- ✓ 黑名单使用小写形式存储和比较
- ✓ 仅HTTP/1.1环境，无HTTP/2支持

### 灰色判定（风险较低但需注意）
- 仅内部服务通信
- 大小写差异仅影响非安全功能
- 使用ASGI服务器但版本不确定

---

## 实现建议

### 核心防护方案

**方案1：使用框架提供的大小写不敏感访问**
```python
from flask import request

def get_header_safe(name):
    # Werkzeug的Headers对象是大小写不敏感的
    return request.headers.get(name)

def has_header_safe(name):
    # 使用get而非in操作符
    return request.headers.get(name) is not None
```

**方案2：统一小写化比较**
```python
BLOCKED_HEADERS = frozenset(['x-forwarded-for', 'x-real-ip', 'x-forwarded-host'])

def is_blocked_header(name):
    return name.lower() in BLOCKED_HEADERS

def filter_headers(headers):
    return {
        name: value
        for name, value in headers.items()
        if not is_blocked_header(name)
    }
```

**方案3：中间件统一处理**
```python
from flask import Flask, request, g

app = Flask(__name__)

@app.before_request
def normalize_headers():
    # 创建规范化的头字典
    g.normalized_headers = {
        name.lower(): value
        for name, value in request.headers
    }

def get_header(name):
    return g.normalized_headers.get(name.lower())
```

### 检查清单
- [ ] 使用框架提供的大小写不敏感头访问方法
- [ ] 黑名单/白名单使用小写形式或`.lower()`比较
- [ ] 避免直接使用`in headers`检查
- [ ] HTTP/2伪头与HTTP/1.1头处理一致
- [ ] 测试HTTP/2请求的小写头绕过

---

## 修复优先级

1. **立即修复**：安全检查使用大小写敏感比较
2. **本周修复**：统一使用框架的头访问方法
3. **可选加强**：添加HTTP/2协议处理测试
4. **长期优化**：使用ASGI服务器的安全抽象

