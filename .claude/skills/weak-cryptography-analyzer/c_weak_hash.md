# C/C++ 弱哈希算法审计

## Details

### 典型代码特征
```c
// OpenSSL EVP接口使用MD5
EVP_MD_CTX *ctx = EVP_MD_CTX_new();
EVP_DigestInit_ex(ctx, EVP_md5(), NULL);
EVP_DigestUpdate(ctx, data, len);
EVP_DigestFinal_ex(ctx, hash, &hash_len);

// OpenSSL 传统MD5接口
MD5_CTX md5_ctx;
MD5_Init(&md5_ctx);
MD5_Update(&md5_ctx, password, strlen(password));
MD5_Final(digest, &md5_ctx);

// SHA1密码存储
unsigned char sha1_hash[SHA_DIGEST_LENGTH];
SHA1((unsigned char*)password, strlen(password), sha1_hash);

// mbedTLS使用MD5/SHA1
mbedtls_md5_context md5;
mbedtls_md5_init(&md5);
mbedtls_md5_starts(&md5);
mbedtls_md5_update(&md5, input, len);
mbedtls_md5_finish(&md5, output);

// 直接哈希密码无加盐
char hash[33];
sprintf(hash, "%02x%02x...", digest[0], digest[1]); // 直接存储
```

### 快速定位核心操作（L1-L3）

**关键符号扫描（L1）：**
```bash
grep -E "MD5_|SHA1_|EVP_md5|EVP_sha1|MBEDTLS_MD_MD5|MBEDTLS_MD_SHA1" *.c *.cpp
grep -E "md5sum|sha1sum|hash.*password" *.c
nm binary | grep -i "md5_\|sha1_"
strings binary | grep -E "md5|sha1" -i
```

**高危API模式（L2 跳读）：**
- `EVP_md5()` / `EVP_sha1()` 作为摘要初始化参数
- `MD5_Init()` / `MD5_Update()` / `MD5_Final()` 系列
- `SHA1()` / `SHA1_Init()` / `SHA1_Update()` / `SHA1_Final()`
- `mbedtls_md5_*()` / `mbedtls_sha1_*()` 函数
- `MD5_DIGEST_LENGTH` (16) / `SHA_DIGEST_LENGTH` (20) 魔数
- 密码/凭证字段直接输入哈希函数

**函数调用链追踪（L3 逐行）：**
- 定位 `EVP_DigestInit*` 第二参数：检查 `EVP_md5()` / `EVP_sha1()`
- 密码验证逻辑：`strcmp(stored_hash, MD5(input))` 模式
- 签名生成：HMAC-MD5 / HMAC-SHA1 用于令牌签名
- 配置文件：`hash_algorithm="md5"` / `DIGEST_TYPE MD5`
- 函数指针赋值：`digest_func = MD5;` / `hash_type = NID_md5;`

### 快速定位保护机制（L2-L4）

**无保护特征（L2 跳读）：**
- 密码直接进入哈希：`MD5(password)` 无 salt 参数
- 单轮哈希：无迭代计数/PBKDF2/bcrypt/scrypt
- 硬编码算法：无动态选择逻辑或升级路径
- 比较逻辑暴露时序攻击：`strcmp(hash1, hash2)`

**伪保护识别（L3 逐行）：**
```c
// 加盐但仍用弱哈希
char salted[256];
sprintf(salted, "%s%s", password, salt);
MD5(salted, strlen(salted), hash);  // 仍易彩虹表攻击

// 多轮迭代但算法过弱
for(int i = 0; i < 1000; i++) {
    SHA1(hash, 20, hash);  // 迭代次数不足且SHA1已碰撞
}

// HMAC使用弱哈希
HMAC(EVP_md5(), key, keylen, data, datalen, out, &outlen);  // 仍不安全
```

**跨模块保护追踪（L4）：**
- 检查密码库选择：是否有 bcrypt/argon2/scrypt 并行实现
- 运行时禁用：`SSL_CTX_set_security_level(ctx, 2)` 排除弱哈希
- 配置文件审计：`allowed_digests` 白名单是否包含 md5/sha1
- 依赖库版本：OpenSSL 3.0+ 默认禁用MD5签名
- 证书链验证：`X509_verify*` 是否接受MD5/SHA1签名证书
- 编译宏：`OPENSSL_NO_MD5` / `OPENSSL_NO_SHA1` 是否定义

## Classify

**确认漏洞：**
- 密码存储直接用MD5/SHA1（无论是否加盐）
- 会话令牌/API签名使用HMAC-MD5/HMAC-SHA1
- 证书签名/代码签名用SHA1（已碰撞）
- 身份认证/授权决策依赖弱哈希输出
- 密钥派生函数（KDF）基于MD5/SHA1单轮
- 无替代算法的强制弱哈希实现

**研判误报：**
- 文件完整性校验（非对抗场景，如备份去重）
- 哈希表键生成（内存数据结构，非持久化）
- 非密码学用途（ETags、Cache-Key、分片标识）
- 解析历史格式（读取旧系统遗留数据，只读）
- 单元测试/Mock数据（明确标注测试代码）
- 已废弃代码路径（`#if 0` 或配置默认禁用）

**代码异味：**
- 文档声称"安全哈希"但实现用MD5
- 加盐MD5用于新用户，历史用户未升级
- 配置可选SHA256但默认MD5/SHA1
- 注释"TODO: 升级到SHA256"无时间表
- 算法协商中MD5/SHA1优先级高于SHA256

**关键判断点：**
1. 哈希目标：文件校验 vs 密码/密钥
2. 对抗模型：是否需防御预映像/碰撞攻击
3. 存储时长：临时会话 vs 长期持久化
4. 替代方案：系统是否支持SHA256/SHA512/Blake2
5. 攻击面：内部校验 vs 外部暴露接口

## Low risk

**可接受的低风险场景：**
- 本地文件去重（rsync/dedup，无安全边界）
- Git对象ID生成（SHA1用于内容寻址非签名）
- 缓存键生成（CDN/Nginx，碰撞仅导致性能问题）
- 日志消息摘要（快速检索非完整性保证）
- 开发环境调试标识（非生产部署）

**降级条件：**
- 碰撞攻击成本远高于资产价值
- 数据不涉及身份认证/授权/签名验证
- 内部系统无外部输入可控（无碰撞注入机会）
- 短生命周期数据（临时文件标识 < 1小时）
- 已有外层强签名保护（如TLS 1.3 + EdDSA）

**注意：** MD5已实现实用碰撞攻击（2^21复杂度），SHA1理论碰撞已证明（SHAttered）。任何认证/签名场景应立即迁移至 SHA-256/SHA-512/Blake2b。文件校验建议升级到 SHA-256 防御前缀碰撞攻击。低风险评级仅适用于非安全关键场景。
