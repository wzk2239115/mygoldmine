# Vyper Prevrandao Assumption

**漏洞类型：** 不安全随机数  
**影响范围：** DeFi 奖励分发、链上游戏、抽奖合约、NFT 铸造  
**核心问题：** 将 `block.prevrandao` 误用作安全随机源，忽视其可预测性和矿工可操纵性

## Details

### 代码示例

```vyper
# 典型易受攻击模式
@external
def claim_reward():
    random_value: uint256 = block.prevrandao % 100
    if random_value < 10:  # 10% 中奖概率
        self._distribute_prize(msg.sender)

@external  
def mint_random_nft():
    token_id: uint256 = block.prevrandao % self.total_supply
    self._mint(msg.sender, token_id)

# 组合使用但仍不安全
@external
def lottery():
    seed: uint256 = convert(keccak256(concat(
        convert(block.prevrandao, bytes32),
        convert(block.timestamp, bytes32)
    )), uint256)
    winner: uint256 = seed % self.participants_count
```

### 快速定位核心操作 **[L1-L2]**

**L1 关键词扫描：**
- 搜索 `block.prevrandao` 或已弃用的 `block.difficulty`
- 搜索 `random`、`lottery`、`prize`、`winner` 等函数名
- 搜索取模运算 `%` 与区块属性的组合使用

**L2 跳读验证：**
- 检查 prevrandao 是否参与条件分支（`if`/`assert`）
- 检查是否影响价值分配逻辑（transfer、mint、权限授予）
- 验证是否存在经济激励诱导操纵（奖池大小 vs 区块奖励）

### 快速定位保护机制 **[L2-L3]**

**L2 跳读排查：**
- 查找是否引入外部随机数预言机（Chainlink VRF、Pyth 等）
- 检查是否使用 Commit-Reveal 模式（两阶段提交）
- 验证是否有延迟执行机制（请求时区块号 + N 后执行）

**L3 逐行审查：**
- **无效保护1：** 仅组合 `timestamp`/`number`/`prevrandao` 进行哈希仍可预测
- **无效保护2：** 与 `msg.sender`/`tx.origin` 混合运算，攻击者通过合约调用仍可控制
- **有效保护：** 引入多轮用户输入 + 区块信息 + 时间间隔（需验证间隔充分性）

**关键检查点：**
```vyper
# 危险信号
block.prevrandao % x  # 直接取模
keccak256(block.prevrandao)  # 单一哈希不解决问题

# 需深入验证
if block.number > self.request_block + DELAY:  # 延迟是否 >= 1
external_oracle.get_randomness()  # 预言机调用是否正确处理回调
```

## Classify

### 漏洞判定标准

**确认为漏洞：**
1. prevrandao 直接或简单变换后影响经济价值分配
2. 单次交易可获利超过矿工出块成本（约 0.1-2 ETH）
3. 攻击窗口期可预测且可重复执行

**归为代码异味：**
1. 仅用于无经济价值的展示性随机（UI随机颜色）
2. 攻击成本远超潜在收益（奖池 < 0.01 ETH）
3. 随机结果不影响状态变更，仅用于事件日志

**误报情况：**
1. prevrandao 仅用于时间戳对比/区块标识，非随机数用途
2. 已通过 RANDAO 增强（需验证是否真实 PoS 共识且难度目标充分）
3. 组合了充分的链下签名 + 链上验证多方熵源

### 研判流程

1. **追踪影响范围：** 从 prevrandao 使用点向下追踪到最终状态变更
2. **评估攻击收益：** 量化可操纵价值（代币数量、NFT 稀有度价值）
3. **计算攻击成本：** 以太坊主网矿工放弃区块成本 vs 侧链/L2 验证者成本
4. **验证攻击可行性：** 是否需要连续多区块操纵或单区块即可完成

## Low risk

### 降级为低风险的场景

1. **经济价值极低：** 单次可操纵价值 < 0.005 ETH 且总奖池 < 0.1 ETH
2. **攻击窗口受限：** 需要连续控制 10+ 个区块才能成功操纵
3. **多方参与稀释：** 需 100+ 参与者同时提交熵值，单一验证者影响 < 1%
4. **紧急暂停机制：** 存在实时监控 + 3分钟内可暂停的安全开关
5. **测试网环境：** 明确标注为实验性功能且不处理真实资产
6. **链特性保护：** 运行在具有 VDF（可验证延迟函数）等抗操纵共识的链上

### 降级注意事项

即使满足上述条件，仍需在报告中明确说明：
- 该随机数方案**不适合**生产环境高价值场景
- 建议后续版本迁移至 VRF 等密码学安全方案
- 需持续监控经济参数变化避免风险升级
