# Java｜Controller 缺失 @PreAuthorize 权限注解

## Details

### 漏洞成因
在 Spring MVC/Spring Boot 项目中，常通过 `@PreAuthorize`、`@Secured`、`@RolesAllowed` 等注解实现函数级访问控制。如果开发者漏加注解或仅依赖控制器路径命名约定，就会导致敏感接口被任意角色访问。常见于新增后台功能、重构后忘记补规则、不同环境下注解被禁用等情况。

### 代码示例

**易受攻击示例：**
```java
@RestController
@RequestMapping("/admin")
public class AdminController {

    @PostMapping("/users/{id}/reset-password")
    public void resetPassword(@PathVariable Long id) {
        userService.resetPassword(id); // 未加 @PreAuthorize
    }
}
```

**安全示例：**
```java
@RestController
@RequestMapping("/admin")
public class AdminController {

    @PreAuthorize("hasAuthority('user:reset')")
    @PostMapping("/users/{id}/reset-password")
    public void resetPassword(@PathVariable Long id) {
        userService.resetPassword(id);
    }
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `@RestController`, `@Controller`, `@RequestMapping`, `@PostMapping`, `@PreAuthorize`, `@Secured`。

**定位步骤：**
1. 搜索敏感控制器方法（用户、角色、配置等）；
2. 跳读（L2）检查方法或类上是否存在权限注解；
3. 确认项目是否启用 Spring Security 方法级保护 (`@EnableGlobalMethodSecurity`)。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- 类级别 `@PreAuthorize` 或 `@Secured`；
- 自定义 AOP 拦截器进行权限校验；
- API Gateway / 过滤器执行 RBAC 检查；
- Service 层二次校验调用者身份。

**定位技巧：**
- 逐行读（L3）敏感方法，检查 service 层是否补充校验；
- 跨模块追踪（L4）网关、微服务调用中是否存在缺口。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| Controller/Service 均使用注解保护 | **L0（快速跳过）** | 权限覆盖充分 |
| 仅类级注解，部分方法需额外确认 | **L2（跳读）** | 快速核对 |
| 完全缺少权限注解 | **L3（逐行读）** | 高风险 |
| 跨服务调用绕过注解 | **L4（跨模块追踪）** | 全链路排查 |

## Classify

### 研判标准

#### 确认漏洞
1. 方法缺少权限注解或其他校验；
2. 通过低权限账户访问该接口成功；
3. 接口执行敏感操作（重置密码、分配角色、导出数据）。

#### 误报
1. 上层网关已阻止低权限角色访问该路径；
2. Service 层包含权限校验并拒绝违规请求；
3. 接口仅用于内部测试环境，不对外部署（需证据）。

#### 代码异味
1. 注释写明“TODO 添加权限”却未落实；
2. 使用自定义注解但配置错误导致失效；
3. 权限注解被条件编译 / profile 关闭而未说明。

## Low risk

### 低风险评级场景

#### 1. 接口仅读取非敏感信息
- **场景：** 缺少权限但返回内容公开；
- **评估：** 可标低风险。

#### 2. 内部工具接口
- **场景：** 仅在内网或测试环境可访问，并有额外网络控制；
- **评估：** 攻击面小，但需记录。

#### 3. 改造计划在执行
- **场景：** 已排期补充权限注解并通过安全测试；
- **评估：** 可暂降级，跟踪落实。

#### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 返回公共信息 | 影响有限 | 低 |
| 内部受控环境 | 攻击面低 | 中 |
| 改造计划明确 | 可暂缓 | 低 |
