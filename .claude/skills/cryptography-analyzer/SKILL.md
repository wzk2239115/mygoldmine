---
name: cryptography-analyzer
description: 专业的审计工作流程，通过静态代码分析识别和验证密码学基础漏洞；重点关注检测密码学实现中的常见错误，包括不安全的算法选择（对称/非对称加密、哈希、MAC）、密钥生成与管理缺陷、初始化向量（IV）不随机或重复使用、填充（Padding）实现错误、密钥派生函数不当使用、模式选择不当等，从而导致加密保护失效、数据泄露、密钥恢复等安全问题；利用按编程语言组织的参考资料目录中的参考指南。
---

**Attention**
当项目中涉及对敏感数据的加密、解密、消息认证、数字签名等密码学操作时，需严格审查密码学实现的正确性。此类问题常源于算法选择不当（如使用已被破解的算法）、参数配置错误（如 IV 不随机或重复、填充实现缺陷）、密钥管理不规范（如硬编码密钥、密钥派生参数不足）或模式选择不当（如 ECB 模式导致模式泄露）。问题通常出现在数据加密存储、HTTPS/TLS 配置、API 签名、会话管理等模块中。

**Early exit**
若项目代码完全不涉及任何密码学操作（如无加密、解密、哈希、签名、密钥管理等逻辑），或仅调用高层安全框架（如 TLS 库、JWT 库等）且完全不涉及底层密码学参数配置，则可快速退出对该漏洞类型的审计。

---

## 通用密码学缺陷模式（所有项目必审）

查看详细说明：[general.md](general.md)

快速概览：不安全的加密算法或模式（弱算法/ECB模式/无认证加密）、初始化向量（IV）使用不当（不随机/可预测/重复使用）、密钥管理缺陷（硬编码/存储不安全/长度不足）、密钥派生函数（KDF）参数不足（PBKDF2配置不当/未使用现代KDF）、不安全的哈希算法（MD5/SHA-1/过时算法）、随机数生成器不安全（弱RNG/可预测种子）、填充（Padding）实现错误（手动实现/Padding Oracle）、使用废弃或过时的密码学库（pycrypto/mcrypt等）

查看详细说明：
- 常见误报场景，详见：[COMMON_FALSE_POSITIVES.md](COMMON_FALSE_POSITIVES.md)

---

**语言特定实现（根据项目语言选择性审计）**

以下漏洞场景与具体编程语言的密码学库实现相关。根据项目所使用的编程语言，仅需审计对应语言章节中的漏洞模式。

