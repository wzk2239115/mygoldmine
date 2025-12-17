# PHP｜前端JavaScript加密常见错误

## Details

### 漏洞成因
在现代Web应用中，前端JavaScript加密常被用于客户端数据保护、表单数据预加密、或作为额外安全层。然而，由于JavaScript运行在客户端，面临代码可见性、密钥管理、随机数质量等多重挑战。PHP后端如果过度依赖或不当验证前端加密结果，可能引入严重的安全漏洞。常见错误包括：硬编码加密密钥、使用不安全的随机数生成器、实现不完整的加密模式、缺少完整性验证、以及"加密即安全"的误解。

### 代码示例

**易受攻击的代码 - 硬编码密钥的前端加密：**
```php
// PHP后端过度依赖前端加密
// login.php
?>
<!DOCTYPE html>
<html>
<head>
<script src="https://cdnjs.cloudflare.com/ajax/libs/crypto-js/4.1.1/crypto-js.min.js"></script>
<script>
// 严重错误：硬编码加密密钥
const ENCRYPTION_KEY = 'hardcoded_key_12345'; // 对攻击者完全可见

function encryptPassword(password) {
    // 使用可见的密钥进行加密
    return CryptoJS.AES.encrypt(password, ENCRYPTION_KEY).toString();
}

document.getElementById('loginForm').addEventListener('submit', function(e) {
    e.preventDefault();
    const password = document.getElementById('password').value;
    const encryptedPassword = encryptPassword(password);
    
    // 发送"加密"的密码
    fetch('/api/login', {
        method: 'POST',
        body: JSON.stringify({
            username: document.getElementById('username').value,
            encrypted_password: encryptedPassword
        })
    });
});
</script>
</head>
<body>
<form id="loginForm">
    <input type="text" id="username" placeholder="Username">
    <input type="password" id="password" placeholder="Password">
    <button type="submit">Login</button>
</form>
</body>
</html>
<?php
// 后端PHP验证
data = json_decode(file_get_contents('php://input'), true);
$encrypted_password = $data['encrypted_password'];

// 危险：使用相同的硬编码密钥解密
$key = 'hardcoded_key_12345';
$decrypted = openssl_decrypt($encrypted_password, 'AES-256-CBC', $key, 0, $iv);

// 验证解密后的密码
if (password_verify($decrypted, $stored_hash)) {
    // 登录成功 - 但整个加密毫无意义
}
```

**易受攻击的代码 - ECB模式和不完整实现：**
```php
// 前端提供的加密数据
$client_encrypted = $_POST['encrypted_data'];
$client_iv = $_POST['iv']; // 客户端提供的IV

// 使用ECB模式（不安全）
$decrypted = openssl_decrypt($client_encrypted, 'AES-256-ECB', $server_key, 0);

// 或者使用CBC但缺少认证
$decrypted = openssl_decrypt($client_encrypted, 'AES-256-CBC', $server_key, 0, $client_iv);

// 直接信任解密结果，缺少完整性验证
processClientData($decrypted);
```

**易受攻击的代码 - 弱随机数生成：**
```javascript
// 前端JavaScript弱随机数生成
function generateKey() {
    // 使用Math.random() - 不适合加密用途
    var key = '';
    for (var i = 0; i < 32; i++) {
        key += Math.random().toString(36).substr(2, 1);
    }
    return key;
}

function generateIV() {
    // 同样使用弱随机数
    var iv = '';
    for (var i = 0; i < 16; i++) {
        iv += Math.floor(Math.random() * 16).toString(16);
    }
    return iv;
}
```

**安全示例 - 正确的客户端-服务器交互：**
```php
// 安全的方法：TLS + 服务器端验证
?>
<!DOCTYPE html>
<html>
<head>
<script>
// 正确的做法：仅使用HTTPS传输，不在客户端加密敏感数据
document.getElementById('loginForm').addEventListener('submit', function(e) {
    e.preventDefault();
    
    // 仅收集表单数据，不执行客户端加密
    const formData = new FormData(this);
    
    // 通过HTTPS发送到服务器
    fetch('/api/login', {
        method: 'POST',
        body: formData,
        headers: {
            'X-CSRF-Token': document.querySelector('meta[name="csrf-token"]').content
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            window.location.href = '/dashboard';
        } else {
            alert('Login failed');
        }
    });
});
</script>
</head>
<body>
<form id="loginForm">
    <input type="text" name="username" placeholder="Username" required>
    <input type="password" name="password" placeholder="Password" required>
    <button type="submit">Login</button>
</form>
</body>
</html>
<?php
// 后端PHP - 标准安全处理
class SecureLoginHandler {
    
    public function handleLogin($request) {
        // 1. CSRF验证
        if (!$this->validateCSRFToken($request['csrf_token'])) {
            throw new Exception('Invalid CSRF token');
        }
        
        // 2. 输入验证
        $username = $this->validateInput($request['username']);
        $password = $request['password']; // 密码不需要特殊验证
        
        // 3. 速率限制检查
        if (!$this->checkRateLimit($request['ip_address'])) {
            throw new Exception('Too many login attempts');
        }
        
        // 4. 用户认证
        $user = $this->authenticateUser($username, $password);
        
        if ($user) {
            // 5. 创建安全Session
            $this->createSecureSession($user);
            return ['success' => true, 'redirect' => '/dashboard'];
        } else {
            // 6. 记录失败尝试
            $this->recordFailedAttempt($username, $request['ip_address']);
            return ['success' => false, 'message' => 'Invalid credentials'];
        }
    }
    
    private function authenticateUser($username, $password) {
        // 使用安全的密码验证
        $user = User::where('username', $username)->first();
        
        if ($user && password_verify($password, $user->password_hash)) {
            if (password_needs_rehash($user->password_hash, PASSWORD_DEFAULT)) {
                $user->password_hash = password_hash($password, PASSWORD_DEFAULT);
                $user->save();
            }
            return $user;
        }
        
        return null;
    }
}
```

