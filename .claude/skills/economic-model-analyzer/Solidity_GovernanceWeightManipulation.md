# Solidity_GovernanceWeightManipulation

**治理权重操纵漏洞**：治理投票权重计算存在漏洞，允许通过特定操作放大投票权或绕过权重限制。

---

## Details

**代码示例场景：**
```solidity
// 典型漏洞模式
function getVotingPower(address user) public view returns (uint256) {
    return balanceOf(user) * multiplier;  // 权重计算无快照保护
}

function delegate(address to) external {
    delegatedVotes[to] += balanceOf(msg.sender);  // 可重复委托累加
}

function vote(uint proposalId) external {
    uint power = token.balanceOf(msg.sender);  // 实时余额可闪电贷操纵
    proposals[proposalId].votes += power;
}
```

**快速定位核心操作技巧（L3-逐行读）：**
- 搜索关键函数：`vote`, `delegate`, `getVotingPower`, `cast`, `propose`
- 检查权重来源：`balanceOf()`, `stakedAmount`, `delegatedVotes`, `votingPower`
- 追踪时间维度：是否使用快照（`snapshot`, `checkpoints`, `getPastVotes`）或实时余额
- 委托逻辑：`delegate`, `delegateBySig` 是否允许循环委托、重复委托、链式委托
- 倍数计算：`multiplier`, `weight`, `boost` 等系数是否可被操纵
- 提案阈值：`proposalThreshold`, `quorum` 检查点是提案创建时还是投票时

**快速定位保护机制技巧（L2-跳读）：**
- 快照机制（L1-关键词）：搜索 `snapshot`, `_checkpoint`, `getPastVotes`, `blockNumber` - 权重是否锁定在特定区块
- 时间锁（L1-关键词）：`timelock`, `votingDelay`, `minVotingPeriod` - 是否有冷静期防止即时操纵
- 重入保护（L1-关键词）：`nonReentrant`, `ReentrancyGuard` - 防止递归调用放大权重
- 上限检查（L2-跳读）：`maxVotingPower`, `cap`, `require(power <= max)` - 权重是否有天花板
- 委托限制（L3-逐行读）：检查 `_delegate` 内部是否清零旧委托、防止循环引用（`delegatee != msg.sender`, 深度限制）
- 提案创建门槛（L1-关键词）：`proposalThreshold` 是否基于历史快照而非当前余额

---

## Classify

**漏洞标准：**
- 权重可通过闪电贷/转账在单区块内放大且影响治理结果
- 委托机制允许双重计票、循环委托或重复累加
- 权重计算使用可操纵的外部价格源（如DEX现货价格）而无TWAP或预言机
- 提案创建/投票时无历史快照保护，攻击者可临时借入代币

**误报识别：**
- 已使用OpenZeppelin ERC20Votes标准快照机制（`_checkpoint`系统）
- 权重锁定在提案创建前的历史区块（`proposalSnapshot`）
- 委托逻辑正确维护`_moveDelegates`且防止自委托/循环
- 存在足够长的`votingDelay`（如1天）阻止即时套利

**代码异味（需进一步验证）：**
- 使用实时余额但存在其他经济约束（如高额提案押金、长锁定期）
- 权重计算复杂涉及多代币/跨链数据但有独立审计和限制器
- 自定义快照实现（非标准库）需逐行验证正确性

---

## Low risk

**以下场景可评为低风险：**

1. **经济约束足够强**：虽用实时余额但代币流动性差（如锁仓代币）、治理仅限内部小圈子、恶意提案成本极高

2. **影响范围受限**：治理权限仅控制非关键参数（如前端展示、文档链接）而非资金/协议核心逻辑

3. **多重防护降低可利用性**：结合短期时间锁+多签批准+紧急暂停的多层治理，单次投票操纵难以完成攻击

4. **闪电贷防护存在但不完美**：如使用双区块快照（攻击需跨区块持仓）但未达到建议的7天锁定

5. **委托边界清晰**：允许委托但有深度限制（如3层）、权重衰减机制或单地址委托上限

6. **仅影响链下治理**：投票结果仅作链下参考（Snapshot式），最终执行需链下多签确认

---

## 审计专业技巧

### 真实漏洞与误报的区分经验

**关键区分点1：快照时间与投票执行的间隔**

真实漏洞表现：
- 权重快照在 `propose()` 执行，但投票在之后的任意区块进行
- 攻击者可在提案创建后的任何时刻（如投票结束前1分钟）闪电贷借入大量代币投票
- 示例：Compound Governance早期存在的漏洞，提案权重和投票权重检查点不同步

误报场景：
- 快照在 `vote()` 函数执行时锁定权重（虽然这样设计不优雅，但确实防止了闪电贷）
- 使用 OpenZeppelin ERC20Votes 的 `getPastVotes()` 函数，自动从历史检查点读取（需验证调用参数是否为已过去的区块）

