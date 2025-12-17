---
name: csrf-analyzer
description: 专业的审计工作流程，通过静态代码分析识别和验证跨站请求伪造（CSRF）漏洞；重点关注检测Web应用中敏感操作未对请求来源合法性进行充分验证的问题，包括状态修改接口未实施Anti-CSRF Token、未验证Referer/Origin请求头、Cookie未设置SameSite属性、敏感操作未要求二次认证、Token生成可预测或未绑定用户会话、防护机制被错误禁用或豁免等，从而导致攻击者诱导已认证用户在不知情情况下执行密码修改、资金转账、权限变更等非预期敏感操作的安全问题；利用按编程语言组织的参考资料目录中的参考指南。
---
**Attention**
CSRF（跨站请求伪造）漏洞通常源于系统未对用户发起的敏感操作请求验证其来源合法性，攻击者可诱导用户在已认证状态下执行非预期操作。当项目中涉及用户身份认证且包含状态修改类操作（如修改密码、转账、资料变更等）的Web接口时，尤其需要重点审计是否实施了有效的CSRF防护机制，如使用Anti-CSRF Token、验证Referer/Origin头或采用SameSite Cookie属性等。

**重要提示：绕过技巧参考**
在审计过程中遇到各种 CSRF 防护机制时，请参考 [bypassTricks.md](bypassTricks.md) 获取详细的绕过技巧：
- **遇到 Token 验证** → 查看"令牌验证绕过"部分（令牌缺失验证、令牌验证不严格、预测或枚举令牌）
- **遇到 Content-Type 检查** → 查看"Content-Type绕过"部分（改变Content-Type、简化的Content-Type）
- **遇到 SameSite Cookie** → 查看"SameSite Cookie绕过"部分（SameSite=Lax绕过、SameSite=None不安全、Cookie未设置SameSite）
- **遇到 HTTP 方法限制** → 查看"HTTP方法绕过"部分（GET请求CSRF、HEAD和OPTIONS）
- **遇到 Origin/Referer 检查** → 查看"跨域和CORS绕过"部分（简单请求CSRF、错误的Origin检查）
- **遇到复杂场景** → 查看"隐藏表单和自动提交"、"Flash和旧技术CSRF"等部分

**Early exit**

**在开始审计之前，必须首先运行 CSRF 扫描脚本完成初步检索**，识别潜在的 CSRF 防护机制缺失或配置不当的风险点。这是审计流程的强制性第一步，不可跳过。

**调用方式：**

```python
# 获取当前工作目录（项目路径）
target_path = get_cwd()

# 运行 CSRF 扫描脚本
scan_result = skill_run_command(path="bash", params=["scripts/scan.sh", target_path])
```

**快速退出条件：**

若项目为纯静态网站、无用户会话认证机制、或所有敏感操作均通过无状态API（如基于JWT且无Cookie自动携带机制）实现，并明确不依赖浏览器自动附带凭证（如Cookie）进行身份验证，则可快速退出对该漏洞类型的审计。
---

## 通用 CSRF 漏洞模式（所有项目必审）

查看详细说明：[general.md](general.md)

快速概览：
- **CSRF Token 机制缺失或未启用** - 遇到此保护，详见 bypassTricks.md 的"令牌缺失验证"部分
- **Token 生成机制不安全**（可预测/未绑定会话/固定不变） - 遇到此保护，详见 bypassTricks.md 的"预测或枚举令牌"部分
- **Token 验证逻辑缺陷**（仅检查存在性/空值绕过/比对算法缺陷） - 遇到此保护，详见 bypassTricks.md 的"令牌验证不严格"部分
- **依赖不可靠的请求来源验证**（仅依赖 Referer/Origin） - 遇到此保护，详见 bypassTricks.md 的"错误的Origin检查"部分
- **Cookie 安全属性配置不当**（未设置 SameSite/属性配置不完整） - 遇到此保护，详见 bypassTricks.md 的"SameSite Cookie绕过"部分
- **敏感操作缺乏额外验证**（无二次认证/无用户交互确认）

