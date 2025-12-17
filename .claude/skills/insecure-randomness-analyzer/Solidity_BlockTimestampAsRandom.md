# Solidity - 区块时间戳作为随机数源

## Details

**典型代码模式：**
```solidity
function getRandomNumber() public view returns (uint256) {
    return uint256(keccak256(abi.encodePacked(block.timestamp))) % 100;
}

function lottery() public payable {
    uint256 random = uint256(keccak256(abi.encodePacked(block.timestamp, msg.sender))) % players.length;
    winners[random].transfer(address(this).balance);
}
```

**快速定位核心操作（L2:跳读）：**
- 全局搜索 `block.timestamp` 并检查其是否参与 keccak256/sha256 哈希计算
- 定位函数中涉及资产转移、奖励分配、权限决策的逻辑分支
- 追踪返回值或哈希结果是否用于取模、条件判断、数组索引等随机性决策

**快速定位保护机制（L3:逐行读）：**
- 检查是否存在 Chainlink VRF、commit-reveal 模式等外部随机源引入
- 确认是否有多个不可预测变量混合（如 block.number、blockhash、nonce、多方输入）
- 验证业务逻辑是否设置了时间窗口限制或冷却期（可削弱但不能消除风险）
- 排查是否有 Oracle 预言机或链下随机数验证机制

## Classify

**漏洞判定标准：**
- block.timestamp 直接或间接影响高价值资产分配结果（如抽奖、NFT稀有度）
- 业务允许用户在同一区块内多次调用或回退交易重试
- 矿工操纵时间戳（±15秒）可产生经济套利空间

**误报条件：**
- 仅用于非关键业务的时间记录（如日志、冷却期检查）
- 与多个不可控链上变量组合使用且单一变量操纵成本超过收益
- 随机结果不直接影响资产或权限分配

**代码异味：**
- 低价值场景但缺乏注释说明随机性弱点
- 存在替代方案但使用 block.timestamp 作为便捷实现

## Low risk

**低风险评级场景：**
1. **经济不可行性**：操纵成本（如矿工贿赂、算力投入）远超预期收益
2. **多变量混淆**：结合 blockhash、交易序列、多用户输入等至少3个独立变量，且单一变量操纵无法显著改变结果
3. **非金融场景**：游戏娱乐性随机（无资产损失）、展示排序、非关键 UI 交互
4. **时间约束**：设置跨区块的 commit-reveal 延迟机制，虽仍有风险但攻击窗口被大幅压缩
5. **金额上限**：单次随机决策涉及资产价值低于攻击成本阈值（需结合当前 Gas 费和 MEV 市场评估）

## Audit Professional Techniques

**四层递进式审计框架：**

### L1: 快速扫描（5分钟）
- 正则匹配 `block\.timestamp.*keccak|block\.timestamp.*%|block\.timestamp.*random`
- 查看合约继承链是否有 GameInterface/LotteryBase 等模式合约（常见漏洞库存地）
- 检查 Natspec 注释，若缺少或声称"安全的随机"则提高警戒
- 搜索 TODO/FIXME/REVIEW 相关注释暗示不完整实现

### L2: 数据流追踪（15分钟）
1. **输入端污染分析**：block.timestamp 被接收后，检查是否经过 `keccak256()` 单层哈希（易攻击）
   - 单层哈希：直接可预测
   - 建议至少2层独立哈希 + 多变量混合
2. **传播路径追踪**：随机结果用作：
   - 数组索引 → 涉及资产转移 → **高危**
   - 条件判断 → 权限检查 → **中危**（需评估权限价值）
   - 仅展示用 → **低危**
3. **上下文关联**：同一函数内是否有其他 block 相关变量（block.number、blockhash）
   - 若仅 timestamp：风险 +70%
   - 若结合 3+ 变量且独立可操纵困难：风险 -30%

### L3: 攻击场景仿真（20分钟）
**矿工攻击成本评估矩阵：**
```
风险等级 = 预期收益 / (操纵成本 + 发现风险)

预期收益计算：
  - 彩票池 = 奖池总额 × 赢率（1/N）
  - Flashloan 借贷 = 需要注入的流动性
  - NFT Rarity = 稀有度溢价 × 拥有占比

操纵成本计算：
  - 矿工贿赂 = MEV 市场当日均价 × 目标块权重
  - 区块确认延迟 = 预期收益 × 概率折扣
  - 重试成本 = 交易费用 × 尝试次数

实际案例基准：
  - ETH 主网：单次 MEV 调度成本 ≈ 0.1 ~ 2 ETH（2024年数据）
  - 小于 5 ETH 的彩票不具有矿工攻击吸引力
```

### L4: 误报排除检查清单

**常见误报 Pattern A：时间锁 + 单一 timestamp**
```solidity
// 易误报为高危，实际低风险
function claim() external {
    require(block.timestamp > lockTime, "locked");
    // ... 转账逻辑
}
```
**判定逻辑**：时间戳用于业务流程控制（时间锁），不参与资产分配随机性
**应标记为**：时间检查，非随机数使用

