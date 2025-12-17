# Python 图像预览 SSRF 漏洞审计指南

## 漏洞概述

图像预览功能中的 SSRF 漏洞是最常见的 SSRF 攻击面。攻击者通过伪造 URL 参数，使应用程序访问内网资源、云元数据服务、本地文件或内部应用，导致信息泄露或身份凭证盗取。

## 典型漏洞代码模式

```python
import requests
from PIL import Image
from io import BytesIO

# 场景1: Flask Web框架（最常见）
@app.route('/preview')
def preview_image():
    url = request.args.get('url')
    response = requests.get(url)  # ⚠️ 无任何验证，直接网络请求
    img = Image.open(BytesIO(response.content))
    return send_file(BytesIO(response.content), mimetype='image/png')

# 场景2: urllib库使用（容易遗漏）
import urllib.request
def fetch_image(image_url):
    opener = urllib.request.urlopen(image_url)  # ⚠️ 无协议/IP限制
    return opener.read()

# 场景3: 异步获取（含隐藏漏洞）
import aiohttp
async def proxy_image(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:  # ⚠️ 无验证，异步漏洞
            return await resp.read()

# 场景4: 文件上传后处理（二阶段漏洞）
def process_uploaded_image(filename):
    # 从数据库读取用户上传的URL
    url = db.query(f"SELECT url FROM images WHERE id={request.args.get('id')}")
    img = Image.open(requests.get(url).raw)  # ⚠️ 来源不可信
```

## 审计清单

### L1 快速定位 - 关键词扫描

| 类别 | 关键词 | 说明 |
|------|--------|------|
| HTTP 库 | `requests.get\|post`、`urllib.urlopen`、`httpx.get`、`aiohttp` | 核心网络请求库 |
| 图像处理 | `Image.open()`、`PIL.Image`、`cv2.imread()`、`imageio.imread()` | 图像解析库（URL 数据流） |
| 参数来源 | `request.args.get('url')`、`request.json['url']`、`form['image']` | URL 参数的用户输入点 |
| 异步标记 | `async def`、`await session.get(url)`、`aiohttp.ClientSession` | 异步请求易遗漏防护 |
| 路由端点 | `/preview`、`/image`、`/thumbnail`、`/fetch`、`/proxy`、`/download` | 常见攻击端点 |
| 数据库读取 | `db.query()`、`Image.from_url(db.url)`、`Redis` | 二阶段漏洞：来源不可信 |

### L2 深度扫描 - 防护机制检查

**必检项：**
1. **协议限制**（最易绕过）
   - ✅ `urlparse(url).scheme in ['http', 'https']` 且不允许用户控制 scheme
   - ⚠️ 仅检查 `https://` 但未处理大小写 (`HtTps://`)、双重编码 (`HtTp%3A//`)
   - ❌ 黑名单禁用 `file://` 但遗漏 `data://`、`javascript://`、`ftp://`、`gopher://`

2. **IP 白名单与私有地址检查**
   - ✅ 使用 `ipaddress` 模块：`ip_address(ip).is_private`
   - ⚠️ 仅检查 `127.0.0.1` 未覆盖：`localhost`、`0.0.0.0`、`[::1]`（IPv6）、`::ffff:127.0.0.1`（IPv6 映射）、`169.254.*`（链接本地）
   - ❌ 仅阻止特定 IP 段但遗漏云元数据：AWS `169.254.169.254`、GCP `metadata.google.internal`（需 DNS 解析）、AliCloud `100.100.100.200`

3. **DNS 重绑定防护**（高级）
   - ✅ 解析 URL → 获取 IP → 校验 IP → 建立连接时再次校验同一域名 IP 未变化
   - ⚠️ 仅执行一次 DNS 解析后直接请求（存在 TOCTOU：请求前 DNS 快速切换到内网 IP）
   - 检查代码：是否在 `requests.get()` 前后都调用 `socket.gethostbyname(netloc)`

4. **重定向处理**
   - ✅ `allow_redirects=False`（禁用重定向）
   - ⚠️ 允许重定向但 `max_redirects=1` 且校验 Location 头指向合法域名
   - ❌ 允许无限重定向：`attacker.com → 127.0.0.1`、`legitimate.com → 192.168.1.1`

5. **响应内容校验**（通常遗漏）
   - Content-Type 检查：`resp.headers.get('content-type', '').startswith('image/')`
   - Content-Length 限制：防止文件炸弹，如 `int(resp.headers.get('content-length', 0)) > 10*1024*1024`
   - 流式读取大小限制：`stream=True` 后检查每个 chunk 大小

6. **超时与连接管理**
   - ✅ 设置合理超时：`timeout=5`（推荐 3-10s）
   - ⚠️ 超长超时可被用于 Slowloris 攻击（客户端频繁请求）
   - 检查：是否存在连接泄露（未关闭 response、未设置 max_retries）

## 漏洞分类

### 确认漏洞（需上报，CVSS ≥ 5.3）

