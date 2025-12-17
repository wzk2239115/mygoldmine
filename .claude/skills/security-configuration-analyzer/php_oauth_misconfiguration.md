# PHP｜OAuth/OpenID Connect 配置错误

## Details

### 漏洞成因
OAuth 2.0和OpenID Connect是现代Web应用中常用的认证授权协议。PHP应用中，当OAuth配置不当或验证逻辑存在缺陷时，可能导致认证绕过、授权劫持、用户信息泄露等安全问题。常见配置错误包括：重定向URI验证不严、state参数缺失、scope范围过大、令牌验证不完整、issuer验证缺失等。这些配置缺陷可能被攻击者利用来获取未授权的访问权限或用户信息。

### 代码示例

**易受攻击的代码 - 重定向URI验证不严：**
```php
// 危险的OAuth回调处理
$redirect_uri = $_GET['redirect_uri'] ?? $_POST['redirect_uri'];

// 仅检查是否以配置的URI开头（不完整验证）
if (strpos($redirect_uri, 'https://example.com/callback') === 0) {
    // 通过验证 - 但存在绕过风险
    header("Location: $redirect_uri?code=$auth_code");
    exit;
}

// 攻击者可以构造：https://example.com/callback.evil.com/
```

**易受攻击的代码 - 缺少state参数验证：**
```php
// OAuth授权请求 - 缺少state参数
$auth_url = "https://oauth.provider.com/authorize?";
$auth_url .= "client_id=" . urlencode($client_id);
$auth_url .= "&response_type=code";
$auth_url .= "&redirect_uri=" . urlencode($redirect_uri);
// 缺少 &state= 参数 - 易受CSRF攻击

header("Location: $auth_url");
```

**易受攻击的代码 - 令牌验证不完整：**
```php
// 危险的令牌验证 - 仅检查签名存在
$token = $_GET['id_token'];
$parts = explode('.', $token);

if (count($parts) === 3) {
    // 仅验证JWT格式，未验证签名和内容
    $payload = json_decode(base64_decode($parts[1]));
    $user_email = $payload->email;
    // 直接信任未验证的令牌内容
}
```

**安全示例 - 完整的OAuth流程：**
```php
class SecureOAuthHandler {
    private $client_id;
    private $client_secret;
    private $redirect_uri;
    private $authorization_endpoint;
    private $token_endpoint;
    
    public function initiateAuth() {
        // 生成并存储state参数防止CSRF
        $state = bin2hex(random_bytes(16));
        $_SESSION['oauth_state'] = $state;
        
        // 生成PKCE code_verifier防止授权码拦截
        $code_verifier = bin2hex(random_bytes(32));
        $_SESSION['oauth_code_verifier'] = $code_verifier;
        $code_challenge = rtrim(strtr(base64_encode(hash('sha256', $code_verifier, true)), '+/', '-_'), '=');
        
        $params = [
            'client_id' => $this->client_id,
            'response_type' => 'code',
            'redirect_uri' => $this->redirect_uri,
            'state' => $state,
            'scope' => 'openid email profile', // 最小权限原则
            'code_challenge' => $code_challenge,
            'code_challenge_method' => 'S256',
            'response_mode' => 'query'
        ];
        
        $auth_url = $this->authorization_endpoint . '?' . http_build_query($params);
        header("Location: $auth_url");
        exit;
    }
    
    public function handleCallback() {
        // 验证state参数防止CSRF
        if (!isset($_GET['state']) || $_GET['state'] !== $_SESSION['oauth_state']) {
            throw new Exception('Invalid state parameter - possible CSRF attack');
        }
        
        // 验证授权码存在
        if (!isset($_GET['code'])) {
            throw new Exception('Authorization code missing');
        }
        
        // 交换授权码获取令牌
        $token_response = $this->exchangeCodeForToken($_GET['code']);
        
        // 完整验证ID令牌
        $id_token = $this->validateIdToken($token_response['id_token']);
        
        // 清理OAuth流程数据
        unset($_SESSION['oauth_state']);
        unset($_SESSION['oauth_code_verifier']);
        
        return $id_token;
    }
    
    private function validateIdToken($id_token) {
        // 分割JWT令牌
        $parts = explode('.', $id_token);
        if (count($parts) !== 3) {
            throw new Exception('Invalid ID token format');
        }
        
        // 验证签名（简化示例，实际应使用适当的JWT库）
        $header = json_decode(base64_decode($parts[0]));
        $payload = json_decode(base64_decode($parts[1]));
        
        // 验证issuer
        if ($payload->iss !== $this->getExpectedIssuer()) {
            throw new Exception('Invalid token issuer');
        }
        
        // 验证audience
        if ($payload->aud !== $this->client_id) {
            throw new Exception('Invalid token audience');
        }
        
        // 验证过期时间
        if ($payload->exp < time()) {
            throw new Exception('Token has expired');
        }
        
        // 验证颁发时间
        if ($payload->iat > time() + 300) { // 允许5分钟时钟偏差
            throw new Exception('Token issued in the future');
        }
        
        // 验证nonce（如果存在）
        if (isset($payload->nonce) && $payload->nonce !== $_SESSION['oauth_nonce']) {
            throw new Exception('Invalid nonce');
        }
        
        return $payload;
    }
}
```