**常见误报 Pattern B：哈希但无资产转移**
```solidity
function getMetadata() public view returns (string) {
    uint256 seed = uint256(keccak256(abi.encodePacked(block.timestamp)));
    return traits[seed % 100]; // 仅返回字符串，无资产转移
}
```
**判定逻辑**：随机结果不涉及金融决策，攻击者获益为零
**应标记为**：审美级随机化，可忽略风险等级

**常见误报 Pattern C：多变量 + 攻击成本分析**
```solidity
function selectWinner() public {
    uint256 rand = uint256(keccak256(abi.encodePacked(
        block.timestamp,
        block.number,
        blockhash(block.number-1),
        msg.sender,
        tx.gasprice
    ))) % winnerCount;
    payable(winners[rand]).transfer(1e16); // 0.01 ETH
}
```
**判定逻辑**：
- 变量数 = 5（≥3，良好混淆）
- 矿工可控 = timestamp + block.number（2/5 = 40%）
- 用户可控贡献 = msg.sender + tx.gasprice（难以预测）
- 预期收益 = 0.01 ETH（低于攻击成本）
**应标记为**：低风险（已过期代码或生产级已加缓解）

## Real Vulnerability vs False Positive Cases

**真实漏洞案例 1：Reentrancy + Timestamp Randomness（Poly Network，2021年）**
```solidity
// 伪代码示意
function claimReward() public {
    uint256 reward = rewards[msg.sender];
    uint256 randomMultiplier = uint256(keccak256(abi.encodePacked(block.timestamp))) % 2;
    payable(msg.sender).call{value: reward * (1 + randomMultiplier)}(""); // 可重入
    rewards[msg.sender] = 0;
}
```
- **为何是真漏洞**：矿工在同一区块内可预测 randomMultiplier，再结合重入漏洞，可在单笔交易内多次领取 2x 奖励
- **修复方式**：使用 Chainlink VRF 或 commit-reveal 方案

**真实漏洞案例 2：彩票抽奖跨度过短（TRON 生态某彩票，2022年）**
```solidity
function lottery() public {
    require(msg.value == 1 ether);
    tickets.push(msg.sender);

    if (tickets.length == 100) {
        uint winner_index = uint256(keccak256(abi.encodePacked(block.timestamp))) % 100;
        payable(tickets[winner_index]).transfer(99 ether);
        delete tickets;
    }
}
```
- **为何是真漏洞**：
  - 固定 100 人达到触发条件（攻击者可提前预知）
  - block.timestamp 精度仅秒级（±15秒操纵空间）
  - 矿工可通过延迟 15 秒来控制随机数，99 ETH 奖励远超 MEV 成本
- **修复方案**：Chainlink Automation 触发 + VRF 随机数

**误报案例 1：Governance 投票权重计算**
```solidity
function getVotingPower() public view returns (uint256) {
    return balance * (block.timestamp - depositTime) / 365 days;
}
```
- **为何是误报**：
  - block.timestamp 仅用于计算权重衰减，不涉及随机决策
  - 攻击者即使操纵时间戳也无法凭空增加 balance（由链上状态保证）
  - 符合 Low Risk Pattern：非随机数使用

**误报案例 2：应急停止机制中的时间戳检查**
```solidity
function emergencyWithdraw() external {
    require(block.timestamp < emergencyDeadline, "emergency period expired");
    require(msg.sender == owner);
    // 安全提取，需要 owner 权限
}
```
- **为何是误报**：
  - block.timestamp 仅作为业务流程检查点
  - 攻击者即使延迟区块也无法越过 owner 权限检查
  - 风险等级应为零（权限检查 > 时间检查）

## Distinction Experience

| 维度 | 真实漏洞 | 误报 | 审计技巧 |
|------|--------|------|--------|
| **随机参与** | timestamp 直接决定高价值资产分配 | timestamp 仅用于日志或权限辅助判断 | 追踪返回值用途，非资产转移可忽略 |
| **矿工收益** | 操纵成本 < 预期收益（明显正 ROI） | 操纵成本 >> 预期收益或无收益 | 计算 MEV 吸引力，查询当日 MEV 市场均价 |
| **变量独立性** | 大多变量矿工可控（>50%） | 多个独立链下输入或多链变量混合 | 逐个标记变量的可操纵性（C/U/M） |
| **时间窗口** | 单区块决议或用户可延迟 | 跨多个区块的 commit-reveal 模式 | 检查是否存在阶段分离（发起/验证/执行） |
| **资产规模** | 单次决策 > 5 ETH 或 100K USD | 单次 < 1 ETH 或纯展示用途 | 结合当前市场价格和 gas 费实时评估 |
| **代码迹象** | 缺乏安全注释、无替代方案研究 | 有明确的时间锁注释或已废弃代码 | 看注释、commit 历史、git blame 追溯意图 |
