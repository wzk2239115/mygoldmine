# Rust_UncheckedCPI

**漏洞类型：** 未检查跨程序调用结果  
**适用框架：** Solana（主要）、Substrate  
**核心风险：** 跨程序调用失败被静默忽略，导致状态不一致或权限绕过

## Details

### 代码示例

**漏洞代码：**
```rust
// Solana CPI 未检查返回值
invoke(
    &transfer_instruction,
    &[from.clone(), to.clone(), authority.clone()],
)?; // 仅传播错误，未验证执行结果

// 更危险：完全忽略结果
let _ = invoke(&instruction, accounts);

// invoke_signed 同样存在问题
invoke_signed(
    &spl_token::instruction::transfer(...)?,
    &[...],
    &[signer_seeds],
); // 缺少 ? 或错误处理
```

**正常代码：**
```rust
// 正确：检查并处理 Result
invoke(
    &transfer_instruction,
    &[from.clone(), to.clone(), authority.clone()],
).map_err(|e| ProgramError::Custom(e.into()))?;

// 或显式检查
let result = invoke_signed(...)?;
// 后续可选：验证账户状态变化
```

### 快速定位核心操作 **[L2: 跳读]**

**关键模式识别：**
1. **搜索 CPI 调用点**：`invoke(`、`invoke_signed(`
2. **关注跨程序交互**：`system_instruction::`、`spl_token::instruction::`、自定义 program ID
3. **识别高风险场景**：
   - 资产转移后的状态更新
   - 权限验证依赖外部程序
   - 多步骤原子操作的中间步骤

**快速筛选技巧：**
- 直接跳转到函数末尾，倒序检查是否有状态回滚逻辑
- 搜索 `let _ = invoke` 模式（明确忽略结果的危险信号）
- 检查 CPI 后是否紧跟账户状态断言（`require!`/`assert!`）

### 快速定位保护机制 **[L3: 逐行读]**

**验证层级：**
1. **Result 传播检查**：
   - `invoke(...)?` 是基础但不充分（仅防崩溃，不验证成功）
   - 需结合 `map_err` 或 `ok_or` 转换错误类型

2. **状态验证检查**：
   ```rust
   invoke(...)?;
   // 必须有后续验证
   require!(
       destination_account.amount == expected_amount,
       ErrorCode::TransferFailed
   );
   ```

3. **幂等性保护**：
   - 检查是否使用 nonce 或状态标志防止重入
   - CPI 前后的账户快照对比

**审计检查清单：**
- [ ] CPI 返回值是否被捕获（非 `let _`）
- [ ] 是否使用 `?` 或 `unwrap` 处理 Result
- [ ] CPI 后是否验证预期状态变更（余额/所有权）
- [ ] 失败场景是否有状态回滚（Solana 自动回滚，但需注意跨 CPI 的累积效应）
- [ ] 是否存在依赖 CPI 成功但未验证的后续逻辑

## Classify

### 确认为漏洞的标准：
1. **状态不一致**：CPI 失败但合约状态已更新（如扣除用户积分但转账未成功）
2. **权限绕过**：依赖外部调用的权限检查，但未验证调用结果
3. **资金风险**：涉及代币/SOL 转移的 CPI 未检查结果
4. **逻辑中断**：多步骤操作中某步 CPI 失败导致业务流程异常完成

### 误报场景：
1. **已有隐式保证**：某些 Solana 内置指令（如 `create_account`）失败会自动回滚整个交易
2. **不影响核心逻辑**：可选的日志记录或通知类 CPI 失败不影响主流程
3. **外层已检查**：调用链上层已对结果进行验证（需跨函数追踪确认）

### 代码异味（需进一步确认）：
- 使用 `let _ = invoke` 但后续有状态断言（可能是防御性编程）
- CPI 在 `match` 块中但仅处理 Ok 分支（需确认 Err 分支是否合理忽略）
- 测试代码中的未检查调用（测试与生产环境需区分）

## Low risk

**降级为低风险的情况：**

1. **非关键路径**：
   - 事件日志记录 CPI（如发送通知到链下索引器）
   - 统计数据更新（失败不影响核心业务）

2. **已有冗余保护**：
   - 上层调用已验证结果
   - 前置条件检查已覆盖失败场景（如余额充足性预检）
   - 定时任务/清算机制可修正不一致状态

3. **技术限制**：
   - Solana 交易原子性保证：CPI 失败会回滚整个交易（但需警惕跨交易的状态残留）
   - 被调用程序已实现严格的前置检查（需审查被调用合约代码）

4. **影响可控**：
   - 仅影响单个用户，且用户可重试
   - 经济损失上限明确且较小
   - 存在管理员手动修正机制

**降级评估要点：**
- 必须明确失败场景的业务影响
- 需追踪 CPI 失败是否触发其他异常处理
- 评估攻击者是否可主动构造失败场景获利
