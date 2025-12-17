# Solidity - Commit-Reveal 绕过

Commit-Reveal 模式旨在通过两阶段提交防止随机数预测，但实现不当时可被绕过或操纵，常见于链上游戏、NFT 盲盒、抽奖合约等场景。

## Details

**典型代码特征：**
```solidity
mapping(address => bytes32) public commits;
mapping(address => uint256) public reveals;

function commit(bytes32 hash) external {
    commits[msg.sender] = hash;
}

function reveal(uint256 value) external {
    require(keccak256(abi.encodePacked(value)) == commits[msg.sender]);
    reveals[msg.sender] = value;
}
```

**快速定位核心操作（L2-跳读）：**
- 搜索关键函数对：`commit` + `reveal` / `commit` + `open` / `hide` + `show`
- 定位哈希计算：`keccak256(abi.encodePacked(...))` 或 `sha256(...)`
- 追踪状态变更：commit 存储 → reveal 验证 → 随机数生成
- 检查时间锁：`block.number` 或 `block.timestamp` 约束条件

**快速定位保护机制（L3-逐行读）：**
- **哈希验证完整性**：reveal 值必须匹配 commit 哈希，检查是否遗漏 `require` 验证
- **时间窗口限制**：commit 与 reveal 间是否强制最小间隔（防止同区块绕过）
- **盐值混淆**：`keccak256(abi.encodePacked(value, salt, msg.sender))` 是否包含用户无法控制的盐
- **选择性披露惩罚**：未 reveal 或延迟 reveal 是否有罚金/质押机制
- **reveal 截止时间**：是否限制最大 reveal 时间窗口（防止攻击者观察后决定是否披露）
- **跨用户熵混合**：最终随机数是否依赖多方 reveal 值（单方可控则可操纵）

## Classify

**确认为漏洞的判定标准：**
- commit 哈希未验证或验证逻辑可绕过（如使用 `tx.origin` 而非 `msg.sender`）
- 缺少时间间隔限制，允许同区块内 commit-reveal（矿工/验证者可预演结果）
- reveal 阶段允许选择性披露且无惩罚（参与者可计算后决定是否 reveal）
- 盐值由用户完全控制或可预测（如仅用 `block.timestamp`）
- 最终随机数仅依赖单方 reveal 值（该方可完全操纵结果）

**误报情形：**
- 已有其他外部熵源（如 Chainlink VRF）作为随机数补充
- 业务逻辑不依赖随机性的公平性（如仅用于 UI 展示）
- reveal 失败会触发默认安全值（如退款而非分配奖励）

**代码异味：**
- 时间窗口过短但理论上足够（如 1 区块间隔，需评估 MEV 风险）
- 盐值包含部分链上数据但未包含用户不可控部分
- 多方 commit-reveal 但参与者数量过少（<5 方）

## Low risk

**适用低风险评级的场景：**
- 资金池规模小（<$1000）且单次奖励价值低，攻击成本超过收益
- 仅影响非货币化游戏体验（如装备属性随机，无交易市场）
- 已实现基本保护机制但时间参数配置保守（如 10 区块间隔）
- 多方参与且需 >50% 合谋才能操纵（如彩票需所有参与者联合作弊）
- 有前端监控机制可检测异常 reveal 模式（虽无法阻止但可预警）
- 部署在高性能链（出块时间 <1s），单区块预演成本较高

## 审计专业技巧

### 1. 深度问题签名识别

**真实漏洞的标志性代码模式：**
```solidity
// 反面例子1：时间窗口无限制
uint256 revealDeadline;  // 从不检查或检查不严格
function reveal(uint256 value) external {
    require(keccak256(abi.encodePacked(value)) == commits[msg.sender]);
    // 缺少 require(block.number <= revealDeadline) 或 require(block.timestamp < deadline)
    reveals[msg.sender] = value;
}

// 反面例子2：单方可控的盐值
bytes32 hash = keccak256(abi.encodePacked(value, block.timestamp));
// 攻击者可在 reveal 时重新计算，因为 block.timestamp 对其可见

// 反面例子3：缺少多方熵混合
uint256 randomness = keccak256(abi.encodePacked(reveals[msg.sender]));
// 单个参与者完全控制结果
```

### 2. 误报高频场景辨别

