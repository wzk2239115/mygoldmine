# JWT - JWKS URI 验证漏洞

## Details

### 什么是 JWKS 和 JWKS URI

**JWKS (JSON Web Key Set)** 是一个包含公钥的 JSON 结构，用于验证 JWT 的签名。

**JWKS URI** 是指向 JWKS 数据的 HTTP 端点的 URL（通常在 JWT 的 `jku` 参数或应用配置中指定）。

应用需要从 JWKS URI 获取公钥来验证 JWT 签名。如果 JWKS URI 的验证不当，攻击者可以：
1. 指向恶意的 JWKS 端点
2. 执行中间人攻击
3. 用恶意公钥替换真正的公钥

### 典型代码示例

**Java - Spring Security JWT 验证（不安全）：**
```java
@Configuration
public class SecurityConfig {
    @Bean
    public JwtDecoder jwtDecoder(@Value("${jwt.jwks-uri}") String jwksUri) throws Exception {
        // 危险：直接使用配置中的 JWKS URI，未验证
        return NimbusJwtDecoder.withJwkSetUri(jwksUri).build();
    }
}
```

**Python - PyJWT 验证（不安全）：**
```python
import requests
import jwt
from jwt import PyJWT

def verify_token(token, jwks_uri):
    # 危险：直接从用户控制的 JWKS URI 获取公钥
    response = requests.get(jwks_uri)
    jwks = response.json()

    # 从 JWKS 中提取公钥
    public_key = jwt.algorithms.RSAAlgorithm.from_jwks(jwks)

    # 验证 token
    decoded = jwt.decode(token, public_key, algorithms=['RS256'])
    return decoded
```

**Node.js - jsonwebtoken（不安全）：**
```javascript
const jwt = require('jsonwebtoken');
const axios = require('axios');

async function verifyToken(token, jwksUri) {
    // 危险：直接从 JWKS URI 获取公钥，未验证 URL 来源
    const response = await axios.get(jwksUri);
    const jwks = response.data;

    const publicKey = jwks.keys[0].x5c[0];  // 提取证书链中的公钥

    const decoded = jwt.verify(token, publicKey, { algorithms: ['RS256'] });
    return decoded;
}

// 在路由中使用
app.post('/api/protected', (req, res) => {
    const token = req.headers.authorization?.split(' ')[1];
    const jwksUri = req.headers['x-jwks-uri'];  // 用户可控的 JWKS URI

    verifyToken(token, jwksUri).then(decoded => {
        res.json({ user: decoded });
    });
});
```

### 攻击场景一：JWKS URI 指向恶意服务器

**正常流程：**
```
1. JWT 中包含 jku: "https://trusted.com/.well-known/jwks.json"
2. 应用从该 URI 获取 JWKS
3. 应用使用 JWKS 中的公钥验证签名
```

**攻击流程：**
```
1. 攻击者创建恶意的 JWKS URI: "https://attacker.com/jwks.json"
2. 攻击者生成 JWT：
   {
     "jku": "https://attacker.com/jwks.json",
     "alg": "RS256"
   }
3. 攻击者用自己的私钥签名该 JWT
4. 应用从 attacker.com 获取 JWKS（包含攻击者的公钥）
5. 应用验证 JWT，成功（因为使用了攻击者的公钥）
6. 攻击者成功伪造身份
```

### 攻击场景二：HTTPS 降级和中间人攻击

**应用接受 HTTP JWKS URI：**
```java
String jwksUri = "http://auth.example.com/.well-known/jwks.json";  // HTTP，不是 HTTPS
NimbusJwtDecoder.withJwkSetUri(jwksUri).build();
```

**中间人攻击：**
```
1. 攻击者在网络上截获 HTTP 请求
2. 替换 JWKS 响应，返回包含攻击者公钥的 JWKS
3. 应用接受该 JWKS，使用攻击者的公钥验证伪造的 JWT
```

### 攻击场景三：JWKS URI 重定向攻击

**服务器不验证重定向目标：**
```python
def fetch_jwks(jwks_uri):
    # 危险：自动跟随重定向，未验证目标 URL
    response = requests.get(jwks_uri, allow_redirects=True)
    return response.json()

# 攻击
# 应用配置：jwks_uri = "https://trusted.com/jwks"
# 但 trusted.com 被配置为重定向到 attacker.com/fake-jwks
# 应用跟随重定向，获取来自 attacker.com 的恶意 JWKS
```

### 快速定位核心操作（L1: 关键词扫描）

**JWKS 相关库函数：**
```
Java:
  NimbusJwtDecoder.withJwkSetUri()
  JwkSetUri
  getJwkSet()

Python:
  requests.get(jwks_uri)
  jwt.algorithms.RSAAlgorithm.from_jwks()
  jwt.get_unverified_header()

JavaScript:
  axios.get(jwksUri)
  fetch(jwksUri)
  jose.importSPKI()
  jsonwebtoken.verify()

Go:
  net/http.Get()
  crypto/rsa
  JWT 库的 GetKeys()
```

**危险模式：**
```
// 从用户输入读取 JWKS URI
String jwksUri = request.getParameter("jwks_uri");
decoder = NimbusJwtDecoder.withJwkSetUri(jwksUri).build();

// 接受 HTTP URL
if (!jwksUri.startsWith("https://")) {
    // 但没有拒绝 HTTP
}

// 自动跟随重定向
requests.get(jwksUri, allow_redirects=True)
```

