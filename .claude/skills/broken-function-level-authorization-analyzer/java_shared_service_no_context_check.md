# Java｜共享 Service 缺少调用上下文校验

## Details

### 漏洞成因
在分层架构中，多个 Controller 可能调用同一 Service 方法。如果 Service 内部未根据调用者上下文（角色、租户、所属组织）进行权限判断，而只执行操作，普通用户可通过调用共享 Service 方法越权访问管理员功能。常见于重用业务逻辑、微服务内部 API、GraphQL/REST 混用时遗漏授权。

### 代码示例

**易受攻击示例：**
```java
@Service
public class UserService {
    public void disableUser(Long userId) {
        userRepository.updateStatus(userId, Status.DISABLED);
    }
}

// 管理端接口
@PreAuthorize("hasAuthority('user:disable')")
@PostMapping("/admin/users/{id}/disable")
public void adminDisable(@PathVariable Long id) {
    userService.disableUser(id);
}

// 普通用户误用
@PostMapping("/profile/disable")
public void selfDisable(@AuthenticationPrincipal UserPrincipal me) {
    userService.disableUser(me.getId()); // 未校验调用者身份
}
```

**安全示例：**
```java
@Service
public class UserService {
    public void disableUser(Long targetId, UserPrincipal actor) {
        if (!actor.hasAuthority("user:disable") && !actor.getId().equals(targetId)) {
            throw new AccessDeniedException("insufficient permission");
        }
        userRepository.updateStatus(targetId, Status.DISABLED);
    }
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `@Service`, `disable`, `updateRole`, `resetPassword`, `shared`, `internal`。

**定位步骤：**
1. 找出被多个 Controller 调用的 Service 方法；
2. 跳读（L2）检查方法签名是否接受调用者上下文参数；
3. 查看方法内部是否包含 `SecurityContextHolder`, `AuthorizationChecker` 等校验。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- Service 方法接收 `UserPrincipal`/`Authentication` 并校验；
- 使用注解 `@PreAuthorize` 搭配 `#authentication`; 
- GraphQL/内部 API 层引入权限拦截器；
- 业务流程使用策略模式区分不同角色。

**定位技巧：**
- 逐行读（L3）Service 代码，确认是否仅依赖 Controller 校验；
- 跨模块追踪（L4）其他服务/批处理是否直接调用该 Service 绕过权限。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| Service 内部统一校验 actor 权限 | **L0（快速跳过）** | 风险低 |
| Service 部分方法校验、部分未校验 | **L2（跳读）** | 需确认遗漏 |
| Service 完全信任调用方 | **L3（逐行读）** | 高风险 |
| Service 被外部系统直接调用 | **L4（跨模块追踪）** | 全链路审计 |

## Classify

### 研判标准

#### 确认漏洞
1. 共享 Service 缺少调用者权限判断；
2. 普通用户可通过 API/GraphQL 调用管理员逻辑；
3. 操作影响敏感资源（禁用账号、调整权限）。

#### 误报
1. Controller 层已对所有调用路径加注解限制；
2. Service 仅被内部批处理使用，不对外暴露；
3. Service 只读取公开信息。

#### 代码异味
1. Service 依赖 Controller 传入角色标志但未验证；
2. 调用方法返回布尔值但忽略异常处理；
3. 设计文档声称“只供管理员”但未实现检查。

## Low risk

### 低风险评级场景

#### 1. 仅涉及非敏感操作
- **场景：** Service 仅修改偏好设置、日志标记；
- **评估：** 可降级，但记录。

#### 2. 运行在受限网络
- **场景：** 服务仅内网访问，外部不可达；
- **评估：** 攻击面有限。

#### 3. 已排期补充校验
- **场景：** 改造计划纳入下个迭代；
- **评估：** 暂记低风险并跟踪。

#### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 非敏感操作 | 影响有限 | 低 |
| 内部网络 | 攻击面小 | 中 |
| 改造在即 | 可暂缓 | 低 |
