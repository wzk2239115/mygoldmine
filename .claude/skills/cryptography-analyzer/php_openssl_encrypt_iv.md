# 密码学实现缺陷审计指南

## 基本信息
- **难度等级：** ★★★☆☆ (中级)
- **审计时间：** 20-30分钟

## 🚀 30秒快速清单
- [ ] 使用的加密算法是否符合现代标准？
- [ ] IV/Nonce生成是否使用强随机源？
- [ ] 密钥派生函数参数是否足够强？
- [ ] 密钥管理和存储是否安全？

## Details
密码学实现的安全性取决于算法选择、参数配置和密钥管理的多个方面。

### 常见问题
1. **弱算法使用** - DES、3DES、RC4等
2. **不安全的模式** - ECB模式
3. **IV不安全** - 硬编码、可预测或重复使用
4. **弱密钥派生** - 迭代次数不足、盐值不够强
5. **密钥泄露** - 硬编码、配置文件明文存储

## Classify
- **漏洞**：使用已破裂算法或配置严重缺陷
- **安全**：现代算法+足够强的参数+安全的密钥管理

## Low risk
- ✅ AES-256-GCM或ChaCha20-Poly1305
- ✅ 随机IV/Nonce
- ✅ 足够强的KDF参数
- ✅ 密钥分离存储

## 审计专业技巧

### 1. PHP OpenSSL IV参数检查清单
**关键点：** IV（初始化向量）的安全性直接影响加密强度

```php
// ❌ 不安全：硬编码IV
openssl_encrypt($data, 'AES-256-CBC', $key, OPENSSL_RAW_DATA, '0123456789abcdef');

// ❌ 不安全：IV长度不足
$iv = substr($key, 0, 8);  // 仅8字节，AES需要16字节
openssl_encrypt($data, 'AES-256-CBC', $key, OPENSSL_RAW_DATA, $iv);

// ❌ 不安全：IV重复使用
$iv = hash('sha256', $salt, true);  // 确定性生成，每次相同
for ($i = 0; $i < 100; $i++) {
    openssl_encrypt($data[$i], 'AES-256-CBC', $key, OPENSSL_RAW_DATA, $iv);
}

// ✅ 安全：随机且足够长的IV
$iv = openssl_random_pseudo_bytes(16);  // 或 random_bytes(16)
openssl_encrypt($data, 'AES-256-CBC', $key, OPENSSL_RAW_DATA, $iv);
```

### 2. 真实漏洞 vs 误报区分经验

#### **情形A：静态分析误报 - 字符串注入**
```php
// 伪报警：动态IV生成，工具误识别为硬编码
$iv_source = $_ENV['ENCRYPTION_IV'] ?? openssl_random_pseudo_bytes(16);
$iv = is_string($iv_source) ? hash('sha256', $iv_source, true) : $iv_source;
openssl_encrypt($data, 'AES-256-CBC', $key, OPENSSL_RAW_DATA, $iv);
```
**判断方法：** 追踪$iv_source的完整来源链。若最终来自环境变量+哈希，需评估环境变量的改变频率。
**真实漏洞判定：** 如果$iv_source完全从配置文件读取且从不更新 → **真实漏洞**
**安全判定：** 如果$iv_source由随机数或时间戳派生，每次加密都变化 → **误报**

#### **情形B：密钥派生弱参数**
```php
// ❌ 真实漏洞：迭代次数太低
$key = hash_pbkdf2('sha256', $password, $salt, 1000, 32);

// ✅ 安全：现代标准（>=100,000或argon2）
$key = hash_pbkdf2('sha256', $password, $salt, 100000, 32);
// 或使用 password_hash() 系列函数
```
**判断规则：**
- PBKDF2：迭代次数 < 100,000 → 漏洞
- Argon2：cost参数 < 2 → 漏洞
- 时间判断：派生一个密钥应耗时 ≥ 100ms

