# Java 权限提升逻辑缺陷（Permission Escalation via Logic Flaw）

**漏洞成因**：权限变更、角色切换、授权判断逻辑存在缺陷，攻击者通过特定操作序列（修改中间状态、重放请求、绕过校验）实现越权访问或角色提升，获取超出自身权限的资源或功能。

---

## Details

**审计等级：L3-L4（逐行读+跨模块追踪）- 权限逻辑需完整追踪授权链路**

**核心代码特征**：
```java
// 典型漏洞模式 1：权限检查与权限应用分离
public void updateUserRole(Long userId, String newRole) {
    User user = userService.getUser(userId);
    // 缺失权限校验：未检查当前用户是否有权修改目标用户角色
    user.setRole(newRole);
    userRepository.save(user);
}

// 典型漏洞模式 2：中间状态可被操控
public void approveRoleChange(Long requestId) {
    RoleRequest req = roleRequestRepo.findById(requestId);
    // 危险：未验证 req.targetRole 是否被篡改
    User user = req.getUser();
    user.setRole(req.getTargetRole());  // targetRole 可能在审批前被修改
}
```

**快速定位核心操作（L1-L2）**：
- **关键词扫描**：`setRole`、`updateRole`、`grantPermission`、`changeAuthority`、`promoteUser`、`assignRole`
- **权限字段**：`role`、`permission`、`authority`、`privilege`、`level`、`scope`、`capabilities`
- **敏感注解**：`@PreAuthorize`、`@RolesAllowed`、`@Secured`、`hasRole()`、`hasAuthority()`
- **API端点**：`/admin/`、`/role/update`、`/permission/grant`、`/user/promote`

**快速定位保护机制（L3-L4）**：
- **当前用户校验**：`SecurityContextHolder.getContext().getAuthentication()`
- **角色层级检查**：`if (currentRole.level >= targetRole.level)`
- **双因子确认**：密码二次确认、OTP验证、审批工作流
- **审计日志**：权限变更操作必须记录 `who/what/when/from/to`
- **事务一致性**：权限修改与业务操作在同一事务中，回滚机制完整

**危险信号（审计等级提升至L3-L4）**：
- 权限修改接口无身份认证或仅依赖前端校验
- 使用 HTTP 参数直接设置角色：`@RequestParam String role`
- 权限检查与权限应用跨越多个请求周期
- Session 或 Token 中的角色信息可被客户端修改
- 批量授权接口未逐个验证目标用户合法性

**审计追踪路径**：
1. **入口定位**：找到所有权限修改的 Controller 方法
2. **权限源追踪**：确认新权限值来自何处（参数、数据库、配置）
3. **检查点验证**：在权限应用前，是否验证当前用户身份和权限等级
4. **状态一致性**：权限对象在检查与应用之间是否可能被并发修改
5. **生效时机**：新权限何时生效（立即、下次登录、缓存刷新）

---

## Classify

### ✅ 确认漏洞

**直接越权**：
- 权限修改接口无任何身份校验，普通用户可修改自己或他人角色
- 使用用户可控参数直接赋值：`user.setRole(request.getParameter("role"))`
- 仅校验是否登录，未校验是否有权限变更权限

**逻辑绕过**：
- 通过修改 JWT payload 中的 `role` 字段提升权限（未验证签名或签名可伪造）
- 先申请低权限角色通过审批，再修改申请记录中的 `targetRole` 字段
- 批量操作接口允许在列表中夹带高权限用户 ID

**时序问题**：
- 权限检查使用旧缓存，权限应用使用实时数据（TOCTOU）
- 审批流中，审批人权限在审批后被降级，但审批已生效
- 并发请求利用竞态窗口绕过"每人只能申请一次"限制

**中间状态污染**：
- 权限申请流程中，待审批对象的 `targetRole` 字段可被申请人再次修改
- Session 中存储角色字符串，未与数据库双向验证

### ⚠️ 误报/需深入确认

- **已有上游校验**：Gateway 或拦截器已统一校验，业务层只处理已授权请求（需确认拦截器覆盖所有路径）
- **内部服务调用**：仅供内部微服务调用，不直接暴露给用户（需确认服务间认证机制）
- **管理员专用接口**：明确标注仅限超级管理员调用（需确认运行时强制校验，非仅代码注释）
- **只读权限变更**：修改的是临时展示权限，不影响实际授权决策

### 🔍 代码异味

- **注释依赖校验**：代码注释写"调用前需确保用户是管理员"，但无强制检查
- **多重防御不完整**：部分接口有校验，部分无（说明开发者遗漏）
- **硬编码角色名**：使用字符串比对 `if ("admin".equals(role))` 而非枚举
- **日志缺失**：权限变更无审计日志，事后无法追溯
- **异常处理不当**：权限校验失败时返回 500 而非 403，易被误判为系统错误

---

## Low Risk

以下场景可评为低风险（但仍需标注并建议修复）：

1. **仅影响非敏感功能**：权限控制的是 UI 主题、通知偏好等无关业务核心的配置
2. **自动降级机制**：系统每次请求实时查询数据库权限，Session 篡改无效
3. **时效性限制**：提升的权限仅在当前会话有效，且会话超时时间 < 5 分钟
4. **需配合其他高成本条件**：需同时绕过 MFA、IP 白名单、设备指纹等多重防护
5. **影响范围受限**：只能提升到"初级管理员"，仍无法访问核心敏感操作
6. **审计兜底**：所有权限变更有完整日志，异常行为会触发告警和自动回滚
7. **测试/沙箱环境**：仅在隔离环境存在，生产环境已修复（需明确确认）

**风险升级条件（低风险→高风险）**：
- 可提升至系统管理员、财务角色等高敏感权限
- 历史出现真实攻击案例或用户投诉
- 防护措施依赖客户端行为（前端校验、Cookie 校验）
- 可通过自动化脚本批量提升多个账号权限