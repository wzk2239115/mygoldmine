---
name: weak-cryptography-analyzer
description: 专业的审计工作流程，通过静态代码分析识别和验证弱加密漏洞；重点关注检测使用已被证明不安全、过时或配置不当的密码学算法（如 MD5、SHA1、DES、ECB 模式）、硬编码密钥、不安全的随机数生成等问题，从而导致敏感数据保护失效；利用按编程语言组织的参考资料目录中的参考指南。
---

**Attention**  
当项目中涉及敏感数据保护（如用户凭证、通信内容、令牌、密钥等）并使用了加密、哈希、签名或密钥派生等密码学操作时，需仔细审计其密码学算法、参数、实现方式是否符合现代安全标准。此类漏洞通常源于使用已被证明不安全、过时、自定义或配置不当的密码学原语（如 MD5、SHA1、DES、ECB 模式、硬编码密钥、不安全的随机数生成等），常见于身份认证、数据传输、存储加密、API 签名等模块。

**Early exit**  
若项目代码完全不涉及任何密码学操作（即无加密、解密、哈希、签名、密钥管理、随机数生成等逻辑），或仅使用高层安全框架（如 TLS、JWT 库等）且未自定义底层密码学实现，则可快速退出对该漏洞类型的审计。
---

## 通用弱加密漏洞模式（所有项目必审）

查看详细说明：[general.md](general.md)

快速概览：使用已废弃或弱加密算法（DES/3DES/RC4/MD5/SHA-1/短密钥）、使用不安全的加密模式（ECB模式泄露、CBC配置不当、IV重用）、密钥管理缺陷（硬编码/明文存储、强度不足、轮换缺失）、密钥派生函数配置不当（PBKDF2/Bcrypt/Scrypt/Argon2参数不足、盐值缺失或可预测）、不安全的随机数生成（弱PRNG、熵源不足）、自定义密码学实现（自定义算法、不安全原语组合）、初始化向量（IV）使用不当（重用/可预测/未随机生成）、使用废弃或过时的密码学库、时序攻击风险（未使用常量时间比较）

查看详细说明：
- Argon2 密码派生函数最佳实践，详见：[crypto_argon2_best_practice.md](crypto_argon2_best_practice.md)

---
**语言特定实现（根据项目语言选择性审计）**

以下漏洞场景与具体编程语言的密码学库实现方式相关。根据项目所使用的编程语言，仅需审计对应语言章节中的漏洞模式。

