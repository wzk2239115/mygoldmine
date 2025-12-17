# 无上限固定 APY (Solidity)

**漏洞类型：** 经济模型缺陷 - 通货膨胀失控

**常见场景：** 质押收益合约、流动性挖矿、锁仓奖励、债券协议、收益聚合器

---

## Details

**代码特征示例：**
```solidity
// 典型漏洞模式
function calculateReward(address user) public view returns (uint256) {
    uint256 principal = stakes[user].amount;
    uint256 duration = block.timestamp - stakes[user].startTime;
    return principal * FIXED_APY * duration / (365 days * 100); // 无总量cap检查
}

function claimReward() external {
    uint256 reward = calculateReward(msg.sender);
    rewardToken.mint(msg.sender, reward); // 无限铸币
}
```

**快速定位核心操作 (L3: 逐行读)：**
- 搜索关键函数：`calculateReward/claimReward/getReward/harvest`
- 关注收益计算公式：`principal * rate * time`
- 追踪铸币/转账操作：`mint()`, `transfer()`, `safeTransfer()`
- 检查时间因子：`block.timestamp - startTime`, `duration`, `periods`
- 查找利率常量：`APY`, `RATE`, `YIELD_PER_SECOND`, `REWARD_RATE`

**快速定位保护机制 (L2: 跳读)：**
- 总量上限检查：`require(totalMinted < MAX_SUPPLY)` ✓
- 储备金验证：`require(rewardPool.balance >= pendingReward)` ✓
- 时间窗口限制：`require(duration <= MAX_DURATION)` ✓
- 收益率动态调整：`rate = adjustRate(totalStaked, remainingRewards)` ✓
- 紧急熔断机制：`whenNotPaused`, `emergencyWithdraw` ✓
- **缺失任一机制需提高审计等级至 L4 跨模块追踪**

---

## Classify

**漏洞判定条件：**
1. 固定利率 + 无总量上限 + 可无限铸币 → **确认漏洞**
2. 固定利率 + 有名义上限但不检查 → **确认漏洞**
3. 固定利率 + 储备金有限 + 先到先得 → **经济风险**（非技术漏洞但需披露）

**误报排除：**
- 奖励来自预充值池且代码强制检查余额充足 → **误报**
- 合约生命周期有明确终止区块/时间且已限制 → **误报**
- APY 看似固定但实际由 Oracle 或治理动态调节 → **需进一步审计调节机制**

**代码异味边界：**
- 有硬顶但设置过高（如 uint256.max）→ **代码异味**，需评估实际经济影响
- 依赖外部合约 balanceOf 判断但未考虑闪电贷攻击 → **升级为漏洞**

---

## Low risk

**可接受的低风险场景：**
1. **测试网/实验性功能：** 协议明确标注为测试阶段，TVL 限额 < $10k
2. **多层保护冗余：** 同时具备 `cap检查 + 储备金验证 + 时间锁 + 治理暂停` 四重机制
3. **经济自洽性：** 协议费收入 > 预期奖励支出，且经过压力测试验证
4. **极短周期：** 活动持续时间 < 7 天且有白名单限制参与者
5. **可升级合约 + 活跃治理：** 管理员能在 24 小时内响应并调整参数（需评估中心化风险）

**降级条件（从 High → Low）：**
- 总锁仓价值 < $50k 且用户明确知晓风险
- 合约已运行 > 1 年且储备金充足度 > 300%
- 存在强制清算机制限制单一用户收益占比

---

## 审计专业技巧

### 1. 真实漏洞的四重确认法

**症状识别阶段：**
- 搜索所有 `mint()` 调用，记录调用栈深度（越浅风险越高）
- 对比 ERC20 代币的 `totalSupply()` 增长趋势与 TVL 增长倍数
- 追踪奖励资金来源：自铸币 vs 预充值 vs 动态调拨
  - 自铸币：需要严格的总量cap (95%概率是漏洞)
  - 预充值：需要验证充值时机与取款时序防止耗尽
  - 动态调拨：需要审计调拨逻辑本身是否安全

**数学验证阶段：**
```
计算公式：总铸币量 = Σ(principal_i × APY × time_i) for all users
预期储备 = 初始资金 + 合约费收入
风险判定：if (总铸币量 > 预期储备) → 高风险
```
- 模拟1年、3年、5年后的代币总量
- 对比链上实际价值与合约锁定资产比例
- 检查是否存在通过前期高APY吸血后跑路的模式

