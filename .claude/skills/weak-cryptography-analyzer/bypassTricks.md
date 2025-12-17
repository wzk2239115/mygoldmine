# 弱加密绕过秘笈

## 随机数可预测

### 线性同余生成器(LCG)
```
PHP mt_rand()默认算法是MT19937

漏洞：
1. PHP < 7.1 seed来自进程ID和时间，空间有限
2. 可暴力破解所有可能的种子（86400个/天）

破解代码：
for ($seed = time() - 86400; $seed < time() + 86400; $seed++) {
    mt_srand($seed);
    if (md5(mt_rand()) == $target_token) {
        echo "Found seed: $seed";
        mt_rand();  // 同步状态
        $next = md5(mt_rand());  // 预测下一个token
        break;
    }
}
```

### Java Random可预测
```java
// java.util.Random 使用LCG，种子为48位
// 可暴力破解

Random rand = new Random();
long seed = System.currentTimeMillis();
// seed空间: ~5000万(毫秒级)

攻击：
for (long i = System.currentTimeMillis() - 100000; i < System.currentTimeMillis(); i++) {
    Random r = new Random(i);
    if (r.nextInt() == target_token) {
        System.out.println("Found seed: " + i);
        // 现在可预测后续随机数
    }
}
```

### Python random预测
```python
import random

# 如果了解足够的输出，可恢复内部状态
# 需要624个连续32位输出

MT19937状态恢复：
from mt19937predictor import MT19937Predictor

predictor = MT19937Predictor()
for i in range(624):
    predictor.predict(output[i])

# 现在可预测后续所有值
```

## 弱密钥和短密钥

### 短密钥DES
```
DES使用56位密钥，现已被破解

使用DES加密敏感数据：
cipher = DES.new(key, DES.MODE_ECB)
ciphertext = cipher.encrypt(password)

攻击：
1. 现代硬件可在天内暴力破解所有56位组合
2. 预计算彩虹表
```

### 默认或硬编码密钥
```
常见弱密钥：
- "secret"
- "password"
- "123456"
- 应用名称
- 服务器IP地址
- 版本号

检查：
1. 源代码
2. Docker镜像
3. 配置文件
4. 编译的二进制文件
```

## Hash碰撞和冲突

### MD5弱类型比较漏洞
```php
// PHP中的松散比较会导致0e开头的哈希相等

// 已知MD5弱碰撞对：
'QNKCDZO' => '240610708'  // MD5都以0e开头
'0e215962017' => '0e291242476940'  // 两者被视为0

// 利用原理：
$hash1 = md5('QNKCDZO');  // 0e215962017...
$hash2 = md5('240610708'); // 0e291242476940...

if ($hash1 == $hash2) {  // 松散比较，都被解释为0e+数字
    // 条件成立！（应该不成立）
}

// 攻击场景：
if (md5($_GET['a']) == md5($_GET['b'])) {
    approve();  // 可通过两个不同的MD5值绕过
}

// 防御：使用===或hash_equals
if (hash_equals(md5($_GET['a']), md5($_GET['b']))) {
    // 错误，hash_equals比较的是字符串
}

// 正确防御：
if (strcmp(md5($_GET['a']), md5($_GET['b'])) === 0) {
    // 字符串比较
}
```

### MD5弱碰撞列表
```php
// 完整的已知MD5弱碰撞对：

$weakHashes = array(
    'QNKCDZO' => '240610708',
    '0e215962017' => '0e291242476940',
    '0e291242476940' => '0e215962017',
    '0e884322' => '0e957393868307',
    '0e957393868307' => '0e884322',
    '0e539124087' => '0e575527695633',
    // 更多...
);

// 攻击工具：
// HashPump: 用于长度扩展攻击
// Hashtag: MD5碰撞查询
// Online碰撞数据库

// 利用步骤：
// 1. 发现应用使用MD5进行验证
// 2. 检查是否使用松散比较(==)
// 3. 查表获取已知碰撞对
// 4. 提交碰撞对绕过验证
```

### 科学计数法与MD5
```php
// 当MD5结果以0e开头并全是数字时，被当作科学计数法

$str1 = 'QNKCDZO';
$str2 = '240610708';

$md5_1 = md5($str1);  // 0e215962017...
$md5_2 = md5($str2);  // 0e291242476940...

// 在科学计数法中
// 0e215962017 = 0 * 10^215962017 = 0
// 0e291242476940 = 0 * 10^291242476940 = 0

if ($md5_1 == 0 || $md5_2 == 0) {
    // 都满足！
}

// 更危险的是：
if ($md5_1 == $md5_2) {
    // 0e... == 0e... 两个0相等!
}
```

