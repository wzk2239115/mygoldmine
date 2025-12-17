# Python requests库请求头用户输入注入

## 基本信息
- **难度等级：** ★★☆☆☆ | **审计时间：** 15-25分钟
- **关键词搜索：** `requests.get`, `requests.post`, `headers=`, `Session()`, `prepare_request`, `urllib.request`, `HTTPConnection`
- **快速检查：** 请求头字典是否包含用户输入，头名称或值是否可控

## 漏洞成因

使用Python `requests`库或`urllib`发起HTTP请求时，若请求头直接包含未验证的用户输入，攻击者可能注入CRLF字符实现请求走私、或通过控制敏感头（如`Host`、`Authorization`）实现SSRF增强、认证绕过等攻击。

### 常见漏洞模式

```python
# ✗ 漏洞：用户输入直接作为请求头值
import requests

def fetch_api(user_agent):
    headers = {
        'User-Agent': user_agent,  # 用户输入未验证
        'Accept': 'application/json'
    }
    return requests.get('https://api.example.com/data', headers=headers)
    # 攻击: user_agent="Mozilla\r\nX-Injected: malicious"
```

```python
# ✗ 漏洞：用户可控制头名称
def proxy_request(header_name, header_value, url):
    headers = {
        header_name: header_value  # 头名称用户可控
    }
    return requests.get(url, headers=headers)
    # 攻击: header_name="Host", header_value="internal-service"
```

```python
# ✗ 漏洞：从请求复制头到内部请求
from flask import request
import requests

@app.route('/proxy')
def proxy():
    # 复制所有用户请求头到内部请求
    headers = dict(request.headers)
    return requests.get('http://internal-api/data', headers=headers).text
    # 攻击者可控制Host、X-Forwarded-For等敏感头
```

```python
# ✗ 漏洞：Authorization头来自用户输入
def call_api(api_token):
    headers = {
        'Authorization': f'Bearer {api_token}'  # 未验证格式
    }
    return requests.post('https://api.example.com/action', headers=headers)
    # api_token可能包含CRLF或恶意内容
```

```python
# ✓ 修复：白名单验证和过滤
ALLOWED_HEADERS = {'x-request-id', 'x-correlation-id', 'accept-language'}

def safe_proxy_request(custom_headers, url):
    safe_headers = {}
    for name, value in custom_headers.items():
        # 白名单验证头名称
        if name.lower() not in ALLOWED_HEADERS:
            continue
        # 过滤CRLF
        safe_value = value.replace('\r', '').replace('\n', '')
        safe_headers[name] = safe_value

    return requests.get(url, headers=safe_headers)
```

### 审计检查清单（按优先级）

| 优先级 | 检查项 | 审计方法 |
|--------|--------|---------|
| **P0** | 头名称用户可控 | 搜索 `headers\[.*\]` 或 `headers={`，检查字典键是否来自用户输入 |
| **P0** | Host/Authorization头 | 搜索 `'Host':`、`'Authorization':`，检查值来源 |
| **P1** | 请求头复制 | 搜索 `dict(request.headers)`、`request.headers.get`，检查是否原样传递 |
| **P1** | Session对象 | 搜索 `Session().headers`，检查是否持久化用户输入 |
| **P2** | urllib使用 | 搜索 `urllib.request`、`HTTPConnection`、`add_header`，检查头来源 |
| **P2** | 代理转发 | 搜索 `proxy`、`forward`，检查头过滤逻辑 |

### 审计等级判定

| 等级 | 特征 | 审计重点 |
|------|------|---------|
| **L0** | 请求头全部硬编码 | **跳过**，无用户输入 |
| **L1** | 头值来自配置或环境变量 | 关键词扫描确认来源可信 |
| **L2** | 单函数内头值使用用户输入 | 检查是否有CRLF过滤和白名单 |
| **L3** | 头值由外部函数返回 | 逐行追踪返回值来源 |
| **L4** | 请求代理/转发中间件 | 跨模块审计头过滤机制 |

---

## 审计专业技巧

### 真实漏洞与误报区分

