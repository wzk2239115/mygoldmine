# Python_WebhookProxySSRF

**漏洞类型**: Webhook 回调代理场景中直接使用用户输入构造请求目标，缺乏对回调地址的验证

---

## Details

### 代码示例

**易受攻击的代码模式**:
```python
# requests 示例
import requests

@app.route('/webhook/register', methods=['POST'])
def register_webhook():
    callback_url = request.json.get('callback_url')  # 用户可控的回调URL
    # 触发事件时直接请求回调地址
    response = requests.post(callback_url, json=event_data)  # 无验证直接发送
    return {'status': 'registered'}

# urllib 示例
from urllib.request import urlopen

def notify_webhook(webhook_url, data):
    # webhook_url 来自数据库但原始由用户注册
    req = Request(webhook_url, data=json.dumps(data).encode())  # 直接使用
    urlopen(req)

# httpx 示例
import httpx

async def trigger_callback(user_id):
    webhook = db.query(Webhook).filter_by(user_id=user_id).first()
    async with httpx.AsyncClient() as client:
        await client.post(webhook.url, json=payload)  # 存储的用户输入

# aiohttp 示例
import aiohttp

async def send_notification(callback_endpoint):
    url = f"http://{request.form['host']}/callback"  # URL 拼接
    async with aiohttp.ClientSession() as session:
        await session.post(url, json=data)
```

### 快速定位核心操作 **[L1-L2]**

**L1 关键词扫描**:
- HTTP 客户端库导入: `import requests`, `from urllib.request import`, `import httpx`, `import aiohttp`
- 请求方法: `requests.post()`, `requests.get()`, `urlopen()`, `client.post()`, `session.post()`
- Webhook 相关关键词: `webhook`, `callback`, `notify`, `hook_url`, `callback_url`, `notification_url`
- 用户输入来源: `request.json`, `request.form`, `request.args`, 数据库查询 `.filter_by()`, `.get()`

**L2 跳读定位**:
- 从 Webhook 注册/配置接口入口扫描用户输入获取点
- 追踪 URL 变量从存储（数据库/缓存）到实际请求发送的完整流程
- 重点关注: 异步任务、事件触发器、定时任务中的 HTTP 请求调用
- 检查 Celery 任务、消息队列消费者、事件监听器中的回调逻辑

### 快速定位保护机制 **[L2-L4]**

**L2 跳读检测**:
- URL 白名单检查: `if url in allowed_urls`, `if domain in TRUSTED_DOMAINS`, 正则匹配 `re.match(r'^https://trusted\.com', url)`
- URL 解析验证: `urlparse(url)`, 然后检查 `.scheme`, `.netloc`, `.hostname`
- IP 过滤: 检查是否有 `is_private_ip()`, `is_internal_address()`, `ipaddress.ip_address()` 等函数调用
- 协议限制: `url.startswith('https://')`, `parsed.scheme in ['http', 'https']`

**L3 逐行分析**:
- 检查白名单实现是否可绕过 (如 `url.startswith()` 可用 `@` 绕过, `url.endswith()` 可用 `.` 绕过)
- 验证 DNS rebinding 防护: 是否多次解析 hostname 或使用 IP 地址校验
- 确认重定向跟随是否禁用 (`allow_redirects=False`, `max_redirects=0`)
- 检查 SSRF 专用防护库: `ssrf-protect`, `safecurl-py` 的使用

**L4 跨模块追踪**:
- 追踪 Webhook 模型类的 `url` 字段验证器 (Django: `validators=[]`, SQLAlchemy: `@validates`)
- 检查序列化器/表单类中的 URL 字段校验 (DRF: `URLField`, WTForms: `validators.URL()`)
- 检查中间件、装饰器、信号处理器中的全局保护
- 验证 Celery 任务参数过滤、消息队列数据验证
- 追踪配置文件中的代理设置 (`proxies=`, `trust_env=False`)

---

## Classify

### 漏洞判定标准

**确认为漏洞**:
- 用户可完全控制 Webhook 回调 URL，且无任何域名/IP 验证
- 可访问内网资源 (如 `127.0.0.1`, `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`)
- 可访问云元数据服务 (`169.254.169.254`, `fd00:ec2::254`)
- 保护机制存在可绕过缺陷 (如 `http://evil.com@127.0.0.1`、DNS rebinding、302 跳转)
- URL 验证在存储时检查但发送时未重新校验 (TOCTOU 时间窗口攻击)

**误报判定**:
- Webhook URL 来自管理员配置文件或环境变量，普通用户不可修改
- URL 从严格的白名单配置中选择（用户仅提供索引 ID）
- 存在完整且正确的防护链: 协议限制 (http/https) + 域名白名单 + 私有IP过滤 + 禁用重定向
- 在隔离网络环境运行，出站流量经过网关层 SSRF 检测

**代码异味**:
- 有基础验证但不够完善 (如仅检查协议为 http/https，未限制目标地址)
- 使用黑名单而非白名单 (如仅阻止 `127.0.0.1` 但允许 `localhost`, `0.0.0.0`)
- 依赖不完整的 `urlparse` 校验 (Python URL 解析存在已知问题)
- 在注册时校验但允许更新 URL 时未重新验证
- 异步任务/延迟队列中发送请求，验证与执行存在时间差

---

## Low risk

### 低风险场景

**应用场景受限**:
- 功能仅限管理员或经过严格实名认证的企业用户可访问
- 需要有效的 API Token/OAuth 且有严格的速率限制 (如每小时仅 10 次请求)
- 请求结果不直接返回，仅作内部日志记录或异步处理，无信息回显
- Webhook 触发需要特定复杂条件，攻击者难以可控地触发回调

**网络隔离保护**:
- 应用部署在严格的 DMZ 区域或容器网络，无法访问敏感内网服务
- 出口流量经过 NAT 网关并配置严格防火墙规则，拒绝私有 IP 段
- 使用专用的 Webhook 代理服务且代理层已实现 SSRF 防护
- 云环境已禁用 IMDS v1 且使用 v2 需要特殊 token header

**攻击面有限**:
- 仅允许 POST 到公开的第三方服务 (如 Slack、Discord webhook)，且有签名验证
- 响应内容不被处理，仅关心状态码 2xx/非 2xx，不解析响应体
- 连接超时极短 (1-3秒)，读取超时严格，难以进行慢速端口扫描
- 请求数据不包含敏感信息，仅发送公开事件通知

**部分缓解措施**:
- 虽采用黑名单但涵盖较全面 (私有IP、特殊域名、loopback 地址多种表示形式)
- 有完整的审计日志和异常告警，可快速检测到内网探测行为
- Webhook URL 需要通过验证流程 (如返回 challenge 验证、点击确认链接)
- 限制每个用户可注册的 Webhook 数量和触发频率