**JWKS URI 来源：**
- JWT 的 `jku` (JWK Set URL) 参数
- 应用配置文件
- 环境变量
- 运行时用户输入
- OpenID Connect Discovery 端点返回的 `jwks_uri`

### 快速定位保护机制（L2: 跳读）

**正确的防护方式：**

**Java - 使用配置中的 JWKS URI：**
```java
@Configuration
public class SecurityConfig {
    @Bean
    public JwtDecoder jwtDecoder(
        @Value("${jwt.issuer.jwks-uri}") String jwksUri) {
        // 从配置文件读取，不接受用户输入
        return NimbusJwtDecoder.withJwkSetUri(jwksUri).build();
    }
}

// 配置文件中严格定义 JWKS URI
// application.properties:
// jwt.issuer.jwks-uri=https://auth.example.com/.well-known/jwks.json
```

**Python - 验证 JWKS URI：**
```python
def verify_jwks_uri(jwks_uri):
    # 检查 URL 是否使用 HTTPS
    if not jwks_uri.startswith("https://"):
        raise ValueError("JWKS URI must use HTTPS")

    # 验证 URL 是否在白名单内
    ALLOWED_JWKS_URIS = [
        "https://auth.example.com/.well-known/jwks.json",
        "https://accounts.google.com/o/oauth2/certs"
    ]
    if jwks_uri not in ALLOWED_JWKS_URIS:
        raise ValueError(f"JWKS URI not in whitelist: {jwks_uri}")

    # 验证证书链
    response = requests.get(jwks_uri, verify=True)  # verify SSL 证书
    return response.json()
```

**Node.js - 验证重定向：**
```javascript
async function fetch_jwks_safe(jwksUri) {
    // 禁止重定向
    const response = await axios.get(jwksUri, {
        maxRedirects: 0,  // 禁止跟随重定向
        validateStatus: () => true  // 手动处理状态码
    });

    if (response.status === 301 || response.status === 302) {
        throw new Error("JWKS URI returned redirect");
    }

    return response.data;
}
```

**Go - 验证 JWKS URI 和证书：**
```go
func verifyJWKSURI(jwksUri string) ([]interface{}, error) {
    // 验证 HTTPS
    if !strings.HasPrefix(jwksUri, "https://") {
        return nil, errors.New("JWKS URI must use HTTPS")
    }

    // 验证主机名是否在白名单
    u, _ := url.Parse(jwksUri)
    allowed := []string{"auth.example.com", "accounts.google.com"}
    if !containsHost(allowed, u.Host) {
        return nil, errors.New("Host not in whitelist")
    }

    // 获取 JWKS
    resp, err := http.Get(jwksUri)
    if err != nil {
        return nil, err
    }
    // ... 处理响应
}
```

**审计技巧（L3: 逐行读）：**
- 检查 JWKS URI 的来源：是配置、常量还是用户输入
- 验证是否检查了 HTTPS
- 查找是否有 URL 白名单验证
- 确认是否禁用了 HTTP 重定向
- 检查是否验证了 SSL 证书链

**跨模块保护（L4: 跨模块追踪）：**
- OpenID Connect 配置：`/.well-known/openid-configuration` 中的 `jwks_uri` 是否被信任
- 缓存机制：JWKS 缓存是否包含过期时间
- 密钥轮换：是否检测到新的 JWKS 更新
- WAF/代理：是否限制了可以访问的外部端点

## Classify

### 确认为漏洞

- JWKS URI 来自不可信来源（用户输入、JWT header 的 `jku` 参数、不安全的重定向）
- 未检查 JWKS URI 是否为 HTTPS
- 接受 HTTP 协议的 JWKS URI
- 自动跟随重定向到不同的服务器
- 未验证 SSL 证书链或允许自签证书
- 可以通过 PoC 验证：创建指向恶意 JWKS 的 JWT，成功被应用接受

### 误报场景

- JWKS URI 来自应用配置或环境变量，已由管理员审核
- JWKS URI 使用 HTTPS 且有严格的域名白名单
- 应用禁用了 HTTP 重定向
- JWKS 数据存储在内存中（不需要从外部获取）
- 使用的是 OpenID Connect 标准流程，已验证 issuer 和证书链

### 代码异味

- 应用同时支持来自不同来源的多个 JWKS URIs
- JWKS URI 验证逻辑分散在不同模块
- 缓存 JWKS 数据但没有过期时间
- 没有日志记录 JWKS 获取失败的情况

## Low risk

### 降级为低风险的情况

- **硬编码 JWKS URI**：JWKS URI 在源代码或配置中硬编码，使用可信的服务提供商
- **HTTPS 强制**：所有 JWKS URI 都必须使用 HTTPS，且验证了证书
- **白名单验证**：JWKS URI 严格限制在预定义的白名单内
- **禁止重定向**：应用显式禁用了 HTTP 重定向
- **Issuer 验证**：应用验证了 JWT 的 `iss` (issuer) 声明，并确认它与 JWKS URI 的来源一致
- **超时限制**：JWKS 获取有严格的超时时间，防止 SSRF 到内网或慢速服务

### 需要额外评估的因素

- 攻击者是否可以通过 SSRF 访问内网的 JWKS 端点
- JWKS 缓存是否可能导致密钥过期问题
- 是否存在 DNS rebinding 的可能性
- 被盗的密钥是否可以被用于签名其他应用的 JWT
- 是否有 Key ID (kid) 冲突的可能性