#### 常见误报场景（需排除）

**误报1：硬编码头值但包含变量名**
```python
# ✓ 安全 - 这不是注入漏洞
def get_user_info(user_id):
    headers = {
        'Authorization': 'Bearer token_for_user_id'  # 字符串字面量，不是用户输入
    }
    return requests.get(f'/api/users/{user_id}', headers=headers)
```

**误报2：单向数据流的头值验证**
```python
# ✓ 安全 - 单向流，值已验证
def request_with_timeout(timeout_val):
    timeout_val = int(timeout_val)  # 转换为整数
    headers = {
        'X-Timeout': str(timeout_val)  # 已验证为整数，CRLF注入不可能
    }
    return requests.get('http://example.com', headers=headers)
```

**误报3：requests库版本>=2.25.0自动防护**
```python
# ⚠️ 条件安全 - 需验证requests版本
import requests

def api_call(custom_value):
    headers = {'Custom-Header': custom_value}
    # requests>=2.25.0会自动移除CRLF，但仍需验证版本
    return requests.get('http://api.example.com', headers=headers)
    # 审计方法：检查requirements.txt或setup.py中的版本要求
```

#### 真实漏洞确认要点

**漏洞确认1：头值直接拼接用户输入**
```python
# ✗ 确认漏洞 - 直接字符串格式化
def fetch_data(api_token):
    headers = {
        'X-API-Key': f'key_{api_token}'  # 用户输入直接在f-string中
    }
    return requests.post('http://internal-api/action', headers=headers)
    # 攻击: api_token="abc\r\nSet-Cookie: admin=true"
```

**漏洞确认2：请求头来自多层函数传递**
```python
# ✗ 确认漏洞 - 跨函数追踪
def layer1(user_headers):
    return layer2(user_headers)

def layer2(user_headers):
    return requests.get('http://example.com', headers=user_headers)
    # 每一层都未做验证，需确认最源头是否用户可控
```

**漏洞确认3：条件判断过于宽松**
```python
# ✗ 确认漏洞 - 黑名单方案（容易绕过）
def filter_headers(headers):
    dangerous = ['eval', 'exec']
    for key, value in headers.items():
        if any(danger in value.lower() for danger in dangerous):
            continue  # 只过滤部分恶意字符
        headers_to_use = headers
    return headers_to_use
    # CRLF注入仍可行，黑名单方案不充分
```

### 审计深度分析技巧

**技巧1：请求头污染(HPP)检测**
```python
# 审计标志：同一请求头出现多次拼接
# ✗ 漏洞示意
def process_request(user_lang):
    headers = {}
    headers['Accept-Language'] = 'en'
    headers['Accept-Language'] = user_lang  # 后者覆盖前者
    return requests.get('http://example.com', headers=headers)

# 需要检查：后续头值是否覆盖安全默认值
```

**技巧2：Session持久化污染**
```python
# ✗ 确认漏洞 - Session头污染
class APIClient:
    def __init__(self):
        self.session = requests.Session()

    def call(self, user_headers):
        # 错误：持久化用户输入到session
        self.session.headers.update(user_headers)
        return self.session.get('http://api.example.com')
        # 后续请求都会携带污染的头

# 审计要点：检查session.headers.update()是否接收用户输入
```

**技巧3：编码绕过的风险**
```python
# ✗ 潜在漏洞 - 编码转换后注入
def safe_header(user_value):
    # 错误认为URLencode能防止CRLF
    encoded = quote(user_value)
    headers = {'X-Data': encoded}
    return requests.get('http://example.com', headers=headers)

# 审计要点：requests传输时会自动decode，编码方案无效
```

### 审计检查流程图

```
发现用户输入进入头字典
    ↓
[是否为头名称] → 是 → 立即判定为P0漏洞 → 停止
    ↓ 否
[是否为敏感头值] → 是 → 查看防护机制
    │            └→ Host/Authorization/Cookie/Referer等
    ↓ 否          └→ 有效白名单 → 安全
                  └→ 仅CRLF过滤 → 检查过滤完整性
                  └→ 版本自防护 → 验证版本号
[是否为自定义头值] → 是 → 检查CRLF过滤或白名单
    ├→ 有有效防护 → 安全
    ├→ 无防护 → 风险评估（判定为P1/P2）
```