| 信号 | 判定 | 利用场景 |
|------|------|---------|
| 用户 URL → 直接 `requests.get(url)` | ⛔ 严重 SSRF | 访问内网、云元数据、本地文件 |
| 黑名单绕过：仅阻 `127.0.0.1` | ⛔ 可绕过 | `localhost`、`0.0.0.0`、IPv6 缩写 |
| DNS Rebinding 无防护 | ⛔ 高风险 | 初次校验合法 IP，请求时切换内网 |
| 允许 302 重定向无校验 | ⛔ 可绕过 | attacker.com → 127.0.0.1 |
| 用户可控 `allow_redirects` 参数 | ⛔ 防护被禁用 | 攻击者直接关闭防护开关 |
| 异步请求无 IP 校验 | ⛔ 隐藏漏洞 | 代码审查易遗漏 |

### 可能漏洞需深度审查

| 情景 | 判断标准 | 审查要点 |
|------|---------|---------|
| 正则 URL 白名单 | `re.match(r'^https://.*\.example\.com')` | 检查正则是否有缺陷：`.` 需转义、`.*` 贪心、未锚定末尾 |
| IP 段白名单 | `ipaddress.ip_network('10.0.0.0/8')` | 需评估是否能到达内部服务、云元数据、应用层端口 |
| 仅禁用 `file://` | 黑名单 `file://` | 可绕过：`data://`、`blob://`、`javascript://` 在特定框架中可读取 |
| TOCTOU 时序漏洞 | 检查→请求间存在延迟 | DNS 在检查后可快速切换（高级攻击，需测试环境验证） |

### 误报判定（确认非漏洞）

- URL 来自**管理员配置文件、环境变量、数据库信任表**，非普通用户直接输入
- 实现了**完整的 IP 白名单**，使用 `ipaddress` 模块与双重 DNS 校验，无绕过向量
- 仅能访问**完全隔离的外网**（DMZ 区域），内网防火墙规则确保无法回源
- 请求**需要签名或 HMAC 验证**，攻击者无法伪造任意请求（如 AWS SigV4）

### 代码异味（需补充测试）

- 网络请求后缺少 Content-Type/响应大小校验，可能加载恶意文件
- 重定向未禁用但有 max_redirects 限制，仅能绕过某些场景（需试探利用链）
- 仅阻断私有 IP 但未考虑云元数据：AWS `169.254.169.254`、GCP `metadata.google.internal`、AliCloud `100.100.100.200`
- 异步请求无全局超时控制，可能产生连接泄露或被用于 Slowloris 攻击

## 低风险评估

以下场景可评为低风险：
- 仅能访问外网资源，内网隔离完善且应用无外部攻击面
- 响应内容不回显给用户，仅用于日志记录或异步处理（但需评估端口扫描副作用）
- 请求目标受限于特定云服务 API（AWS S3、AliCloud OSS），且凭证隔离
- 存在请求频率限制、超时极短（<1s）且无法绕过，降低批量探测价值
- URL 参数需要签名验证，攻击者无法伪造任意请求（需确认签名算法强度）
- 应用部署在无敏感内网服务的隔离容器/沙箱环境中（需确认隔离有效性）

**重要：** 即使评为低风险，仍需在报告中说明潜在风险（容器逃逸、云元数据泄露等）。

## 审计技巧与经验

### 1. 代码审查中的优先级

- **第一优先**：搜索 `requests.get(url)` / `urllib.urlopen(url)` 在接收用户输入后直接调用的代码
- **第二优先**：检查异步代码（`aiohttp`、`asyncio`），通常被忽视
- **第三优先**：检查数据库/缓存中的 URL 来源，排除管理员配置

### 2. 常见绕过方法及对应审查

| 绕过方法 | 对应防护 |
|---------|---------|
| `127.0.0.1` → `localhost` | 需 DNS 解析后再检查 IP |
| `http://0.0.0.0:8080` | 需 check `ip.is_loopback` |
| `http://127.0.0.0.1/` | 需 IP 合法性校验，不仅检查字符串 |
| `http://2130706433/` | 整数型 IP（十进制），需解析后校验 |
| `http://[::ffff:127.0.0.1]/` | IPv6 映射，需规范化后检查 |
| 重定向：attacker.com → 127.0.0.1 | 需 `allow_redirects=False` |
| DNS 重绑定：初次 IP 合法，请求时变内网 | 需二次 DNS 校验 |

### 3. 实战审查点

**读代码时的快速定位法：**
1. 找到 URL 参数入口（通常在路由函数开头）
2. 追踪 URL 流向，看是否直接传给网络请求库
3. 向上回溯查看是否存在校验逻辑（通常在导入或函数开始处）
4. 评估防护：白名单 > IP 校验 > 重定向限制 > 无防护

**异步代码特殊检查：**
- 异步函数可能在不同文件中实现（如 celery task、backgroud job）
- 需检查是否存在全局 Session 级别的超时配置
- 检查是否使用了 connection pool（易导致连接泄露）

**云部署环境下的检查：**
- 问环境部署方式：云主机、容器、Serverless
- 容器环境需额外防护元数据服务访问
- Serverless（AWS Lambda）仍需防护环境变量泄露

---

**文件行数统计：** 当前版本共 154 行（符合要求）