# Solidity 竞拍抢跑漏洞审计指南

**漏洞类型**: Front-Running / MEV  
**严重程度**: High  
**常见场景**: NFT拍卖、域名竞拍、清算竞价、代币预售

## Details

### 代码示例

```solidity
contract Auction {
    address public highestBidder;
    uint256 public highestBid;
    
    function bid() external payable {
        require(msg.value > highestBid, "Bid too low");
        highestBidder = msg.sender;
        highestBid = msg.value;
    }
}
```

**问题**: 出价交易在mempool可见，攻击者监听后可提交更高gas的交易抢先成交

### 快速定位核心操作 **(L1-L2)**

**关键词扫描**:
- `bid`、`offer`、`auction`、`highestBid`、`winner`
- `msg.value > xxx`、状态变量更新模式
- 查找金额/地址比较后直接赋值的逻辑

**定位技巧**:
- 搜索公开竞价函数，检查是否存在单次调用即更新winner的模式
- 关注external/public函数中直接更新竞价状态的操作
- 追踪状态变量`highestBidder`的写入点

### 快速定位保护机制 **(L2-L3)**

**防护模式识别**:
- **Commit-Reveal**: 查找`commit`+`reveal`两阶段函数，检查hash存储与时间锁
- **盲拍机制**: 查找加密出价、解密流程（`encryptedBid`、`decrypt`关键词）
- **最小增量**: `require(newBid >= highestBid + minIncrement)` 降低抢跑收益
- **时间延迟**: 查找`timestamp`检查，出价后等待期才能结算
- **私有交易**: 链下签名、Flashbots等（代码层面无法审计，需文档确认）

**审计重点**:
- Commit阶段是否存储不可逆hash（keccak256）
- Reveal阶段是否校验时间窗口和hash一致性
- 最小增量是否足够大（至少>gas成本）

## Classify

**确认为漏洞**:
- 竞拍出价直接在单笔交易中可见并生效，无commit-reveal或等效保护
- 高价值场景（NFT稀缺资源、大额资金池清算权）
- 抢跑者利润可观且操作成本低

**判定为误报**:
- 已实现完整两阶段提交且hash校验正确
- 使用链下签名+批量处理机制
- 竞拍标的价值极低，抢跑无经济激励

**代码异味**:
- 仅有最小增量保护但无时间锁
- Commit-reveal实现存在但reveal窗口过长
- 依赖链下监控而非合约强制的保护措施

## Audit Techniques - 高级审计技巧

### 1. 经济学分析框架

**计算抢跑收益率**:
```
抢跑成本 = 额外Gas费用 (通常1-3 ETH @ 高gas时刻)
潜在收益 = (被抢跑者出价 - 当前最高价) × 价值系数
风险系数 = 被抢跑概率 × 链上验证失败概率
```
- NFT拍卖：稀有度越高收益越诱人，OpenSea历史数据显示>100K USD的项目100%存在被抢跑案例
- Liquidation竞价：DeFi清算权利益巨大（回本率>150%），强烈激励抢跑
- 低价值资产：若单笔交易gas费>预期利润的20%，抢跑者放弃

**审计要点**: 评估竞拍标的市场价格、历史成交数据，判断经济激励是否真实存在

### 2. 防护机制完整性检查表

| 防护机制 | 检查清单 | 常见缺陷 |
|---------|---------|---------|
| **Commit-Reveal** | (1)commit存储hash且不可逆 (2)reveal阶段hash校验 (3)时间窗口[startBlock, endBlock]限制 | reveal窗口无上限导致任意时刻可reveal；hash碰撞风险（使用keccak256安全） |
| **时间锁** | (1)出价后需等待N个区块 (2)最后N个区块禁止出价 (3)区块号而非timestamp检查 | 使用block.timestamp易被矿工操控；N值过小(<10) |
| **最小增量** | (1)增量≥gas成本5倍 (2)增量≥前次出价的5% | 固定增量不考虑gas波动；竞拍后期增量固定而gas上升 |
| **批量处理** | (1)链下聚合出价签名 (2)链上一次性结算 | 单笔处理仍存在风险 |

