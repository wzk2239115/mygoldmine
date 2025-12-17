# 密码学漏洞绕过秘笈

## 密钥导出函数漏洞

### 弱盐值
```php
// 漏洞：盐值太短或可预测
$salt = substr(md5(time()), 0, 4);  // 仅4字节
$hash = md5($password . $salt);

// 攻击：
// 1. 暴力破解盐值（仅256M组合）
// 2. 预计算彩虹表
```

### 无盐hash
```php
// 最危险：完全无盐
$hash = md5($password);
$hash = sha1($password);

// 攻击：
// 1. 公开彩虹表
// 2. 预计算所有常见密码
```

### 自定义KDF
```php
// 漏洞：实现了不安全的KDF
function my_kdf($password, $salt) {
    return md5($password) . md5($salt);
}

// 应该使用：
password_hash($password, PASSWORD_BCRYPT);  // PHP
or PBKDF2, Argon2
```

## 散列函数碰撞

### MD5碰撞
```
两个不同文件可产生相同MD5：
file1.pdf != file2.pdf
但 md5(file1.pdf) == md5(file2.pdf)

攻击：
1. 上传恶意PDF但名字相同
2. 完整性检查失败
```

### SHA1碰撞
```
2017年Google演示了SHA1碰撞
SHAttered project: 两个不同的PDF

攻击场景：
1. 代码签名使用SHA1
2. 攻击者创建相同hash的恶意代码
3. 签名验证通过
```

## 随机数预测

### 系统时间作种子
```javascript
// JavaScript的随机数
Math.random()  // 不加密安全，不该用于密码学

// Java默认
Random rand = new Random();  // 基于时间戳，可预测

攻击：
1. 记录时间戳范围
2. 枚举所有可能的随机数
```

### 低熵种子
```php
mt_srand(time());  // 仅秒级精度
mt_rand();         // 可预测

攻击：
1. 当前时间±几秒内暴力破解
2. 预测session token
```

## 公钥密码漏洞

### 小的公开指数
```
RSA: e=3（太小）

某些攻击可行：
1. 立方根攻击
2. 同步编码攻击（多条消息加密）
```

### 弱密钥大小
```
512位或更小的RSA密钥可被破解

现代攻击：
1. 数字筛法（GNFS）
2. 预计算
```

## Padding Oracle

### PKCS#1 v1.5 Padding
```
如果服务器泄露padding错误信息：

有效padding: [0x00 0x02 ...]
无效padding: 返回不同错误

攻击者可：
1. 解密密文（Bleichenbacher攻击）
2. 需要数百万次请求
```

## 动作和时间泄露

### 基于时间的侧通道
```python
# 危险：执行时间泄露信息
def compare_secrets(provided, actual):
    for i in range(len(actual)):
        if provided[i] != actual[i]:
            return False  # 快速返回
    return True

# 攻击：通过响应时间推断密钥
# 第一个字符匹配时间长，不匹配时间短
```

### 恒定时间比较
```python
# 安全做法
import hmac
hmac.compare_digest(provided, actual)  # 恒定时间

或手动实现：
diff = 0
for x, y in zip(provided, actual):
    diff |= ord(x) ^ ord(y)
return diff == 0
```

## 快速定位和利用

**关键词识别**：
- md5()、sha1()、sha256()无盐
- 自定义hash/加密算法
- 小于2048位RSA密钥
- 使用弱随机数(Math.random, time-seeded)
- 时间敏感操作无恒定时间

**测试优先级**：
1. 识别使用的密码学算法
2. 检查是否使用了过时算法
3. 评估密钥长度
4. 检查盐值和种子强度
5. 时间侧通道分析

## IV（初始化向量）重用

### 静态或可预测的IV
```python
# 漏洞：每次加密使用相同IV
iv = b"1234567890123456"  # 固定16字节
cipher = AES.new(key, AES.MODE_CBC, iv)
ciphertext = cipher.encrypt(plaintext)

# 攻击：
# 1. 相同密钥+相同IV加密两条消息
# 2. C1 XOR C2 = (IV XOR M1) XOR (IV XOR M2) = M1 XOR M2
# 3. 可恢复消息之间的关系
```

### IV重用密钥流攻击
```javascript
// 漏洞：CTR模式下IV重用
const crypto = require('crypto');
const iv = Buffer.alloc(16, 0);  // 零IV

function encrypt(data) {
    const cipher = crypto.createCipheriv('aes-256-ctr', key, iv);
    return cipher.update(data);
}

// 攻击：
// CTR模式下，相同IV会产生相同的密钥流
// C1 = P1 XOR KeyStream
// C2 = P2 XOR KeyStream
// C1 XOR C2 = P1 XOR P2（已知明文攻击）
```

### 从密文中提取IV
```php
// 常见但危险的做法：IV附加在密文前
$iv = openssl_random_pseudo_bytes(16);
$ciphertext = openssl_encrypt($plaintext, 'aes-256-cbc', $key, 0, $iv);
$result = base64_encode($iv . $ciphertext);

// 攻击者可以：
// 1. 提取IV（前16字节）
// 2. 修改IV进行位翻转攻击
// 3. 影响第一个明文块的解密
```

## 长度扩展攻击

### Hash长度扩展
```python
# 漏洞：使用MD5/SHA1/SHA256进行MAC而非HMAC
import hashlib

def weak_mac(key, message):
    return hashlib.sha256(key + message).hexdigest()

# 已知：hash = SHA256(key || message)
# 攻击者可以：
# 1. 不知道key的情况下
# 2. 计算 SHA256(key || message || padding || extra_data)
# 3. 工具：HashPump、hash_extender
```

