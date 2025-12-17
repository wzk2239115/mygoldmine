# PHP JWT 硬编码密钥

## 漏洞成因
使用 firebase/php-jwt、lcobucci/jwt 等库时，签名密钥直接硬编码在代码或配置文件中，导致密钥泄露风险。攻击者获取源码后可伪造任意 JWT token。

## Details

### 代码示例

**firebase/php-jwt 库：**
```php
use Firebase\JWT\JWT;
use Firebase\JWT\Key;

// 危险：硬编码密钥
$key = "my_secret_key_123";
$payload = ['user_id' => 1, 'exp' => time() + 3600];
$jwt = JWT::encode($payload, $key, 'HS256');

// 验证时同样硬编码
$decoded = JWT::decode($jwt, new Key($key, 'HS256'));
```

**lcobucci/jwt 库：**
```php
use Lcobucci\JWT\Configuration;
use Lcobucci\JWT\Signer\Hmac\Sha256;
use Lcobucci\JWT\Signer\Key\InMemory;

// 危险：密钥字符串硬编码
$config = Configuration::forSymmetricSigner(
    new Sha256(),
    InMemory::plainText('hardcoded_secret')
);
$token = $config->builder()->getToken($config->signer(), $config->signingKey());
```

### 快速定位核心操作技巧 **[L1-L2]**

**关键词扫描 (L1)：**
- `JWT::encode()` / `JWT::decode()` - firebase/php-jwt
- `Configuration::forSymmetricSigner()` - lcobucci/jwt
- `InMemory::plainText()` / `InMemory::base64Encoded()`
- 算法关键词：`'HS256'`、`'HS384'`、`'HS512'`、`new Sha256()`

**跳读定位 (L2)：**
- 搜索 `use Firebase\JWT\JWT` 或 `use Lcobucci\JWT` 定位引入点
- 追踪 `encode()`/`builder()` 的第二个参数（密钥参数）
- 检查密钥来源：字面量字符串 = 硬编码，变量 = 需追踪
- 配置文件特征：`.env`、`config.php`、`settings.php` 中的明文密钥

### 快速定位保护机制技巧 **[L2-L3]**

**跳读检查 (L2)：**
- 查找环境变量读取：`getenv('JWT_SECRET')`、`$_ENV['JWT_SECRET']`、`env('JWT_SECRET')`
- 查找配置类调用：`Config::get()`、`Settings::read()`
- 密钥管理服务：AWS Secrets Manager、HashiCorp Vault 的 SDK 调用

**逐行验证 (L3)：**
- 确认环境变量是否在 `.env.example` 中有占位符但无真实值
- 验证配置加载链：`config.php` → 环境变量 → 运行时
- 检查密钥生成函数：`random_bytes()`、`openssl_random_pseudo_bytes()`
- 排查版本控制：`.gitignore` 是否排除 `.env` 文件

## Classify

### 漏洞判定标准
- **确认漏洞**：密钥为字面量字符串（无论强度）或在版本控制中可见的配置文件内
- **误报情形**：密钥通过安全机制动态加载（KMS、密钥管理服务、加密配置）且原始密钥未暴露
- **代码异味**：密钥从本地文件读取但文件权限受限（如仅 root 可读），存在风险但未直接暴露

### 研判要点
1. **源码可见性**：密钥是否存在于代码仓库、容器镜像、文档中
2. **动态性**：密钥是否支持运行时更换而无需重新部署
3. **访问控制**：密钥存储位置的访问权限限制程度
4. **范围影响**：同一密钥是否用于多个环境（开发/测试/生产共享）

## Low risk

### 低风险场景
1. **测试环境隔离**：仅用于单元测试的硬编码密钥，且测试环境完全隔离无真实数据
2. **示例代码**：文档或教程中的演示代码，明确标注"仅供演示"且未部署
3. **临时 token**：短期有效（<5分钟）且仅用于非敏感操作的场景，如邮件验证链接
4. **已轮换密钥**：历史代码中的旧密钥，已确认在生产环境完成轮换且旧 token 已失效
5. **受限内网**：应用运行在完全隔离的内网环境，攻击者无法访问源码或网络流量

### 风险降级条件
- 配合其他强认证机制使用（如 IP 白名单 + 硬编码密钥）
- Token payload 不包含敏感信息，仅作为会话标识
- 存在额外的服务端状态验证（如 Redis 会话校验）