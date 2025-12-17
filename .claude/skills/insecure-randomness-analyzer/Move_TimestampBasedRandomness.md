# Move 时间戳随机性漏洞 (Timestamp-Based Randomness)

**漏洞类型**：不安全的随机数生成  
**影响范围**：NFT 属性随机生成、链上抽奖、游戏机制、资产分配  
**核心问题**：使用链上时间戳（`timestamp::now_microseconds()`、`tx_context::epoch()`）作为随机源，验证者可预测或操纵

## Details

### 典型代码模式

```move
// Sui 示例
public entry fun mint_random_nft(ctx: &mut TxContext) {
    let random_seed = tx_context::epoch(ctx); // ❌ 可预测
    let nft_type = random_seed % 10;
}

// Aptos 示例
public entry fun lottery(account: &signer) {
    let seed = timestamp::now_microseconds(); // ❌ 可操纵
    let winner = seed % 100;
}
```

### 快速定位核心操作 **(L1: 关键词扫描)**

**扫描目标**：
- `timestamp::now_microseconds()` / `timestamp::now_seconds()`
- `tx_context::epoch()` / `tx_context::epoch_timestamp_ms()`
- `object::id()` / `object::uid_to_bytes()` 直接用于随机
- `bcs::to_bytes()` + 时间戳/哈希的组合
- 任何 `% (取模)` 运算符后接数字范围

**重点关注**：
- 函数名包含 `random`、`lottery`、`mint`、`draw`、`select`
- 结果影响资产分配、权益获取、游戏输赢

### 快速定位保护机制 **(L2: 跳读)**

**检查是否存在**：
- 调用官方随机数模块：
  - Sui: `sui::random` 模块 (0x8)
  - Aptos: `aptos_framework::randomness` (需验证是否正确使用 commitment 机制)
- VRF 集成：Chainlink VRF、Pyth EntropyOracle
- Commit-Reveal 模式：
  - 两阶段提交：先 hash 预提交，后 reveal
  - 检查 `hash::sha3_256()`、`vector::append()` 配合使用
- 多参数混合：
  - 结合不可控因素：`block_height + user_input + previous_hash`
  - **注意**：仅混合仍可能不足，需检查参数独立性

**审计重点**：
- 保护机制是否在所有分支生效
- 是否存在回滚攻击风险（多次尝试直到满意结果）

## Classify

### 确认为漏洞 ✅
1. **直接使用时间戳作为唯一随机源**，且结果影响价值分配
2. **验证者/矿工可操纵**：单一区块内时间可微调（±几秒）
3. **前端可预测**：用户可观察当前 epoch/timestamp 提前计算结果
4. **缺乏经济惩罚**：攻击者可零成本反复尝试

### 误报场景 ⚠️
1. **已实现 Commit-Reveal**：且 reveal 阶段引入不可预测参数（如未来区块哈希）
2. **使用官方随机数 API**：正确调用 `sui::random::new_generator()` 并验证
3. **低价值场景**：仅用于 UI 展示、非关键属性（如宠物颜色，不影响战力）
4. **多源混合 + 经济限制**：结合多个独立参数且单次尝试成本高

### 代码异味 🔶
1. **过度混合**：将 10+ 个参数混合但仍包含可控时间戳
2. **误用对象 ID**：`object::id()` 在单个交易内可预测
3. **假随机注释**：代码注释声称"随机"但实际可预测

## Low Risk

以下情况可评为 **Low / Informational**：

1. **影响范围受限**：
   - 仅影响视觉效果（NFT 背景图案）、非交易属性
   - 单账户损失 < $100 且无法批量攻击

2. **经济不可行**：
   - 需消耗高昂 gas 反复尝试（> 潜在收益 10 倍）
   - 存在冷却时间（每账户每 7 天仅可尝试一次）

3. **已有缓解措施**：
   - 管理员可手动干预异常结果
   - 配合链下签名验证（虽非完美但增加攻击成本）

4. **概率影响有限**：
   - 时间戳仅影响 1% 的结果差异（如 99/100 vs 100/100）
   - 需极精准时间控制（微秒级）且收益边际

**注意**：即使评为 Low，仍应建议迁移至安全随机数方案，避免未来价值变化时升级为 High。
