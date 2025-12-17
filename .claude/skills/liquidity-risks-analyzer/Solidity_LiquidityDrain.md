# Solidity 流动性耗尽漏洞审计手册

**漏洞类型：** Liquidity Drain  
**常见场景：** AMM 兑换、流动性提供与移除、单边质押收益池  
**典型成因：** 流动性比例计算错误、未限制最小流动性阈值、移除流动性时未校验池状态

---

## Details

### 代码示例
```solidity
function removeLiquidity(uint256 shares) external {
    uint256 amount = (totalAssets * shares) / totalShares;
    totalShares -= shares;
    totalAssets -= amount;
    token.transfer(msg.sender, amount); // 未检查池子是否完全耗尽
}
```

### 快速定位核心操作（L3: 逐行读）
- **关注函数：** `removeLiquidity`, `withdraw`, `burn`, `redeem`, `exit`
- **计算逻辑：** 定位 `shares/totalSupply` 或 `amount/reserve` 比例计算
- **转账语句：** 追踪 `transfer`/`safeTransfer` 前的状态更新顺序
- **边界条件：** 检查 `totalSupply == 0` 或 `reserve == 0` 时的处理逻辑
- **最后提取者：** 验证最后一个提取者是否能取走所有剩余资产

### 快速定位保护机制（L2: 跳读）
- **最小流动性锁定：** 搜索 `MINIMUM_LIQUIDITY`、`MIN_RESERVE`、`1000` 等常量
- **阈值检查：** 定位 `require(reserve >= minReserve)` 类似断言
- **重入保护：** 确认是否有 `nonReentrant` 或状态变更在转账前
- **零地址销毁：** 检查是否永久锁定初始流动性至 `address(0)` 或 `DEAD`
- **紧急暂停：** 查找 `pause`/`emergency` 相关状态检查

---

## Classify

**漏洞判定标准：**
- 最后提取者可取走全部资产导致池子无法恢复运作 → **高危漏洞**
- 首次流动性提供者可通过精心构造的微小份额操纵比例 → **中危漏洞**
- 缺少最小流动性锁定但有外部监控机制可干预 → **低危漏洞**

**误报排除条件：**
- 协议设计明确允许池子归零并有重启机制（如管理员重新初始化）
- 首次存款通过工厂合约强制锁定足够初始流动性
- 池子类型为临时性质（如清算专用池，完成后自动销毁）

**代码异味识别：**
- 存在最小流动性保护但阈值设置过低（如仅 1 wei）
- 依赖链下机器人或治理投票来维持最低流动性
- 保护逻辑存在但被 `onlyOwner` 可禁用

---

## Low Risk

**以下情况评定为低风险：**

1. **已有充分保护但实现不优雅：** 使用外部监控而非合约原生强制，如依赖定时任务补充流动性
2. **影响范围可控：** 仅影响单一隔离池子，不会传导至其他模块或跨链资产
3. **经济成本不合理：** 攻击者需持有大量份额且成本远超收益（如需持有 99% 流动性）
4. **存在替代防护：** 如时间锁延迟提取、多签审批大额移除、社区监督窗口期
5. **限定场景触发：** 仅在特殊市场条件下（如极端价格偏离）才可能耗尽，正常运营概率极低
6. **可快速恢复：** 协议有自动注资机制或保险基金可在区块内恢复流动性

**风险降级考虑因素：**
- 审计历史与运行时长（已稳定运行 1 年以上）
- TVL 规模（实际锁仓价值低于攻击成本）
- 治理响应速度（可在 1 小时内紧急干预）

---

## 审计专业技巧

### 真实漏洞 vs 误报的核心区分

#### 实战案例一：最小流动性锁定的真假判别
**误报场景（错误判断）：**
```solidity
// Uniswap V2 风格（正确实现）
uint256 constant MINIMUM_LIQUIDITY = 1000;
function removeLiquidity(...) {
    require(liquidity > MINIMUM_LIQUIDITY, "Insufficient liquidity");
    // ...
}
```
初审审计员看到"只锁定 1000 wei"就报高危。**实际上这是标准做法**，因为：
- 1000 wei 对于 18 位小数代币是 0.000000000000001000，经济价值近似于零
- 首次流动性提供者通常会锁定远超最小值的流动性，实际锁定量是百万级别
- 即使被绕过，攻击者也只能取出 999 wei 级别的额外资产

**真实漏洞（需要报的）：**
```solidity
// 问题代码
uint256 constant MIN_LIQUIDITY = 1; // 只锁定 1 wei
function removeLiquidity(uint256 shares) external {
    require(shares > 0, "Invalid shares");
    // 缺少任何流动性余量检查
    uint256 amount = (totalAssets * shares) / totalShares;
    totalShares -= shares;
    token.transfer(msg.sender, amount);
}
// 攻击者可完全耗尽池子，最后提取者获得所有剩余资产
```

