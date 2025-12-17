---
name: authentication-jwt-analyzer
description: 专业的审计工作流程，通过静态代码分析识别和验证 JWT（JSON Web Token）认证相关漏洞；重点关注检测不安全的 JWT 实现，包括未验证签名、允许算法降级（如 "none" 算法）、使用弱密钥或硬编码密钥、未校验关键声明（exp/iss/aud）等，从而导致身份认证绕过、权限提升、会话劫持等安全问题；利用按编程语言组织的参考资料目录中的参考指南。
---

**Attention**

当项目中涉及基于 JWT（JSON Web Token）实现用户身份认证或授权功能时，若对令牌的签发、校验、解析等环节处理不当（如未验证签名、未校验 issuer/audience/exp 等声明、使用弱密钥或硬编码密钥、允许算法降级等），就可能导致 authentication_jwt 类漏洞。此类问题通常出现在认证中心、API 网关、用户登录/会话管理、单点登录（SSO）等模块中。

---
**Early exit**

**在开始审计之前，必须首先运行 JWT 扫描脚本完成初步检索**，以快速判断项目是否使用了 JWT 认证机制及相关库。这是审计流程的强制性第一步，不可跳过。

**调用方式：**

```python
# 获取当前工作目录（项目路径）
target_path = get_cwd()

# 运行 JWT 扫描脚本
scan_result = skill_run_command(path="bash", params=["scripts/scan.sh", target_path])
```

若项目代码中未使用 JWT 作为认证或授权机制（例如仅使用 Session/Cookie、OAuth2 access token（非 JWT 格式）、自定义 token 且无 JWT 结构），或完全未实现任何基于 token 的认证逻辑，则可快速退出对该漏洞类型的审计。

---

## 通用 JWT 认证漏洞模式（所有项目必审）

查看详细说明：[general.md](general.md)

快速概览：JWT 密钥管理漏洞（JWKS URI 验证不足、kid 注入、jku 参数攻击、密钥轮换不完整、密钥存储不安全）、JWT 声明验证绕过（exp/iss/aud 验证缺失）

查看详细说明：
- JWKS URI 验证漏洞，详见：[jwt_jwks_uri_validation.md](jwt_jwks_uri_validation.md)

---

**语言特定漏洞（根据项目语言选择性审计）**

以下漏洞场景与具体编程语言的 JWT 库实现相关。根据项目所使用的编程语言，仅需审计对应语言章节中的漏洞模式。

**Java**  
- 使用 JJWT、java-jwt 等库时允许 "none" 算法，绕过签名校验机制，详见：[Java_JWT_None_Algorithm.md](Java_JWT_None_Algorithm.md)  
- JWT 签名使用弱密钥或硬编码密钥，易被暴力破解或泄露，详见：[Java_JWT_Weak_Secret.md](Java_JWT_Weak_Secret.md)  
- 未校验 JWT 的 exp/iss/aud 等关键声明，导致过期令牌或伪造令牌被接受，详见：[Java_JWT_Missing_Claim_Validation.md](Java_JWT_Missing_Claim_Validation.md)  

**Python**  
- 使用 PyJWT、python-jose 等库时禁用或跳过签名验证，导致任意令牌被接受，详见：[Python_JWT_Signature_Bypass.md](Python_JWT_Signature_Bypass.md)  
- JWT 签名密钥硬编码在代码中或使用弱密钥，存在密钥泄露风险，详见：[Python_JWT_Hardcoded_Key.md](Python_JWT_Hardcoded_Key.md)  
- 解码 JWT 时忽略 exp/aud/iss 等声明校验，允许过期或伪造令牌通过，详见：[Python_JWT_Claim_Ignored.md](Python_JWT_Claim_Ignored.md)  

**Go**  
- 使用 jwt-go、golang-jwt 等库时允许客户端指定签名算法，导致算法降级攻击，详见：[Go_JWT_Algorithm_Switch.md](Go_JWT_Algorithm_Switch.md)  
- JWT 解析时未校验 exp（过期时间）声明，允许过期令牌继续使用，详见：[Go_JWT_No_Exp_Check.md](Go_JWT_No_Exp_Check.md)  
- JWT 签名使用静态密钥或硬编码密钥，缺乏密钥轮换机制，详见：[Go_JWT_Static_Secret.md](Go_JWT_Static_Secret.md)  

