# Move 交易哈希误用（Transaction Hash Misuse）

**漏洞类型**: 不安全随机数生成  
**适用平台**: Sui、Aptos 等 Move 生态  
**高发场景**: NFT 属性生成、链上抽奖、游戏随机事件

## Details

### 代码示例

```move
// 典型漏洞代码
public entry fun mint_random_nft(ctx: &mut TxContext) {
    let digest = tx_context::digest(ctx);  // 获取交易哈希
    let random_value = vector::borrow(&digest, 0);
    let rarity = (*random_value % 100) as u8;  // 基于交易哈希生成稀有度
    // ... 铸造 NFT
}

// Aptos 变体
fun lottery(account: &signer) acquires LotteryState {
    let tx_hash = transaction::get_transaction_hash();
    let winner_index = hash_to_u64(tx_hash) % total_participants;
    // ... 分配奖励
}
```

### 快速定位核心操作 **[L1-L2]**

**关键函数特征**（L1：关键词扫描）：
- `tx_context::digest()` / `transaction::get_transaction_hash()` 
- `object::id()` / `object::uid_to_bytes()` 用于对象 ID
- `hash::sha2_256()` / `hash::sha3_256()` 配合交易数据
- 搜索模式：`%`（取模运算）+ 上述函数组合

**操作流程识别**（L2：跳读）：
1. 获取交易/对象哈希 → 转换为数值 → 取模/位运算 → 业务逻辑
2. 重点关注值流动：哈希值是否直接影响资产分配/属性生成
3. 检查调用链：`entry fun` 或 `public fun` 中直接使用 `TxContext` 派生值

### 快速定位保护机制 **[L2-L3]**

**有效防护**（L2：跳读）：
- 存在 VRF/预言机调用：`oracle::request_randomness()`、`vrf::verify()`
- 承诺-揭示模式：`commitment = hash(secret + input)`，后续 `reveal(secret)`
- 多方参与：组合多个无关参与者的不可预测输入

**伪防护陷阱**（L3：逐行读）：
- 仅添加 `timestamp` 或 `epoch`：仍可预测
- 多次哈希嵌套：`hash(hash(tx_digest))`，本质未变
- 对象 ID 混淆：`object::id(obj)` 在对象创建时已确定，攻击者可预先计算

**审计要点**：
- 验证随机源是否在交易提交前对所有参与方不可知
- 确认关键决策（>0.1% 资金/稀有资产）未依赖可预测值

## Classify

### 确认为漏洞
- **经济影响**：随机结果直接决定资产归属（抽奖中奖、NFT 稀有度定价）
- **可操控性**：攻击者可通过控制交易输入/时序影响哈希值
- **无有效熵源**：代码中无外部随机源或多方协议

### 归类为误报
- **非关键随机**：仅用于 UI 展示、日志记录等非共识逻辑
- **已验证随机**：交易哈希作为 VRF 输入的一部分，但最终结果经密码学验证
- **多方博弈平衡**：虽单个交易哈希可控，但多方同时提交形成纳什均衡（需严格证明）

### 代码异味
- **低价值资产**：随机结果影响金额 <$10 等值
- **测试/演示代码**：明确标注为非生产环境
- **已有缓解措施**：存在单次参与限制、cooldown、反作弊检测（降低但未消除风险）

## Low risk

### 低风险场景
1. **无经济激励**：随机结果无市场价值（如纯展示类徽章）
2. **操控成本高于收益**：Gas 费 + MEV 成本超过预期收益
3. **影响范围可控**：单次异常仅影响单个用户且金额封顶
4. **存在补偿机制**：协议有保险库/追溯机制可纠正异常结果

### 评级依据
- **影响金额** < 协议 TVL 的 0.01%
- **可利用窗口**：需在特定区块高度/时段，机会成本高
- **历史数据**：类似场景未出现实际攻击（需结合链上数据验证）

**审计建议**: 即使评为低风险，仍应在报告中列明隐患，建议后续迭代中引入真随机源。