### SHA1碰撞
```
2017年Google发现SHA1碰撞

对于使用SHA1作为密钥或token的系统：
1. 可能构造两个不同输入产生相同SHA1
2. 冒充用户或文件
```

### MD5碰撞
```
已知MD5存在碰撞

两个不同内容的相同MD5（理论上）：
实际CTF中使用弱碰撞对（0e开头）更常见

风险：
1. 文件完整性验证失败
2. 签名验证可被欺骗
3. 松散比较中的0e科学计数法风险
```

### SHA1碰撞
```
2017年Google发现SHA1碰撞

对于使用SHA1作为密钥或token的系统：
1. 可能构造两个不同输入产生相同SHA1
2. 冒充用户或文件
```

## ECB模式弱点

### ECB加密相同块得到相同密文
```
ECB（Electronic Codebook）模式：
明文: [block1][block2][block3][block1]
密文: [cipherA][cipherB][cipherC][cipherA]  # 块1重复！

攻击：
1. 模式识别：看密文就能猜测明文模式
2. 不安全用于加密密钥或令牌

AES-ECB加密密码：
password="adminadmin" → 两个相同块产生相同密文
```

## IV（初始化向量）重用

### IV重用导致密钥泄露
```
CBC/CTR模式中，相同的IV和密钥处理两条不同消息

Message1: "hello"
Message2: "world"
相同密钥K和IV

攻击：
C1 = E(K, IV XOR M1)
C2 = E(K, IV XOR M2)
C1 XOR C2 = E(...) XOR E(...) = M1 XOR M2
# 可恢复消息关系
```

### 静态或可预测的IV
```
每次加密使用相同IV：
iv = b"initialization"
cipher = AES.new(key, AES.MODE_CBC, iv)

# IV应该是随机且唯一的
# 同一密钥下，重用IV会泄露密钥信息
```

## Padding Oracle

### CBC模式Padding Oracle攻击
```
如果服务器在验证padding失败时返回不同错误：

有效padding: 明文末尾正确的padding字节
无效padding: 明文末尾错误的padding字节

攻击者可：
1. 逐字节解密密文
2. 通过观察padding验证失败/成功推断字节值
3. 需要大量请求（可能数千次）

缓解：
- 不要在padding验证失败时返回不同错误
- 使用authenticated encryption (GCM, ChaCha20-Poly1305)
```

## 算法选择漏洞

### 过时算法使用
```
WEP加密（已被破解）
RC4（已被破解）
MD5（已被破解）
SHA1（已被破解）
DES（已被破解）

应该使用：
AES-256
SHA-256/SHA-512
ChaCha20-Poly1305
```

### 客户端选择加密算法
```
某些TLS/SSL实现允许客户端降级算法

攻击：
1. 客户端支持AES-256
2. 攻击者强制降级到RC4
3. 中间人攻击成功

缓解：服务器强制最小安全标准
```

## 快速定位和利用

**关键词识别**：
- 使用md5()、sha1()、DES等过时算法
- 使用ECB模式
- 硬编码密钥或默认密钥
- 随机数种子基于时间戳或PID
- 无盐hash
- IV未妥善管理

**测试优先级**：
1. 识别使用的加密算法
2. 检查密钥强度（length >= 256位）
3. 测试随机数可预测性（相同种子）
4. 查找硬编码或默认密钥
5. 评估密钥管理（轮换、存储）

## 密钥管理漏洞

### 密钥轮换缺失
```python
# 漏洞：长期使用同一密钥
SECRET_KEY = "static-key-since-2015"  # 从未更改

# 风险：
# 1. 泄露后所有历史数据失效
# 2. 无法撤销已泄露的密钥
# 3. 增加密钥被破解的时间窗口

# 防御：定期轮换密钥
# 1. 支持多版本密钥
# 2. 新数据用新密钥加密
# 3. 旧数据逐步迁移
```

### 环境变量中的密钥
```bash
# 漏洞：通过环境变量传递密钥
export SECRET_KEY="my-secret-key-12345"

# 攻击：
# 1. /proc/<pid>/environ 可读
# 2. 进程列表泄露（ps aux）
# 3. 错误日志可能包含环境变量
# 4. 容器编排配置文件

# 防御：使用专用密钥管理系统
# - AWS Secrets Manager
# - HashiCorp Vault
# - Azure Key Vault
```

