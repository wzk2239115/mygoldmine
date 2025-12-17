# Solidity - 无上限铸币奖励 (Unbounded Mint Reward)

**漏洞分类**: 经济模型缺陷  
**常见场景**: 质押奖励、流动性挖矿、代币分发、治理激励  
**核心风险**: 代币铸造奖励未设总量上限，导致通胀失控或经济模型崩溃

---

## Details

**代码特征示例**:
```solidity
function claimReward(address user) external {
    uint256 reward = calculateReward(user);
    token.mint(user, reward);  // ⚠️ 无总量校验
}

function distributeStakingReward(uint256 amount) external {
    for(uint i=0; i<stakers.length; i++) {
        rewardToken.mint(stakers[i], amount);  // ⚠️ 循环铸币无上限
    }
}
```

**快速定位核心操作**（L3-逐行读）:
- 搜索关键函数: `mint()`, `_mint()`, `mintReward()`, `distributeReward()`
- 追踪奖励计算逻辑: `calculateReward()`, `pendingReward()`, `earned()`
- 检查铸币触发点: 质押/解质押时、定期分发时、手动claim时
- 确认是否存在: `totalSupply` 边界检查、`maxSupply` 常量、累计铸币量记录

**快速定位保护机制**（L2-跳读 → L4-跨模块追踪）:
- **L2-跳读**: 在铸币函数内查找 `require(totalSupply() + amount <= maxSupply)`
- **L2-跳读**: 检查是否有 `rewardCap`, `emissionLimit`, `inflationRate` 等限制变量
- **L3-逐行读**: 验证保护条件是否在所有铸币路径生效（包括批量操作）
- **L4-跨模块追踪**: 确认 `maxSupply` 是否可被管理员修改（治理风险）
- **L4-跨模块追踪**: 检查代币合约是否在外部实现了供应量限制

---

## Classify

**研判为高危漏洞**:
- 铸币函数无任何总量限制，且调用频率不可控
- 奖励计算依赖可操纵参数（时间戳、外部价格、用户余额）
- 存在循环铸币且迭代次数不受限
- 管理员可无限铸币且无时间锁/多签保护

**研判为误报**:
- 代币合约在 `_mint()` 内部已实现 `maxSupply` 校验（需跨合约验证）
- 铸币权限已通过 DAO 治理锁定，且需多数票通过
- 奖励池采用预铸币模式（从储备池转账而非铸造）
- 铸币触发条件极度严苛（如需销毁等量其他资产）

**降级为代码异味**:
- 铸币有上限但阈值设置不合理（过高或通过简单操作即可达到）
- 存在速率限制但时间窗口过长
- 依赖链下预言机喂价控制铸币量（预言机攻击风险）

---

## Low risk

**低风险场景**:
1. **短期测试合约**: 明确标注为测试网部署或有明确的生命周期限制
2. **经济沉没成本**: 触发无限铸币需要攻击者先销毁/锁定大量其他资产，且ROI为负
3. **已有外部熔断机制**: 
   - 跨链桥有铸币总量监控并可紧急暂停
   - 依赖外部 Oracle 且有异常检测熔断
4. **治理延迟保护**: 铸币参数修改需经过 7+ 天时间锁，社区有充分响应时间
5. **奖励池预分配**: 虽代码中调用 `mint()`，但实际已通过构造函数预铸币并转入奖励合约
6. **经济模型容忍**: 项目明确采用通胀模型（如PoS共识奖励），且年通胀率在预期范围内（<10%）

**关键判断依据**:
- 计算最大铸币速率: `单次铸币量 × 调用频率 × 时间周期`
- 对比代币总供应量: 若年通胀 <5% 且有递减机制，可降级
- 验证攻击成本: 若触发铸币需质押 >1M USD 且有 Slashing 惩罚，可降级

---

## 审计专业技巧与经验

### 1. 多维度审计检查清单

**第一步：全局供应量追踪**
```
□ 在所有合约构造函数中统计初始铸币量
□ 遍历所有包含 mint/burn 的函数，计算净增长
□ 跨合约追踪（主合约 → 奖励合约 → 流动性合约 → 桥接合约）
□ 检查是否存在隐藏的 selfdestruct() 销毁资产或 delegatecall() 逃逸
□ 验证 totalSupply 变量与实际铸币量的一致性
```

**第二步：权限与访问控制验证**
```
□ mint 函数的 msg.sender 限制：是否仅限 owner/minter 角色？
□ minter 角色如何授予与撤销？是否有时间锁或多签要求？
□ 管理员是否能改写 maxSupply、rewardRate 等关键参数？
□ 是否存在 renounceOwnership() 后的 onlyOwner 调用漏洞？
□ 代理合约升级是否受限（UUPS/Transparent Proxy 的 ProxyAdmin 权限）？
```

**第三步：时间维度分析**
```
□ 奖励调用频率：block.number 间隔？时间戳精度？
□ 是否存在 block.timestamp 操纵风险（矿工/验证者）？
□ 时间锁有效期：设置为 0 = 无保护；>7 天 = 合理
□ 利息计算周期：秒级精度是否导致精度损失或溢出？
□ 过期奖励是否会无限累积（lastClaimTime 初始化不当）？
```

### 2. 真实漏洞 vs 误报的区分标准