**安全示例 - OpenID Connect配置：**
```php
// OpenID Connect发现配置验证
class OIDCValidator {
    private $issuer;
    private $discovery_url;
    
    public function __construct($issuer) {
        $this->issuer = rtrim($issuer, '/');
        $this->discovery_url = $this->issuer . '/.well-known/openid-configuration';
    }
    
    public function validateDiscoveryDocument() {
        $discovery = $this->fetchDiscoveryDocument();
        
        // 验证issuer一致性
        if ($discovery['issuer'] !== $this->issuer) {
            throw new Exception('Issuer mismatch in discovery document');
        }
        
        // 验证必需端点
        $required_endpoints = ['authorization_endpoint', 'token_endpoint', 'jwks_uri'];
        foreach ($required_endpoints as $endpoint) {
            if (!isset($discovery[$endpoint])) {
                throw new Exception("Missing required endpoint: $endpoint");
            }
        }
        
        return $discovery;
    }
    
    public function validateJwks() {
        $discovery = $this->validateDiscoveryDocument();
        $jwks_uri = $discovery['jwks_uri'];
        
        // 验证JWKS URI属于同一issuer域
        if (!str_starts_with($jwks_uri, $this->issuer)) {
            throw new Exception('JWKS URI not in issuer domain');
        }
        
        $jwks = $this->fetchJwks($jwks_uri);
        
        // 验证密钥算法和用途
        foreach ($jwks['keys'] as $key) {
            if (!isset($key['use']) || $key['use'] !== 'sig') {
                continue; // 只关注签名密钥
            }
            
            // 验证算法安全性
            $secure_algorithms = ['RS256', 'RS384', 'RS512', 'ES256', 'ES384', 'ES512'];
            if (!isset($key['alg']) || !in_array($key['alg'], $secure_algorithms)) {
                throw new Exception('Insecure or missing key algorithm: ' . ($key['alg'] ?? 'none'));
            }
        }
        
        return $jwks;
    }
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- OAuth流程：`authorization_endpoint`, `token_endpoint`, `redirect_uri`
- 验证逻辑：`state`, `nonce`, `code_verifier`, `id_token`
- 令牌处理：`access_token`, `id_token`, `validate`, `verify`

**定位步骤：**
1. 搜索项目中所有OAuth相关的处理逻辑
2. 检查是否存在state参数验证
3. 验证重定向URI的处理逻辑
4. 检查令牌验证的完整性

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **State验证：** CSRF防护机制
- **PKCE支持：** 授权码拦截防护
- **Scope限制：** 最小权限原则
- **重定向URI验证：** 严格的URI匹配
- **Nonce验证：** 重放攻击防护

**定位技巧：**
- 检查是否使用state参数进行CSRF防护
- 确认是否实现PKCE（Proof Key for Code Exchange）
- 验证重定向URI的严格匹配逻辑
- 检查ID令牌的完整验证流程

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 完整OAuth流程+PKCE | **L0（快速跳过）** | 配置安全 |
| 有state但缺少PKCE | **L2（跳读）** | 需验证其他防护 |
| 重定向URI验证不严 | **L3（逐行读）** | 高风险配置 |
| 完全缺少state验证 | **L4（跨模块追踪）** | 严重缺失 |

## Classify

### 研判标准

#### 确认漏洞
需满足：
1. 缺少state参数验证（CSRF防护缺失）
2. 重定向URI验证不严格（允许部分匹配或通配符）
3. 未实现PKCE防护（授权码拦截风险）
4. 令牌验证不完整（未验证签名、issuer、audience等）

#### 误报
以下情景可判定为误报：
1. 完整的OAuth流程包含state和PKCE
2. 严格的重定向URI完整匹配验证
3. 完整的ID令牌验证（签名、issuer、audience、过期时间）
4. 使用成熟的OAuth库并正确配置

#### 代码异味
需记录的风险：
1. 仅在部分流程中实现state验证
2. 重定向URI验证逻辑不一致
3. 动态生成的OAuth参数存在注入风险
4. Scope范围过大或未限制

## Low risk

### 低风险评级场景

#### 1. 使用成熟OAuth库
- **场景：** 使用知名OAuth库（如PHP League OAuth2）并正确配置
- **风险评估：** 库通常实现了标准的安全防护

#### 2. 内部OAuth实现
- **场景：** 在受信任的内部环境中使用OAuth
- **风险评估：** 风险相对较低，但仍建议遵循最佳实践

#### 3. 分阶段安全增强
- **场景：** 逐步添加PKCE等现代安全特性
- **风险评估：** 合理的实施策略，需跟踪进度

### OAuth安全检查表

| 检查项 | 安全要求 | 风险等级 | 检测方法 |
|--------|----------|----------|----------|
| State参数 | 必须验证 | 高 | CSRF防护检查 |
| 重定向URI | 完整匹配 | 高 | URI验证逻辑检查 |
| PKCE支持 | 推荐实现 | 中 | 授权码拦截防护 |
| Scope范围 | 最小权限 | 中 | 权限范围审查 |
| ID令牌验证 | 完整验证 | 高 | 令牌验证流程 |
| Issuer验证 | 必须匹配 | 高 | Issuer一致性检查 |

### 常见OAuth攻击向量

| 攻击类型 | 利用条件 | 检测方法 | 防护建议 |
|----------|----------|----------|----------|
| CSRF攻击 | 缺少state参数 | state验证检查 | 强制state验证 |
| 授权码拦截 | 缺少PKCE | PKCE实现检查 | 实现PKCE流程 |
| 重定向劫持 | URI验证不严 | URI验证逻辑 | 完整URI匹配 |
| 令牌伪造 | 验证不完整 | 令牌验证流程 | 完整令牌验证 |

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 完整OAuth流程 | 标准安全实现 | 高 |
| 成熟库使用 | 专业安全实现 | 高 |
| PKCE支持 | 现代安全标准 | 中 |
| 严格验证逻辑 | 完整防护链 | 高 |