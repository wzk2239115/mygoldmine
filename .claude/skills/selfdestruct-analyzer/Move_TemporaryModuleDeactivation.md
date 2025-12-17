**Move - 临时模块失效漏洞审计**  

Move 语言中虽无直接 `selfdestruct`，但可通过 `move_to`/`move_from` 或资源销毁（如 `burn`）间接实现合约逻辑"失效"。临时模块通过移除关键资源实现"自毁"，但未处理对其他依赖模块的影响，导致依赖链断裂或状态不一致。

---

## Details

**代码示例特征**：
```move
// 临时策略模块移除自身关键资源
public entry fun deactivate_policy(account: &signer) {
    let policy = move_from<PolicyConfig>(signer::address_of(account));
    // 直接销毁资源，未通知依赖方
    let PolicyConfig { ... } = policy;
}

// 其他模块依然尝试访问已失效资源
public fun execute_with_policy(user: address) {
    let policy = borrow_global<PolicyConfig>(user); // 运行时中止
}
```

**快速定位核心操作（L2-跳读）**：
- 扫描 `move_from<T>` + 立即解构模式，无状态迁移或通知机制
- 关注 `acquires` 声明中的资源，检查是否在函数中被完全移除
- 查找资源销毁后是否更新全局映射表或依赖列表

**快速定位保护机制（L3-逐行读）**：
- 检查是否存在 `event::emit` 通知依赖方资源失效
- 验证是否有全局注册表（如 `Table` 或 `SmartTable`）同步更新状态
- 确认是否实现软删除（标记 `is_active: bool` 而非直接销毁）
- 审查依赖模块是否用 `exists<T>` 预检查资源存在性

---

## Classify

**漏洞判定**：
- 资源销毁后，依赖模块仍尝试 `borrow_global` 或 `move_from` 访问，无保护检查
- 临时模块失效导致外部合约调用中止，影响业务连续性
- 缺少事件通知或状态同步机制，依赖方无法感知失效

**误报情况**：
- 模块设计为单次使用（One-Time-Use），资源销毁前已完成所有依赖清理
- 采用软删除标记 + `assert!` 前置检查，依赖方能正确处理失效状态
- 仅内部模块可触发失效，且通过 `friend` 机制严格控制调用权限

**代码异味**：
- 资源销毁后虽不引发运行时错误，但缺少优雅降级逻辑
- 未提供资源迁移路径（如将状态转移至新模块）
- 事件通知存在但依赖方未实际监听处理

---

## Low risk

**低风险场景**：
- **受限生命周期**：临时模块在可预测时间窗口内失效，所有依赖方提前清理完毕
- **原子操作内失效**：资源创建与销毁在同一事务内完成，无外部依赖风险
- **仅存储无逻辑**：被销毁资源仅作数据载体，不涉及跨模块调用链
- **白名单控制**：仅允许特定管理员触发失效，且需通过多重签名或时间锁保护
- **降级兜底**：依赖模块已实现 `if (exists<T>) { ... } else { fallback_logic }`

---

## 审计专业技巧与真实漏洞区分

### 关键区分点：真实漏洞 vs 误报

#### 1. **依赖链追踪**（真实漏洞的核心特征）
**真实漏洞表现**：
- 资源销毁后，存在多个公开函数（`public entry`）仍然直接调用 `borrow_global<T>` 无条件访问
- 跨模块依赖关系在 `Move.toml` 中明确声明，但销毁端未实现通知机制
- 同一地址上同时存在需读写的多个资源，销毁其一会导致其他资源孤立无法访问

**常见误报触发**：
- 静态分析工具检测到 `move_from` 操作后，机械地标记为漏洞，未考虑资源生命周期作用域
- 检查工具发现 `borrow_global` 但未验证前置条件（如 `assert!(exists<T>)`）

**审计技巧**：构建资源依赖图，从销毁点反向追溯所有读写操作，验证每个路径是否有守卫

#### 2. **权限隔离验证**（区分误操作与恶意设计）
**真实漏洞表现**：
- `deactivate_policy` 等销毁函数无 `#[only_owner]` 或 `friend` 限制，任意账户可调用
- 或虽有权限检查，但检查逻辑绕过（如检查的是 `signer` 而非实际操作权限）