### 审计注意事项

| 场景 | 判定 | 审计建议 |
|------|------|--------|
| 头名称可控 | **必定漏洞** | 立即标记P0，不需评估防护 |
| 敏感头可控（Host等） | **必定漏洞** | 即使有CRLF过滤也存在风险 |
| 无白名单，仅CRLF过滤 | **风险** | 需检查过滤是否覆盖所有变体（如%0d%0a） |
| 内部服务调用 | **降低风险** | 需确认不涉及跨域，且服务链可控 |
| requests版本自防护 | **有条件安全** | 必须验证requirements.txt和CI/CD版本 |

---

## 漏洞判定

### 确认漏洞（三个条件全部满足）
1. 请求头名称或值来自用户输入
2. 未进行CRLF过滤或白名单验证
3. 可能影响请求安全性（SSRF增强、认证绕过）

### 典型漏洞特征（满足任一项即确认）
- ✗ `headers[user_input] = value` 头名称用户可控
- ✗ `headers['Host'] = request.args.get('host')` Host头可控
- ✗ `dict(request.headers)` 直接复制到内部请求
- ✗ `Authorization: Bearer {user_token}` 未验证token格式

### 安全排除（任一项充分）
- ✓ 头名称使用白名单：`if name in ALLOWED_HEADERS`
- ✓ CRLF过滤：`value.replace('\r', '').replace('\n', '')`
- ✓ requests库自动拒绝CRLF（需验证版本>=2.25.0）
- ✓ 敏感头被删除：`headers.pop('Host', None)`

### 灰色判定（风险较低但需注意）
- 内部服务间调用
- 头值有长度限制
- 仅非敏感自定义头可控

---

## 实现建议

### 核心防护方案

**方案1：白名单验证**
```python
ALLOWED_CUSTOM_HEADERS = {'x-request-id', 'x-correlation-id', 'accept-language'}
SENSITIVE_HEADERS = {'host', 'authorization', 'cookie', 'x-forwarded-for'}

def filter_headers(user_headers):
    safe_headers = {}
    for name, value in user_headers.items():
        name_lower = name.lower()
        # 拒绝敏感头
        if name_lower in SENSITIVE_HEADERS:
            continue
        # 白名单验证
        if name_lower not in ALLOWED_CUSTOM_HEADERS:
            continue
        # CRLF过滤
        safe_headers[name] = value.replace('\r', '').replace('\n', '')
    return safe_headers
```

**方案2：安全的代理请求**
```python
def safe_proxy(target_url, request_headers):
    # 仅保留安全的头
    safe_headers = {
        'Accept': request_headers.get('Accept', '*/*'),
        'Accept-Language': request_headers.get('Accept-Language', 'en'),
    }

    # 生成新的请求ID
    safe_headers['X-Request-ID'] = generate_request_id()

    return requests.get(target_url, headers=safe_headers)
```

**方案3：Session安全使用**
```python
def create_safe_session(base_headers=None):
    session = requests.Session()
    # 仅设置安全的默认头
    session.headers.update({
        'User-Agent': 'MyApp/1.0',
        'Accept': 'application/json'
    })
    # 不要持久化用户输入到session
    return session
```

### 检查清单
- [ ] 请求头名称不接受用户输入
- [ ] 敏感头（Host、Authorization）不使用未验证的用户输入
- [ ] 代理转发时过滤或重写敏感头
- [ ] CRLF过滤：`replace('\r', '').replace('\n', '')`
- [ ] 测试CRLF注入：`header_value="test\r\nX-Injected: evil"`

---

## 修复优先级

1. **立即修复**：禁止用户控制头名称，过滤敏感头
2. **本周修复**：添加CRLF过滤，实现白名单验证
3. **可选加强**：升级requests库到最新版本
4. **长期优化**：封装安全的HTTP客户端包装器