**Java**
- Cipher 初始化时 IV 使用不当或重复，详见：[java_cipher_iv_reuse.md](java_cipher_iv_reuse.md) | 遇到 IV 重用保护机制，详见：[bypassTricks.md#iv初始化向量重用](bypassTricks.md#iv初始化向量重用)
- 使用 ECB 模式或其他不安全的加密模式，详见：[java_insecure_cipher_mode.md](java_insecure_cipher_mode.md) | 遇到 ECB 模式保护机制，详见：[bypassTricks.md#ecb模式弱点](bypassTricks.md#ecb模式弱点)
- 密钥派生时使用 PBKDF2 但参数配置不足（迭代次数少、哈希函数弱），详见：[java_weak_pbkdf2_config.md](java_weak_pbkdf2_config.md) | 遇到弱密钥派生保护机制，详见：[bypassTricks.md#密钥导出函数漏洞](bypassTricks.md#密钥导出函数漏洞)

**Python**
- 使用 AES 加密时 IV 不随机或重复使用，详见：[python_aes_iv_reuse.md](python_aes_iv_reuse.md) | 遇到 IV 重用保护机制，详见：[bypassTricks.md#iv初始化向量重用](bypassTricks.md#iv初始化向量重用)
- 密钥派生使用 PBKDF2 但迭代次数过少或哈希算法过弱，详见：[python_pbkdf2_iteration_count.md](python_pbkdf2_iteration_count.md) | 遇到弱密钥派生保护机制，详见：[bypassTricks.md#密钥导出函数漏洞](bypassTricks.md#密钥导出函数漏洞)
- 使用已弃用的 pycrypto 库替代 cryptography，详见：[python_deprecated_pycrypto.md](python_deprecated_pycrypto.md) | 遇到过时算法保护机制，详见：[bypassTricks.md#算法选择漏洞](bypassTricks.md#算法选择漏洞)

**Go**
- 密钥派生使用 PBKDF2 但迭代次数不足，详见：[go_pbkdf2_weak_iteration.md](go_pbkdf2_weak_iteration.md) | 遇到弱密钥派生保护机制，详见：[bypassTricks.md#密钥导出函数漏洞](bypassTricks.md#密钥导出函数漏洞)
- AES 加密时 IV 不随机或使用零 IV，详见：[go_aes_zero_iv.md](go_aes_zero_iv.md) | 遇到 IV 重用保护机制，详见：[bypassTricks.md#iv初始化向量重用](bypassTricks.md#iv初始化向量重用)
- 使用 ECB 模式进行数据加密，详见：[go_ecb_cipher_usage.md](go_ecb_cipher_usage.md) | 遇到 ECB 模式保护机制，详见：[bypassTricks.md#ecb模式弱点](bypassTricks.md#ecb模式弱点)

**PHP**
- openssl_encrypt 使用 IV 但未正确生成随机 IV，详见：[php_openssl_encrypt_iv.md](php_openssl_encrypt_iv.md) | 遇到 IV 重用保护机制，详见：[bypassTricks.md#iv初始化向量重用](bypassTricks.md#iv初始化向量重用)
- 密钥派生使用 hash_pbkdf2 但参数配置不足，详见：[php_pbkdf2_weak_config.md](php_pbkdf2_weak_config.md) | 遇到弱密钥派生保护机制，详见：[bypassTricks.md#密钥导出函数漏洞](bypassTricks.md#密钥导出函数漏洞)
- 使用 mcrypt（已废弃库）进行加密而非 openssl，详见：[php_deprecated_mcrypt.md](php_deprecated_mcrypt.md) | 遇到过时算法保护机制，详见：[bypassTricks.md#算法选择漏洞](bypassTricks.md#算法选择漏洞)

**JavaScript / TypeScript**
- Node.js crypto createCipheriv 时 IV 不随机或重复，详见：[js_crypto_iv_reuse.md](js_crypto_iv_reuse.md) | 遇到 IV 重用保护机制，详见：[bypassTricks.md#iv初始化向量重用](bypassTricks.md#iv初始化向量重用)
- 使用 PBKDF2 派生密钥但迭代次数过少，详见：[js_pbkdf2_weak_iteration.md](js_pbkdf2_weak_iteration.md) | 遇到弱密钥派生保护机制，详见：[bypassTricks.md#密钥导出函数漏洞](bypassTricks.md#密钥导出函数漏洞)
- 使用 crypto-js 库在前端进行加密（不安全），详见：[ts_frontend_cryptojs_usage.md](ts_frontend_cryptojs_usage.md) | 遇到前端加密保护机制，详见：[bypassTricks.md#算法选择漏洞](bypassTricks.md#算法选择漏洞)

**C/C++**
- 对称加密密钥长度不足或初始化向量（IV）不随机，详见：[c_weak_iv_generation.md](c_weak_iv_generation.md) | 遇到 IV 重用保护机制，详见：[bypassTricks.md#iv初始化向量重用](bypassTricks.md#iv初始化向量重用)
- 使用 ECB 模式进行 AES 加密导致明文模式泄露，详见：[c_ecb_mode_usage.md](c_ecb_mode_usage.md) | 遇到 ECB 模式保护机制，详见：[bypassTricks.md#ecb模式弱点](bypassTricks.md#ecb模式弱点)
- 密钥派生函数使用不当（如 PBKDF2 迭代次数过少），详见：[c_weak_kdf_parameters.md](c_weak_kdf_parameters.md) | 遇到弱密钥派生保护机制，详见：[bypassTricks.md#密钥导出函数漏洞](bypassTricks.md#密钥导出函数漏洞)

**Rust**
- 使用 aes-cbc 时 IV 不随机或重复，详见：[rust_aes_cbc_iv_reuse.md](rust_aes_cbc_iv_reuse.md) | 遇到 IV 重用保护机制，详见：[bypassTricks.md#iv初始化向量重用](bypassTricks.md#iv初始化向量重用)
- 密钥派生使用 pbkdf2 但迭代次数不足，详见：[rust_pbkdf2_weak_params.md](rust_pbkdf2_weak_params.md) | 遇到弱密钥派生保护机制，详见：[bypassTricks.md#密钥导出函数漏洞](bypassTricks.md#密钥导出函数漏洞)
- 在内存中以明文形式存储密钥，缺乏内存保护机制，详见：[rust_key_material_in_memory.md](rust_key_material_in_memory.md) | 遇到密钥存储保护机制，详见：[bypassTricks.md#动作和时间泄露](bypassTricks.md#动作和时间泄露)

## 快速开始

### 步骤 0：理解项目功能与结构

**在开始审计之前，彻底理解项目的功能与结构，特别关注密码学相关的实现：**

- 查阅项目文档，重点关注加密、签名、密钥管理等说明
- 理解业务领域和核心功能，识别涉及密码学操作的场景
- 识别关键组件、模块及其关系，特别是加密模块、签名模块、密钥管理模块
- 梳理应用流程（重点：数据加密流程、密钥派生流程、密钥存储与加载流程、签名与验证流程）
- 识别关键业务功能（用户密码存储、数据库字段加密、API 签名、会话加密、通信加密等）
- 理解所用技术栈和框架（加密库类型和版本，如 OpenSSL、cryptography、crypto-js、bcrypt、argon2 等）
- 查阅配置文件以理解系统行为（加密算法配置、密钥派生参数、初始化向量生成策略、填充方案等）
- 定位加密操作位置（Cipher 初始化、加密函数调用、解密函数调用）
- 定位密钥生成与派生位置（密钥生成函数、PBKDF2/Bcrypt/Scrypt/Argon2 调用）
- 定位密钥存储位置（硬编码、配置文件、密钥管理系统、内存保护）
- 定位初始化向量生成位置（IV 生成方式、随机性来源）

**Early exit（早期退出）：**

在理解项目结构的过程中，如果发现项目不符合前面 **Early exit** 章节描述的条件（例如完全不涉及密码学操作、仅使用高层框架且不涉及底层配置），可立即退出该漏洞类型的审计，无需继续深入分析。

只有在确认项目存在密码学操作并获得足够的项目背景信息后，才继续查阅各漏洞类型的参考指南并开始有针对性的漏洞分析。

### 步骤 1：查阅密码学基础漏洞的参考指南

密码学漏洞审计分为两个层次，需要按顺序进行：

**第一步：审计通用密码学缺陷模式（所有项目必审）**

在 **通用密码学缺陷模式** 章节中，列举了所有涉及密码学操作的项目都必须审计的安全问题：
- 不安全的加密算法或模式（弱算法、ECB模式、无认证加密）
- 初始化向量（IV）使用不当（不随机、可预测、重复使用）
- 密钥管理缺陷（硬编码、存储不安全、长度不足）
- 密钥派生函数（KDF）参数不足（PBKDF2配置不当、未使用现代KDF）
- 不安全的哈希算法（MD5、SHA-1、过时算法）
- 随机数生成器不安全（弱RNG、可预测种子）
- 填充（Padding）实现错误（手动实现、Padding Oracle）
- 使用废弃或过时的密码学库（pycrypto、mcrypt等）

这些问题与编程语言无关，是密码学使用和配置层面的通用缺陷，任何有密码学操作的项目都需要检查。

**第二步：审计语言特定实现（根据项目语言选择性审计）**

在 **语言特定实现** 章节中，按编程语言组织了各语言密码学库的特定实现问题：
- 按编程语言分类（Java、Python、Go、PHP、JavaScript/TypeScript、C/C++、Rust）
- 列出该语言密码学库的典型误用模式和对应的参考文档链接

根据项目所用编程语言，仅需查找和审计对应语言章节中的漏洞场景。

### 步骤 2：深入学习具体的审计指南

根据 **通用密码学缺陷模式** 和 **语言特定实现** 章节中的引用，打开对应的具体审计指南文件（如 `crypto_ecb_mode_usage.md`、`java_cipher_iv_reuse.md`、`python_pbkdf2_iteration_count.md` 等）。这些文件主要包含三个核心部分：

1. **Details（详细说明）**：漏洞成因、危险代码与安全代码对比示例、快速定位技巧（核心操作定位和保护机制定位）
2. **Classify（分类研判）**：明确的研判标准，包括确认漏洞、判定误报、识别代码异味的具体条件
3. **Low risk（低风险场景）**：列举可以降低风险等级的场景和条件

通过学习这些具体指南，可以准确识别代码中的密码学实现漏洞，并进行有效的审计和评估。

## 核心审计原则

### 验证要求

- 必须根据实际源代码验证发现结果，而非仅依赖模式匹配
- 必须验证完整的漏洞利用链：入口（密码学操作）→ 参数配置 → 算法/模式选择 → 实现缺陷 → 安全影响
- 每一步都需要文件路径、函数名和行号的具体证据
- 考虑密码学库本身的安全性和版本（是否过时、已知漏洞等）

### 密码学审计清单

- 验证所有加密算法是否符合现代安全标准（AES-256、ChaCha20 等）
- 验证初始化向量（IV）是否为随机生成且不重复使用
- 验证密钥长度是否符合标准（128 位起，推荐 256 位）
- 验证加密模式是否安全（CBC、GCM、ChaCha20-Poly1305，避免 ECB）
- 验证密钥派生函数参数（PBKDF2 迭代次数≥600000，优先使用 Bcrypt/Scrypt/Argon2）
- 验证填充（Padding）实现是否正确（优先使用库内置，避免手动实现）
- 验证密钥存储是否安全（不硬编码、使用密钥管理系统、内存保护）
- 验证随机数生成器是否为密码学安全 RNG（避免 Math.random()、rand() 等弱 RNG）
- 绕过技巧，详见：[bypassTricks.md](bypassTricks.md)

# 输出要求

确认漏洞后，加载 `bug-report` 技能获取标准化报告格式，生成漏洞报告文件。

**加载技能**：`bug-report`

**输出路径**：`.workspace/findings/BUG-crypto-{file}-L{line}-{source}-{sink}.md`

**约束**：
- 每个漏洞必须生成独立的 BUG 文件，禁止合并或省略
- 漏洞报告格式严格遵循 `bug-report` 技能定义的模板
