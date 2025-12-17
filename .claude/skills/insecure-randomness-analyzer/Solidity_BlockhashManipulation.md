# Solidity - Blockhash 操纵

**漏洞类型：** 不安全的随机数生成  
**业务场景：** 链上游戏、NFT 铸造、抽奖合约、随机奖励分配  
**成因：** 使用 `blockhash(blockNumber)` 作为随机源，矿工/验证者可通过选择性丢弃不利区块来操纵随机结果

---

## Details

**代码特征示例：**
```solidity
function lottery() public {
    uint256 random = uint256(blockhash(block.number - 1)) % 100;
    if (random < 10) {
        winner = msg.sender;
    }
}
```

**快速定位核心操作（L1-关键词扫描）：**
- 全局搜索 `blockhash(`、`keccak256(abi.encodePacked(block`
- 关注返回值流向决策分支（`if`、三元运算符）或资产转移（`transfer`、`mint`）
- 检查是否用于 `%` 取模、随机数组索引、中奖判定

**快速定位保护机制（L2-跳读 + L3-逐行读）：**
- **L2** 跳读函数调用链：搜索 `Chainlink VRF`、`Oraclize`、`Commit-Reveal` 模式关键字
- **L3** 逐行检查随机数生成前后：
  - 是否有多轮确认机制（延迟结算 + 不可逆状态锁）
  - 是否存在外部熵源混入（用户签名、链下预言机）
  - `blockhash` 的参数是否为未来区块号或超 256 区块历史（会返回 0）

---

## Classify

**确认为漏洞：**
- 随机结果直接影响资产分配或重要权限，且 blockhash 为唯一熵源
- 区块生产者可无成本重试（PoS 链多数场景）或成本低于潜在收益
- 缺乏时间窗口限制或状态快照机制，允许链上反复尝试

**归类为误报：**
- 随机数仅用于不影响资产/权限的视觉效果（如 NFT 元数据随机属性展示）
- 存在多方承诺（commit-reveal）且至少一方不可预测
- 已结合链下 VRF 或可信预言机，blockhash 仅作为辅助混淆

**代码异味：**
- 使用 blockhash 但添加了用户输入盐值，理论上增加操纵成本但仍存在前端运行风险
- 延迟结算逻辑存在但时间窗口设置不合理（过短或可被抢跑）

---

## Low Risk

**评定为低风险的场景：**
1. **经济激励不足：** 预期收益低于矿工放弃出块奖励的成本（需量化对比链的出块奖励）
2. **多参与方随机：** 多个独立用户操作叠加，单一矿工难以控制所有参与者的链上行为
3. **频率限制：** 单一地址高频交互成本（Gas 累积）远超可操纵收益
4. **时间衰减机制：** 随机结果价值随区块推移指数衰减，延迟攻击无利可图
5. **已有部分缓解：** 虽未完全消除但已增加滑点保护、最大损失上限等风险控制手段

---

## 审计专业技巧

### 区分真实漏洞 vs 误报的核心维度

**1. 经济学分析：MEV 与矿工收益对标**

真实漏洞的必要条件是**经济激励 > 攻击成本**，需要计算：
- 出块奖励：Ethereum 2.0 = 4ETH + MEV，L2 = 0.5-2ETH（链而异）
- 交易费用成本：攻击合约消耗的 gas 乘以 gwei 价格
- 可获得的价值：一次中奖金额或权限价值

**示例判定**
```
场景A：NFT 抽奖奖品 = 0.1 ETH，验证者放弃出块奖励 > 4 ETH → 误报
场景B：Uniswap V4 hook 随机滑点，单次可窃取 100 ETH → 真实漏洞
场景C：链游赚取 0.001 USDC/天的掉落，矿工成本 5 USDC → 真实漏洞
```

### 2. 链类型与共识模型的影响判断

| 链类型 | 矿工/验证者权力 | 是否为高风险 | 备注 |
|-------|--------------|----------|------|
| Ethereum PoW | 选择性打包，可短期分叉 | ✓ 高 | 矿池可集中控制 |
| Ethereum PoS | 验证者固定，长期分叉成本高 | △ 中 | Lido 中心化风险但已知 |
| Polygon | 21 验证者集合 | △ 中 | 多签治理但分散度低 |
| BSC | 21 验证者集合 | △ 中 | PoA 机制，权力集中 |
| Arbitrum | 测序器单一 | ✓ 高 | DEX 前置交易可控制 |
| zkSync | 排序器 & 证明者分离 | △ 中 | 设计缓解但需验证 |