**JavaScript / TypeScript**  
- 使用 jsonwebtoken 库时签名密钥为空字符串或未设置，导致签名失效，详见：[JS_JWT_Empty_Secret.md](JS_JWT_Empty_Secret.md)  
- JWT 验证时未校验 issuer（签发者）声明，允许伪造来源的令牌通过，详见：[TS_JWT_No_Issuer_Validation.md](TS_JWT_No_Issuer_Validation.md)  
- JWT 解析时忽略 exp（过期时间）校验，允许过期令牌继续有效，详见：[JS_JWT_Exp_Ignored.md](JS_JWT_Exp_Ignored.md)  

**PHP**  
- 使用 firebase/php-jwt、lcobucci/jwt 等库时签名密钥硬编码在配置文件或代码中，详见：[PHP_JWT_Hardcoded_Secret.md](PHP_JWT_Hardcoded_Secret.md)  
- JWT 解码时未调用签名验证方法或跳过验证步骤，接受任意令牌，详见：[PHP_JWT_Missing_Signature_Verify.md](PHP_JWT_Missing_Signature_Verify.md)  
- 未校验 JWT 的 exp/aud/nbf 等时间和受众声明，允许无效令牌使用，详见：[PHP_JWT_Claim_Not_Checked.md](PHP_JWT_Claim_Not_Checked.md)  

**C/C++**  
- 手动解析 JWT payload 而跳过签名校验环节，直接信任令牌内容，详见：[C_JWT_Manual_Payload_Parse.md](C_JWT_Manual_Payload_Parse.md)  
- 使用轻量级 JWT 库时未调用签名验证函数或验证逻辑缺失，详见：[CPP_JWT_No_Signature_Check.md](CPP_JWT_No_Signature_Check.md)  
- JWT 解析时忽略 header 中的算法字段，未限制允许的签名算法类型，详见：[C_JWT_Algorithm_Ignored.md](C_JWT_Algorithm_Ignored.md)  

**Rust**  
- 使用 jsonwebtoken crate 时配置 Validation 不当，禁用关键校验项，详见：[Rust_JWT_Insecure_Decoding.md](Rust_JWT_Insecure_Decoding.md)  
- JWT 验证时未设置 exp/iss/aud 等必要声明的校验规则，接受无效令牌，详见：[Rust_JWT_Missing_Validation.md](Rust_JWT_Missing_Validation.md)  
- JWT 签名使用静态密钥或硬编码密钥，缺乏动态密钥管理机制，详见：[Rust_JWT_Static_Key.md](Rust_JWT_Static_Key.md)

## 快速开始

### 步骤 0：理解项目功能与结构

**在开始审计之前，彻底理解项目的功能与结构，特别关注 JWT 认证相关的实现：**

- 查阅项目文档，重点关注身份认证和授权机制说明
- 理解业务领域和核心功能，识别涉及用户身份验证的场景
- 识别关键组件、模块及其关系，特别是认证中心、API 网关、SSO 模块
- 梳理应用流程（重点：JWT 签发流程、JWT 校验流程、令牌刷新机制）
- 识别关键业务功能（用户登录、会话管理、权限验证、令牌续期等）
- 理解所用技术栈和框架（Web框架、JWT库类型和版本，如 JJWT、PyJWT、jwt-go、jsonwebtoken 等）
- 查阅配置文件以理解系统行为（JWT密钥配置、签名算法、过期时间、声明校验规则等）
- 定位 JWT 的生成位置（签发函数、密钥来源、算法选择）
- 定位 JWT 的验证位置（解码函数、签名校验逻辑、声明校验实现）
- 识别 JWT 传递方式（HTTP Header、Cookie、URL参数等）

**Early exit（早期退出）：**

