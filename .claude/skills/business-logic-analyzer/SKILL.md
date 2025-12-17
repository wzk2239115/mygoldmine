---
name: business-logic-analyzer
description: 专业的审计工作流程，通过静态代码分析识别和验证业务逻辑漏洞；重点关注检测业务流程中未对用户操作合法性、状态转换合理性、资源访问授权边界进行充分校验的问题，包括状态机跳转未校验前置条件、操作顺序可被绕过、资源归属未验证、优惠券/积分/配额可重复使用、并发操作下状态不一致、多步骤流程可跳过中间环节等，从而导致攻击者绕过预期流程、篡改操作顺序、滥用接口实现非预期行为等安全问题；利用按编程语言组织的参考资料目录中的参考指南。

---

**Attention**  
当业务逻辑未对用户操作的合法性、状态转换的合理性或资源访问的授权边界进行充分校验时，攻击者可能绕过预期流程、篡改操作顺序或滥用接口实现非预期行为。此类漏洞常见于涉及状态机（如订单、审批、支付）、权限控制（如角色切换、资源归属）、资源计费/配额、多步骤流程（如注册、验证、兑换）等模块中，需重点审计相关业务链路的状态校验、条件判断与权限检查逻辑。

**Early exit**
若项目为纯静态内容服务（如静态网站、无交互式后端）、或完全不包含任何用户驱动的状态变更、资源操作、流程控制逻辑（例如仅提供只读API且无任何业务规则），则可快速退出对该漏洞类型的审计。

**绕过技巧索引**
遇到保护机制时，可参考 [bypassTricks.md](bypassTricks.md) 中对应章节的绕过方法。

---

## 通用业务逻辑缺陷模式（所有项目必审）

查看详细说明：[general.md](general.md)

