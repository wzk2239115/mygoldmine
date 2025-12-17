---
name: broken-function-level-authorization-analyzer
description: 专业的审计工作流程，通过静态代码分析识别和验证功能级访问控制缺陷漏洞；重点关注检测敏感操作接口、管理功能、特权函数等在执行时未对当前用户的角色或权限进行充分校验的问题，包括缺失权限注解、仅依赖路径隐藏、共享服务方法未区分调用上下文、动态函数调用绕过授权检查等，从而导致普通用户可执行管理员功能、越权调用敏感接口、权限提升等安全问题；利用按编程语言组织的参考资料目录中的参考指南。
---
**Attention**  
当系统中存在基于角色或权限的函数级访问控制，但未在每个敏感操作入口处显式校验当前用户是否具备调用该函数的权限时，即可能触发 broken_function_level_authorization（函数级授权缺失）漏洞。此类问题通常出现在后台管理接口、用户操作接口、API 网关路由处理、权限变更或资源操作等模块中，尤其在多角色系统（如 admin/user/guest）中更为常见。

**Early exit**  
若项目代码中完全未实现任何基于用户身份/角色的函数访问控制逻辑（例如无 RBAC、ABAC 等机制，且所有接口均为公开或仅依赖前端隐藏控制），或项目仅为静态内容服务、无用户身份区分的工具型程序（如纯计算脚本、无登录态的 CLI 工具），则可快速退出对该漏洞类型的审计。

---

## 通用授权缺陷模式（所有项目必审）

查看详细说明：[general.md](general.md)