**必须先执行前面 Early exit 章节中要求的扫描脚本**，根据扫描结果判断是否继续审计。如果扫描结果显示项目不符合条件（例如未使用 JWT 认证、未引入 JWT 库、无相关配置等），必须立即退出该漏洞类型的审计，无需继续深入分析。

只有在扫描脚本确认项目使用了 JWT 认证机制并获得足够的项目背景信息后，才继续查阅各漏洞类型的参考指南并开始有针对性的漏洞分析。

### 步骤 1：查阅 JWT 认证漏洞的参考指南

JWT 认证漏洞审计分为两个层次，需要按顺序进行：

**第一步：审计通用漏洞场景（所有项目必审）**

在 **通用漏洞场景** 章节中，列举了所有 JWT 项目都必须审计的安全问题：
- JWT 密钥管理漏洞（JWKS、kid、jku、密钥轮换、密钥存储）
- JWT 声明验证绕过（exp、iss、aud 等声明的校验）

这些问题与编程语言无关，是 JWT 协议层面的安全问题，任何使用 JWT 的项目都需要检查。

**第二步：审计语言特定漏洞（根据项目语言选择性审计）**

在 **语言特定漏洞** 章节中，按编程语言组织了各语言 JWT 库的特定实现问题：
- 按编程语言分类（Java、Python、Go、JavaScript/TypeScript、PHP、C/C++、Rust）
- 列出该语言 JWT 库的典型漏洞模式和对应的参考文档链接

根据项目所用编程语言，仅需查找和审计对应语言章节中的漏洞场景。

### 步骤 2：深入学习具体的审计指南

根据 **通用漏洞场景** 和 **语言特定漏洞** 章节中的引用，打开对应的具体审计指南文件（如 `jwt_jwks_uri_validation.md`、`Java_JWT_None_Algorithm.md`、`Python_JWT_Signature_Bypass.md` 等）。这些文件主要包含三个核心部分：

1. **Details（详细说明）**：漏洞成因、危险代码与安全代码对比示例、快速定位技巧（核心操作定位和保护机制定位）
2. **Classify（分类研判）**：明确的研判标准，包括确认漏洞、判定误报、识别代码异味的具体条件
3. **Low risk（低风险场景）**：列举可以降低风险等级的场景和条件

通过学习这些具体指南，可以准确识别代码中的漏洞模式，并进行有效的审计和评估。

## 审计等级定义

JWT 认证漏洞审计采用分层的审计等级制度，根据 JWT 实现的安全程度来指导审计深度。

| 等级 | 名称 | 时间 | JWT 实现特征 |
|------|------|------|---------|
| **L0** | 快速跳过 | 1-2 分钟 | 完整验证：签名校验 + 强密钥 + exp/iss/aud 校验，算法白名单 |
| **L1** | 快速扫描 | 3-5 分钟 | 有验证但需确认：签名校验存在，需验证密钥强度和声明校验 |
| **L2** | 跳读 | 5-10 分钟 | 部分验证：缺失关键声明校验或密钥管理有缺陷，需验证完整性 |
| **L3** | 逐行读 | 15-30 分钟 | 明显缺陷：无签名验证或允许 "none" 算法、硬编码密钥、关键声明缺失校验 |
| **L4** | 跨模块追踪 | 30-60 分钟 | 复杂链路：多处签发/验证、动态密钥、JWKS 验证、算法降级攻击 |

### 快速判断流程

**第 1 步：是否验证 JWT 签名？**
- 跳过签名验证或允许 "none" 算法 → **L3+**
- 有签名验证 → 继续第 2 步

**第 2 步：密钥管理如何？**
- 硬编码密钥或弱密钥 → **L2-L3**
- 强密钥（足够长度、随机生成）→ 继续第 3 步

**第 3 步：声明校验如何？**
- 无 exp/iss/aud 校验 → **L2-L3**
- 完整的声明校验 → **L0-L1**
- 多处验证逻辑不一致或 JWKS 验证缺陷 → **L3-L4**

### 各等级操作指南

**L0**：完整验证
```
✅ jwt.verify(token, secret, { algorithms: ['HS256'] });
✅ 校验 exp、iss、aud 声明
✅ 密钥强度足够（≥256 bits）
✅ 仅允许特定算法
```