### Git历史中的密钥
```bash
# 检测历史提交中的密钥
git log -p | grep -i "secret\|key\|password"

# 常见泄露场景：
# 1. .env文件被提交
# 2. 配置文件包含明文密钥
# 3. 测试代码中的硬编码密钥

# 工具：
# - TruffleHog
# - GitLeaks
# - GitRob
```

## Base64编码不是加密

### Base64"加密"误区
```javascript
// 危险：将Base64当作加密
const secret = "admin-token-12345";
const encoded = Buffer.from(secret).toString('base64');
// 存储: YWRtaW4tdG9rZW4tMTIzNDU=

// "解密"：
const decoded = Buffer.from(encoded, 'base64').toString();

// 攻击：Base64是编码，任何人都能解码
echo "YWRtaW4tdG9rZW4tMTIzNDU=" | base64 -d
```

### URL编码"保护"
```php
// 同样危险：URL编码不是加密
$token = urlencode($sensitive_data);

// 攻击者可以轻易解码
$decoded = urldecode($token);
```

## 时序攻击深入

### 数据库查询时序
```python
# 漏洞：查询时间泄露用户存在性
def check_password(username, password):
    user = db.query("SELECT * FROM users WHERE username = ?", username)
    if user is None:
        return False  # 快速返回

    # 耗时的密码验证
    return bcrypt.checkpw(password, user.password_hash)

# 攻击：
# 1. 不存在的用户立即返回
# 2. 存在的用户需验证密码（耗时）
# 3. 枚举有效用户名
```

### 字符串比较时序
```java
// 危险：equals()不是恒定时间
public boolean verifyToken(String provided, String actual) {
    return provided.equals(actual);  // 逐字符比较，早期退出
}

// 攻击：通过时序测量逐字节爆破
// 第1字节正确：耗时T1
// 第1字节错误：耗时T0 (T0 < T1)

// 防御：使用MessageDigest.isEqual()
return MessageDigest.isEqual(
    provided.getBytes(),
    actual.getBytes()
);
```

## 认证加密组合错误

### Encrypt-and-MAC（不安全）
```python
# 不推荐：可能泄露明文信息
ciphertext = encrypt(plaintext, key1)
mac = HMAC(plaintext, key2)  # MAC明文
send(ciphertext, mac)

# 问题：MAC可能泄露明文信息
```

### MAC-then-Encrypt（不安全）
```python
# 不推荐：填充oracle风险
mac = HMAC(plaintext, key2)
ciphertext = encrypt(plaintext + mac, key1)

# 问题：解密前无法验证完整性
```

### Encrypt-then-MAC（正确）
```python
# 推荐做法
ciphertext = encrypt(plaintext, key1)
mac = HMAC(ciphertext, key2)  # MAC密文
send(ciphertext, mac)

# 优势：先验证MAC，避免处理恶意密文
```

### 最佳实践：使用AEAD
```python
# 最安全：使用认证加密模式
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

aesgcm = AESGCM(key)
nonce = os.urandom(12)
ciphertext = aesgcm.encrypt(nonce, plaintext, associated_data)

# 内置认证，无需单独MAC
```

## 加密模式降级攻击

### TLS降级攻击
```python
# 服务器支持多种加密套件
SUPPORTED_CIPHERS = [
    'AES256-GCM-SHA384',  # 强
    'AES128-CBC-SHA',     # 中等
    'RC4-MD5'             # 弱（不应支持）
]

# 攻击：中间人强制降级到RC4-MD5
# 防御：
# 1. 禁用弱加密套件
# 2. 启用TLS_FALLBACK_SCSV
# 3. 仅支持TLS 1.2+
```

### 协议版本降级
```javascript
// 危险：允许旧版本协议
const server = https.createServer({
    minVersion: 'TLSv1.0',  // 太旧
    maxVersion: 'TLSv1.3'
});

// 攻击：POODLE、BEAST等针对旧版本
// 防御：
const server = https.createServer({
    minVersion: 'TLSv1.2',  // 最低1.2
    maxVersion: 'TLSv1.3'
});
```

## 密钥派生Salt复用

