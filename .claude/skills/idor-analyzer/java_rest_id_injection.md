# Java REST ID注入型IDOR

## Details

**代码示例：**
```java
@GetMapping("/api/orders/{orderId}")
public Order getOrder(@PathVariable Long orderId) {
    return orderRepository.findById(orderId).orElse(null);
}

@GetMapping("/api/user/profile")
public User getProfile(@RequestParam Long userId) {
    return userService.getUserById(userId);
}
```

**快速定位核心操作（L1-L2）：**
- L1：关键词扫描 - 搜索 `@PathVariable`、`@RequestParam`、`@GetMapping`、`@PostMapping`、`@RequestMapping` 注解
- L2：跳读 - 追踪参数流向，查看是否直接用于 `findById()`、`getById()`、`selectByPrimaryKey()`、JPQL/SQL查询的WHERE条件

**快速定位保护机制（L2-L4）：**
- L2：跳读 - 检查方法内是否存在 `getCurrentUser()`、`@PreAuthorize`、`checkPermission()` 等权限校验
- L3：逐行读 - 确认ID参数与当前用户身份的关联逻辑（如 `order.getUserId().equals(currentUserId)`）
- L4：跨模块追踪 - 检查AOP切面、Spring Security配置、自定义拦截器中是否有全局IDOR防护

## Classify

**漏洞判定标准：**
- 满足条件：外部可控ID参数 + 直接查询敏感资源 + 无权限校验 + 数据涉及跨用户隔离
- 典型场景：订单、账单、个人文件、私信、医疗记录等私密数据的直接查询

**误报情形：**
- 查询的是公开资源（如公告、商品详情等面向所有用户的数据）
- 虽无显式校验但数据库层已通过视图/行级安全策略做过滤
- 方法调用链上层已完成权限验证（需追溯调用栈）

**代码异味：**
- 对半公开资源（如脱敏后的用户信息）无校验，虽非直接泄露但存在信息收集风险
- 查询结果做了后置过滤但未在数据库层面限制，性能与安全存在隐患

## Low risk

**低风险评级场景：**
1. **数据敏感度低**：查询的是已公开/对业务影响极小的数据（如公开评论、统计数据）
2. **返回信息受限**：虽可越权查询但返回字段已充分脱敏（如仅返回状态码不含详情）
3. **业务逻辑限制**：虽无代码校验但业务上ID不可预测（UUID）且无枚举接口，实际利用难度极高
4. **读取无害操作**：仅读取非敏感元数据且无法通过此接口进行进一步利用
5. **环境隔离明确**：仅内网调用或有网络层/网关层强认证的管理后台接口