#### **情形C：算法模式选择误报**
```php
// ❌ 旧警告但仍安全：CBC模式需要有效的PKCS#7 Padding
openssl_encrypt($data, 'AES-256-CBC', $key, 0);

// ✅ 现代推荐：认证加密模式（AEAD）
openssl_encrypt($data, 'AES-256-GCM', $key, OPENSSL_RAW_DATA, $iv, $tag);
```
**判断逻辑：**
- CBC模式 + 正确Padding + 完整性检验 → 可接受但非最优
- CBC模式 + 无完整性检验 → 需要深入分析
- GCM/ChaCha20-Poly1305 → 符合现代标准

### 3. 审计重点步骤

**第一步：定位所有加密调用**
```bash
grep -rn "openssl_encrypt\|openssl_decrypt\|mcrypt_\|hash_pbkdf2" --include="*.php"
```

**第二步：检查IV来源链**
- 追踪IV变量的完整定义路径
- 确认是否每次调用都产生新IV
- 检验IV长度是否与算法匹配（CBC/CTR需16字节，GCM需12-16字节）

**第三步：评估算法组合**
| 组合 | 评分 | 建议 |
|------|------|------|
| AES-256-GCM + 随机IV | ✅ 安全 | 保持 |
| AES-256-CBC + 随机IV + HMAC | ⚠️ 可接受 | 升级到GCM |
| AES-256-CBC + 固定IV | ❌ 漏洞 | 立即修复 |
| DES/3DES | ❌ 漏洞 | 替换算法 |

**第四步：密钥管理评估**
- [ ] 密钥存储位置（配置文件/环境变量/密钥库）
- [ ] 密钥是否参与版本控制
- [ ] 是否实现密钥轮换机制
- [ ] 是否限制密钥访问权限

### 4. 常见误报场景

1. **场景：环境变量注入疑虑**
   ```php
   $iv = hex2bin(getenv('IV'));  // 看似来自外部
   ```
   检查方式：验证环境变量是否由部署系统安全设置，非用户可控

2. **场景：导入外部加密库**
   ```php
   use Defuse\Crypto\Crypto;
   Crypto::encrypt($plaintext, $key);
   ```
   判断：查看该库的安全审计报告，通常可信库无需再审

3. **场景：遗留代码注释**
   ```php
   // 旧实现：使用mcrypt（已弃用）
   // $encrypted = mcrypt_encrypt(...);

   // 新实现：使用openssl_encrypt
   $encrypted = openssl_encrypt(...);
   ```
   判断：代码实际使用openssl → 安全，注释可忽略

### 5. 实战漏洞检测模式

**模式1：IV硬编码检测**
```php
// 反面教材
$iv = 'default_iv_1234';  // 违规
$encrypted = openssl_encrypt($data, 'AES-256-CBC', $key, 0, $iv);
```

**模式2：IV部分随机检测**
```php
// 警惕信号
$iv = substr(bin2hex(random_bytes(8)), 0, 16);  // 仅8字节随机
```

**模式3：密钥硬编码检测**
```php
define('ENCRYPTION_KEY', 'my-secret-key-123');  // 违规
```

**模式4：完整性保护缺失检测**
```php
// CBC模式但无HMAC验证
$encrypted = openssl_encrypt($data, 'AES-256-CBC', $key, 0, $iv);
// 直接反序列化 - 危险！
$original = unserialize(openssl_decrypt($encrypted, ...));
```

## 修复建议

### 升级方案流程
1. 评估影响范围（有多少数据、多少端点）
2. 实现双算法支持（新加密用新算法，解密支持两种）
3. 数据迁移（批量重加密为新算法）
4. 验证和部署
5. 下线旧算法

### 快速修复模板
```php
class SecureEncryption {
    public static function encrypt($data, $key) {
        $iv = random_bytes(16);
        $encrypted = openssl_encrypt(
            $data,
            'AES-256-GCM',
            $key,
            OPENSSL_RAW_DATA,
            $iv,
            $tag
        );
        return base64_encode($iv . $tag . $encrypted);
    }

    public static function decrypt($data, $key) {
        $data = base64_decode($data);
        $iv = substr($data, 0, 16);
        $tag = substr($data, 16, 16);
        $encrypted = substr($data, 32);

        return openssl_decrypt(
            $encrypted,
            'AES-256-GCM',
            $key,
            OPENSSL_RAW_DATA,
            $iv,
            $tag
        );
    }
}
```