快速概览：
- 状态转换未校验前置条件（状态机跳转、多步骤流程绕过）
- 资源操作缺乏授权或归属验证（资源归属、配额限制），遇到整数边界检查详见：[bypassTricks.md - 整数溢出和下溢](bypassTricks.md#整数溢出和下溢)
- 并发竞态导致状态不一致（库存竞态、幂等性缺失），遇到锁/事务保护详见：[bypassTricks.md - 条件竞争和时间窗口](bypassTricks.md#条件竞争和时间窗口)
- 回调或异步操作缺乏来源验证（第三方回调、异步任务）
- 依赖客户端逻辑进行安全决策（客户端参数、前端状态），遇到类型检查详见：[bypassTricks.md - JavaScript类型混淆漏洞](bypassTricks.md#javascript类型混淆漏洞) 和 [类型混淆和类型强制转换](bypassTricks.md#类型混淆和类型强制转换)
- 条件判断逻辑不完整（边界条件、异常路径、不安全比较 CWE-1053），遇到负数/边界值检查详见：[bypassTricks.md - 业务逻辑黑洞](bypassTricks.md#业务逻辑黑洞)

---
**语言特定实现（根据项目语言选择性审计）**

以下漏洞场景与具体编程语言的业务逻辑实现相关。根据项目所使用的编程语言，仅需审计对应语言章节中的漏洞模式。

**Java**  
- 订单状态流转未校验操作顺序或前置条件，允许跳过支付等关键步骤，详见：[java_order_state_abuse.md](java_order_state_abuse.md)  
- 权限变更或角色切换逻辑存在缺陷，可通过特定操作序列实现权限提升，详见：[java_permission_escalation_via_logic_flaw.md](java_permission_escalation_via_logic_flaw.md)  
- 优惠券、积分或奖励兑换未实施去重机制，允许重复使用或并发滥用，详见：[java_coupon_reuse_without_dedup.md](java_coupon_reuse_without_dedup.md)  

**Python**  
- 多步骤表单或流程处理中参数未与会话状态绑定，可跳过中间验证步骤，详见：[python_form_step_bypass.md](python_form_step_bypass.md)  
- 条件分支判断逻辑覆盖不完整，存在边界情况或异常路径绕过校验，详见：[python_incomplete_condition_check.md](python_incomplete_condition_check.md)  
- 异步任务或定时任务未校验触发上下文，允许伪造触发来源或权限，详见：[python_async_task_context_spoofing.md](python_async_task_context_spoofing.md)  

**Go**  
- 支付或第三方回调处理未验证来源合法性（如签名、IP白名单），可被伪造触发，详见：[go_callback_logic_spoofing.md](go_callback_logic_spoofing.md)  
- 配额扣减、库存更新等操作存在并发竞态，允许超限使用或重复消费，详见：[go_quota_race_condition.md](go_quota_race_condition.md)  
- 微服务间状态协调逻辑不一致，部分服务状态更新失败后未回滚或补偿，详见：[go_state_inconsistency_in_orchestration.md](go_state_inconsistency_in_orchestration.md)  

**PHP**  
- 注册或登录流程中步骤校验不严格，可通过直接访问后续步骤绕过验证，详见：[php_registration_step_skip.md](php_registration_step_skip.md)  
- 奖励兑换或商品购买未实施幂等性控制，重复提交导致资源重复发放，详见：[php_reward_redemption_duplication.md](php_reward_redemption_duplication.md)  
- 文件上传审批流程中权限检查与操作执行分离，可在审批前绕过限制，详见：[php_upload_approval_bypass.md](php_upload_approval_bypass.md)  

**JavaScript / TypeScript**  
- 前端状态管理依赖本地存储或内存状态，可被用户篡改后绕过业务校验，详见：[js_frontend_state_tampering.md](js_frontend_state_tampering.md)  
- SPA 路由守卫或权限控制逻辑不完整，存在路径或条件分支可绕过检查，详见：[ts_route_guard_incomplete.md](ts_route_guard_incomplete.md)  
- 将客户端业务逻辑（如价格计算、权限判断）误用于服务端决策，详见：[js_client_side_authorization_reliance.md](js_client_side_authorization_reliance.md)  

**C/C++**  
- 状态机跳转未校验前置条件，允许非法状态转换，详见：[c_state_transition_bypass.md](c_state_transition_bypass.md)  
- 资源消耗操作未绑定上下文权限或配额限制，可被恶意触发，详见：[c_unchecked_resource_consumption.md](c_unchecked_resource_consumption.md)  
- 业务逻辑存在并发竞态条件，导致状态不一致或资源重复处理，详见：[c_race_condition_in_logic.md](c_race_condition_in_logic.md)  

**Rust**  
- 状态机转换未充分利用枚举类型系统约束，允许运行时非法状态跳转，详见：[rust_enum_state_bypass.md](rust_enum_state_bypass.md)  
- 资源所有权转移逻辑在异步或并发场景下存在竞态或不一致，详见：[rust_ownership_logic_flaw.md](rust_ownership_logic_flaw.md)  
- 业务规则未在类型系统中编码（如 newtype、trait bound），依赖运行时检查，详见：[rust_business_rule_not_encoded_in_type.md](rust_business_rule_not_encoded_in_type.md)

## 快速开始

### 步骤 0：理解项目功能与结构

**在开始审计之前，彻底理解项目的功能与结构，特别关注业务流程相关的实现：**

- 查阅项目文档，重点关注核心业务流程、状态转换、权限控制机制说明
- 理解业务领域和核心功能，识别涉及状态变更、资源操作、多步骤流程的场景
- 识别关键组件、模块及其关系，特别是订单系统、支付模块、审批流程、权限管理模块
- 梳理应用流程（重点：状态机转换流程、多步骤业务流程、资源分配与扣减逻辑）
- 识别关键业务功能（订单处理、支付回调、优惠券兑换、权限变更、配额管理、审批流程等）
- 理解所用技术栈和框架（Web框架、ORM框架、状态管理库、事务管理机制）
- 查阅配置文件以理解系统行为（业务规则配置、状态机定义、权限策略配置等）
- 定位状态转换的实现位置（状态更新函数、前置条件校验、后置操作处理）
- 定位权限和资源校验的位置（归属验证、配额检查、操作授权逻辑）
- 识别业务数据流向（用户输入 → 业务逻辑处理 → 状态/资源变更 → 响应）

**Early exit（早期退出）：**

在理解项目结构的过程中，如果发现项目不符合前面 **Early exit** 章节描述的条件（例如纯静态网站、无状态变更逻辑、无用户驱动的业务流程等），可立即退出该漏洞类型的审计，无需继续深入分析。

只有在确认项目包含业务逻辑处理（状态机、多步骤流程、资源操作等）并获得足够的项目背景信息后，才继续查阅各漏洞类型的参考指南并开始有针对性的漏洞分析。

### 步骤 1：查阅业务逻辑漏洞的参考指南

业务逻辑漏洞审计分为两个层次，需要按顺序进行：

**第一步：审计通用业务逻辑缺陷模式（所有项目必审）**

在 **通用业务逻辑缺陷模式** 章节中，列举了所有包含业务逻辑的项目都必须审计的缺陷：
- 状态转换未校验前置条件（状态机跳转、多步骤流程绕过）
- 资源操作缺乏授权或归属验证（资源归属、配额限制）
- 并发竞态导致状态不一致（库存竞态、幂等性缺失）
- 回调或异步操作缺乏来源验证（第三方回调、异步任务）
- 依赖客户端逻辑进行安全决策（客户端参数、前端状态）
- 条件判断逻辑不完整（边界条件、异常路径）

这些问题与编程语言无关，是业务逻辑设计和实现层面的通用缺陷，任何有业务流程的项目都需要检查。

**第二步：审计语言特定实现（根据项目语言选择性审计）**

在 **语言特定实现** 章节中，按编程语言组织了各语言业务逻辑的特定实现问题：
- 按编程语言分类（Java、Python、Go、PHP、JavaScript/TypeScript、C/C++、Rust）
- 列出该语言框架和特性的典型业务逻辑缺陷和对应的参考文档链接

根据项目所用编程语言，仅需查找和审计对应语言章节中的漏洞场景。

### 步骤 2：深入学习具体的审计指南

根据 **通用业务逻辑缺陷模式** 和 **语言特定实现** 章节中的引用，打开对应的具体审计指南文件（如 `logic_state_transition_skip.md`、`java_order_state_abuse.md`、`python_form_step_bypass.md` 等）。这些文件主要包含三个核心部分：

1. **Details（详细说明）**：漏洞成因、危险代码与安全代码对比示例、快速定位技巧（核心操作定位和保护机制定位）
2. **Classify（分类研判）**：明确的研判标准，包括确认漏洞、判定误报、识别代码异味的具体条件
3. **Low risk（低风险场景）**：列举可以降低风险等级的场景和条件

通过学习这些具体指南，可以准确识别代码中的漏洞模式，并进行有效的审计和评估。

## 审计等级定义

业务逻辑漏洞审计采用分层的审计等级制度，根据业务流程的校验完备性来指导审计深度。

| 等级 | 名称 | 时间 | 业务校验特征 |
|------|------|------|---------|
| **L0** | 快速跳过 | 1-2 分钟 | 完整校验：状态转换有前置条件、资源有归属验证、并发有控制 |
| **L1** | 快速扫描 | 3-5 分钟 | 有校验 + 需确认：需验证所有业务流程是否都有完整校验 |
| **L2** | 跳读 | 5-10 分钟 | 部分校验：部分流程有校验，需验证覆盖范围和边界条件 |
| **L3** | 逐行读 | 15-30 分钟 | 无校验或明显缺陷：状态可跳转、资源无归属验证、流程可绕过 |
| **L4** | 跨模块追踪 | 30-60 分钟 | 复杂链路：多步骤流程、异步回调、分布式状态、竞态条件 |

### 快速判断流程

**第 1 步：是否存在业务流程？**
- 无业务流程（纯静态） → L0 跳过
- 有业务流程 → 继续第 2 步

**第 2 步：状态转换是否有前置条件校验？**
- 无前置条件校验 → **L3+**
- 有前置条件校验 → 继续第 3 步

**第 3 步：资源操作是否有归属验证和并发控制？**
- 完整校验（归属 + 并发控制） → **L0-L1**
- 部分校验或边界条件缺失 → **L2**
- 多步骤流程或异步回调 → **L3-L4**

### 各等级操作指南

**L0**：完整校验
```java
// 状态转换有前置条件校验
if (order.getStatus() != OrderStatus.PAID) {
    throw new IllegalStateException("订单未支付");
}
order.setStatus(OrderStatus.SHIPPED);

// 资源有归属验证
if (!coupon.getUserId().equals(currentUser.getId())) {
    throw new ForbiddenException();
}

// 并发有控制（乐观锁）
@Version
private Long version;
```

**L1**：有校验 + 需确认
- 所有状态转换是否都有前置条件校验？
- 所有资源操作是否都有归属验证？
- 是否实施了幂等性控制？遇到令牌/验证码机制详见：[bypassTricks.md - 验证码和令牌漏洞](bypassTricks.md#验证码和令牌漏洞)
- 并发操作是否有锁或版本控制？遇到竞态条件详见：[bypassTricks.md - 条件竞争和时间窗口](bypassTricks.md#条件竞争和时间窗口)

**L2**：部分校验
- 哪些流程有校验？哪些没有？
- 边界条件是否考虑完整（如数量为 0、负数）？遇到负数/边界值检查详见：[bypassTricks.md - 业务逻辑黑洞](bypassTricks.md#业务逻辑黑洞)
- 异常路径是否有校验？
- 客户端参数是否被信任？遇到类型检查详见：[bypassTricks.md - JavaScript类型混淆漏洞](bypassTricks.md#javascript类型混淆漏洞) 和 [类型混淆和类型强制转换](bypassTricks.md#类型混淆和类型强制转换)

**L3**：无校验或明显缺陷
```java
// 状态可直接跳转，无前置条件校验
order.setStatus(OrderStatus.COMPLETED);  // 未检查是否已支付

// 资源无归属验证
coupon.use();  // 未检查是否属于当前用户

// 流程可绕过
if (step == 3) {  // 未校验 step 1 和 2 是否完成
    completeRegistration();
}

// 依赖客户端参数
if (request.getParameter("isAdmin").equals("true")) {  // 存在风险
    grantAdminAccess();
}
```
完整分析业务流程和状态转换，追踪数据流，确认绕过方式

**L4**：复杂链路
- 多步骤流程：注册 → 验证 → 激活，每步是否校验前置条件？
- 异步回调：支付回调是否验证签名和来源？遇到回调伪造详见：[bypassTricks.md - 原型链污染导致RCE](bypassTricks.md#原型链污染导致rce) 和 [EJS模板引擎污染](bypassTricks.md#ejs模板引擎污染)
- 分布式状态：微服务间状态是否一致？是否有补偿机制？
- 竞态条件：库存扣减、配额消耗是否有并发控制？遇到TOCTOU详见：[bypassTricks.md - 条件竞争和时间窗口](bypassTricks.md#条件竞争和时间窗口)
- 幂等性：重复请求是否会导致重复操作？遇到令牌验证详见：[bypassTricks.md - 验证码和令牌漏洞](bypassTricks.md#验证码和令牌漏洞)

### 审计等级应用

```markdown
| 场景 | 等级 | 说明 |
|------|------|------|
| 完整前置条件校验 + 归属验证 | L0 | 无风险 |
| 有校验 + 需确认覆盖范围 | L1 | 验证所有流程 |
| 部分校验或边界条件缺失 | L2 | 验证完整性 |
| 无前置条件校验 | L3 | 高风险 |
| 状态可跳转或资源无归属验证 | L3 | 高风险 |
| 多步骤流程或异步回调 | L4 | 完整追踪 |
```

## 核心审计原则

### 验证要求

- 必须根据实际源代码验证发现结果，而非仅依赖模式匹配
- 必须验证完整的漏洞利用链：入口（用户操作）→ 业务逻辑处理 → 状态/资源变更 → 安全影响
- 每一步都需要文件路径、函数名和行号的具体证据
- 考虑框架和项目中实现的业务规则保护机制（如事务、锁、幂等性控制等）
- 绕过技巧索引：
  - 遇到类型检查/参数验证：[bypassTricks.md - JavaScript类型混淆漏洞](bypassTricks.md#javascript类型混淆漏洞) 和 [类型混淆和类型强制转换](bypassTricks.md#类型混淆和类型强制转换)
  - 遇到并发控制/锁机制：[bypassTricks.md - 条件竞争和时间窗口](bypassTricks.md#条件竞争和时间窗口)
  - 遇到整数边界检查：[bypassTricks.md - 整数溢出和下溢](bypassTricks.md#整数溢出和下溢)
  - 遇到令牌/验证码机制：[bypassTricks.md - 验证码和令牌漏洞](bypassTricks.md#验证码和令牌漏洞)
  - 遇到负数/金额检查：[bypassTricks.md - 业务逻辑黑洞](bypassTricks.md#业务逻辑黑洞)
  - 遇到回调/异步操作：[bypassTricks.md - 原型链污染导致RCE](bypassTricks.md#原型链污染导致rce) 和 [EJS模板引擎污染](bypassTricks.md#ejs模板引擎污染)
  - 遇到运算符/条件判断：[bypassTricks.md - 运算符优先级滥用](bypassTricks.md#运算符优先级滥用)

# 输出要求

确认漏洞后，加载 `bug-report` 技能获取标准化报告格式，生成漏洞报告文件。

**加载技能**：`bug-report`

**输出路径**：`.workspace/findings/BUG-business-logic-{file}-L{line}-{source}-{sink}.md`

**约束**：
- 每个漏洞必须生成独立的 BUG 文件，禁止合并或省略
- 漏洞报告格式严格遵循 `bug-report` 技能定义的模板