**关键判断：** 检查官方文档中验证者/矿工分散度，PoS 链优先调查 MEV 保护机制。

### 3. 时间锚点的深度验证

误报陷阱：代码看起来用了 `blockhash` 但实际有时间延迟

```solidity
// 误报案例：虽有 blockhash，但实际延迟 256 区块结算
function submitLottery() public {
    participationBlock = block.number;
    emit LotteryJoined(participationBlock);
}

function revealWinner() public {
    require(block.number >= participationBlock + 256, "Wait");  // ← 此时 blockhash 已失效
    uint256 random = uint256(blockhash(participationBlock)) % 100; // ← 返回 0
    // 此行为无法操纵的安全操作或逻辑异常
}
```

**审计技巧**：
- 搜索 `block.number` 的所有出现位置
- 绘制时间轴：参与→提交→结算，计算区块间隔
- 验证 256 区块历史限制是否被正确应用

### 4. 熵源混合度评估

单一熵源 vs 混合熵源的安全性本质不同

```solidity
// 案例 A：单一 blockhash（真实漏洞）
uint256 random = uint256(blockhash(block.number - 1)) % 100;

// 案例 B：混合用户签名 + blockhash（已显著增加成本）
uint256 random = uint256(keccak256(abi.encodePacked(
    msg.sender,
    blockhash(block.number - 1),
    block.timestamp
))) % 100;

// 案例 C：用户预提交 + blockhash（安全等级最高）
bytes32 commit = keccak256(abi.encodePacked(userSecret, blockhash(block.number)));
require(commit == userCommit, "Invalid");
uint256 random = uint256(keccak256(abi.encodePacked(userSecret, blockhash(block.number)))) % 100;
```

**判定标准**：
- A 类：前置可操纵 ✓ 真实漏洞
- B 类：成本增加但仍可操纵 △ 需评估经济学
- C 类：用户拥有主动权，矿工无法单方面操纵 ✗ 低风险

### 5. 链上反复尝试（Retry Loop）检测

**关键搜索模式**：寻找"可重入模式"或"回滚+重试"的迹象

```solidity
// 真实漏洞：无状态锁，无限重试
function play() public {
    uint256 rand = uint256(blockhash(block.number - 1)) % 10;
    if (rand == 7) { // 中奖概率 10%
        payable(msg.sender).transfer(1 ether);
    }
    // 每个区块都可再调用一次，直到中奖
}

// 误报：存在状态锁
mapping(address => uint256) lastPlayBlock;
function play() public {
    require(block.number > lastPlayBlock[msg.sender] + 100, "Cool down"); // ← 防重试
    lastPlayBlock[msg.sender] = block.number;
    uint256 rand = uint256(blockhash(block.number - 1)) % 10;
    if (rand == 7) {
        payable(msg.sender).transfer(1 ether);
    }
}
```

**审计技巧**：
- 检查函数是否存在 nonce、lastCall、或其他状态计数器
- 验证冷却期是否足长（建议 > 256 区块）
- 检查是否支持同一交易内的可重入（ERC777 风险）

### 6. 实战案例对标

**真实漏洞案例（应拉入报告）**
- Reentrancy + blockhash：合约支持 ERC777 withdraw + blockhash 随机，用户可在同一交易重试
- MEV 完全覆盖：Arbitrum 中单一排序器掌握全部交易顺序，可完全操纵 blockhash
- 应收账款合约：使用 blockhash 决定应收人，矿工通过排序改变资产分配

**常见误报案例（标记为低风险）**
- NFT 属性随机：虽用 blockhash 但属性仅影响 metadata，无经济价值
- 日志记录随机化：用于减轻日志存储的取样，不涉及资产
- UI 颜色随机：纯展示层的随机，与链上状态无关

---

## 审计检查清单

- [ ] **L1-关键词扫描** 已执行 `blockhash` 全局搜索
- [ ] **时间轴映射** 已绘制参与→结算的完整区块间隔
- [ ] **经济学量化** 已对标当前链的出块奖励和 gas 成本
- [ ] **熵源审计** 已识别所有随机源及其可预测性
- [ ] **重试防护** 已确认是否存在状态锁与冷却期
- [ ] **共识模型** 已研究目标链的验证者分散度与 MEV 机制
- [ ] **链外承诺** 已确认是否使用 Chainlink VRF、RANDAO 等外部熵
- [ ] **边界测试** 已验证 256 区块历史限制是否被应用
