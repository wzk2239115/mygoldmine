# Python 远程文件包含 (RFI)

## 漏洞成因
允许 `urllib.request`/`requests` 等库拉取用户可控的远程 URL，并将内容写入临时目录或直接执行/引用，导致攻击者可注入恶意远程代码。

---

## Details

### 代码示例

```python
# 危险示例 1: urllib.request 拉取远程文件
import urllib.request
from flask import request

@app.route('/download')
def download():
    url = request.args.get('url')  # 用户可控
    urllib.request.urlretrieve(url, '/tmp/downloaded_file')
    exec(open('/tmp/downloaded_file').read())

# 危险示例 2: requests 拉取后执行
import requests
remote_url = request.form.get('config_url')  # 用户可控
resp = requests.get(remote_url)
exec(resp.text)

# 危险示例 3: 动态导入远程模块
import importlib.util
spec = importlib.util.spec_from_file_location("module", user_url)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
```

### 快速定位核心操作 (L2: 跳读)
- **关键函数**：`urllib.request.urlopen/urlretrieve`、`requests.get/post`、`httpx.get`
- **后续危险操作**：
  - `exec()`/`eval()` 执行远程内容
  - `importlib` 动态加载远程模块
  - `pickle.load()` 反序列化远程数据
  - `open().write()` 写入后由其他模块读取执行
- **数据流追踪**：URL 参数 → HTTP 库 → 文件写入/执行

### 快速定位保护机制 (L3: 逐行读)
- **白名单验证**：
  - `if url.startswith('https://trusted-domain.com/')`
  - `urlparse(url).netloc in ALLOWED_HOSTS`
- **协议限制**：
  - `if parsed.scheme not in ['http', 'https']`（禁止 file://）
- **内容验证**：
  - 拉取后检查 `Content-Type` 头
  - 签名验证：`hmac.compare_digest(signature, expected)`
- **沙箱执行**：
  - `subprocess.run(..., timeout=5)` 限制执行环境
- **审计重点**：验证逻辑是否可被绕过（如大小写、编码、重定向）

---

## Classify

### 漏洞
- URL 来源完全/部分可控，且无白名单或白名单可绕过
- 拉取内容后直接 `exec/eval/pickle.load` 或写入可执行路径
- 跨模块场景：A 模块拉取 URL，B 模块无验证执行

### 误报
- URL 硬编码或仅取自配置文件（非用户输入）
- 白名单严格且涵盖域名/路径/协议，无绕过路径
- 拉取内容仅用于静态资源（如图片、CSS），不涉及代码执行

### 代码异味
- URL 部分可控但有弱验证（如仅检查后缀 `.json`，未检查域名）
- 拉取内容未立即执行，但存储路径可被其他攻击链利用
- 依赖外部服务验证 URL 安全性，但验证服务本身不可信

---

## Low risk

- **拉取内容类型受限**：仅处理 JSON/XML 等数据格式，且后续仅做数据解析（如 `json.loads`），无反序列化/代码执行
- **网络隔离环境**：应用运行在无外网访问的内网，攻击者无法部署恶意远程服务器
- **强白名单 + 签名验证**：同时满足域名白名单和 HMAC 签名校验，且密钥管理安全
- **只读操作**：拉取内容仅用于展示或日志记录，未写入磁盘或传递给危险函数
- **短期临时性代码**：如测试脚本、一次性数据迁移工具（非生产代码）