**正确实现样例**：
```move
#[only_owner]
public entry fun deactivate_policy(account: &signer, admin: address) {
    assert!(signer::address_of(account) == admin, ERR_UNAUTHORIZED);
    let policy = move_from<PolicyConfig>(admin);
    event::emit(PolicyDeactivatedEvent { ... });
}
```

**审计技巧**：检查权限修饰符覆盖率，追踪权限验证函数的实现，测试使用非授权账户调用销毁函数

#### 3. **事件与链下监听**（判断可观测性）
**真实漏洞标志**：
- 资源销毁但完全无 `event::emit`，外部系统（钱包、应用层）无法感知失效
- 有事件但事件字段不完整（如缺少受影响的用户地址列表）

**关键事件检查清单**：
```move
// ✓ 正确的事件设计
struct PolicyDeactivated has drop, copy {
    policy_id: u64,
    owner: address,
    timestamp: u64,
    reason: u8,
}

// ✗ 不完整的事件
struct PolicyDeactivated has drop { }
```

**审计技巧**：搜索所有 `event::emit` 调用点，验证事件粒度（应包含 affected_user, timestamp, reason），检查钱包或应用层是否监听这些事件

#### 4. **状态迁移 vs 直接销毁**（判断优雅度）
**高风险销毁模式**：
```move
public entry fun deactivate(account: &signer) {
    let PolicyConfig { id, owner, .. } = move_from<PolicyConfig>(signer::address_of(account));
    // 什么都不做，资源消失
}
```

**低风险迁移模式**：
```move
public entry fun deactivate(account: &signer) {
    let config = move_from<PolicyConfig>(signer::address_of(account));
    // 关键：将状态转移到备用表或归档模块
    archived_policies::store(signer::address_of(account), config);
    event::emit(PolicyArchived { owner: signer::address_of(account), .. });
}
```

**审计技巧**：搜索 `move_from` 后的立即解构，判断是否有后续状态转移或回收逻辑

#### 5. **软删除 vs 硬删除**（时间维度的漏洞判断）
**硬删除（高风险）**：资源立即从链上消失，无恢复机制
**软删除（低风险）**：使用 `is_active: bool` 标记，历史可追溯

**审计脚本示例**：
```move
// 检查是否实现软删除保护
public fun get_policy_if_active(user: address): Option<PolicyConfig> {
    if (exists<PolicyConfig>(user)) {
        let config = borrow_global<PolicyConfig>(user);
        if (config.is_active) {
            return option::some(*config)
        }
    }
    option::none()
}
```

**审计技巧**：搜索资源定义中的 bool 字段名（`is_active`, `enabled`, `paused`），检查访问函数是否都检查这些字段

#### 6. **时间锁与多签保护**（风险等级降低）
**高风险场景**：
```move
public entry fun immediate_deactivate(account: &signer) {
    // 没有延迟，立即执行
    move_from<PolicyConfig>(signer::address_of(account));
}
```

**低风险场景**：
```move
public entry fun request_deactivate(account: &signer) {
    let addr = signer::address_of(account);
    deactivation_queue::enqueue(addr, timestamp::now_seconds() + 7 * 24 * 3600);
    event::emit(DeactivationRequested { ... });
}

public entry fun execute_deactivate(account: &signer, target: address) {
    let (addr, scheduled_time) = deactivation_queue::dequeue(target);
    assert!(timestamp::now_seconds() >= scheduled_time, ERR_TOO_EARLY);
    move_from<PolicyConfig>(addr);
}
```

**审计技巧**：检查销毁函数是否关联 `timelock` 模块，查看是否有 pending 队列实现

---

## 实战审计检查清单

| 检查项 | 真实漏洞 | 误报 | 技巧 |
|-------|--------|------|------|
| 权限控制 | 无或可绕过 | 存在 `#[only_owner]` | 尝试非授权账户调用 |
| 事件通知 | 完全缺失 | 有完整的 PolicyDeactivated 事件 | 验证事件包含所有关键字段 |
| 依赖保护 | `borrow_global` 无守卫 | 所有访问前都有 `exists<T>` 检查 | 构建资源依赖图，逐个验证 |
| 状态恢复 | 硬删除，无备份 | 实现了软删除或迁移机制 | 搜索 `move_from` 后的操作 |
| 时间保护 | 立即执行 | 有时间锁或多签延迟 | 检查是否引入 timelock 模块 |
| 范围隔离 | 跨模块影响，多个 public 函数受影响 | 仅内部使用或一次性资源 | 追踪 acquires 声明和调用关系 |