---

**语言特定实现（根据项目语言选择性审计）**

以下漏洞场景与具体编程语言的 CSRF 防护实现方式相关。根据项目所使用的编程语言，仅需审计对应语言章节中的漏洞模式。

**Java**
- Spring Boot应用中通过csrf().disable()显式关闭Security默认的CSRF防护，详见：[java_SpringCsrfDisabled.md](java_SpringCsrfDisabled.md)  
- 自定义Filter或Interceptor实现Token校验时存在逻辑缺陷（如空值绕过、大小写不敏感），详见：[java_CustomTokenLogicFlaw.md](java_CustomTokenLogicFlaw.md)  
- Servlet中POST/PUT/DELETE等状态修改端点未添加CsrfFilter或未验证Token，详见：[java_MissingCsrfInStateChangingRequest.md](java_MissingCsrfInStateChangingRequest.md)

**Python**
- Django视图函数中对敏感操作（如用户资料更新、支付接口）使用@csrf_exempt装饰器豁免检查，详见：[python_DjangoCsrfExemptMisuse.md](python_DjangoCsrfExemptMisuse.md)  
- Flask应用未集成Flask-WTF或Flask-SeaSurf等CSRF防护扩展，表单提交缺少Token验证，详见：[python_FlaskMissingCsrfProtection.md](python_FlaskMissingCsrfProtection.md)  
- 自行实现Token校验逻辑时存在条件判断漏洞（如仅检查Token存在性而不验证值），详见：[python_ManualTokenCheckBypass.md](python_ManualTokenCheckBypass.md)

**Go**
- Gin/Echo框架中处理POST/PUT等状态修改请求时未使用gorilla/csrf等CSRF中间件，详见：[go_MissingCsrfMiddleware.md](go_MissingCsrfMiddleware.md)  
- 自行实现Token生成和验证机制时仅检查Token格式，未对比服务端存储的预期值，详见：[go_CustomTokenNotValidated.md](go_CustomTokenNotValidated.md)  
- 中间件配置中通过路径豁免规则跳过了关键业务端点（如/api/user/delete）的CSRF检查，详见：[go_MiddlewareSkippedForSensitiveRoute.md](go_MiddlewareSkippedForSensitiveRoute.md)

**PHP**
- 用户设置修改、文章发布等表单提交处理逻辑中未生成隐藏Token字段或未在服务端验证，详见：[php_MissingTokenInForm.md](php_MissingTokenInForm.md)  
- 使用md5(time())、uniqid()等弱随机方式生成Token，攻击者可预测或暴力破解，详见：[php_PredictableCsrfToken.md](php_PredictableCsrfToken.md)  
- Token存储在$_SESSION中但验证时未校验与当前用户会话的绑定关系，可跨会话复用，详见：[php_TokenNotTiedToSession.md](php_TokenNotTiedToSession.md)

**JavaScript**
- 前端表单提交敏感操作（如修改密码、删除账户）时未在请求中携带CSRF Token，详见：[js_FormWithoutCsrfToken.md](js_FormWithoutCsrfToken.md)  
- 使用fetch/XMLHttpRequest发起状态修改请求时未添加Token验证头，详见：[js_AjaxNoTokenValidation.md](js_AjaxNoTokenValidation.md)  
- 仅通过检查document.referrer判断请求来源，未实施Token机制，详见：[js_RelianceOnRefererAlone.md](js_RelianceOnRefererAlone.md)

**TypeScript**
- Angular应用中HttpClient未配置withXsrfConfiguration，状态变更API调用缺少Token，详见：[ts_MissingXsrfTokenInHttpClient.md](ts_MissingXsrfTokenInHttpClient.md)  
- Next.js/React应用中手动禁用或未启用框架提供的CSRF防护中间件，详见：[ts_FrameworkCsrfProtectionDisabled.md](ts_FrameworkCsrfProtectionDisabled.md)  
- 自定义Token生成后未与服务端用户会话进行绑定校验，可跨用户复用，详见：[ts_TokenNotBoundToSession.md](ts_TokenNotBoundToSession.md)

