# Solidity 质押奖励时间依赖漏洞

## Details

**代码特征示例：**
```solidity
function calculateReward(address user) public returns (uint256) {
    uint256 timeElapsed = block.timestamp - stakes[user].lastClaimTime;
    uint256 reward = stakes[user].amount * rewardRate * timeElapsed / 1 days;
    stakes[user].lastClaimTime = block.timestamp;
    return reward;
}
```

**快速定位核心操作技巧（L3：逐行读）：**
- 搜索关键模式：`block.timestamp` 与算术运算（`*`、`/`、`-`）组合
- 追踪奖励计算函数：`calculateReward`、`claimReward`、`getReward`、`earned`
- 检查时间差计算：查找 `timestamp - lastUpdate` 或 `duration` 相关变量
- 关注累积逻辑：`rewardPerToken`、`userRewardPerTokenPaid` 等状态变量更新时机

**快速定位保护机制技巧（L2：跳读）：**
- 检查时间窗口限制：`require(block.timestamp >= lastClaim + minInterval)`
- 验证区块高度辅助：是否同时使用 `block.number` 作为第二道防护
- 查找快照机制：是否在区块级别记录累积奖励而非实时计算
- 检查更新频率控制：`updateReward` modifier 是否在所有入口强制执行
- 审查管理员权限：时间参数（`rewardRate`）修改是否有时间锁保护

## Classify

**漏洞判定标准：**
- 奖励计算**直接依赖** `block.timestamp` 差值且无区块高度辅助校验
- 验证者可通过时间戳操纵（±15秒）获取超额奖励或导致其他用户奖励稀释
- 单笔操作的时间戳偏差可产生经济意义上的套利空间

**误报识别：**
- 时间戳仅用于**显示**或**事件记录**，不参与链上状态计算
- 存在严格的区块高度校验：`require((block.timestamp - lastUpdate) / BLOCK_TIME == (block.number - lastBlock))`
- 采用预言机喂价时间戳而非 `block.timestamp`

**代码异味：**
- 使用 `block.timestamp` 但配合了足够长的时间窗口（>1小时），时间戳操纵收益低于 Gas 成本
- 存在部分保护但不完整（如仅限制最小间隔但未限制最大间隔）

## Low risk

**低风险场景判定：**
1. **经济不可行性**：时间戳操纵（±15秒）带来的收益增量 < 0.01% 总奖励池且 < 单笔 Gas 费用
2. **时间粒度粗糙**：奖励计算以天/周为单位（`timeElapsed / 1 weeks`），秒级操纵影响可忽略
3. **存在对冲机制**：系统采用平均区块时间校准或定期重新锚定（如每 N 个区块强制同步）
4. **权限隔离**：仅链下计算使用时间戳，链上结算依赖默克尔树或签名授权
5. **测试/演示环节**：合约标记为非生产环境或总锁仓价值 < $1000

**降级依据：**
- 即使存在时间依赖，若攻击成本（矿工/验证者贿赂、MEV竞价）远高于预期收益，可降级为 Low
- 若项目已明确文档说明该设计权衡并设置了熔断机制，可视为已知风险降级处理

## 审计专业技巧

### 1. 真实漏洞识别要点

**高可信度风险信号（需报告）：**
- **直接流动性提取**：时间戳差值直接影响可转账代币数量，如 `transfer(user, reward)` 的 reward 完全由时间戳决定
- **关键状态污染**：更新的 `rewardPerToken`、`accruedReward` 等在后续计算中被重复使用，形成级联放大
- **无防护的外部调用**：奖励计算后立即执行 `safeTransfer(user, reward)` 而非先更新状态再转账
- **验证者激励对齐**：PoS 系统中验证者直接获益于时间戳操纵（如在自己的区块中延长时间），动机强烈

**现实攻击场景（主链实测）：**
```solidity
// Curve Finance 早期版本的真实风险
function claim_rewards(address addr) external:
    rewards = calculate_rewards(addr)  // 直接用 block.timestamp - lastClaim
    total_claimed += rewards           // 累积状态污染
    token.transfer(addr, rewards)      // 立即转账，无检查
```
验证者可在同一区块内多次调用（通过闪电贷重入）或推迟 1-2 个区块来积累时间戳差值。

### 2. 常见误报陷阱与排除法

**误报 1：过度敏感的时间戳检测**
- 工具检出所有 `block.timestamp` 使用都标记为风险
- **排除方法**：查看上下文，如果仅用于 `emit Event(timestamp)` 或用户可见的 `lastWithdraw` 返回值，则非漏洞
- **示例**：
  ```solidity
  withdrawals[msg.sender] = block.timestamp;  // 仅记录，不影响计算
  emit Withdrawal(msg.sender, block.timestamp, amount);  // 事件日志
  ```