### HashPump利用
```bash
# 已知原始消息和hash
original_msg = "user=guest"
original_hash = "abc123..."

# 使用HashPump扩展
hashpump -s "abc123..." -d "user=guest" -a "&admin=1" -k 16

# 输出新的hash和消息
# 可以伪造有效签名
```

## 弱随机数生成

### 时间戳作为种子
```java
// 漏洞：可预测的种子
Random rand = new Random(System.currentTimeMillis());
String token = Long.toHexString(rand.nextLong());

// 攻击：
long now = System.currentTimeMillis();
for (long seed = now - 10000; seed <= now + 10000; seed++) {
    Random r = new Random(seed);
    if (Long.toHexString(r.nextLong()).equals(observed_token)) {
        // 找到种子，可预测后续所有随机数
        String next_token = Long.toHexString(r.nextLong());
    }
}
```

### UUID v1可预测
```python
# UUID v1包含时间戳和MAC地址
import uuid
u = uuid.uuid1()

# 攻击：
# 1. 提取时间戳（可预测）
# 2. 提取MAC地址（可枚举）
# 3. 生成有效的UUID序列
#
# 防御：使用UUID v4（随机）
u = uuid.uuid4()
```

## 认证加密缺失

### 加密但未认证
```python
# 漏洞：仅加密不验证完整性
from Crypto.Cipher import AES
cipher = AES.new(key, AES.MODE_CBC, iv)
ciphertext = cipher.encrypt(pad(plaintext))

# 攻击：Bit-flipping attack
# 1. 修改密文某位
# 2. 导致明文对应位翻转
# 3. 可构造恶意明文

# 防御：使用GCM或添加HMAC
cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
ciphertext, tag = cipher.encrypt_and_digest(plaintext)
```

### CBC位翻转攻击
```
假设CBC加密的cookie：
明文: {"user":"guest","admin":false}
密文: C1|C2|C3

攻击者修改C2某位：
1. C2' = C2 XOR 0x01（翻转一位）
2. 解密后P3' = P3 XOR 0x01
3. false -> true（在第3块）

无完整性保护时可成功
```

## RSA填充攻击

### PKCS#1 v1.5 Padding Oracle
```python
# 服务器解密并返回不同错误
def decrypt(ciphertext):
    plaintext = rsa_decrypt(ciphertext)
    if not valid_pkcs1_padding(plaintext):
        return "Padding Error"  # 泄露padding信息
    return process(plaintext)

# Bleichenbacher攻击：
# 1. 修改密文
# 2. 观察是否返回padding错误
# 3. 通过数百万次请求恢复明文
```

### 小公钥指数攻击
```python
# RSA: e=3时的漏洞
# 如果明文m很小，m^3 < n
# 则 c = m^3 mod n = m^3
# 攻击：直接计算c的立方根得到m

import gmpy2
m = gmpy2.iroot(c, 3)[0]  # 恢复明文
```

## 密钥派生弱点

### 密码直接用作密钥
```javascript
// 危险：密码直接作为AES密钥
const crypto = require('crypto');
const key = Buffer.from(password.padEnd(32, '0'));  // 弱密钥
const cipher = crypto.createCipheriv('aes-256-cbc', key, iv);

// 攻击：
// 1. 密码空间有限
// 2. 可暴力破解
//
// 防御：使用PBKDF2/Scrypt/Argon2
const key = crypto.pbkdf2Sync(password, salt, 600000, 32, 'sha256');
```

### 迭代次数过少
```python
# NIST建议PBKDF2最少600,000次迭代
from hashlib import pbkdf2_hmac

# 危险：仅1000次
key = pbkdf2_hmac('sha256', password, salt, 1000)

# 攻击：GPU可快速暴力破解
# 防御：≥600,000次
key = pbkdf2_hmac('sha256', password, salt, 600000)
```

## 侧信道攻击

### 缓存时序攻击
```c
// 漏洞：查表操作产生时序差异
uint8_t sbox[256] = {...};
uint8_t lookup(uint8_t index) {
    return sbox[index];  // 缓存命中/未命中时间不同
}

// 攻击：Flush+Reload
// 1. 刷新缓存
// 2. 触发加密
// 3. 测量访问时间
// 4. 推断密钥
```

### 分支时序泄露
```python
# 危险：比较时间与数据相关
def compare_token(provided, actual):
    if len(provided) != len(actual):
        return False
    for i in range(len(actual)):
        if provided[i] != actual[i]:
            return False  # 早期退出
    return True

# 攻击：测量响应时间
# 1. 第1字节正确时耗时长
# 2. 第1字节错误时耗时短
# 3. 逐字节爆破

# 防御：恒定时间比较
import hmac
return hmac.compare_digest(provided, actual)
```

## 防御检查清单

- ✓ 使用标准库的安全函数（bcrypt、scrypt、Argon2）
- ✓ 密钥大小≥256位（对称），≥2048位（RSA）
- ✓ 随机数使用密码学安全RNG（/dev/urandom、crypto模块）
- ✓ 盐值长度≥16字节，随机生成
- ✓ 恒定时间的敏感比较（HMAC-SHA256）
- ✓ 避免使用已破解的算法（MD5、SHA1）
- ✓ 定期更新密码学库
- ✓ 代码审查所有密码学操作
- ✓ 避免实现自己的加密算法
- ✓ IV必须随机生成且不重复使用
- ✓ 使用认证加密（GCM、ChaCha20-Poly1305）
- ✓ PBKDF2迭代次数≥600,000
- ✓ 使用HMAC而非Hash进行消息认证
- ✓ RSA使用OAEP填充而非PKCS#1 v1.5
- ✓ 密钥派生使用KDF，不直接用密码作密钥