**审计技巧**：追踪权重快照的三个时间点：
1. 提案创建时刻的块号保存（`proposalSnapshot`）
2. 投票时使用的块号（应等于第1点，而非 `block.number`）
3. 权重更新的区块确认（确保没有中间交易修改余额）

---

**关键区分点2：委托逻辑中的"幽灵投票"**

真实漏洞表现：
- 委托者转账代币后，仍保留委托权重；受委托者也获得了权重
- 导致同一份代币被计算两次
- 示例代码：
```solidity
function delegate(address to) external {
    uint amount = token.balanceOf(msg.sender);
    delegatedVotes[to] += amount;
    // 错误：未清空msg.sender自身的votes
}
```

误报场景：
- 使用 `_moveDelegates()` 模式，委托时自动从委托者余额移出到受委托者
- 委托者的 `_delegates[msg.sender]` 被正确设置为新地址
- 验证方法：检查 `vote()` 函数是否使用 `delegatedVotes[addr]` 还是 `votes[addr]`；正确实现应使用后者并通过 `_delegates` 链找到最终受益人

**审计技巧**：绘制"权重流图"，追踪单个代币在不同地址间的权重映射关系，确保每个代币仅被计算一次。

---

**关键区分点3：提案创建门槛与权重膨胀**

真实漏洞表现：
- `proposalThreshold` 基于实时余额计算（如需要当前 1% 供应量创建提案）
- 攻击者可用闪电贷临时获得足够代币来创建恶意提案
- 示例：MakerDAO 早期治理中的 MKR 代币可被瞬间集中

误报场景：
- 提案阈值基于历史快照（如 "需要投票启动前1天的持仓达到1%"）
- 或提案创建需要高额真实押金（如锁定等额代币7天），经济成本足够高

**审计技巧**：搜索 `proposalThreshold` 变量的赋值和使用：
- 如果直接调用 `token.totalSupply()` 和 `token.balanceOf()`，判定为风险
- 如果引用过去的某个快照或检查点，判定为安全

---

**关键区分点4：权重倍数与价格预言机风险**

真实漏洞表现：
- 投票权基于代币余额×外部价格（如 tokenA余额×USDC价格）
- 使用即时DEX价格而非时间加权平均价（TWAP）
- 闪电贷可操纵DEX现货价格，进而放大投票权

误报场景：
- 使用链上预言机如 Chainlink，具有多源聚合和延迟保护
- 权重倍数仅基于固定系数（如 tokenA 权重=2×tokenB），与价格无关

**审计技巧**：搜索所有权重计算中的乘除操作，特别是涉及外部数据源的部分：
```solidity
// 危险模式
voting_power = balance * dex.getPrice(token)

// 安全模式
voting_power = balance * oracle.getTWAP(token, 1 hour)
```

---

### 实战审计检查清单

**第一阶段：快速排查（5分钟）**
- [ ] 搜索 "snapshot" 或 "Votes" 确认是否使用标准库
- [ ] 检查 `vote()` 函数中的权重来源：`balanceOf()` 还是 `getPastVotes()`
- [ ] 查看 `propose()` 是否保存块号，以及投票时是否使用该块号

**第二阶段：深度验证（20分钟）**
- [ ] 追踪委托链：从投票地址→委托目标→最终权重拥有者，确保路径唯一
- [ ] 验证权重快照的时间线：提案创建→投票启动→投票结束→执行的块号关系
- [ ] 检查是否存在权重累加点（如委托后未清空自身权重）

**第三阶段：经济可行性评估（15分钟）**
- [ ] 评估闪电贷成本：借入所需代币量的费用（通常0.05%）vs 获益
- [ ] 检查代币流动性：是否存在足够的DEX或借贷池支持大额闪电贷
- [ ] 评估治理权限范围：最坏情况下控制投票会产生什么经济损失

---

## 高风险指标表

| 指标 | 高风险 | 中风险 | 低风险 |
|------|--------|--------|---------|
| 权重快照来源 | `block.number` | 提案创建时的块 | `getPastVotes()` + 明确块号 |
| 委托机制 | 无深度限制+无清零 | 自定义实现+有检查 | OpenZeppelin `_moveDelegates` |
| 投票延迟 | 0 区块 | 1-100 区块（<15分钟） | >1000 区块（>4小时） |
| 提案创建门槛 | 实时余额+低占比 | 历史快照+中等占比 | 高额真实押金+历史快照 |
| 价格预言机 | 即时现货价格 | 短期TWAP（<1小时） | Chainlink+多源聚合 |
| 提案执行 | 直接链上执行 | 时间锁+单签 | 时间锁+多签+紧急暂停 |
