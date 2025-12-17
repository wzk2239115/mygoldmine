---
name: csp-analyzer
description: 专业的审计工作流程，通过静态代码分析识别和验证内容安全策略（Content Security Policy, CSP）配置漏洞；重点关注检测 CSP 响应头配置不当或缺失，包括使用 unsafe-inline、unsafe-eval、过于宽松的白名单、默认策略设置不当、规则优先级混乱等导致 CSP 防护失效的问题，从而使得恶意脚本注入、样式注入、资源加载劫持等攻击成为可能；利用按编程语言组织的参考资料目录中的参考指南。
---

**Attention**
当项目中存在 Web 应用需要防护 XSS 攻击但未配置 CSP 响应头，或 CSP 配置过于宽松使用了 unsafe-inline、unsafe-eval、通配符等危险指令时，攻击者可绕过 CSP 防护从而注入和执行恶意脚本。此类问题常见于所有动态生成 HTML 的 Web 应用，尤其是涉及用户生成内容、富文本编辑器、多租户系统的模块。CSP 不仅是防护层，其配置本身也需要审计。

**Early exit**
若项目为纯 API 后端（无 HTML 生成）、所有内容完全静态、或明确不需要防护 XSS（如内网限制应用），则可快速退出对该漏洞类型的审计。

---

## 通用 CSP 配置缺陷模式（所有项目必审）

查看详细说明：[general.md](general.md)