**对比分析阶段：**
- 同期 Aave/Curve/Uniswap 的真实利率基准 (通常 0.5%-15%)
- 固定APY与市场波动率的乖离度分析
- 项目创始人历史信用评分

**修复验证阶段：**
- 若代码中存在cap，验证cap值是否可由任意地址修改
- 审计 `onlyOwner` 修饰符的权限控制是否为多签/timelock
- 检查升级机制是否引入新的绕过漏洞

### 2. 常见误报陷阱及区分方法

**误报案例1：看似无cap的动态计算**
```solidity
// 看起来风险很高
uint256 reward = balance * APY / 100;
rewardToken.transfer(msg.sender, reward);
```
但实际上可能是：
- `balance` 受限于 `min(staked, rewardPool.available())`
- `APY` 实际上是按块动态降速的（伪代码）
- 转账可能会因 `rewardPool` 余额不足而回滚

**识别方法：** 必须追踪 `rewardPool` 和 `available()` 的全部赋值点，不能仅看单个函数

**误报案例2：链接到预言机的"固定"利率**
```solidity
uint256 fixedAPY = 10; // 看起来是常数
uint256 reward = principal * fixedAPY / 100;
// 但可能在其他函数修改
function updateAPY(uint256 newRate) external onlyGovernance { fixedAPY = newRate; }
```

**识别方法：** 搜索所有对利率常量的写操作，评估修改权限和时间延迟

**误报案例3：铸币总量有hardcap但溢出**
```solidity
// uint96 hardcap 但通过多次mint累加可能溢出
require(totalMinted <= type(uint96).max);
totalMinted += reward;
rewardToken.mint(msg.sender, reward);
```

**识别方法：** 检查变量类型，计算最大可能累加次数与类型上限

### 3. 现场审计检查清单

| 检查项 | 判断标准 | 优先级 |
|--------|--------|--------|
| 奖励资金来源 | 自铸币(必须有cap) vs 预充值(必须验证余额) | P0 |
| Cap机制有效性 | 类型溢出风险、管理员可修改性、跨合约绕过 | P0 |
| 时间参数安全 | 防止block.timestamp操纵、计算精度损失 | P1 |
| 提取限流 | 单用户/单时段提取上限、冷却期 | P1 |
| 外部依赖安全 | Oracle风险、闪电贷、重入 | P1 |
| 储备金充足率 | 实际资金 vs 待支付承诺、压力测试覆盖率 | P2 |
| 治理权限 | 参数修改门槛、时间锁有效期 | P2 |
| 历史对比 | 同行业协议的利率水平与运行时长 | P2 |

### 4. 真实案例区分练习

**案例A：Olympus DAO 的初期模型**
- 症状：固定的高APY（最高可达8000%）+ 无明确总量cap
- 判定：**真实漏洞** - 导致OHM超发，需要不断新用户充值维持
- 关键：虽然项目方可能声称"有治理调整"，但初期缺乏有效制约

**案例B：某测试网APY合约**
- 症状：固定APY 10% + `require(msg.sender == testAdmin)`
- 判定：**误报** - 权限严格限制，测试性质明确
- 关键：小规模且完全中心化，无实际经济风险

**案例C：Curve 的gauge奖励**
- 症状：固定APY数值 + 实际由veToken投票动态调整
- 判定：**误报** - 虽然代码变量名为"fixed"但本质动态
- 关键：需阅读治理合约和历史提案，理解制度设计意图

### 5. 审计报告撰写要点

对于此类问题，风险等级判定需要包含：
- **发生概率**：基于资金充足率、运营天数、团队信用
- **经济影响**：计算用户最坏情况下损失的百分比
- **修复难度**：升级合约改参数 vs 重设计 vs 无法修复
- **利益相关者**：显式列出谁从通货膨胀中获益

**建议范例：**
> 本合约存在固定APY + 无总量cap的组合漏洞。基于当前$500K TVL，若按固定20% APY，12个月后需支付$100K奖励。经审查发现奖励资金来自新用户充值而非内生收益。若用户净流入停止，则后进入用户无法获得承诺奖励，构成结构性风险。**评级：High**（假设团队无可升级权限）或 **Medium**（若具备3日时间锁升级权限）。
