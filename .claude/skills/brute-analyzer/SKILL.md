---
name: brute-analyzer
description: 专业的审计工作流程，通过静态代码分析识别和验证暴力破解（Brute Force）风险；重点关注检测未对身份认证、权限验证、资源访问等敏感操作实施有效的防护机制，包括缺失或不当的速率限制、账号锁定机制、验证码/多因素认证、延迟、IP 黑名单、分布式攻击防护等，从而导致攻击者可通过穷举尝试绕过身份认证、破解密码、枚举有效账号、转账码验证等安全问题；利用按编程语言组织的参考资料目录中的参考指南。
---

**Attention**
当项目中存在身份认证、权限校验、验证码验证、一次性密码（OTP）校验等需要防止穷举的关键操作，但未实施或实施不当速率限制（绕过详见 [bypassTricks.md#速率限制绕过](bypassTricks.md#速率限制绕过)）、账号锁定（绕过详见 [bypassTricks.md#时间延迟利用](bypassTricks.md#时间延迟利用)）、延迟退避、验证码生成与校验等防护机制时，即可能触发暴力破解漏洞。此类问题通常出现在登录接口、密码重置、邮箱验证码、支付密码、两步验证、API 密钥生成等模块中，攻击成本低但危害严重。

**Early exit**
若项目完全不涉及身份认证、权限校验或任何需要防止穷举的业务逻辑（例如无登录功能、无验证流程、无敏感操作），则可快速退出对该漏洞类型的审计。

---

## 通用防护缺陷模式（所有项目必审）

查看详细说明：[general.md](general.md)

快速概览：速率限制缺失或配置不当（绕过详见 [bypassTricks.md#速率限制绕过](bypassTricks.md#速率限制绕过)）、账号锁定机制缺失或可绕过（绕过详见 [bypassTricks.md#时间延迟利用](bypassTricks.md#时间延迟利用)）、验证码生成或验证缺陷、OTP/2FA 验证防护不足、分布式环境状态同步问题

---
**语言特定实现（根据项目语言选择性审计）**

以下漏洞场景与具体编程语言的防护机制实现相关。根据项目所使用的编程语言，仅需审计对应语言章节中的漏洞模式。

**Java**
- Spring Security 登录过滤器未配置防暴力破解机制，详见：[java_spring_auth_brute_force.md](java_spring_auth_brute_force.md)
- 登录接口缺乏速率限制导致暴力破解，详见：[Java_LoginBruteForceNoLimit.md](Java_LoginBruteForceNoLimit.md)
- 验证码验证逻辑缺陷（校验后不删除、可重复使用），详见：[java_captcha_reuse.md](java_captcha_reuse.md)
- 密码重置功能中的验证码或链接缺乏时间限制和次数限制，详见：[java_password_reset_brute_force.md](java_password_reset_brute_force.md)
- 密码重置功能暴力破解漏洞，详见：[java_password_reset_brute.md](java_password_reset_brute.md)

**Python**
- Django 登录视图缺乏速率限制中间件，详见：[python_django_login_brute_force.md](python_django_login_brute_force.md)
- 验证码存储在 session 中但未设置过期时间或尝试次数限制，详见：[python_session_captcha_brute.md](python_session_captcha_brute.md)
- OTP 验证码尝试次数无限制或次数限制易绕过，详见：[python_otp_brute_force.md](python_otp_brute_force.md)

**Go**
- HTTP 处理器中登录端点缺少速率限制中间件配置，详见：[go_http_login_rate_limit.md](go_http_login_rate_limit.md)
- 验证码生成使用不安全的随机源（如 rand 包未正确初始化），详见：[go_weak_random_captcha.md](go_weak_random_captcha.md)
- 分布式系统中账号锁定状态未正确同步，导致锁定可被绕过，详见：[go_distributed_lockout_sync.md](go_distributed_lockout_sync.md)

**PHP**
- Laravel 登录控制器未使用 ThrottleRequests 中间件或配置过宽松，详见：[php_laravel_login_throttle.md](php_laravel_login_throttle.md)
- 验证码存储在 $_SESSION 中但未设置校验次数限制，详见：[php_captcha_verification_limit.md](php_captcha_verification_limit.md)
- 两步验证（2FA）码验证允许无限重试，详见：[php_2fa_brute_force.md](php_2fa_brute_force.md)

**JavaScript / TypeScript (Node.js)**
- Express 登录路由缺乏速率限制或中间件配置错误，详见：[js_express_rate_limit_bypass.md](js_express_rate_limit_bypass.md)
- NestJS 认证守卫中验证码验证后未标记为已用，详见：[ts_captcha_not_invalidated.md](ts_captcha_not_invalidated.md)
- Redis 缓存中的限流计数器易过期或未正确同步，详见：[js_redis_rate_limit_sync.md](js_redis_rate_limit_sync.md)

**C/C++**
- 登录接口缺失频率限制或限制易绕过，详见：[c_login_brute_force.md](c_login_brute_force.md)
- 验证码生成算法弱或可预测，导致可被暴力枚举，详见：[c_weak_captcha_generation.md](c_weak_captcha_generation.md)
- 账号锁定机制缺失或可被绕过（如通过改变用户标识），详见：[c_account_lockout_bypass.md](c_account_lockout_bypass.md)

**Rust**
- Actix-web 路由处理中缺少速率限制 middleware 配置，详见：[rust_actix_rate_limit.md](rust_actix_rate_limit.md)
- 验证码使用不安全的随机源或生成逻辑可预测，详见：[rust_weak_captcha_generation.md](rust_weak_captcha_generation.md)
- 分布式 Rust 服务中账号锁定状态使用本地内存存储，导致跨实例锁定失效，详见：[rust_distributed_account_lockout.md](rust_distributed_account_lockout.md)

## 快速开始

### 步骤 0：理解项目功能与结构

**在开始审计之前，彻底理解项目的功能与结构，特别关注身份认证和防护机制相关的实现：**

- 查阅项目文档，重点关注身份认证、验证、限流防护机制说明
- 理解业务领域和核心功能，识别涉及身份认证和验证的场景
- 识别关键组件、模块及其关系，特别是认证模块、限流中间件、验证码生成与验证模块
- 梳理应用流程（重点：登录流程、验证流程、限流与限速机制、账号锁定流程）
- 识别关键业务功能（用户登录、密码重置、邮箱验证、OTP 验证、两步验证、支付密码等）
- 理解所用技术栈和框架（Web 框架、认证框架、限流库、缓存中间件等）
- 查阅配置文件以理解系统行为（速率限制配置、账号锁定策略、验证码生成规则、IP 黑名单等）
- 定位认证入口（登录接口、权限校验接口、验证接口）
- 定位限流与限速机制位置（限流中间件、装饰器、拦截器、手动实现的计数逻辑）
- 定位验证码生成与校验位置（生成函数、存储位置、校验逻辑、过期机制）
- 定位账号锁定机制位置（锁定触发条件、持久化存储、解锁机制）

**Early exit（早期退出）：**

在理解项目结构的过程中，如果发现项目不符合前面 **Early exit** 章节描述的条件（例如完全无身份认证、无验证流程、无敏感操作），可立即退出该漏洞类型的审计，无需继续深入分析。

只有在确认项目存在身份认证或需要防止穷举的操作并获得足够的项目背景信息后，才继续查阅各漏洞类型的参考指南并开始有针对性的漏洞分析。

### 步骤 1：查阅暴力破解漏洞的参考指南

暴力破解漏洞审计分为两个层次，需要按顺序进行：

**第一步:审计通用防护缺陷模式（所有项目必审）**

在 **通用防护缺陷模式** 章节中，列举了所有有身份认证或需要防穷举的项目都必须审计的防护缺陷：
- 速率限制缺失或配置不当（认证端点缺乏限制、限流规则易绕过），绕过详见 [bypassTricks.md#速率限制绕过](bypassTricks.md#速率限制绕过)
- 账号锁定机制缺失或可绕过（锁定机制缺失、锁定状态未同步），绕过详见 [bypassTricks.md#时间延迟利用](bypassTricks.md#时间延迟利用)
- 验证码生成或验证缺陷（生成算法弱、验证逻辑缺陷）
- OTP/2FA 验证防护不足（尝试次数无限制）
- 分布式环境状态同步问题（限流或锁定状态未同步）

这些问题与编程语言无关，是暴力破解防护机制设计和实现层面的通用缺陷，任何有认证或验证功能的项目都需要检查。

**第二步：审计语言特定实现（根据项目语言选择性审计）**

在 **语言特定实现** 章节中，按编程语言组织了各语言防护机制的特定实现问题：
- 按编程语言分类（Java、Python、Go、PHP、JavaScript/TypeScript、C/C++、Rust）
- 列出该语言框架和库的典型防护缺陷模式和对应的参考文档链接

根据项目所用编程语言，仅需查找和审计对应语言章节中的漏洞场景。

### 步骤 2：深入学习具体的审计指南

根据 **通用防护缺陷模式** 和 **语言特定实现** 章节中的引用，打开对应的具体审计指南文件（如 `brute_login_no_rate_limit.md`、`java_spring_auth_brute_force.md`、`python_django_login_brute_force.md` 等）。这些文件主要包含三个核心部分：

1. **Details（详细说明）**：漏洞成因、危险代码与安全代码对比示例、快速定位技巧（核心操作定位和保护机制定位）
2. **Classify（分类研判）**：明确的研判标准，包括确认漏洞、判定误报、识别代码异味的具体条件
3. **Low risk（低风险场景）**：列举可以降低风险等级的场景和条件

通过学习这些具体指南，可以准确识别代码中的漏洞模式，并进行有效的审计和评估。

## 审计等级定义

暴力破解漏洞审计采用分层的审计等级制度，根据防护机制的完备性来指导审计深度。

| 等级 | 名称 | 时间 | 防护情况 |
|------|------|------|---------|
| **L0** | 快速跳过 | 1-2 分钟 | 完整防护：速率限制 + 账号锁定 + 验证码/2FA，配置合理 |
| **L1** | 快速扫描 | 3-5 分钟 | 有防护但需确认配置有效性和覆盖范围 |
| **L2** | 跳读 | 5-10 分钟 | 基础防护但可能缺失或部分不一致；需验证端点覆盖和分布式同步 |
| **L3** | 逐行读 | 15-30 分钟 | 防护缺失或明显缺陷；直接拼接、易绕过或未应用到所有端点 |
| **L4** | 跨模块追踪 | 30-60 分钟 | 链路复杂：多文件多端点、分布式环境状态同步问题 |

### 快速判断流程

**第 1 步：是否存在认证/验证操作？**
- 登录、密码重置、验证码、OTP、2FA 等
- 无则 L0 跳过 | 有则继续第 2 步

**第 2 步：是否有防护机制？**
- 无防护 → **L3+**
- 有防护 → 继续第 3 步

**第 3 步：防护配置和链路复杂度**
- 完整配置 + 单点 → **L0-L1**
- 配置部分/需验证 → **L2**
- 跨多个文件/分布式 → **L3-L4**

### 各等级操作指南

**L0**：完整防护（速率限制 5 次/分钟 + 账号锁定 15 分钟 + 验证码）且无明显绕过 → 记录为安全

**L1**：防护存在，快速验证：
- 速率限制参数（阈值、时间窗口、IP 或账号范围），绕过详见 [bypassTricks.md#速率限制绕过](bypassTricks.md#速率限制绕过)
- 账号锁定机制和解锁逻辑，绕过详见 [bypassTricks.md#时间延迟利用](bypassTricks.md#时间延迟利用)
- 验证码生成和验证逻辑

**L2**：防护部分，需核实：
- 所有认证/验证端点是否都有防护？
- 配置是否过于宽松（如 100 次/分钟）？
- 分布式环境中限流状态是否正确同步？

**L3**：防护缺陷，深度分析：
- 完全或部分缺失防护
- 使用可绕过的防护（如仅基于 IP、可通过改变账号绕过），IP 绕过详见 [bypassTricks.md#速率限制绕过](bypassTricks.md#速率限制绕过)
- 验证码可预测、可重用或缺时间限制
- 追踪完整防护链路和绕过方式

**L4**：复杂链路，完整追踪：
- 防护跨多个文件/模块/框架
- 分布式环境中的多实例防护同步问题
- 例：实例 A 检查 Redis，实例 B 检查本地内存 → 可绕过

### 审计等级应用

```markdown
| 场景 | 等级 | 说明 |
|------|------|------|
| 完整防护 + 合理配置 | L0 | 无风险 |
| 有防护 + 需确认 | L1 | 快速验证配置 |
| 部分防护 | L2 | 验证覆盖范围 |
| 无防护或易绕过 | L3 | 高风险深度分析 |
| 多模块/分布式 | L4 | 完整链路追踪 |
```

## 核心审计原则

### 验证要求

- 必须根据实际源代码验证发现结果，而非仅依赖模式匹配
- 必须验证完整的漏洞利用链：入口（认证/验证请求）→ 限流/限速机制 → 防护缺失或绕过 → 穷举成功 → 影响
- 每一步都需要文件路径、函数名和行号的具体证据
- 考虑框架和项目中实现的自动防护（速率限制、账号锁定、验证码、多因素认证等）
- 绕过技巧：
  - 速率限制绕过详见 [bypassTricks.md#速率限制绕过](bypassTricks.md#速率限制绕过)
  - 账号锁定和时间限制绕过详见 [bypassTricks.md#时间延迟利用](bypassTricks.md#时间延迟利用)
  - 账户枚举和检测回避详见 [bypassTricks.md#账户枚举和检测回避](bypassTricks.md#账户枚举和检测回避)
  - Token/Session 预测详见 [bypassTricks.md#token和session预测](bypassTricks.md#token和session预测)
  - 其他技巧详见 [bypassTricks.md](bypassTricks.md)

# 输出要求

确认漏洞后，加载 `bug-report` 技能获取标准化报告格式，生成漏洞报告文件。

**加载技能**：`bug-report`

**输出路径**：`.workspace/findings/BUG-brute-{file}-L{line}-{source}-{sink}.md`

**约束**：
- 每个漏洞必须生成独立的 BUG 文件，禁止合并或省略
- 漏洞报告格式严格遵循 `bug-report` 技能定义的模板