快速概览及对应绕过技巧：
- 遇到 CSP 响应头缺失或未启用，详见：[bypassTricks.md#完全缺失-CSP-的绕过](bypassTricks.md#完全缺失-CSP-的绕过) 和 [bypassTricks.md#部分路由缺失-CSP-的绕过](bypassTricks.md#部分路由缺失-CSP-的绕过)
- 遇到使用不安全的 CSP 指令（unsafe-inline/unsafe-eval），详见：[bypassTricks.md#unsafe-inline-绕过技巧](bypassTricks.md#unsafe-inline-绕过技巧) 和 [bypassTricks.md#unsafe-eval-绕过技巧](bypassTricks.md#unsafe-eval-绕过技巧)
- 遇到白名单配置过于宽松，详见：[bypassTricks.md#白名单域名绕过](bypassTricks.md#白名单域名绕过) 和 [bypassTricks.md#通配符绕过](bypassTricks.md#通配符绕过)
- 遇到关键 CSP 指令缺失（default-src/script-src/style-src），详见：[bypassTricks.md#指令缺失的绕过](bypassTricks.md#指令缺失的绕过)
- 遇到 Nonce 或 Hash 机制实现不当，详见：[bypassTricks.md#Nonce-和-Hash-绕过](bypassTricks.md#Nonce-和-Hash-绕过)
- 遇到 CSP 报告机制缺失（无 report-uri/report-to），详见：[bypassTricks.md#Report-Only-模式绕过](bypassTricks.md#Report-Only-模式绕过)

---
**语言特定实现（根据项目语言选择性审计）**

以下漏洞场景与具体编程语言的 CSP 配置方式相关。根据项目所使用的编程语言，仅需审计对应语言章节中的漏洞模式。

**Java**
- 遇到 Spring Security 未配置 CSP 响应头或配置缺失关键指令，详见漏洞指南：[java_spring_security_no_csp.md](java_spring_security_no_csp.md)，绕过技巧详见：[bypassTricks.md#基于框架默认配置缺失的绕过](bypassTricks.md#基于框架默认配置缺失的绕过)
- 遇到 CSP 策略包含 unsafe-inline 或 unsafe-eval 导致防护绕过，详见漏洞指南：[java_csp_unsafe_directives.md](java_csp_unsafe_directives.md)，绕过技巧详见：[bypassTricks.md#unsafe-inline-绕过技巧](bypassTricks.md#unsafe-inline-绕过技巧) 和 [bypassTricks.md#unsafe-eval-绕过技巧](bypassTricks.md#unsafe-eval-绕过技巧)
- 遇到自定义 Filter 中 CSP 规则定义不当，使用通配符或过宽松的白名单，详见漏洞指南：[java_custom_csp_filter.md](java_custom_csp_filter.md)，绕过技巧详见：[bypassTricks.md#白名单域名绕过](bypassTricks.md#白名单域名绕过) 和 [bypassTricks.md#通配符绕过](bypassTricks.md#通配符绕过)

**Python**
- 遇到 Flask 应用未添加 CSP 响应头中间件，详见漏洞指南：[python_flask_missing_csp.md](python_flask_missing_csp.md)，绕过技巧详见：[bypassTricks.md#完全缺失-CSP-的绕过](bypassTricks.md#完全缺失-CSP-的绕过)
- 遇到 Django 中间件配置的 CSP 策略过于宽松，允许 unsafe-inline，详见漏洞指南：[python_django_csp_configuration.md](python_django_csp_configuration.md)，绕过技巧详见：[bypassTricks.md#unsafe-inline-绕过技巧](bypassTricks.md#unsafe-inline-绕过技巧)
- 遇到 CSP 规则中使用通配符或未限制脚本来源导致防护失效，详见漏洞指南：[python_csp_wildcard_source.md](python_csp_wildcard_source.md)，绕过技巧详见：[bypassTricks.md#通配符绕过](bypassTricks.md#通配符绕过) 和 [bypassTricks.md#白名单域名绕过](bypassTricks.md#白名单域名绕过)

**Go**
- 遇到 HTTP 处理器中缺失设置 Content-Security-Policy 响应头，详见漏洞指南：[go_handler_missing_csp.md](go_handler_missing_csp.md)，绕过技巧详见：[bypassTricks.md#完全缺失-CSP-的绕过](bypassTricks.md#完全缺失-CSP-的绕过)
- 遇到 CSP 策略配置包含 unsafe-inline 或使用通配符白名单，详见漏洞指南：[go_csp_unsafe_config.md](go_csp_unsafe_config.md)，绕过技巧详见：[bypassTricks.md#unsafe-inline-绕过技巧](bypassTricks.md#unsafe-inline-绕过技巧) 和 [bypassTricks.md#通配符绕过](bypassTricks.md#通配符绕过)
- 遇到 Gin/Echo 框架中间件未正确设置 CSP 响应头导致所有路由无保护，详见漏洞指南：[go_framework_csp_middleware.md](go_framework_csp_middleware.md)，绕过技巧详见：[bypassTricks.md#部分路由缺失-CSP-的绕过](bypassTricks.md#部分路由缺失-CSP-的绕过)

**PHP**
- 遇到应用中未通过 header() 函数设置 Content-Security-Policy 响应头，详见漏洞指南：[php_no_csp_header.md](php_no_csp_header.md)，绕过技巧详见：[bypassTricks.md#完全缺失-CSP-的绕过](bypassTricks.md#完全缺失-CSP-的绕过)
- 遇到 Laravel/Symfony 框架中 CSP 配置过于宽松或未启用，详见漏洞指南：[php_framework_csp_config.md](php_framework_csp_config.md)，绕过技巧详见：[bypassTricks.md#基于框架默认配置缺失的绕过](bypassTricks.md#基于框架默认配置缺失的绕过) 和 [bypassTricks.md#白名单域名绕过](bypassTricks.md#白名单域名绕过)
- 遇到 CSP 规则使用 unsafe-inline 或 unsafe-eval 导致脚本注入防护失效，详见漏洞指南：[php_csp_unsafe_inline.md](php_csp_unsafe_inline.md)，绕过技巧详见：[bypassTricks.md#unsafe-inline-绕过技巧](bypassTricks.md#unsafe-inline-绕过技巧) 和 [bypassTricks.md#unsafe-eval-绕过技巧](bypassTricks.md#unsafe-eval-绕过技巧)

**JavaScript / TypeScript**
- 遇到 Express 应用中缺失设置 Content-Security-Policy 响应头的中间件，详见漏洞指南：[js_express_missing_csp.md](js_express_missing_csp.md)，绕过技巧详见：[bypassTricks.md#完全缺失-CSP-的绕过](bypassTricks.md#完全缺失-CSP-的绕过)
- 遇到 Next.js 应用中响应头配置过于宽松或使用 unsafe-inline，详见漏洞指南：[ts_nextjs_csp_configuration.md](ts_nextjs_csp_configuration.md)，绕过技巧详见：[bypassTricks.md#unsafe-inline-绕过技巧](bypassTricks.md#unsafe-inline-绕过技巧) 和 [bypassTricks.md#白名单域名绕过](bypassTricks.md#白名单域名绕过)
- 遇到 CSP 规则中包含 unsafe-eval 导致动态脚本执行防护失效，详见漏洞指南：[js_csp_unsafe_eval.md](js_csp_unsafe_eval.md)，绕过技巧详见：[bypassTricks.md#unsafe-eval-绕过技巧](bypassTricks.md#unsafe-eval-绕过技巧)

**C/C++**
- 遇到未在 HTTP 响应中添加 Content-Security-Policy 响应头，详见漏洞指南：[c_missing_csp_header.md](c_missing_csp_header.md)，绕过技巧详见：[bypassTricks.md#完全缺失-CSP-的绕过](bypassTricks.md#完全缺失-CSP-的绕过)
- 遇到 CSP 策略配置过于宽松使用 unsafe-inline 或 unsafe-eval，详见漏洞指南：[c_unsafe_inline_in_csp.md](c_unsafe_inline_in_csp.md)，绕过技巧详见：[bypassTricks.md#unsafe-inline-绕过技巧](bypassTricks.md#unsafe-inline-绕过技巧) 和 [bypassTricks.md#unsafe-eval-绕过技巧](bypassTricks.md#unsafe-eval-绕过技巧)
- 遇到 CSP 指令中使用通配符（如 script-src * 或 script-src 'unsafe-inline'）导致防护失效，详见漏洞指南：[c_wildcard_csp_directive.md](c_wildcard_csp_directive.md)，绕过技巧详见：[bypassTricks.md#通配符绕过](bypassTricks.md#通配符绕过)

**Rust**
- 遇到 Actix-web 应用中缺失设置 CSP 响应头的中间件或在响应中添加，详见漏洞指南：[rust_actix_missing_csp.md](rust_actix_missing_csp.md)，绕过技巧详见：[bypassTricks.md#完全缺失-CSP-的绕过](bypassTricks.md#完全缺失-CSP-的绕过)
- 遇到 Rocket 框架响应头配置未包含安全的 CSP 策略，详见漏洞指南：[rust_rocket_csp_policy.md](rust_rocket_csp_policy.md)，绕过技巧详见：[bypassTricks.md#基于框架默认配置缺失的绕过](bypassTricks.md#基于框架默认配置缺失的绕过)
- 遇到 CSP 策略使用 unsafe-inline 或通配符导致防护绕过，详见漏洞指南：[rust_csp_unsafe_directives.md](rust_csp_unsafe_directives.md)，绕过技巧详见：[bypassTricks.md#unsafe-inline-绕过技巧](bypassTricks.md#unsafe-inline-绕过技巧) 和 [bypassTricks.md#通配符绕过](bypassTricks.md#通配符绕过)

## 快速开始

### 步骤 0：理解项目功能与结构

**在开始审计之前，彻底理解项目的功能与结构，特别关注 CSP 配置相关的实现：**

- 查阅项目文档，重点关注安全策略、内容分发等说明
- 理解业务领域和核心功能，识别涉及动态 HTML 生成的场景
- 识别关键组件、模块及其关系，特别是响应头设置模块、中间件配置、安全策略模块
- 梳理应用流程（重点：HTTP 响应生成流程、响应头设置流程、CSP 策略应用流程）
- 识别关键业务功能（动态页面生成、用户生成内容展示、富文本编辑、管理后台等）
- 理解所用技术栈和框架（Web 框架、CSP 库或中间件、安全配置方式等）
- 查阅配置文件以理解系统行为（CSP 策略定义、响应头配置、白名单规则等）
- 定位响应头设置位置（全局设置、路由级设置、控制器级设置）
- 定位 CSP 策略定义位置（配置文件、代码硬编码、动态生成）
- 定位 CSP 指令配置（script-src、style-src、img-src、default-src 等）
- 识别是否使用 CSP 框架或库（helmet.js、django-csp、symfony/security 等）

**Early exit（早期退出）：**

在理解项目结构的过程中，如果发现项目不符合前面 **Early exit** 章节描述的条件（例如纯 API 后端、完全静态内容、无 XSS 风险场景），可立即退出该漏洞类型的审计，无需继续深入分析。

只有在确认项目为动态 HTML 应用并需要防护 XSS 时，才继续查阅各漏洞类型的参考指南并开始有针对性的漏洞分析。

### 步骤 1：查阅 CSP 漏洞的参考指南

CSP 配置漏洞审计分为两个层次，需要按顺序进行：

**第一步：审计通用 CSP 配置缺陷模式（所有项目必审）**

在 **通用 CSP 配置缺陷模式** 章节中，列举了所有 Web 应用都必须审计的 CSP 配置问题：
- CSP 响应头缺失或未启用（完全缺失、部分路由缺失、仅 Report-Only 模式）
- 使用不安全的 CSP 指令（unsafe-inline、unsafe-eval）
- 白名单配置过于宽松（通配符、不可信域名、绕过风险）
- 关键 CSP 指令缺失（script-src、style-src、default-src 等缺失）
- Nonce 或 Hash 机制实现不当（nonce 可预测、hash 过期）
- CSP 报告机制缺失（无 report-uri/report-to）

这些问题与编程语言无关，是 CSP 策略配置层面的通用缺陷，任何 Web 应用都需要检查。

**第二步：审计语言特定实现（根据项目语言选择性审计）**

在 **语言特定实现** 章节中，按编程语言组织了各语言 CSP 配置方式的特定实现问题：
- 按编程语言分类（Java、Python、Go、PHP、JavaScript/TypeScript、C/C++、Rust）
- 列出该语言框架或库的 CSP 配置典型缺陷和对应的参考文档链接

根据项目所用编程语言，仅需查找和审计对应语言章节中的漏洞场景。

### 步骤 2：深入学习具体的审计指南

根据 **通用 CSP 配置缺陷模式** 和 **语言特定实现** 章节中的引用，打开对应的具体审计指南文件（如 `csp_header_missing.md`、`java_spring_security_no_csp.md`、`python_flask_missing_csp.md` 等）。这些文件主要包含三个核心部分：

1. **Details（详细说明）**：漏洞成因、危险代码与安全代码对比示例、快速定位技巧（核心操作定位和保护机制定位）
2. **Classify（分类研判）**：明确的研判标准，包括确认漏洞、判定误报、识别代码异味的具体条件
3. **Low risk（低风险场景）**：列举可以降低风险等级的场景和条件

通过学习这些具体指南，可以准确识别代码中的 CSP 配置缺陷，并进行有效的审计和评估。

## 审计等级定义

CSP 配置漏洞审计采用分层的审计等级制度，根据响应头设置和指令配置来指导审计深度。

| 等级 | 名称 | 时间 | 配置特征 |
|------|------|------|---------|
| **L0** | 快速跳过 | 1-2 分钟 | 完整 CSP + 安全指令：无 unsafe-inline/eval，使用 nonce/hash，明确的 script-src/style-src |
| **L1** | 快速扫描 | 3-5 分钟 | 有 CSP 但需确认：关键指令存在，需验证白名单范围和是否有危险指令 |
| **L2** | 跳读 | 5-10 分钟 | 部分配置：指令可能缺失或配置宽松（如 `https:` 太通用），需验证完整性 |
| **L3** | 逐行读 | 15-30 分钟 | 明显缺陷：使用 unsafe-inline/eval、通配符、或完全缺失 CSP，需深度分析 |
| **L4** | 跨模块追踪 | 30-60 分钟 | 复杂配置：多位置设置、动态 nonce、中间件链式处理、配置冲突 |

### 快速判断流程

**第 1 步：是否设置 CSP 响应头？**
- 完全或部分缺失 → **L3+**
- 仅 Report-Only 模式 → 中等风险，需深度分析
- 已设置 → 继续第 2 步

**第 2 步：关键指令配置如何？**
- 使用 `unsafe-inline`/`unsafe-eval`/`*` → **L3+**
- 明确的安全来源（如 `'self'`、具体域名）→ 继续第 3 步
- 配置部分/宽松（如 `https:`）→ **L2**

**第 3 步：配置组织方式？**
- 单一全局配置 → **L0-L1**
- 多位置设置/动态 nonce → **L3-L4**

### 各等级操作指南

**L0**：完整安全配置
```
default-src 'self';
script-src 'self' 'nonce-abc123';
style-src 'self' 'nonce-xyz789';
img-src 'self' https:;  // 具体来源，无通配符
```

**L1**：有 CSP，快速验证
- 所有主要路由都有 CSP 吗？
- 检查关键指令：script-src、style-src 是否存在？
- 扫描危险关键词：unsafe-inline、unsafe-eval、`*`

**L2**：部分配置，需核实
- 指令是否完整（default-src、script-src、style-src 等）？
- 白名单是否过于宽松（`https:`、`http:`、多个域名）？
- nonce/hash 是否正确使用？
- 是否配置了 report-uri/report-to？

**L3**：明显缺陷，深度分析
```
// ❌ 危险配置
script-src 'unsafe-inline';    // XSS 防护失效
style-src 'unsafe-inline';
script-src *;                   // 允许任意来源
script-src 'unsafe-eval';       // 动态脚本执行
// 完全缺失 CSP 响应头
```
追踪响应头在哪设置、是否对所有响应应用、是否存在绕过路由

**L4**：复杂配置，完整追踪
- 响应头设置链路：全局中间件 → 路由中间件 → 控制器 → 模板
- 多位置配置是否一致？是否有冲突覆盖？
- 动态 nonce 生成：随机性是否足够？应用位置是否正确？
- 配置冲突示例：全局 `script-src 'self'`，路由覆盖为 `'unsafe-inline'`

### 审计等级应用

```markdown
| 场景 | 等级 | 说明 |
|------|------|------|
| 完整安全 + nonce | L0 | 无风险 |
| 有 CSP + 明确指令 | L1 | 验证配置 |
| 指令缺失或宽松 | L2 | 验证完整性 |
| 使用 unsafe-inline/eval | L3 | 高风险深度分析 |
| 完全或部分缺失 | L3 | 高风险深度分析 |
| 多位置/动态 nonce | L4 | 完整链路追踪 |
```

## 核心审计原则

### 验证要求

- 必须根据实际源代码验证发现结果，而非仅依赖模式匹配
- 必须验证完整的 CSP 防护链：HTTP 响应 → 响应头配置 → CSP 指令 → 白名单 → 防护有效性
- 每一步都需要文件路径、函数名和行号的具体证据
- 考虑框架和项目中实现的自动安全防护

### CSP 审计检查清单

**必须检查项：**
- [ ] 是否设置了 Content-Security-Policy 响应头
- [ ] 是否定义了 default-src 指令（作为后备）
- [ ] 是否为 script-src 显式指定安全来源（避免 'unsafe-inline' 和 'unsafe-eval'）
- [ ] 是否为 style-src 显式指定安全来源（避免 'unsafe-inline'）
- [ ] 是否限制了 img-src、media-src、frame-src 等其他资源来源
- [ ] 是否使用了 nonce 或 hash 而非 'unsafe-inline'（对于内联脚本）
- [ ] 是否配置了 report-uri 或 report-to 用于 CSP 违规报告

**高风险指令：**
- [ ] 避免使用 script-src * 或 script-src 'unsafe-inline'
- [ ] 避免使用 style-src 'unsafe-inline'（除非必要且使用 nonce/hash）
- [ ] 避免使用通配符 * 作为来源白名单
- [ ] 避免使用 'unsafe-eval'（脚本执行时）
- [ ] 避免过于宽松的 connect-src（通常用于 fetch、XHR）

**可选但推荐：**
- [ ] 配置 Strict-Transport-Security（HSTS）配合 CSP
- [ ] 在开发阶段使用 Content-Security-Policy-Report-Only 进行测试
- [ ] 为不同页面类型配置不同的 CSP 策略

**常见 CSP 绕过技巧参考：**
- 遇到完全缺失 CSP 的情况，详见：[bypassTricks.md#完全缺失-CSP-的绕过](bypassTricks.md#完全缺失-CSP-的绕过)
- 遇到部分路由缺失 CSP 的情况，详见：[bypassTricks.md#部分路由缺失-CSP-的绕过](bypassTricks.md#部分路由缺失-CSP-的绕过)
- 遇到 unsafe-inline 保护机制，详见：[bypassTricks.md#unsafe-inline-绕过技巧](bypassTricks.md#unsafe-inline-绕过技巧)
- 遇到 unsafe-eval 保护机制，详见：[bypassTricks.md#unsafe-eval-绕过技巧](bypassTricks.md#unsafe-eval-绕过技巧)
- 遇到白名单域名保护机制，详见：[bypassTricks.md#白名单域名绕过](bypassTricks.md#白名单域名绕过)
- 遇到通配符保护机制，详见：[bypassTricks.md#通配符绕过](bypassTricks.md#通配符绕过)
- 遇到关键 CSP 指令缺失的情况，详见：[bypassTricks.md#指令缺失的绕过](bypassTricks.md#指令缺失的绕过)
- 遇到 Nonce 或 Hash 保护机制，详见：[bypassTricks.md#Nonce-和-Hash-绕过](bypassTricks.md#Nonce-和-Hash-绕过)
- 遇到 Report-Only 模式，详见：[bypassTricks.md#Report-Only-模式绕过](bypassTricks.md#Report-Only-模式绕过)
- 遇到基于框架默认配置的保护，详见：[bypassTricks.md#基于框架默认配置缺失的绕过](bypassTricks.md#基于框架默认配置缺失的绕过)
- 遇到 JSONP 端点保护机制，详见：[bypassTricks.md#JSONP-端点绕过](bypassTricks.md#JSONP-端点绕过)
- 遇到 AngularJS 等前端框架保护，详见：[bypassTricks.md#AngularJS-CSP-绕过](bypassTricks.md#AngularJS-CSP-绕过)
- 遇到基于路径的 CSP 策略，详见：[bypassTricks.md#路径遍历绕过-CSP](bypassTricks.md#路径遍历绕过-CSP)
- 遇到 base-uri 指令缺失，详见：[bypassTricks.md#base-uri-绕过](bypassTricks.md#base-uri-绕过)
- 遇到使用 CDN 资源的白名单，详见：[bypassTricks.md#CDN-资源绕过](bypassTricks.md#CDN-资源绕过)

完整绕过技巧索引，详见：[bypassTricks.md](bypassTricks.md)

# 输出要求

确认漏洞后，加载 `bug-report` 技能获取标准化报告格式，生成漏洞报告文件。

**加载技能**：`bug-report`

**输出路径**：`.workspace/findings/BUG-csp-{file}-L{line}-{source}-{sink}.md`

**约束**：
- 每个漏洞必须生成独立的 BUG 文件，禁止合并或省略
- 漏洞报告格式严格遵循 `bug-report` 技能定义的模板
