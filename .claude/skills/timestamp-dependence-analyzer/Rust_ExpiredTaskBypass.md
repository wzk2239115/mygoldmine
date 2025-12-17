# Rust_ExpiredTaskBypass - 过期任务绕过

**漏洞类型：** 时间戳依赖 (Timestamp Dependence)  
**平台：** Rust (Solana/Anchor)  
**成因：** 任务/锁定期检查依赖 `Clock::get().unix_timestamp` 而未设容差边界，可被时间漂移利用提前解锁或延迟过期

---

## Details

### 代码特征示例

```rust
// 典型过期检查模式
pub fn claim_vested_tokens(ctx: Context<Claim>) -> Result<()> {
    let clock = Clock::get()?;
    let current_time = clock.unix_timestamp;
    
    require!(
        current_time >= ctx.accounts.vesting.unlock_time,
        ErrorCode::StillLocked
    );
    // 转账逻辑...
}
```

关键风险点：直接使用 `unix_timestamp` 作为硬边界条件（`>=`、`<=`），无容差处理。

### 快速定位核心操作技巧 【L2: 跳读】

1. **关键词扫描：** 搜索 `Clock::get()` → `unix_timestamp` → `slot` 调用点
2. **逻辑模式：** 关注时间比较运算符（`>=`、`<=`、`>`、`<`）与状态转换的绑定关系
3. **高危场景：**
   - `require!` / `assert!` 中包含时间戳比较
   - `if current_time > deadline` 后执行资金转移
   - 奖励计算公式依赖时间差值 `(current - start)`
4. **追踪点：** 确认时间值来源是链上 Clock 还是外部传参（传参风险更高）

### 快速定位保护机制技巧 【L3: 逐行读】

1. **容差设计：** 检查是否设置时间窗口/缓冲期（如 `deadline + GRACE_PERIOD`）
2. **双重验证：** 是否结合 `slot` 与 `unix_timestamp` 交叉校验
3. **边界安全：**
   - 溢出保护：时间加减法使用 `checked_add/sub`
   - 时间范围限制：`require!(unlock_time > MIN_LOCK && unlock_time < MAX_LOCK)`
4. **状态机设计：** 检查是否通过枚举状态（`Locked/Unlocked`）而非单纯时间判断
5. **跨模块追踪 【L4】：** 若时间值从其他合约/账户读取，需回溯初始设置逻辑（如 vesting schedule 创建时的参数验证）

---

## Classify

### 漏洞判定标准

- **确认漏洞：**
  1. 时间戳是唯一解锁/触发条件，无其他权限或状态门控
  2. 存在经济激励利用时间漂移（如提前提取质押、逃避惩罚）
  3. 边界值可被验证者影响（Solana 的 slot 时间戳由领导者控制，最多漂移 ±30s）

- **误报情形：**
  1. 时间检查仅用于信息展示（如 UI 倒计时），不影响状态变更
  2. 配合 `signed_by` 等强权限门控，时间戳仅为辅助条件
  3. 时间差值仅用于事件日志，不参与计算

- **代码异味：**
  1. 过期检查存在但影响范围有限（如仅影响小额积分）
  2. 时间戳用于排序或优先级，非硬性阻断
  3. 未来可能扩展为关键逻辑但当前无实际风险

### 研判流程

1. **识别时间依赖点** → 2. **评估经济影响** → 3. **检查保护层级** → 4. **验证攻击路径可行性**

---

## Low risk

以下情况可评为低风险但仍需标注：

1. **时间窗口极小：** 锁定期 < 1 小时，漂移影响有限（±30s 在几周/几月锁定期中可忽略）
2. **多重条件约束：** 时间戳 + 管理员签名 + 状态检查同时满足才能执行
3. **纯查询场景：** 时间戳用于 `view` 函数或链下索引，不触发交易
4. **容差已设置：** 代码包含合理的 `TOLERANCE` 或 `GRACE_PERIOD` 常量
5. **向后兼容性设计：** 使用 `max(last_update, clock.unix_timestamp)` 确保时间单调递增
6. **非金融应用：** 如 NFT 元数据解锁、成就系统等，无直接资金损失

**审计建议：** 即使评为低风险，也应在报告中注明"时间戳依赖存在"，提醒后续功能迭代时注意边界安全。
