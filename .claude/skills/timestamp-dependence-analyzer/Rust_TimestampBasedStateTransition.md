# Rust 时间戳依赖状态转换漏洞 (Timestamp-Based State Transition)

**漏洞概述**：状态机依赖 `Clock::get().unix_timestamp` 或 `Clock::slot` 作为状态转换条件，验证者可通过时钟漂移影响状态切换时机，导致状态转换顺序被操控。

---

## Details

### 代码示例

```rust
// 脆弱示例：严格的时间戳状态转换
pub fn transition_phase(ctx: Context<TransitionPhase>) -> Result<()> {
    let clock = Clock::get()?;
    let state = &mut ctx.accounts.state;
    
    // 危险：硬编码时间戳边界，无容差机制
    if clock.unix_timestamp >= state.phase_two_start {
        state.phase = Phase::Two;
    } else if clock.unix_timestamp >= state.phase_one_start {
        state.phase = Phase::One;
    }
    
    require!(state.phase == Phase::Two, ErrorCode::PhaseNotReady);
    // 后续关键操作依赖精确的状态切换时机
    Ok(())
}
```

### 快速定位核心操作技巧 **[L2-L3]**

**L2 跳读策略**：
- 搜索 `Clock::get()` + `.unix_timestamp` / `.slot` 组合
- 关注 `if/match` 分支中使用时间戳的比较运算符 `>=`, `<=`, `==`
- 定位状态字段的写操作（`state.phase =`, `state.status =`）

**L3 逐行审查点**：
- 时间戳比较是否为硬边界（无 buffer/grace period）
- 状态转换后是否立即执行高价值操作（资金解锁、权限变更）
- 是否存在多个相互依赖的时间戳检查点

### 快速定位保护机制技巧 **[L3-L4]**

**L3 逐行检查**：
- 时间戳比较是否包含缓冲区（如 `timestamp + BUFFER >= target`）
- 是否使用 `slot` 替代 `unix_timestamp`（slot 更可控但仍可被影响）
- 是否存在额外的签名者/多重签名验证（`require!(signer.key() == authority)`）

**L4 跨模块追踪**：
- 查找全局配置中的时间容差设置（`Config::time_tolerance`）
- 追踪状态转换是否触发其他程序的 CPI 调用
- 检查是否有外部预言机提供时间戳验证（Oracle/Pyth 时间校验）

---

## Classify

**漏洞判定标准**：
1. **Critical**：状态转换直接控制资金释放 + 无容差机制 + 单一时间戳检查
2. **High**：状态转换影响关键权限（管理员/铸造权） + 时间戳为唯一守卫条件
3. **误报排除**：时间戳仅用于记录/日志，不影响控制流或资金安全
4. **代码异味**：使用 `unix_timestamp` 但存在 24 小时以上的粗粒度检查（精度要求低）

**研判流程**：
- 确认时间戳是否为状态转换的**充分条件**（无其他验证）
- 评估时间戳偏差（±1-30 秒）对状态转换的实际影响
- 检查状态转换是否可被重复触发（重入/多次调用）

---

## Low Risk

以下情况降级为低风险：

1. **多重验证机制**：时间戳检查仅为多个条件之一（需同时验证签名、Merkle proof、白名单）
2. **经济不可行**：状态转换攻击收益 < 验证者操控时钟的声誉成本
3. **粗粒度时间窗口**：状态转换以天/周为单位，时钟漂移（秒级）影响可忽略
4. **前置锁定期**：状态转换前需要长时间锁定（>7 天），攻击者无法提前布局
5. **可逆操作**：状态转换后存在争议期，可通过治理回滚

**量化参考**：
- 时间戳容差 ≥ 300 秒（5 分钟）→ 低风险
- 状态转换涉及金额 < $10K 且有额外签名验证 → 低风险
- 转换后操作延迟执行（timelock > 24h）→ 低风险