### 用户间共享Salt
```php
// 危险：所有用户共享一个salt
define('GLOBAL_SALT', 'app-wide-salt-2024');

function hash_password($password) {
    return hash_pbkdf2('sha256', $password, GLOBAL_SALT, 100000);
}

// 攻击：
// 1. 可预计算彩虹表
// 2. 一次破解，处处适用
// 3. 无法防止相同密码检测

// 防御：每个用户独立的随机salt
$salt = random_bytes(16);
$hash = hash_pbkdf2('sha256', $password, $salt, 600000);
```

### 可预测的Salt
```python
# 危险：基于用户名生成salt
def get_salt(username):
    return hashlib.md5(username.encode()).digest()

# 攻击：
# 1. Salt可预测
# 2. 可针对常见用户名预计算
# 3. username1的彩虹表可重用

# 防御：随机生成salt
salt = os.urandom(16)
```

## Nonce重用（AES-GCM）

### GCM模式Nonce重用灾难
```javascript
// 严重漏洞：GCM模式重用nonce
const crypto = require('crypto');
const nonce = Buffer.alloc(12, 0);  // 固定nonce

function encrypt(data) {
    const cipher = crypto.createCipheriv('aes-256-gcm', key, nonce);
    // ...
}

// 后果：
// 1. 完全破坏认证
// 2. 可恢复密钥
// 3. 可伪造任意密文

// 防御：每次加密必须用新的随机nonce
const nonce = crypto.randomBytes(12);
```

### 计数器模式Nonce管理
```python
# CTR模式需要唯一nonce
from Crypto.Cipher import AES
from Crypto.Util import Counter

# 危险：重用计数器初始值
ctr = Counter.new(128, initial_value=0)
cipher = AES.new(key, AES.MODE_CTR, counter=ctr)

# 防御：每条消息使用不同的初始值
import os
nonce = int.from_bytes(os.urandom(16), 'big')
ctr = Counter.new(128, initial_value=nonce)
```

## 密钥强度不足

### DES和3DES
```java
// DES仅56位有效密钥，已被破解
Cipher cipher = Cipher.getInstance("DES/ECB/PKCS5Padding");
SecretKey key = KeyGenerator.getInstance("DES").generateKey();

// 3DES（168位名义，实际112位安全性）也不推荐
Cipher cipher = Cipher.getInstance("DESede/CBC/PKCS5Padding");

// 攻击：
// 1. 暴力破解（DES在天内可破）
// 2. 生日攻击（3DES）

// 防御：使用AES-256
Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
KeyGenerator keyGen = KeyGenerator.getInstance("AES");
keyGen.init(256);  // 256位
```

### RSA密钥过短
```python
# 危险：1024位RSA
from Crypto.PublicKey import RSA
key = RSA.generate(1024)  # 已不安全

# 攻击：数论筛法可在合理时间内分解

# 防御：至少2048位，推荐4096位
key = RSA.generate(2048)
```

## 自定义加密实现陷阱

### 自制XOR加密
```c
// 简单XOR"加密"
void xor_encrypt(char *data, char *key, int len) {
    for (int i = 0; i < len; i++) {
        data[i] ^= key[i % strlen(key)];
    }
}

// 弱点：
// 1. 已知明文攻击可恢复密钥
// 2. 密钥重复产生模式
// 3. data[i] XOR data[j] = key[i%L] XOR key[j%L]
```

### 自定义替换密码
```javascript
// 简单字符替换
function customEncrypt(text) {
    return text.split('').map(c =>
        String.fromCharCode(c.charCodeAt(0) + 13)
    ).join('');
}

// 攻击：频率分析
// 英文字母'e'出现频率最高，密文中对应字符即为'e'+13
```

## 防御检查清单

- ✓ 仅使用安全的算法（AES-256, SHA-256, ChaCha20）
- ✓ 使用CBC/GCM/CTR模式，避免ECB
- ✓ 每次加密生成随机IV/Nonce
- ✓ 使用密钥导出函数（PBKDF2≥600k, Argon2）
- ✓ 严格的密钥管理（HSM、密钥旋转）
- ✓ 使用密码学上安全的随机数生成器
- ✓ 定期更新密码学库
- ✓ 使用认证加密（AES-GCM, ChaCha20-Poly1305）
- ✓ 避免在客户端存储敏感加密密钥
- ✓ 每个用户使用独立的随机salt
- ✓ GCM/CTR模式绝不重用nonce
- ✓ 实施恒定时间比较防止时序攻击
- ✓ 优先使用Encrypt-then-MAC或AEAD
- ✓ 密钥长度：AES≥256位，RSA≥2048位
- ✓ Base64/URL编码不是加密，切勿依赖