#### 实战案例二：比例计算精度问题的识别
**误报高频错误：**
```solidity
// 看起来有风险的代码
function withdrawShare(uint256 share) external {
    uint256 balance = token.balanceOf(address(this));
    uint256 amount = (balance * share) / totalShare;
    // 审计员担心：最后一个提取者获得全部资产
}
```
**关键的区分点：**
- 需要检查 `totalShare` 减少逻辑，如果正确递减，即使有舍入误差也在可控范围
- 真正的风险在于：`share > totalShare` 时是否有防护
- 如果缺少 `require(share <= totalShare)` 才是真漏洞

**真实的舍入漏洞案例：**
```solidity
// 单向舍入导致永久流动性锁定
function deposit(uint256 amount) external returns(uint256) {
    uint256 shares = (amount * totalShares) / totalAssets;
    // 如果 shares 计算结果为 0（因舍入），代币被锁定但不给予任何份额
    require(shares > 0, "Shares must be non-zero");
    // ...
}
```

### 审计检查清单（按风险优先级）

#### Tier 1：必查（95% 真实漏洞命中率）
1. **最后提取者检验：** 手工计算当 `totalShares == 0` 后是否还能提取
   - 实际操作：在纸上模拟 3 个用户，第 3 个用户提交全部份额后的余额情况

2. **初始化阶段的份额操纵：** 第一个流动性提供者能否通过转账前的闪电贷操纵比例
   - 检查是否有 `require(totalShares == 0)` 的 addLiquidity 初始化保护

3. **跨层调用追踪：** 看外部协议是否能绕过内部保护
   - 例：通过 flash loan 增加池子余额，再以虚假比例提取

#### Tier 2：高概率（70% 真实漏洞命中率）
1. **保护机制的可禁用性：** 检查 pause/upgrade 权限是否被滥用
   - 真实案例：MakerDAO 早期投票可直接关闭流动性检查

2. **外部条件依赖检查：** 依赖的预言机、交易对是否可被操纵
   - 如果比例计算依赖 Uniswap 价格，需要检查价格操纵风险

3. **边界整数计算：** 当 amount 非常小时的 rounding 方向
   ```solidity
   // 下舍入导致最终资产丢失
   uint256 amount = (tiny * shares) / totalShares; // 若结果 < 1 wei 则为 0
   ```

#### Tier 3：确认型检查（需要结合上下文）
1. 总资产是否来自单一来源或多个来源（多源更安全）
2. 是否有重入防护（非关键但加分项）
3. 是否有事件日志便于链下监控

### 真实漏洞误报的高频陷阱

**陷阱 1：对标准 AMM 设计的过度担忧**
- Uniswap 早期论文明确提到"最后 LP 可能获得微量额外资产"，这是 trade-off，非漏洞
- 审计应评估：额外资产是否对协议造成不可恢复的破坏

**陷阱 2：混淆"池子可以为空"与"池子会被恶意耗尽"**
- 许多闪电贷 AMM 运行时池子多次归零，但设计允许
- 真正的漏洞是：归零后协议无法继续运作且无恢复机制

**陷阱 3：忽视经济激励层面**
- 提取全部流动性需要持有 ≥ 51% 份额
- 审计员应计算：持有该份额的成本 vs 能获得的收益
- 如果成本 > 收益，经济上不可行，降为低风险

**陷阱 4：错误评估外部保护的强度**
- 多签延迟：7 天内多签可暂停提取 → 实际有效
- 社区监督窗口期：前 24h 风险最高，之后社区反应完成 → 分级评估
- 保险基金覆盖：需确认基金规模 ≥ TVL 的 110%

### 报告撰写指南

**高危报告示例（真实漏洞）：**
```
标题：流动性完全耗尽漏洞
根因：removeLiquidity 函数缺少最小流动性保护
证明：
1. 部署池子并注入 100 ETH 流动性
2. 用户 A 注入 1 ETH，获得相应份额
3. 用户 A 提取全部份额
4. 池子剩余 0.001 ETH（四舍五入损失）
5. 后续用户无法正常交互，协议瘫痪
修复建议：添加 require(reserve >= MINIMUM_LIQUIDITY) 检查
```

**低危报告示例（设计权衡）：**
```
标题：舍入导致的微量资产积累（信息性，非漏洞）
情景：在极端市场波动下，连续的提取操作可能导致池子累积 < 0.1% 的资产
影响：可以忽略不计，但建议添加管理员提取函数用于清理残余资产
修复建议：非关键，可在下版本优化
```

---

## 现实案例学习

### Bancor 的悲剧（学习什么不应该做）
Bancor 协议在流动性耗尽事件中的教训：
- 当 BNT 储备降至危险水位时缺乏自动暂停机制
- 触发条件明确（reserve < 20%）但缺乏可执行的防护代码
- 教训：**检查点和防护之间不能有代码逻辑缺口**

### Curve 的启示（学习如何做对）
- 多层保护：初始化锁定、per-block 限制、管理员紧急制动
- 每一层都是独立的，任一层失效都不会导致完全耗尽
- 教训：**分层防护优于单点防护，检查是否所有层都被正确审计**