**L1**：有验证，快速确认
- 是否对所有 JWT 都进行了签名验证？
- 密钥来自哪里？是否足够强？
- 是否校验了 exp 等关键声明？
- 是否限制了允许的算法？

**L2**：部分验证，需核实
- 签名验证是否完整（是否覆盖所有使用点）？
- 缺失哪些声明校验（exp/iss/aud/nbf）？
- 密钥如何管理（硬编码/文件/环境变量）？
- 是否实现了密钥轮换？

**L3**：明显缺陷，深度分析
```javascript
// ❌ 跳过签名验证
jwt.decode(token);  // 未验证
jwt.decode(token, {verify: false});

// ❌ 允许 "none" 算法
{algorithms: ['none', 'HS256']}

// ❌ 硬编码密钥
const secret = "hardcoded_secret";

// ❌ 缺失声明校验
jwt.verify(token, secret);  // 无 exp/iss 校验

// ❌ 算法未限制
jwt.verify(token, secret);  // 可接受任意算法
```
追踪完整的签发和验证流程，确认漏洞和绕过方式

**L4**：复杂链路，完整追踪
- JWT 签发：哪里生成，用什么密钥，设置了哪些声明？
- JWT 验证：哪些地方验证，验证逻辑是否一致？
- 多实例密钥同步：是否正确同步？
- JWKS 验证：是否完整验证（kid、jku、URI 安全性）？
- 算法降级：客户端是否可指定算法？

### 审计等级应用

```markdown
| 场景 | 等级 | 说明 |
|------|------|------|
| 完整验证 + 强密钥 + exp/iss | L0 | 无风险 |
| 有验证 + 需确认密钥强度 | L1 | 验证密钥和声明 |
| 缺失声明校验或密钥缺陷 | L2 | 验证完整性 |
| 无签名验证或 "none" 算法 | L3 | 高风险深度分析 |
| 硬编码密钥或缺失 exp 校验 | L3 | 高风险深度分析 |
| 多处验证不一致或 JWKS 缺陷 | L4 | 完整链路追踪 |
```

## 核心审计原则

### 验证要求

- 必须根据实际源代码验证发现结果，而非仅依赖模式匹配
- 必须验证完整的漏洞利用链：入口（不可信输入）→ 处理逻辑 → 危险操作 → 影响
- 每一步都需要文件路径、函数名和行号的具体证据
- 考虑框架和项目中实现的自动防护

### 常见保护机制及绕过方法

遇到以下保护机制时，参考 bypassTricks.md 对应章节的绕过技巧：

- **算法白名单限制**（仅允许特定算法）：详见 [算法混淆攻击](bypassTricks.md#算法混淆攻击)
- **签名强制验证**（不允许 none 算法）：详见 [算法改为 none](bypassTricks.md#算法改为-none)
- **非对称算法保护**（使用 RS256 等）：详见 [HMAC密钥替换为公钥](bypassTricks.md#hmac密钥替换为公钥详细操作步骤)
- **强密钥保护**（使用足够长度的随机密钥）：详见 [密钥攻击](bypassTricks.md#密钥攻击)
- **exp 过期时间校验**：详见 [时间和过期绕过](bypassTricks.md#时间和过期绕过)
- **JTI 唯一性校验**（防重放）：详见 [Token重用和重放](bypassTricks.md#token重用和重放)
- **kid/jku 参数验证**：详见 [Header注入和混淆](bypassTricks.md#header注入和混淆)
- **多服务独立密钥**：详见 [跨服务token复用](bypassTricks.md#跨服务token复用)

# 输出要求

确认漏洞后，加载 `bug-report` 技能获取标准化报告格式，生成漏洞报告文件。

**加载技能**：`bug-report`

**输出路径**：`.workspace/findings/BUG-auth-jwt-{file}-L{line}-{source}-{sink}.md`

**约束**：
- 每个漏洞必须生成独立的 BUG 文件，禁止合并或省略
- 漏洞报告格式严格遵循 `bug-report` 技能定义的模板