快速概览：
- **仅验证身份未验证权限**（粗粒度身份认证） - 遇到此类保护机制，详见 [bypassTricks.md - 功能级别授权原理](bypassTricks.md#功能级别授权原理)
- **依赖路径隐藏或前端控制**（安全性依赖隐蔽性） - 遇到此类保护机制，详见 [bypassTricks.md - 功能隐藏与直接访问](bypassTricks.md#功能隐藏与直接访问)、[bypassTricks.md - API端点暴露](bypassTricks.md#api端点暴露)
- **共享服务未区分调用上下文**（多角色共享业务逻辑） - 遇到此类保护机制，详见 [bypassTricks.md - 角色和权限混淆](bypassTricks.md#角色和权限混淆)、[bypassTricks.md - 批量操作授权绕过](bypassTricks.md#批量操作授权绕过)
- **动态函数调用绕过授权检查**（通过参数控制执行路径） - 遇到此类保护机制，详见 [bypassTricks.md - 高级授权绕过 - HTTP方法覆盖](bypassTricks.md#http方法覆盖)、[bypassTricks.md - 高级授权绕过 - 参数污染](bypassTricks.md#参数污染hpp)
- **权限检查覆盖不完整**（授权机制部分失效） - 遇到此类保护机制，详见 [bypassTricks.md - 权限检查不完整](bypassTricks.md#权限检查不完整)、[bypassTricks.md - 功能隐藏与直接访问 - 版本化API绕过](bypassTricks.md#版本化api绕过)

---

**语言特定实现（根据项目语言选择性审计）**

以下漏洞场景与具体编程语言的访问控制机制和框架实现相关。根据项目所使用的编程语言，仅需审计对应语言章节中的漏洞模式。

**C/C++**  
- 基于字符串匹配的命令路由分发，未对调用者身份和权限进行校验，详见：[c_command_dispatch_without_auth.md](c_command_dispatch_without_auth.md)  
- 插件回调机制中允许未授权调用者触发敏感操作，详见：[c_plugin_callback_authorization_bypass.md](c_plugin_callback_authorization_bypass.md)  
- RPC 接口处理函数缺失角色检查，导致内部接口可被任意调用，详见：[c_rpc_handler_missing_role_check.md](c_rpc_handler_missing_role_check.md)  

**Java**  
- Controller 方法未使用 @PreAuthorize 或其他权限注解，导致敏感操作可被任意角色调用，详见：[java_controller_missing_preauthorize.md](java_controller_missing_preauthorize.md)  
- 共享 Service 方法被多个 Controller 调用，但未根据调用上下文区分权限，详见：[java_shared_service_no_context_check.md](java_shared_service_no_context_check.md)  
- 管理员 API 仅通过路径混淆隐藏，未实施真正的权限校验，详见：[java_admin_api_path_obfuscation.md](java_admin_api_path_obfuscation.md)  

**Python**  
- 视图函数仅检查登录态，未验证当前用户角色是否有权执行该操作，详见：[python_view_func_role_not_verified.md](python_view_func_role_not_verified.md)  
- 认证装饰器链覆盖不完整，部分敏感端点漏掉权限装饰器，详见：[python_decorator_gap_in_auth_chain.md](python_decorator_gap_in_auth_chain.md)  
- 通过 URL 参数动态调用内部函数，绕过正常的权限检查流程，详见：[python_dynamic_func_call_by_param.md](python_dynamic_func_call_by_param.md)  

**Go**  
- HTTP handler 在外部进行通用身份验证，但未针对具体操作细化权限检查，详见：[go_handler_missing_operation_auth.md](go_handler_missing_operation_auth.md)  
- 共用 handler 逻辑处理多种角色请求，但未区分不同角色的权限上下文，详见：[go_shared_handler_no_role_context.md](go_shared_handler_no_role_context.md)  
- 通过 map[string]func 注册函数回调，但注册时未添加授权检查包装器，详见：[go_func_map_no_auth_wrapper.md](go_func_map_no_auth_wrapper.md)  

**PHP**  
- 控制器方法仅依赖中间件粗粒度验证，未在方法内检查具体能力或权限，详见：[php_controller_method_no_capability_check.md](php_controller_method_no_capability_check.md)  
- 通过 $_GET/$_POST 参数动态调用内部方法，绕过正常的路由和权限检查，详见：[php_dynamic_method_call_via_param.md](php_dynamic_method_call_via_param.md)  
- 管理员 AJAX 接口未对用户角色进行二次验证，依赖前端访问控制，详见：[php_admin_ajax_no_role_recheck.md](php_admin_ajax_no_role_recheck.md)  

**JavaScript / TypeScript**  
- 路由处理器中间件仅验证 token 有效性，未校验用户对具体操作的权限，详见：[js_route_handler_missing_func_auth.md](js_route_handler_missing_func_auth.md)  
- 共享业务服务被多个角色调用，但服务函数内未区分调用者角色进行权限检查，详见：[ts_shared_service_called_by_multi_role.md](ts_shared_service_called_by_multi_role.md)  
- 通过事件名或 action 字段进行动态路由分发，但未对操作进行授权检查，详见：[js_action_based_routing_no_auth.md](js_action_based_routing_no_auth.md)  

**Rust**  
- Handler 函数在 extractor 层仅解析用户身份，未校验操作权限策略，详见：[rust_handler_missing_operation_policy.md](rust_handler_missing_operation_policy.md)  
- 自定义命令路由器通过字符串匹配调用内部函数，但未检查调用上下文和角色，详见：[rust_command_router_no_role_check.md](rust_command_router_no_role_check.md)  
- 共享状态操作未绑定角色策略，允许未授权用户访问敏感状态，详见：[rust_shared_state_access_unauthorized.md](rust_shared_state_access_unauthorized.md)

## 快速开始

### 步骤 0：理解项目功能与结构

**在开始审计之前，彻底理解项目的功能与结构，特别关注权限控制和访问控制相关的实现：**

- 查阅项目文档，重点关注访问控制、角色权限体系、功能授权机制说明
- 理解业务领域和核心功能，识别涉及敏感操作和管理功能的场景
- 识别关键组件、模块及其关系，特别是权限控制中间件、认证授权模块、RBAC/ABAC 实现
- 梳理应用流程（重点：用户角色分配流程、权限校验流程、操作授权检查机制）
- 识别关键业务功能（用户管理、权限变更、资源操作、管理后台、敏感数据访问等）
- 理解所用技术栈和框架（Web框架、权限框架如 Spring Security、Shiro、Django Permissions、Casbin 等）
- 查阅配置文件以理解系统行为（角色定义、权限配置、访问控制策略、注解配置等）
- 定位权限检查的位置（权限注解、装饰器、中间件、拦截器、守卫等）
- 定位敏感操作的入口（管理员接口、特权函数、批量操作、删除/修改接口等）
- 识别角色体系和权限模型（admin/user/guest、基于角色的访问控制、基于属性的访问控制等）

**Early exit（早期退出）：**

在理解项目结构的过程中，如果发现项目不符合前面 **Early exit** 章节描述的条件（例如完全无用户角色区分、无任何权限控制逻辑、仅为纯计算工具等），可立即退出该漏洞类型的审计，无需继续深入分析。

只有在确认项目实现了基于角色或权限的访问控制机制并获得足够的项目背景信息后，才继续查阅各漏洞类型的参考指南并开始有针对性的漏洞分析。

### 步骤 1：查阅功能级授权缺失漏洞的参考指南

功能级授权缺失漏洞审计分为两个层次，需要按顺序进行：

**第一步：审计通用授权缺陷模式（所有项目必审）**

在 **通用授权缺陷模式** 章节中，列举了所有实现权限控制的项目都必须审计的授权缺陷：
- 仅验证身份未验证权限（粗粒度身份认证）
- 依赖路径隐藏或前端控制（安全性依赖隐蔽性）
- 共享服务未区分调用上下文（多角色共享业务逻辑）
- 动态函数调用绕过授权检查（通过参数控制执行路径）
- 权限检查覆盖不完整（授权机制部分失效）

这些问题与编程语言无关，是访问控制设计和业务逻辑层面的缺陷，任何实现权限控制的项目都需要检查。

**第二步：审计语言特定实现（根据项目语言选择性审计）**

在 **语言特定实现** 章节中，按编程语言组织了各语言权限控制机制的特定实现问题：
- 按编程语言分类（Java、Python、Go、JavaScript/TypeScript、PHP、C/C++、Rust）
- 列出该语言权限框架和实现方式的典型漏洞模式和对应的参考文档链接

根据项目所用编程语言，仅需查找和审计对应语言章节中的漏洞场景。

### 步骤 2：深入学习具体的审计指南

根据 **通用授权缺陷模式** 和 **语言特定实现** 章节中的引用，打开对应的具体审计指南文件（如 `auth_identity_only_no_permission_check.md`、`java_controller_missing_preauthorize.md`、`python_view_func_role_not_verified.md` 等）。这些文件主要包含三个核心部分：

1. **Details（详细说明）**：漏洞成因、危险代码与安全代码对比示例、快速定位技巧（核心操作定位和保护机制定位）
2. **Classify（分类研判）**：明确的研判标准，包括确认漏洞、判定误报、识别代码异味的具体条件
3. **Low risk（低风险场景）**：列举可以降低风险等级的场景和条件

通过学习这些具体指南，可以准确识别代码中的漏洞模式，并进行有效的审计和评估。

## 审计等级定义

函数级授权缺失漏洞审计采用分层的审计等级制度，根据权限检查的完整性来指导审计深度。

| 等级 | 名称 | 时间 | 权限检查特征 |
|------|------|------|---------|
| **L0** | 快速跳过 | 1-2 分钟 | 完整授权：所有敏感操作都有权限注解/检查，无路径隐藏，共享服务有上下文区分 |
| **L1** | 快速扫描 | 3-5 分钟 | 有授权但需确认：权限注解存在，需验证覆盖范围和检查逻辑 |
| **L2** | 跳读 | 5-10 分钟 | 部分授权：缺失部分敏感操作的权限检查或覆盖不完整，需验证完整性 |
| **L3** | 逐行读 | 15-30 分钟 | 明显缺陷：仅验证身份不验证权限、依赖路径隐藏、动态函数调用无检查 |
| **L4** | 跨模块追踪 | 30-60 分钟 | 复杂链路：共享服务无上下文区分、多处调用链不一致、授权逻辑分散 |

### 快速判断流程

**第 1 步：敏感操作是否有权限检查？**
- 无权限检查或仅依赖路径隐藏 → **L3+**
- 有权限检查 → 继续第 2 步

**第 2 步：权限检查覆盖是否完整？**
- 仅在中间件检查身份，未在函数检查权限 → **L2-L3**
- 每个敏感操作都有明确的权限检查 → 继续第 3 步

**第 3 步：多角色调用或动态调用是否安全？**
- 共享服务无上下文区分或动态函数调用无检查 → **L3-L4**
- 所有调用路径都有一致的权限检查 → **L0-L1**

### 各等级操作指南

**L0**：完整授权
```
✅ @PreAuthorize("hasRole('ADMIN')")  // 权限注解明确
✅ 所有敏感操作都有权限检查
✅ 共享 Service 有 user context 区分
✅ 无路径隐藏依赖
✅ 无动态函数调用绕过
```

**L1**：有授权，快速确认
- 所有管理员操作都有权限注解吗？
- 权限注解覆盖范围是否完整（所有 Controller 方法）？
- 是否仅依赖中间件验证身份，未在函数检查权限？
- 是否存在路径混淆隐藏敏感接口？

**L2**：部分授权，需核实
- 哪些敏感操作缺失权限检查（增删改查中的哪些）？
- 权限检查覆盖范围：是否覆盖所有用户面向接口？
- 共享 Service 是否区分了调用者身份和权限？
- 是否存在绕过授权的调用链？

**L3**：明显缺陷，深度分析
```javascript
// ❌ 仅验证身份，未验证权限
app.post('/delete-user', authenticate, (req, res) => {  // 无权限检查
  User.delete(req.body.id);
});

// ❌ 依赖路径隐藏
// /admin/sensitive-op  仅通过路径隐藏，前端未渲染

// ❌ 共享 Service 未区分上下文
function editUser(userId, data) {  // 未检查是否有权限编辑
  return user.update(userId, data);
}

// ❌ 动态函数调用无检查
const action = req.body.action;  // admin/delete 等
callFunction(action, params);  // 直接调用，无授权检查
```
追踪完整的操作路径和权限检查流程，确认缺失点和绕过方式

**L4**：复杂链路，完整追踪
- 敏感操作的完整调用链：Web 层 → Service 层 → DAO 层
- 共享 Service 被多处调用：是否每处都进行了权限检查？
- 权限检查分散的位置：中间件 vs 函数 vs Service，是否一致？
- 动态路由分发：是否所有分发路径都有授权检查？
- 多角色场景：admin/user/guest 调用同一 Service，是否正确区分？

### 审计等级应用

```markdown
| 场景 | 等级 | 说明 |
|------|------|------|
| 所有敏感操作都有权限检查 | L0 | 无风险 |
| 有权限注解，需验证覆盖 | L1 | 验证范围 |
| 部分操作缺失权限检查 | L2 | 验证完整性 |
| 仅验证身份，无权限检查 | L3 | 高风险深度分析 |
| 依赖路径隐藏或动态调用 | L3 | 高风险深度分析 |
| 共享 Service 无上下文 | L4 | 完整链路追踪 |
```

## 核心审计原则

### 验证要求

- 必须根据实际源代码验证发现结果，而非仅依赖模式匹配
- 必须验证完整的漏洞利用链：入口（敏感操作接口）→ 权限检查逻辑 → 操作执行 → 影响
- 每一步都需要文件路径、函数名和行号的具体证据
- 考虑框架和项目中实现的自动防护（全局拦截器、中间件、权限注解等），遇到保护机制时参考绕过技巧：
  - **认证检查机制** - 详见 [bypassTricks.md - HTTP头部认证绕过](bypassTricks.md#http头部认证绕过)
  - **JWT认证** - 详见 [bypassTricks.md - JWT头部攻击](bypassTricks.md#jwt头部攻击)
  - **基于IP的访问控制** - 详见 [bypassTricks.md - 代理头部伪造](bypassTricks.md#代理头部伪造)
  - **会话和Token机制** - 详见 [bypassTricks.md - 会话和Token操作](bypassTricks.md#会话和token操作)
  - **权限缓存机制** - 详见 [bypassTricks.md - 角色和权限缓存漏洞](bypassTricks.md#角色和权限缓存漏洞)
  - **路径规范化保护** - 详见 [bypassTricks.md - 路径遍历和符号链接绕过](bypassTricks.md#路径遍历和符号链接绕过)
  - **CORS保护** - 详见 [bypassTricks.md - CORS预检绕过认证](bypassTricks.md#cors预检绕过认证)
  - **所有权验证** - 详见 [bypassTricks.md - 用户ID和所有权检查](bypassTricks.md#用户id和所有权检查)
  - **条件竞争防护** - 详见 [bypassTricks.md - 条件竞争导致的权限检查绕过](bypassTricks.md#条件竞争导致的权限检查绕过)

# 输出要求

确认漏洞后，加载 `bug-report` 技能获取标准化报告格式，生成漏洞报告文件。

**加载技能**：`bug-report`

**输出路径**：`.workspace/findings/BUG-broken-auth-{file}-L{line}-{source}-{sink}.md`

**约束**：
- 每个漏洞必须生成独立的 BUG 文件，禁止合并或省略
- 漏洞报告格式严格遵循 `bug-report` 技能定义的模板
