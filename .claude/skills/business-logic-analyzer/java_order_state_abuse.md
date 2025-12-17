# Java 订单状态流转漏洞审计

## Details

**成因**: 订单状态流转未校验操作顺序或前置条件，允许跳过支付等关键步骤

**代码特征**:
```java
// 典型漏洞模式
public void cancelOrder(Long orderId) {
    Order order = orderDao.findById(orderId);
    order.setStatus("CANCELLED");  // 直接修改状态，无前置校验
    orderDao.update(order);
}

public void completeOrder(Long orderId) {
    Order order = orderDao.findById(orderId);
    order.setStatus("COMPLETED");  // 未检查是否已支付
    orderDao.update(order);
}
```

**快速定位核心操作**:
- 搜索: `setStatus|updateStatus|changeStatus|setState`
- 关注: `@PostMapping|@PutMapping` + 包含 `order|订单` 的controller方法
- 重点: 状态机关键节点 `PENDING→PAID→SHIPPED→COMPLETED`

**快速定位保护机制**:
- 查找: `if.*status|switch.*status|canTransition|validateState`
- 检查: 状态变更前是否有 `throw|return|assert` 防御逻辑
- 验证: 是否存在状态转换映射表/枚举定义

**审计等级**: **L3 (逐行读)** - 状态流转逻辑需完整追踪条件判断链

## Classify

**✓ 确认漏洞**:
- 状态修改无任何前置条件校验
- 允许从任意状态直接跳转到终态(COMPLETED/CANCELLED)
- 缺少状态转换白名单/状态机约束
- 可绕过支付直接发货/完成订单

**△ 代码异味**:
- 存在校验但逻辑不完整(如仅校验部分状态)
- 前置条件校验在service层，但controller暴露多个入口
- 依赖前端校验，后端无强制约束

**✗ 误报**:
- 使用状态机框架(Spring Statemachine/Squirrel等)并正确配置转换规则
- 明确定义了 `Map<CurrentState, List<AllowedNextState>>`
- 包含 `canTransitionTo()` 且在所有修改点调用

## Low risk

- 仅管理员可操作状态变更(需确认鉴权严密)
- 已存在业务补偿机制(如支付回调强制校验并回滚)
- 异常状态转换会触发告警+人工介入流程
- 涉及的状态非关键流程(如备注状态、显示状态等非交易主链路)
- 数据库触发器/存储过程层面已做二次校验