**C/C++**
- 使用Wt/CppCMS或自研HTTP服务处理用户操作请求时未在响应中生成和验证Token，详见：[cpp_NoTokenInStateChangingEndpoint.md](cpp_NoTokenInStateChangingEndpoint.md)  
- 仅通过解析HTTP_REFERER头判断请求来源（可被伪造或为空），未结合不可预测Token，详见：[cpp_RefererBasedCsrfProtection.md](cpp_RefererBasedCsrfProtection.md)  
- Token生成后存储在全局变量或共享内存中，未与用户Session ID绑定，多用户共享同一Token，详见：[cpp_TokenReusedAcrossSessions.md](cpp_TokenReusedAcrossSessions.md)

**Rust**
- Actix-web/Rocket应用中未使用actix-csrf或rocket_csrf等Guard保护状态修改路由，详见：[rust_MissingCsrfGuard.md](rust_MissingCsrfGuard.md)  
- 自定义Token验证逻辑中未将Token与请求上下文中的session_id或user_id进行关联校验，详见：[rust_TokenNotSessionBound.md](rust_TokenNotSessionBound.md)  
- 路由属性标记或中间件链配置错误，导致/admin/delete等关键端点绕过CSRF检查，详见：[rust_SensitiveRouteExcludedFromCsrfCheck.md](rust_SensitiveRouteExcludedFromCsrfCheck.md)

## 快速开始

### 步骤 0：理解项目功能与结构

**在开始审计之前，彻底理解项目的功能与结构，特别关注 CSRF 防护相关的实现：**

- 查阅项目文档，重点关注身份认证和会话管理机制说明
- 理解业务领域和核心功能，识别涉及状态修改的敏感操作场景
- 识别关键组件、模块及其关系，特别是用户认证、会话管理、表单处理模块
- 梳理应用流程（重点：用户登录流程、敏感操作请求流程、凭证传递机制）
- 识别关键业务功能（密码修改、资料更新、资金转账、权限变更、账户删除等状态修改操作）
- 理解所用技术栈和框架（Web框架、CSRF防护库类型和版本，如 Spring Security、Django CSRF、Flask-WTF、csurf、gorilla/csrf 等）
- 查阅配置文件以理解系统行为（CSRF防护配置、Token生成机制、SameSite Cookie属性、豁免路径规则等）
- 定位 CSRF Token 的生成位置（Token生成函数、随机性来源、与会话的绑定方式）
- 定位 CSRF Token 的验证位置（验证逻辑、中间件/过滤器配置、验证豁免条件）
- 识别凭证传递方式（Cookie、Session、Authorization Header 等）

**Early exit（早期退出）：**

**必须先执行前面 Early exit 章节中要求的扫描脚本**，根据扫描结果判断是否继续审计。如果扫描结果显示项目不符合条件（例如纯静态网站、无用户会话认证机制、所有敏感操作均通过无状态API且不依赖Cookie等），必须立即退出该漏洞类型的审计，无需继续深入分析。

只有在扫描脚本确认项目存在基于Cookie/Session的身份认证且包含状态修改操作，并获得足够的项目背景信息后，才继续查阅各漏洞类型的参考指南并开始有针对性的漏洞分析。

### 步骤 1：查阅 CSRF 漏洞的参考指南

CSRF 防护漏洞审计分为两个层次，需要按顺序进行：

**第一步：审计通用 CSRF 防护缺陷模式（所有项目必审）**