**Java**
常出现在 JWT 签名、数据库字段加密、HTTPS 自定义证书校验等业务逻辑中，包括但不限于使用 MessageDigest.getInstance("MD5")、Cipher.getInstance("DES")、不安全的 KeyGenerator 配置等方式，详见：
- 使用 MD5 等弱哈希算法进行数据摘要或密码验证，详见：[java_md5_usage.md](java_md5_usage.md) | 遇到 MD5 碰撞保护机制，详见：[bypassTricks.md#hash碰撞和冲突](bypassTricks.md#hash碰撞和冲突)
- 使用 DES 弱加密算法进行敏感数据保护，详见：[java_des_cipher.md](java_des_cipher.md) | 遇到短密钥保护机制，详见：[bypassTricks.md#弱密钥和短密钥](bypassTricks.md#弱密钥和短密钥)
- 使用不安全的伪随机数生成器（如 Random 类）生成密钥材料，详见：[java_weak_prng.md](java_weak_prng.md) | 遇到随机数可预测保护机制，详见：[bypassTricks.md#随机数可预测](bypassTricks.md#随机数可预测)
- 使用 ECB 模式且未正确处理填充导致的安全风险，详见：[java_ecb_padding_oracle.md](java_ecb_padding_oracle.md) | 遇到 ECB 模式或 Padding Oracle 保护机制，详见：[bypassTricks.md#ecb模式弱点](bypassTricks.md#ecb模式弱点) 或 [bypassTricks.md#padding-oracle](bypassTricks.md#padding-oracle)

**Python**
常出现在 Web 应用的会话管理、API 签名、配置加密等场景中，包括但不限于使用 hashlib.md5()、pycryptodome 中的 DES 模块、os.urandom 误用、自定义 XOR 加密等方式，详见：
- 使用 MD5 哈希算法处理敏感数据或密码存储，详见：[python_md5_hash.md](python_md5_hash.md) | 遇到 MD5 碰撞保护机制，详见：[bypassTricks.md#hash碰撞和冲突](bypassTricks.md#hash碰撞和冲突)
- 使用 DES 算法进行数据加密保护，详见：[python_des_encrypt.md](python_des_encrypt.md) | 遇到短密钥保护机制，详见：[bypassTricks.md#弱密钥和短密钥](bypassTricks.md#弱密钥和短密钥)
- 使用简单 XOR 等自定义加密算法替代标准密码学方案，详见：[python_custom_xor_crypto.md](python_custom_xor_crypto.md)
- 使用弱密钥、短密钥或硬编码密钥进行加密操作，详见：[python_weak_secret_key.md](python_weak_secret_key.md) | 遇到硬编码密钥保护机制，详见：[bypassTricks.md#弱密钥和短密钥](bypassTricks.md#弱密钥和短密钥)

**Go**
常出现在 TLS 配置、JWT 实现、密钥派生等逻辑中，包括但不限于 crypto/md5 包直接调用、使用不带盐的弱哈希、硬编码密钥字符串、未启用安全 CipherSuites 等方式，详见：
- 使用 MD5 摘要算法进行数据完整性校验或密码哈希，详见：[go_md5_digest.md](go_md5_digest.md) | 遇到 MD5 碰撞保护机制，详见：[bypassTricks.md#hash碰撞和冲突](bypassTricks.md#hash碰撞和冲突)
- 在代码中硬编码静态密钥或密钥材料，详见：[go_static_key.md](go_static_key.md) | 遇到硬编码密钥保护机制，详见：[bypassTricks.md#弱密钥和短密钥](bypassTricks.md#弱密钥和短密钥)
- 使用不安全的 PBKDF2 配置（如低迭代次数或弱哈希函数），详见：[go_insecure_pbkdf2.md](go_insecure_pbkdf2.md)
- 使用 ECB 模式进行 AES 加密操作，详见：[go_ecb_aes.md](go_ecb_aes.md) | 遇到 ECB 模式保护机制，详见：[bypassTricks.md#ecb模式弱点](bypassTricks.md#ecb模式弱点)

**PHP**
常出现在用户密码存储、API 请求签名、Cookie 加密等业务中，包括但不限于使用 md5()、sha1()、mcrypt 库（已废弃）、openssl_encrypt 未指定安全模式等方式，详见：
- 使用 MD5 函数进行密码哈希存储，详见：[php_md5_password.md](php_md5_password.md) | 遇到 MD5 弱类型比较或碰撞保护机制，详见：[bypassTricks.md#hash碰撞和冲突](bypassTricks.md#hash碰撞和冲突)
- 使用已废弃的 mcrypt 扩展和 DES 算法进行加密，详见：[php_mcrypt_des.md](php_mcrypt_des.md) | 遇到短密钥保护机制，详见：[bypassTricks.md#弱密钥和短密钥](bypassTricks.md#弱密钥和短密钥)
- 使用 ECB 模式进行 AES 加密导致模式泄露，详见：[php_ecb_aes.md](php_ecb_aes.md) | 遇到 ECB 模式保护机制，详见：[bypassTricks.md#ecb模式弱点](bypassTricks.md#ecb模式弱点)
- 使用弱盐值或固定盐值进行密码哈希，详见：[php_weak_salt_hash.md](php_weak_salt_hash.md)
- 密码存储安全策略，详见：[php_password_storage_security.md](php_password_storage_security.md)
- Session加密安全策略，详见：[php_session_crypto_security.md](php_session_crypto_security.md)
- 前端JavaScript加密常见错误，详见：[php_javascript_crypto_security.md](php_javascript_crypto_security.md)

**JavaScript / TypeScript**
常出现在前端加密传输、本地存储保护、Token 生成等场景中，包括但不限于使用 crypto-js 的 MD5/SHA1、自定义哈希函数、硬编码密钥、不安全的随机数生成（如 Math.random()）等方式，详见：
- 使用 crypto-js 等库的 MD5 算法进行数据加密或签名，详见：[js_md5_crypto.md](js_md5_crypto.md) | 遇到 MD5 碰撞保护机制，详见：[bypassTricks.md#hash碰撞和冲突](bypassTricks.md#hash碰撞和冲突)
- 在前端代码中硬编码静态密钥或敏感凭证，详见：[js_static_secret.md](js_static_secret.md) | 遇到硬编码密钥保护机制，详见：[bypassTricks.md#弱密钥和短密钥](bypassTricks.md#弱密钥和短密钥)
- 使用 Math.random() 生成密钥或安全令牌，详见：[ts_math_random_key.md](ts_math_random_key.md)
- 自定义实现哈希函数替代标准密码学算法，详见：[js_custom_hash_func.md](js_custom_hash_func.md)

**C/C++**
常出现在安全通信、本地数据加密、身份认证等功能实现中，包括但不限于使用 OpenSSL/EVP 接口时误配弱算法、自实现加密逻辑、硬编码密钥、使用 rand() 生成密钥材料等方式，详见：
- 使用 MD5/SHA1 等弱哈希算法进行密码存储或签名验证，详见：[c_weak_hash.md](c_weak_hash.md) | 遇到 MD5/SHA1 碰撞保护机制，详见：[bypassTricks.md#hash碰撞和冲突](bypassTricks.md#hash碰撞和冲突)
- 使用已被证明不安全的 DES 算法进行数据加密，详见：[c_des_usage.md](c_des_usage.md) | 遇到短密钥保护机制，详见：[bypassTricks.md#弱密钥和短密钥](bypassTricks.md#弱密钥和短密钥)
- 使用 ECB 模式导致明文模式泄露，详见：[c_ecb_mode.md](c_ecb_mode.md) | 遇到 ECB 模式保护机制，详见：[bypassTricks.md#ecb模式弱点](bypassTricks.md#ecb模式弱点)
- 自定义实现加密算法或不安全的密码学原语组合，详见：[c_custom_crypto.md](c_custom_crypto.md)

**Rust**
常出现在区块链钱包、安全通信、数据密封等模块中，包括但不限于使用 outdated crates（如 rust-crypto）、手动实现加密逻辑、未启用 constant-time 比较、使用不安全的 RNG（如 thread_rng 误用）等方式，详见：
- 使用过时或不安全的密码学 crate 提供弱哈希算法，详见：[rust_weak_hash_crate.md](rust_weak_hash_crate.md) | 遇到弱哈希碰撞保护机制，详见：[bypassTricks.md#hash碰撞和冲突](bypassTricks.md#hash碰撞和冲突)
- 手动实现自定义加密算法而非使用经过审计的标准库，详见：[rust_custom_cipher.md](rust_custom_cipher.md)
- 使用不安全的随机数生成器或误用 RNG 生成密钥，详见：[rust_insecure_rng.md](rust_insecure_rng.md) | 遇到随机数可预测保护机制，详见：[bypassTricks.md#随机数可预测](bypassTricks.md#随机数可预测)
- 在代码中硬编码静态密钥材料或种子，详见：[rust_static_key_material.md](rust_static_key_material.md) | 遇到硬编码密钥保护机制，详见：[bypassTricks.md#弱密钥和短密钥](bypassTricks.md#弱密钥和短密钥)
- 绕过技巧，详见：[bypassTricks.md](bypassTricks.md)

# 输出要求

确认漏洞后，加载 `bug-report` 技能获取标准化报告格式，生成漏洞报告文件。

**加载技能**：`bug-report`

**输出路径**：`.workspace/findings/BUG-weak-crypto-{file}-L{line}-{source}-{sink}.md`

**约束**：
- 每个漏洞必须生成独立的 BUG 文件，禁止合并或省略
- 漏洞报告格式严格遵循 `bug-report` 技能定义的模板