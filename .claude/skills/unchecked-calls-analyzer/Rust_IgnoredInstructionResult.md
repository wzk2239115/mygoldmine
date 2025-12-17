# Rust_IgnoredInstructionResult

**适用范围**：Solana（Anchor/Native）、Substrate（Pallet）  
**核心问题**：CPI 调用、账户操作时未检查 `Result` 返回值，导致静默失败后续逻辑继续执行

---

## Details

### 典型代码模式

**Solana 场景**：
```rust
// 危险：忽略 invoke 返回值
invoke(
    &transfer_instruction,
    &[from.clone(), to.clone(), authority.clone()],
);
// 即使转账失败，后续逻辑仍执行

// 危险：invoke_signed 未检查
invoke_signed(
    &token::burn(...),
    &[...],
    &[&seeds],
);
state.balance -= amount; // burn 失败但仍扣减状态
```

**Substrate 场景**：
```rust
// 危险：ensure! 后直接操作
T::Currency::transfer(&sender, &recipient, value, ExistenceRequirement::KeepAlive);
Self::deposit_event(Event::Transferred(sender, recipient)); // 未检查转账结果

// 危险：链式调用丢弃中间结果
pallet_contract::Pallet::<T>::call(...)
    .ok(); // 仅转换为 Option 后丢弃
```

### 快速定位核心操作【审计等级：L2-L3】
**关键特征**：
- **L2 跳读**：搜索 `invoke`、`invoke_signed`、`transfer`、`burn`、`mint` 等关键词，检查下一行是否有 `.unwrap()`、`?` 或 `match`
- **L3 逐行**：关注函数调用后的**垂直距离**，若返回值未被变量接收且 2 行内无错误处理，标记为疑似漏洞
- **特征模式**：
  ```rust
  invoke(...);  // ← 行尾分号且无 let 绑定
  state.foo = bar;  // ← 紧随状态变更
  ```

### 快速定位保护机制【审计等级：L1-L4】
**L1 关键词扫描**（存在即通过）：
- `.unwrap()` / `.expect()` / `?` 运算符
- `if let Err(...)` / `match result`

**L3 逐行验证**（需确认作用域）：
- 检查 `Result<T, E>` 是否被 `let _ = ...` 故意忽略（代码异味）
- 确认错误处理是否在**同一事务边界**内（Anchor 的 `#[error_code]` 是否正确触发回滚）

**L4 跨模块追踪**（复杂场景）：
- 封装层：若 CPI 调用被封装进辅助函数，需追踪该函数的返回值是否被正确传播
- 事件驱动：Substrate 的 `deposit_event` 不应在操作前触发，需确认**事件顺序**与**操作结果**一致性

---

## Classify

### 漏洞判定标准
1. **高危漏洞**：
   - CPI 调用影响资产状态（转账、铸造、销毁）且未检查结果
   - 失败后续逻辑继续执行导致状态不一致（如：扣款失败但更新余额）
   
2. **误报条件**：
   - 调用的指令本身**不可失败**（如只读查询）
   - 外部已有**顶层错误捕获**（需确认覆盖范围）
   - 使用 Anchor 框架且目标程序在同一 CPI 上下文中会自动回滚（需验证账户约束）

3. **代码异味**：
   - 使用 `let _ = result` 显式忽略但添加注释说明原因
   - 非关键路径的操作（如日志记录失败）

---

## Low risk

### 低风险场景评估
1. **只读操作**：
   - 查询账户余额、读取链上数据等操作失败不影响状态
   
2. **双重保护**：
   - 业务逻辑上游已执行 `require!` 校验，使 CPI 调用在实际执行路径中**不可能失败**
   - 下游有最终一致性检查机制（如批量任务的补偿逻辑）

3. **受限影响面**：
   - 仅影响单个用户的非金融操作（如元数据更新）
   - 失败默认行为对用户有利（如空投失败不影响原有余额）

4. **框架特性保障**：
   - Anchor 的 `constraints` 机制已确保前置条件，CPI 目标程序的错误会自动传播回调用者
   - Substrate 的 `transactional` 宏已标记，任何内部错误触发完整回滚

**审计建议**：即使评估为低风险，建议在审计报告中标注为"代码质量改进项"，要求开发者显式处理或添加注释说明忽略原因。