在 **通用 CSRF 防护缺陷模式** 章节中，列举了所有基于 Cookie/Session 认证的 Web 应用都必须审计的 CSRF 防护问题：
- **CSRF Token 机制缺失或未启用**（状态修改接口未验证、框架防护被禁用、敏感操作被豁免） - 遇到此问题，详见 bypassTricks.md 的"令牌缺失验证"部分
- **Token 生成机制不安全**（可预测、未绑定会话、固定不变） - 遇到此问题，详见 bypassTricks.md 的"预测或枚举令牌"部分
- **Token 验证逻辑缺陷**（仅检查存在性、空值绕过、比对算法缺陷） - 遇到此问题，详见 bypassTricks.md 的"令牌验证不严格"部分
- **依赖不可靠的请求来源验证**（仅依赖 Referer/Origin、缺乏多层防护） - 遇到此问题，详见 bypassTricks.md 的"错误的Origin检查"部分
- **Cookie 安全属性配置不当**（未设置 SameSite、属性配置不完整） - 遇到此问题，详见 bypassTricks.md 的"SameSite Cookie绕过"部分
- **敏感操作缺乏额外验证**（无二次认证、无用户交互确认）

这些问题与编程语言无关，是 CSRF 防护机制设计层面的通用缺陷，任何 Web 应用都需要检查。

**第二步：审计语言特定实现（根据项目语言选择性审计）**

在 **语言特定实现** 章节中，按编程语言组织了各语言 CSRF 防护实现方式的特定问题：
- 按编程语言分类（Java、Python、Go、PHP、JavaScript、TypeScript、C/C++、Rust）
- 列出该语言框架或库的 CSRF 防护典型缺陷和对应的参考文档链接

根据项目所用编程语言，仅需查找和审计对应语言章节中的漏洞场景。

### 步骤 2：深入学习具体的审计指南

根据 **Cases** 章节中的引用，打开对应编程语言和场景的具体审计指南文件（如 `java_SpringCsrfDisabled.md`、`python_DjangoCsrfExemptMisuse.md` 等）。这些文件主要包含三个核心部分：

1. **Details（详细说明）**：漏洞成因、危险代码与安全代码对比示例、快速定位技巧（核心操作定位和保护机制定位）
2. **Classify（分类研判）**：明确的研判标准，包括确认漏洞、判定误报、识别代码异味的具体条件
3. **Low risk（低风险场景）**：列举可以降低风险等级的场景和条件

通过学习这些具体指南，可以准确识别代码中的漏洞模式，并进行有效的审计和评估。

## 审计等级定义

CSRF 漏洞审计采用分层的审计等级制度，根据 CSRF 防护机制的完备性来指导审计深度。

| 等级 | 名称 | 时间 | CSRF 防护特征 |
|------|------|------|---------|
| **L0** | 快速跳过 | 1-2 分钟 | 完整防护：CSRF Token + SameSite Cookie + Referer 检查 |
| **L1** | 快速扫描 | 3-5 分钟 | 有防护 + 需确认：需验证所有状态改变操作是否都有 CSRF 保护 |
| **L2** | 跳读 | 5-10 分钟 | 部分防护：部分操作有 Token，需验证覆盖范围和绕过可能 |
| **L3** | 逐行读 | 15-30 分钟 | 无防护或明显缺陷：无 CSRF Token、仅 GET 请求、Token 不随机 |
| **L4** | 跨模块追踪 | 30-60 分钟 | 复杂链路：多站点、JSONP、CORS 配置、Flash/PDF XSS |

### 快速判断流程

**第 1 步：是否存在状态改变操作？**
- 无状态改变（仅只读） → L0 跳过
- 有状态改变 → 继续第 2 步

**第 2 步：是否有 CSRF Token？**
- 无 CSRF Token → **L3+**
- 有 CSRF Token → 继续第 3 步

**第 3 步：CSRF Token 是否正确实施？**
- 所有状态改变操作都有 Token → **L0-L1**
- 部分操作有 Token → **L2**
- Token 生成或验证有缺陷 → **L3-L4**

### 各等级操作指南

**L0**：完整防护
```java
// CSRF Token 验证
@PostMapping("/transfer")
@RequiresCsrfToken
public Response transfer(@CsrfToken String token, @RequestParam Long amount) {
    // 框架自动验证 token
}

// SameSite Cookie
Set-Cookie: session=abc; SameSite=Strict; Secure
```