**Case 1：多链部署中的假阳性**
- **表象**：发现 commit-reveal，且无明显时间锁
- **真实情况**：该合约部署在 Arbitrum（L2），出块时间 0.25s，单区块预演成本极高（需支付数十 tx 费用）
- **判断技巧**：检查 `getChainId()` 和 gas 消耗逻辑，评估实际攻击可行性 ROI

**Case 2：游戏积分 vs 资产价值**
- **表象**：reveal 后计算游戏积分用于排名
- **关键区分**：
  - 如果积分无法提现/交易 → 低风险（用户作弊仅影响自己名次）
  - 如果积分可兑换 NFT/代币 → 高风险（变相操纵资产分配）

**Case 3：失败回滚机制**
```solidity
// 看似无保护
function reveal(uint256 value) external {
    require(keccak256(abi.encodePacked(value)) == commits[msg.sender]);
    // 未 reveal 是否会自动触发退款？
    if (canClaim[msg.sender]) {
        uint256 prize = calculatePrize(value);
        (bool success, ) = msg.sender.call{value: prize}("");
        require(success);  // 如果失败则整个交易回滚
    }
}
// 若调用者钱包合约故意失败，则无法领奖 → 相对安全的隐式惩罚机制
```

### 3. 审计流程中的陷阱规避

**陷阱1：盲目信任多方假设**
- ❌ 错误：看到 3 方 commit-reveal 就判定"足够分散"
- ✅ 正确：检查合约是否允许同一用户多次 commit，或通过合约地址池化（机器人可冒充多方）

**陷阱2：忽视最终随机数生成逻辑**
```solidity
// 看似安全的 commit-reveal，但最终使用方式存在漏洞
uint256[] reveals;
function reveal(uint256 value) external { ... }

// 危险的使用
function drawWinner() external {
    uint256 seed = uint256(keccak256(abi.encodePacked(reveals)));
    winner = participants[seed % participants.length];
    // ✗ 如果参与者在 drawWinner 前仍可 commit/reveal，则可预测 seed
}

// 安全的使用
function drawWinner() external {
    require(now > revealDeadline, "Reveal phase active");
    uint256 seed = uint256(keccak256(abi.encodePacked(reveals)));
    winner = participants[seed % participants.length];
    // ✓ 强制 reveal 阶段已完全结束
}
```

**陷阱3：gas 成本与实际可行性混淆**
- 评估时需计算 MEV bot 的完整成本：
  - 同区块内多次 reveal TX 的 gas 费用
  - Flashbots 等私有交易池的使用成本
  - 与预期收益的比值（高收益项目即使高成本也值得）

### 4. 真实 vs 误报的快速判断表

| 特征 | 真实漏洞信号 | 误报信号 |
|------|-----------|--------|
| **时间锁** | 无或可绕过（如 `if(deadline)` 但不强制） | 强制检查 `require(block.number > deadline)` |
| **盐值来源** | `block.timestamp` 或用户完全可控 | 包含 `blockhash()` 或多链跨越的随机性 |
| **奖励机制** | 直接转账给 winner，数额大 (>$10K) | 积分制，无直接资产转移 |
| **参与者数** | 单方或双方可控 | 需 5+ 独立参与者或 DAO 投票确认 |
| **修复难度** | 需重构状态机或引入外部 oracle | 仅需调整参数或增加事件日志 |

### 5. 现场审计检查清单

```
□ 定位所有 commit 函数的调用限制（是否允许覆盖已有 commit？）
□ 追踪 reveal 的时间戳约束（block.number vs block.timestamp，哪个用？）
□ 搜索是否存在 "revert", "require", "assert" 对 reveal 值的验证
□ 检查最终随机数的 keccak256 输入是否包含用户无法控制的值
□ 评估单次成功攻击的预期收益，与所需 gas 成本对比
□ 验证 commit-reveal 完成后是否立即冻结状态（防止二次操纵）
□ 查找是否存在 fallback 或 receive 函数被用于隐蔽 reveal
□ 测试多签或治理合约是否可绕过时间锁（某些链支持时间戳操纵）
```

### 6. 常见的修复对标

**削弱型修复（容易重新引入漏洞）：**
- 仅增加 reveal 时间窗口（如 100 区块）但未检查
- 添加盐值但盐由用户自己提供

**安全型修复（经过验证）：**
- 引入 Chainlink VRF 作为熵源补充
- 实现强制的多签最终确认机制
- 部署在支持可验证随机数的 L1（如 Ethereum Dencun 后的 PREVRANDAO）