**案例1：Compound 代币铸币漏洞（真漏洞）**
```solidity
// 漏洞代码
function _setComptroller(ComptrollerInterface newComptroller) public {
    ComptrollerInterface oldComptroller = comptroller;
    comptroller = newComptroller;
}

// 风险：新 Comptroller 可以调用 _mint()
// 如果治理被攻占，可以无限铸币 COMP 代币
// 区分依据：
// ✓ 漏洞特征：不需质押/锁定资产，无 ROI 成本
// ✓ 攻击者获益：直接获得代币流动性
// ✓ 历史记录：曾被安全审计指出但修复不彻底
```

**案例2：Yearn 奖励计算溢出（真漏洞）**
```solidity
// 漏洞代码
uint256 reward = (pricePerShare - lastPrice) * sharesOutstanding;
// 未检查 sharesOutstanding 是否被操纵，无上限检查
// 攻击流程：
// 1. 通过闪贷借入大量资金
// 2. 进行质押，增加 sharesOutstanding
// 3. 触发 pricePerShare 的快速变动
// 4. 提取 reward > 实际资金池余额 → 合约破产
// 区分依据：
// ✓ 需要控制多个变量（价格 + 数量）
// ✓ 实际造成经济模型崩溃
```

**案例3：常见误报示例**
```solidity
// 代码：有基础的上限检查
uint256 public maxSupply = 1e9 * 1e18;  // 10 亿
function mint(uint256 amount) external onlyOwner {
    require(totalSupply() + amount <= maxSupply, "Exceed max");
    _mint(msg.sender, amount);
}

// 为什么是误报：
// ✗ 虽然 owner 可以调用，但上限严格
// ✗ 若项目已通过 DAO 治理，owner 权限受限
// ✗ 若代币经过审计并部署时间>1年，说明经济模型稳定
// ✓ 正确判断：降级为"治理监控风险"而非"无上限铸币"
```

### 3. 审计中的常见陷阱与避坑指南

**陷阱1：忽视跨合约的供应量流动**
```
❌ 错误做法：仅审计奖励合约的 mint 上限
✓ 正确做法：
  1. 追踪主代币合约的 _mint()
  2. 检查是否存在多个 minter（奖励合约、流动性合约、国库等）
  3. 对所有 minter 的总吞吐量求和
  4. 计算实际 APY = (所有铸币量) / (初始供应量) / 时间周期
```

**陷阱2：低估预言机操纵的影响**
```
❌ 错误做法：相信链下预言机的价格喂价"不可能被操纵"
✓ 正确做法：
  1. 检查预言机数据源（单点？多链？中心化API？）
  2. 检查更新频率（秒级 vs 小时级？）
  3. 检查是否有价格边界检查（±10% 偏离即暂停？）
  4. 模拟闪贷 + MEV 操纵，计算最坏情况铸币量
  5. 风险评级：若可被操纵 >5%，升级为高危
```

**陷阱3：混淆"权限受限"与"经济受限"**
```
❌ 错误做法：看到 onlyOwner 就认为安全
✓ 正确做法：区分两层防护
  - L1 权限防护：onlyOwner/onlyMinter（容易被治理攻占）
  - L2 经济防护：maxSupply/rewardCap（抗治理攻击）

评估标准：
  若 owner 可单方面改写 maxSupply → 高风险
  若 owner 改写 maxSupply 需 7 天时间锁 + DAO 投票 → 中风险
  若 maxSupply 完全不可改写（在字节码中固定）→ 低风险
```

**陷阱4：未正确计算浮点精度损失**
```
❌ 常见代码：
  uint256 rewardPerSecond = totalReward / secondsPerYear;  // 精度损失

✓ 正确审计：
  1. 检查是否使用 WAD(1e18) 或 RAY(1e27) 精度标准
  2. 计算累积精度损失：(totalReward % secondsPerYear) × 秒数 = 泄露量
  3. 在高频合约（每秒调用一次）中，泄露可能高达总额 1%
  4. 如果 owner 可以通过精度损失套利，升级为高危
```

### 4. 实战审计工作流

**Phase 1: 静态分析（0.5h）**
- 运行 Slither: `slither . --exclude solc-version,naming-convention`
- 关键词搜索：`mint|burn|supply|reward|inflate|emission`
- 绘制铸币流图：mint 函数 → 调用方 → 触发条件

**Phase 2: 经济模型评估（1-2h）**
```python
# 计算最坏情况 APY
max_mint_per_call = 1e6 * 1e18      # 单次铸币量
calls_per_year = 365 * 24 * 3600    # 假设每秒都能调用
worst_case_supply = max_mint_per_call * calls_per_year
initial_supply = 1e9 * 1e18
apy = (worst_case_supply / initial_supply) * 100
print(f"最坏情况年通胀率: {apy}%")
# 若 APY > 100% 且无成本限制 → 必然是漏洞
# 若 APY < 5% 且需质押成本 → 可能是低风险
```

**Phase 3: 交叉验证（1-2h）**
- [ ] 代币合约中的 maxSupply 约束
- [ ] 奖励合约中的 cap/limit 约束
- [ ] 治理合约中的时间锁约束
- [ ] 预言机合约中的价格边界约束
- [ ] 跨链桥中的铸币总额监控

**Phase 4: 漏洞定级（0.5h）**
```
若满足以下任一条件 → 高危漏洞：
□ 无任何供应量限制，且可被单个账户频繁调用
□ 经济模型年通胀 >50% 且无衰减机制
□ 奖励依赖可被闪贷操纵的参数

若满足以下条件 → 降级为中危/低危：
□ 有上限但需多签/时间锁才能修改
□ 年通胀 <10% 且有递减计划
□ 攻击成本 > 预期收益（质押大额资金 + Slashing 惩罚）
```