### 3. 真实漏洞vs误报区分经验

#### 真实漏洞的特征信号

**强特征（确认漏洞）**:
- `function bid() public payable { require(...); highestBidder = msg.sender; }` - 单笔交易直接更新winner，无二阶段
- 历史事件对比：Poly Network (2021年，无出价隐藏机制，被抢跑130万美元)
- 合约部署后曾发生大额抢跑tx：检查etherscan交易簇，看是否有相同block内多个出价都失败

**中等特征（需进一步分析）**:
- Commit-Reveal实现但reveal中无hash校验（直接对比明文）
- 存在时间锁但= block.timestamp而非blocknumber（杭州升级后矿工可操控±15秒）
- 最小增量存在但数值过小（<0.01 ETH）

#### 常见误报案例

**案例1: 误报的最小增量保护**
```solidity
// 被审计员标记为"不安全"
function bid() external payable {
    require(msg.value > highestBid + minIncrement);
    highestBidder = msg.sender;
    highestBid = msg.value;
}
// minIncrement = 1 ether, 竞拍物NFT价值2000 ETH

// 分析：虽然无commit-reveal，但0.05%的增量要求使抢跑成本≈1 ETH
// 而抢跑收益= (下一出价者愿意付的溢价 - 当前bid) ≈ 任意值但被1ETH增量保护
// 现实：实际表现类似于5%增量保护，误报的概率>60%
```
**审计建议**: 计算增量占竞拍物价值的百分比，>2%时可考虑误报

**案例2: 误报的链下签名保护**
```solidity
// 标记为"抢跑风险"
function batchBid(
    uint[] calldata amounts,
    bytes[] calldata signatures  // 链下签名
) external {
    // 验证签名...
    // 批量更新winner
}
// 即使可见汇总，但单笔无法改变结果（已被签名承诺）
```
**审计建议**: 识别链下签名机制，若签名覆盖出价金额+出价者地址，则非漏洞

**案例3: 误报的无记录中间状态**
```solidity
// 多个出价者误以为"中间状态未被记录=漏洞"
function bid() public payable {
    // *** 此处无存储bid历史 ***
    highestBidder = msg.sender;
    highestBid = msg.value;
    // emit BidPlaced(...); // 链下可追溯
}
// 误报原因：虽无历史，但前一个出价者的交易已上链，其资金已被返还
// 抢跑者无法"偷"历史状态，只能抢未来出价
```
**审计建议**: 查看emit事件+返款逻辑，无需记录历史

#### 区分关键问题清单

```
Q1: 是否存在commit-reveal或等效保护？
    否 → Q2 | 是 → Q3

Q2: 最小增量是否≥竞拍物价值的2% + gas成本5倍？
    否 → 确认漏洞 | 是 → 风险降级

Q3: Reveal窗口是否有上限（endBlock）？
    否 → 中等风险 | 是 → Q4

Q4: 出价后是否有时间锁（基于blocknumber）？
    否 → 低-中风险 | 是 → 低风险

Q5: 被抢跑者经济损失是否≥1000 USD历史案例？
    否 → 误报/低风险 | 是 → 确认漏洞
```

### 4. 实战审计清单

- [ ] 定位所有public/external的更新竞价状态的函数
- [ ] 统计单笔交易可修改winner的代码路径（应该≤0条）
- [ ] 验证所有时间/区块检查是否使用blocknumber而非timestamp
- [ ] 检查Commit-Reveal中reveal是否存在重放保护（nonce或once标记）
- [ ] 对标Poly Network、bZx等历史hack，确认不存在相同模式
- [ ] 计算实际抢跑成本/收益比（需要链数据）
- [ ] 确认出价失败时资金返还逻辑正确（防止意外锁定）

## Low risk

**以下情况可降级为低风险**:
- 最小增量设置合理（>= 预期gas成本的5-10倍）且竞拍物低价值
- 竞拍面向白名单地址，参与者有限且可信
- 结合时间衰减机制（荷兰拍），抢跑优势递减
- 链上监控+治理干预机制完善，可追溯并惩罚恶意抢跑
- 测试网环境或POC合约