**安全示例 - 必要的客户端加密（特定场景）：**
```php
// 仅在特定需求下的客户端加密 - 端到端加密场景
?>
<!DOCTYPE html>
<html>
<head>
<script src="https://cdnjs.cloudflare.com/ajax/libs/crypto-js/4.1.1/crypto-js.min.js"></script>
<script>
// 端到端加密场景：服务器不应能解密数据
class EndToEndEncryption {
    constructor() {
        // 生成临时密钥对（每次会话）
        this.generateKeyPair();
    }
    
    async generateKeyPair() {
        // 使用Web Crypto API生成安全的密钥
        this.keyPair = await window.crypto.subtle.generateKey(
            {
                name: "RSA-OAEP",
                modulusLength: 2048,
                publicExponent: new Uint8Array([1, 0, 1]),
                hash: "SHA-256",
            },
            true,
            ["encrypt", "decrypt"]
        );
        
        // 导出公钥发送给服务器
        this.publicKey = await window.crypto.subtle.exportKey("spki", this.keyPair.publicKey);
        this.sendPublicKeyToServer(this.publicKey);
    }
    
    async encryptSensitiveData(data) {
        // 生成随机的对称密钥
        const symmetricKey = await window.crypto.subtle.generateKey(
            {
                name: "AES-GCM",
                length: 256,
            },
            true,
            ["encrypt", "decrypt"]
        );
        
        // 生成安全的随机IV
        const iv = window.crypto.getRandomValues(new Uint8Array(12));
        
        // 使用AES-GCM加密数据
        const encryptedData = await window.crypto.subtle.encrypt(
            {
                name: "AES-GCM",
                iv: iv,
            },
            symmetricKey,
            new TextEncoder().encode(data)
        );
        
        // 返回加密数据和参数
        return {
            encrypted: Array.from(new Uint8Array(encryptedData)),
            iv: Array.from(iv),
            algorithm: "AES-GCM"
        };
    }
}

// 使用示例
const e2e = new EndToEndEncryption();

async function submitSensitiveData() {
    const sensitiveData = document.getElementById('sensitive').value;
    const encrypted = await e2e.encryptSensitiveData(sensitiveData);
    
    // 发送加密数据（服务器无法解密）
    fetch('/api/store-encrypted', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRF-Token': document.querySelector('meta[name="csrf-token"]').content
        },
        body: JSON.stringify({
            encrypted_data: encrypted.encrypted,
            iv: encrypted.iv,
            algorithm: encrypted.algorithm
        })
    });
}
</script>
</head>
<body>
<!-- 仅用于端到端加密场景 -->
<input type="text" id="sensitive" placeholder="Sensitive data">
<button onclick="submitSensitiveData()">Submit Encrypted</button>
</body>
</html>
<?php
// 后端仅存储加密数据，无法解密
class EncryptedDataStorage {
    
    public function storeEncryptedData($user_id, $encrypted_data, $iv, $algorithm) {
        // 验证数据结构
        if (!$this->validateEncryptedData($encrypted_data, $iv, $algorithm)) {
            throw new Exception('Invalid encrypted data format');
        }
        
        // 存储加密数据（服务器无法解密）
        EncryptedData::create([
            'user_id' => $user_id,
            'encrypted_data' => json_encode($encrypted_data),
            'iv' => json_encode($iv),
            'algorithm' => $algorithm,
            'created_at' => now()
        ]);
        
        return ['success' => true, 'message' => 'Encrypted data stored'];
    }
    
    private function validateEncryptedData($encrypted_data, $iv, $algorithm) {
        // 仅验证格式，不解密内容
        return is_array($encrypted_data) && 
               is_array($iv) && 
               count($iv) === 12 && // GCM IV长度
               $algorithm === 'AES-GCM';
    }
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- 前端加密：`CryptoJS`, `encrypt`, `AES`, `crypto.subtle`
- 密码传输：`encrypted_password`, `client_encrypt`
- 密钥管理：`ENCRYPTION_KEY`, `generateKey`

**定位步骤：**
1. 搜索项目中所有前端JavaScript加密相关代码
2. 检查是否存在硬编码的加密密钥
3. 验证加密算法和模式的选择
4. 检查是否存在认证和完整性验证

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **HTTPS传输：** 强制使用TLS加密传输
- **现代Web Crypto：** `window.crypto.subtle` API使用
- **认证加密：** AES-GCM等AEAD算法
- **安全随机数：** `window.crypto.getRandomValues()`

**定位技巧：**
- 检查是否使用Web Crypto API而非第三方库
- 验证是否使用认证加密模式（GCM/CCM）
- 确认是否使用安全的随机数生成器
- 检查是否存在密钥管理策略

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| HTTPS+Web Crypto+AEAD | **L0（快速跳过）** | 现代安全实现 |
| HTTPS但加密实现有缺陷 | **L2（跳读）** | 需验证加密细节 |
| 依赖客户端加密无HTTPS | **L3（逐行读）** | 错误的安全模型 |
| 硬编码密钥+弱算法 | **L4（跨模块追踪）** | 严重安全缺陷 |

## Classify

### 研判标准

#### 确认漏洞
需满足：
1. 前端代码中存在硬编码加密密钥
2. 使用ECB模式或不安全的加密算法
3. 使用Math.random()等弱随机数生成器
4. 缺少认证机制（无HMAC或AEAD）
5. 过度依赖客户端加密而忽略传输层安全

#### 误报
以下情景可判定为误报：
1. 仅使用HTTPS传输，不在客户端执行敏感数据加密
2. 使用Web Crypto API配合AES-GCM等AEAD算法
3. 端到端加密场景且服务器不需要解密能力
4. 使用安全的随机数生成器（window.crypto.getRandomValues）

#### 代码异味
需记录的风险：
1. 自定义加密实现而非使用标准API
2. 加密参数硬编码或可预测
3. 缺少完整性验证机制
4. 将客户端加密作为主要安全控制

## Low risk

### 低风险评级场景

#### 1. 纯HTTPS传输
- **场景：** 仅依赖HTTPS传输层加密，不在客户端加密敏感数据
- **风险评估：** 正确的安全模型，风险最低

#### 2. 端到端加密
- **场景：** 服务器不需要解密能力，仅作为数据通道
- **风险评估：** 合理的加密需求，需正确实现

#### 3. 现代Web Crypto API
- **场景：** 使用原生Web Crypto API实现
- **风险评估：** 浏览器提供的安全API相对可靠

### JavaScript加密安全检查表

| 检查项 | 安全要求 | 风险等级 | 检测方法 |
|--------|----------|----------|----------|
| 传输协议 | HTTPS强制 | 高 | 协议检查 |
| 加密算法 | AES-GCM/ChaCha20-Poly1305 | 高 | 算法识别 |
| 随机数生成 | window.crypto.getRandomValues | 高 | RNG检查 |
| 密钥管理 | 非硬编码 | 高 | 密钥检查 |
| 认证机制 | AEAD或HMAC | 高 | 认证检查 |

### 常见JavaScript加密库对比

| 库名称 | 安全性 | 适用场景 | 检测要点 |
|--------|--------|----------|----------|
| Web Crypto API | ⭐⭐⭐⭐⭐ | 现代浏览器 | 原生API使用 |
| CryptoJS | ⭐⭐⭐ | 兼容性需求 | 算法和模式选择 |
| TweetNaCl.js | ⭐⭐⭐⭐⭐ | 现代加密 | NaCl/libsodium实现 |
| SJCL | ⭐⭐⭐⭐ | 学术研究 | 配置安全性 |

### 不安全模式识别

| 模式 | 风险描述 | 检测方法 | 修复建议 |
|------|----------|----------|----------|
| ECB模式 | 缺少随机性 | 模式识别 | 改为GCM/CCM |
| 固定IV | 重放攻击风险 | IV生成检查 | 随机IV生成 |
| Math.random() | 可预测随机数 | RNG识别 | crypto.getRandomValues |
| 硬编码密钥 | 完全暴露 | 密钥检查 | 安全密钥管理 |

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| HTTPS强制使用 | 传输层安全 | 高 |
| Web Crypto API | 现代安全API | 高 |
| AEAD算法使用 | 认证加密 | 高 |
| 安全随机数 | 不可预测性 | 高 |