**误报 2：已防护的时间窗口被误判**
- 合约虽然依赖时间戳，但强制了足够长的最小间隔（>1小时）
- **排除方法**：计算时间戳操纵能带来的最大收益，若 < 0.01% 奖励且 < 单笔 Gas 成本，风险可忽略
- **案例**：
  ```solidity
  require(block.timestamp >= lastClaim + 1 days, "Too frequent");
  reward = (block.timestamp - lastClaim) * rate;  // 时间差最多受 ±15秒影响
  // 影响量: (15秒 / 86400秒) * reward ≈ 0.017% 奖励，低于 Gas 成本
  ```

**误报 3：多层防护中遗漏单一防护层**
- 单独看某个合约有时间戳风险，但整个系统通过外层合约或预言机进行了约束
- **排除方法**：追踪调用链，查看如何从外部调用本合约，是否存在额外的时间检查或限流
- **示例**：
  ```solidity
  // 子合约：看似有风险
  contract RewardPool {
      function claimReward() external returns (uint256) {
          return (block.timestamp - lastUpdate) * rate;  // 直接依赖时间
      }
  }

  // 父合约：实际防护
  contract Manager {
      function claim() external {
          require(rateLimiter.canClaim(msg.sender), "Rate limited");  // 外层限制
          return rewardPool.claimReward();
      }
  }
  ```

**误报 4：时间戳用于非关键路径**
- 时间戳用于可选的加速轨道或降级模式，但关键路径不依赖
- **排除方法**：追踪所有调用该时间戳值的代码，确认是否必经路径
- **示例**：
  ```solidity
  function claimReward(uint256 proofAmount) external {
      if (proofAmount > 0) {
          // 可选路径：依赖时间戳（低频使用，可降级）
          reward += proofAmount * (block.timestamp - lastUpdate) / DAY;
      }
      // 关键路径：使用预言机喂价，独立于时间戳
      reward += oraclePrice.getAccruedReward(msg.sender);
      token.transfer(msg.sender, reward);
  }
  ```

### 3. 差异化审计策略

**按项目阶段分类：**
- **天使/种子轮**：低价值项目，即使有风险但因经济不可行性可接受，重点关注 Medium（突兀的设计缺陷）
- **主网部署前**：严格审查，任何时间戳依赖都需明确防护机制
- **已上线 > 3 个月**：若未曾被攻击，检查社区资本规模，< $1M TVL 的项目风险通常不值得开采

**按网络特性调整：**
- **权益证明网络（Ethereum 2.0、Polygon）**：验证者不能任意操纵时间戳（由协议约束），风险低于 PoW
- **权力证明网络（Bitcoin 及多签）**：严格限制时间戳在过去 2 小时内，PoW 中矿工操纵成本极高
- **Rollup/侧链**：时间戳完全由排序器控制，风险等同于中心化环节的受信度

**按代币经济学评估：**
```
风险等级 = (时间戳操纵收益 / 攻击成本) * (操纵概率 / 检测难度)

低于 0.01 = Low
0.01-0.1 = Medium
0.1+ = High
```

### 4. 审计中的实战检查清单

**快速筛查（5 分钟内排除 90% 误报）：**
- [ ] grep 所有 `block.timestamp` 出现次数，统计有多少行真的影响状态计算（vs 仅显示/事件）
- [ ] 检查是否存在 `lastUpdate`/`lastClaim` 等时间戳缓存，追踪其更新频率
- [ ] 搜索 `block.number`，若与 `block.timestamp` 并行使用，说明开发者已考虑防护
- [ ] 查看修饰符 `modifier updateReward` 是否在所有公开入口强制执行

**深度审查（15 分钟内定性判定）：**
- [ ] 计算单次操纵能获得的最大奖励绝对值（不是百分比），与 gas 成本比较
- [ ] 追踪该奖励如何流出合约（直接 transfer？分批领取？）
- [ ] 检查是否存在重入保护或预防措施
- [ ] 查看代币白名单，若为稳定币，风险相同；若为无流动性 token，攻击动机低

**复审环节（发现风险后的核实）：**
- [ ] 编写 PoC：模拟验证者延迟 N 个区块并推迟时间戳，计算最终能获利多少
- [ ] 检查历史交易，是否存在类似的时间戳操纵迹象（分析链上数据）
- [ ] 与开发者确认该合约的预期使用方案，是否与审计假设一致

### 5. 真实案例对比

| 项目 | 漏洞特征 | 判定 | 原因 |
|------|--------|------|------|
| Curve Finance | `block.timestamp` 直接计算奖励，无间隔限制 | **HIGH** | 验证者可多次提取同一时刻奖励 |
| Uniswap V3 | TWAP 使用过去 30 秒价格，但有区块高度校验 | **Low** | 15 秒误差 < 0.01%，且有二阶防护 |
| Compound | `accrueInterest()` 依赖时间戳但被 modifier 包装强制执行 | **Low** | 累积发生在所有状态改变前，避免重入 |
| Yearn | 时间戳仅用于 `lastHarvestBlock` 记录，获益计算基于区块数 | **Safe** | 完全解耦时间戳依赖 |

这个表格可帮助理解"相同风险代码"在不同上下文的不同评级。