**L1**：有防护 + 需确认
- 所有 POST/PUT/DELETE 操作是否都有 CSRF Token？（如有遗漏，详见 bypassTricks.md 的"HTTP方法绕过"）
- Token 是否随机生成且足够强？（如可预测，详见 bypassTricks.md 的"预测或枚举令牌"）
- Token 是否与会话绑定？（如未绑定，详见 bypassTricks.md 的"令牌验证不严格"）
- 是否设置了 SameSite Cookie？（如未设置，详见 bypassTricks.md 的"SameSite Cookie绕过"）

**L2**：部分防护
- 哪些操作有 CSRF 保护？哪些没有？
- Token 验证是否可被绕过（空 Token、任意 Token）？- 详见 bypassTricks.md 的"令牌验证绕过"部分
- 是否仅依赖 Referer 检查？- 详见 bypassTricks.md 的"错误的Origin检查"部分
- 是否有 CORS 配置问题？- 详见 bypassTricks.md 的"跨域和CORS绕过"部分

**L3**：无防护或明显缺陷
```java
// 无 CSRF 保护 - 详见 bypassTricks.md 的"令牌缺失验证"部分
@PostMapping("/delete")
public void deleteAccount() {  // 存在 CSRF 风险
    accountService.delete(getCurrentUser());
}

// 仅使用 GET 请求进行状态改变 - 详见 bypassTricks.md 的"GET请求CSRF"部分
@GetMapping("/transfer")  // GET 用于状态改变，存在 CSRF 风险
public void transfer(@RequestParam Long amount) {
    transferService.execute(amount);
}
```
完整分析状态改变操作和 CSRF 防护，追踪数据流，确认风险点

**L4**：复杂链路
- 多站点：子域名、跨域请求 - 详见 bypassTricks.md 的"跨域和CORS绕过"部分
- JSONP：是否可被利用进行 CSRF - 详见 bypassTricks.md 的"简单请求CSRF"部分
- CORS 配置：是否允许任意来源 - 详见 bypassTricks.md 的"跨域和CORS绕过"部分
- Flash/PDF XSS：是否可绕过 SameSite - 详见 bypassTricks.md 的"Flash和旧技术CSRF"部分
- WebSocket：是否有 Origin 检查 - 详见 bypassTricks.md 的"错误的Origin检查"部分

### 审计等级应用

```markdown
| 场景 | 等级 | 说明 |
|------|------|------|
| CSRF Token + SameSite | L0 | 无风险 |
| 有 Token + 需确认覆盖范围 | L1 | 验证所有操作 |
| 部分操作有 Token | L2 | 验证覆盖范围 |
| 无 CSRF Token | L3 | 高风险 |
| GET 用于状态改变 | L3 | 高风险 |
| 多站点或 CORS 问题 | L4 | 完整追踪 |
```

## 核心审计原则

### 验证要求

- 必须根据实际源代码验证发现结果，而非仅依赖模式匹配
- 必须验证完整的漏洞利用链：用户认证状态 → 状态修改请求 → CSRF防护缺失/绕过 → 影响
- 每一步都需要文件路径、函数名和行号的具体证据
- 考虑框架和项目中实现的自动防护
- **遇到 CSRF Token 保护机制，详见 bypassTricks.md 的"令牌验证绕过"部分**
- **遇到 SameSite Cookie 保护，详见 bypassTricks.md 的"SameSite Cookie绕过"部分**
- **遇到 Content-Type 检查，详见 bypassTricks.md 的"Content-Type绕过"部分**
- **遇到 Origin/Referer 检查，详见 bypassTricks.md 的"跨域和CORS绕过"部分**
- **遇到仅 POST 方法受保护，详见 bypassTricks.md 的"HTTP方法绕过"部分**

# 输出要求

确认漏洞后，加载 `bug-report` 技能获取标准化报告格式，生成漏洞报告文件。

**加载技能**：`bug-report`

**输出路径**：`.workspace/findings/BUG-csrf-{file}-L{line}-{source}-{sink}.md`

**约束**：
- 每个漏洞必须生成独立的 BUG 文件，禁止合并或省略
- 漏洞报告格式严格遵循 `bug-report` 技能定义的模板
