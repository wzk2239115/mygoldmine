# Go BlockTime Randomness - 区块时间随机性漏洞

## 漏洞成因
Cosmos SDK 链中，keeper/handler 使用 `ctx.BlockTime()`、`ctx.BlockHeight()` 等区块元数据作为随机源。验证者可操纵出块时间/高度，预测或操控随机结果，导致抽奖、分配、选举等逻辑可被操纵。

## Details

**典型代码模式：**
```go
// 漏洞示例：直接使用区块时间做随机种子
func (k Keeper) SelectWinner(ctx sdk.Context, participants []string) string {
    seed := ctx.BlockTime().Unix() // 或 ctx.BlockHeight()
    rand.Seed(seed)
    idx := rand.Intn(len(participants))
    return participants[idx]
}

// 变种：使用区块哈希 + 时间
blockHash := ctx.BlockHeader().Hash()
randomness := sha256.Sum256(append(blockHash, ctx.BlockTime().Bytes()...))
```

**快速定位核心操作技巧（L2-跳读）：**
- 搜索关键词：`ctx.BlockTime()`、`ctx.BlockHeight()`、`BlockHeader()`、`rand.Seed()`
- 追踪调用链：keeper 方法 → 查看 `sdk.Context` 使用 → 确认是否用于随机数生成
- 重点关注：抽奖、NFT 铸造、奖励分配、验证者选举、游戏结果等业务逻辑

**快速定位保护机制技巧（L3-逐行读）：**
- 检查是否使用 VRF（Verifiable Random Function）：搜索 `vrf.`、`ecvrf.`
- 检查是否引入 Commit-Reveal：查找 `Commit` + `Reveal` 两阶段函数
- 检查是否使用链外预言机：`Chainlink VRF`、`Band Protocol` 等集成
- 检查是否有区块延迟机制：随机数生成延迟 N 个区块后才能使用
- 验证是否混合多源熵：`blockhash + 用户输入 + 历史状态` 且任一方无法单独控制

## Classify

**漏洞判定条件（三要素同时满足）：**
1. **随机性依赖可预测源**：仅使用 BlockTime/BlockHeight/BlockHash
2. **存在经济激励**：操纵随机结果可获利（奖励>操纵成本）
3. **验证者可操纵**：单个验证者可影响区块参数（PoS/PoA 链）

**误报场景：**
- 随机性仅用于非关键逻辑（如 UI 展示顺序、日志ID生成）
- 结果对所有参与方公平（即使可预测，但无人能单独获利）
- 使用 Tendermint 共识的多验证者环境 + 高质押要求（操纵成本极高）

**代码异味（需结合业务评估）：**
- 测试网/开发环境使用简单随机源
- 低价值资产场景（奖池<验证者质押惩罚）
- 配合其他安全措施但实现不完整（如延迟机制但延迟仅1个区块）

## Low risk

**评为低风险的情况：**
- **高操纵成本**：PoS 链验证者质押金额远大于潜在收益，slash 机制严格
- **有限影响范围**：随机结果仅影响非金融类功能（如用户昵称颜色、排行榜排序）
- **多源验证**：虽使用 BlockTime 但结合多个独立随机源，需多方合谋才能操纵
- **时间窗口短**：交易提交到随机数使用间隔极短（<1 block），验证者无足够时间策略性出块
- **存在补偿机制**：即使随机性被操纵，合约有二次校验或补偿逻辑保护用户利益
- **去中心化程度高**：验证者集合极大（>100）且轮换频繁，单一操纵难度指数级增长

## 审计专业技巧

### 1. 真实漏洞的关键信号

**经济激励分析（最关键）：**
- 明确的金额阈值：搜索代码中涉及的奖励/赌注金额，计算操纵成本与预期收益
- 验证者可单独获利场景：审视是否存在"只有当前验证者受益"的逻辑（如验证者本人投注）
- 无slash惩罚路径：检查合约是否完全缺少验证者misbehavior的制裁机制

**操纵可行性检查（需动手复盘）：**
```go
// 真实漏洞示例：可预测且无成本
func (k Keeper) DrawLottery(ctx sdk.Context, roundID uint64) string {
    seed := ctx.BlockTime().Unix() % len(winners)
    return winners[seed] // 验证者可通过调整出块时间（秒级粒度）来操纵结果
}

// 变种：虽用 BlockHeight 但延迟检查不足
func SelectValidator(ctx sdk.Context, applicants []string) error {
    height := ctx.BlockHeight()
    if randomHeight := getProposal(applicants[0]).CreatedAtHeight; height == randomHeight + 1 {
        // 仅延迟1个块，验证者仍可提前/延后交易打包时机
        return assignValidator(applicants[0])
    }
    return nil
}
```

**审计要点：**
1. 验证者是否有动机在看到交易后才决定是否打包
2. 随机数的"锁定点"是否在验证者可控之前（如：在validator竞争前确定，vs 在用户操作后才决定）
3. 是否存在"预言家攻击"：validator 可基于 mempool 交易预见随机结果后再作决策

### 2. 误报的常见陷阱与鉴别

**陷阱1：混淆"可预测"与"可被恶意操纵"**
```go
// 易误判为漏洞，实际低风险
func (k Keeper) AssignShardsRoundRobin(ctx sdk.Context) {
    shard := ctx.BlockHeight() % totalShards // 虽然可预测
    // 但由于是简单轮转，所有验证者都受益相同
    // 单个验证者通过推迟/加速出块来"重新分配分片"没有正收益
}
```
**鉴别方法**：计算特定验证者通过操纵该随机数能获得的额外收益。如为零或负数，非高风险

**陷阱2：高延迟机制被误判为无效**
```go
// 乍看似乎无保护，实际有延迟
function revealWinner(uint roundID) {
    uint drawHeight = proposals[roundID].blockNumber;
    require(block.number >= drawHeight + 256); // Solidity 风格
    // Go 等价：需追踪链上数据结构，确认随机数确实存储在历史高度
    bytes32 randomness = blockhash(drawHeight);
    ...
}
```
**鉴别方法**：关键词搜索 `+1`、`+2`、`+ blockDelay` 等，评估延迟是否足够（通常 >7 blocks 才安全）

**陷阱3：将"多源混合"误判为解决**
```go
// 常见的虚假修复
func SelectWinner(ctx sdk.Context, txHash string, userSeed string) {
    combined := hash(ctx.BlockTime(), txHash, userSeed)
    // 误区：如果 txHash 本身由验证者间接控制（通过交易排序）
    // 或 userSeed 由参与者提前提交且 commit-reveal 不完整
    // 仍然不安全
}
```
**鉴别方法**：逐一检查每个输入源的可控性：
- BlockTime：验证者可控（秒级）
- BlockHash：验证者可控（通过交易排序）
- txHash：验证者可控（选择性包含/排除交易）
- userSeed：如无commit阶段，用户可预测后提交虚假seed

### 3. 现场审计检查清单

**第一阶段：快速筛查（5分钟）**
- [ ] 搜索关键词出现次数（ctx.BlockTime、BlockHeight 等）
- [ ] 是否存在显式的随机数生成函数（如 `drawRandom`, `getWinner`, `selectValidator`）
- [ ] 该函数是否直接操作金钱或权力（转账、权重更改、质押更新）
- [ ] 如有 VRF/Chainlink 引入，是否在核心逻辑中使用

**第二阶段：风险分级（15分钟）**
1. 抽取涉及随机性的最高价值交易路径（如lottery取奖、验证者选举）
2. 画出数据流：输入源 → 哈希/运算 → 决策点 → 资金流出
3. 在每个节点标记"谁可控"：验证者、用户、合约、外部预言机
4. 计算攻击成本：需要多少验证者合谋、质押金额、时间成本

**第三阶段：深度复盘（如有红旗，30分钟）**
```
对于可疑函数，编写简化版PoC：
1. 假设攻击者是验证者
2. 设定一个目标输出（如"我想让地址A获胜"）
3. 反推需要的BlockTime/Height 值
4. 检查验证者是否能够（通过延迟/加速出块）达到这个值
5. 验证成本与收益的比值
```

### 4. 真实案例区分表

| 案例 | 代码特征 | 是否真实漏洞 | 理由 |
|------|--------|----------|------|
| Cosmos Validator Slashing Bug | `ctx.BlockHeight() % numValidators` 无延迟，直接影响质押分配 | **是** | 单验证者可通过控制块高来垄断分配 |
| NFT随机属性（魔法值<1000） | `hash(ctx.BlockTime(), tokenID)` 仅影响cosmetic属性，无价值差异 | **否** | 即使可预测，操纵无经济激励 |
| DeFi清算拍卖 | `blockHash + 用户竞价` 使用Tendermint共识 + 100+验证者 + 严格时间戳范围 | **低** | 操纵难度极高，需大多数验证者合谋 |
| 游戏掉落概率 | `ctx.BlockHeight() % 100` 仅决定掉落与否，后续道具随机值来自链外预言机 | **否** | 关键随机源已外链化，区块数据仅做入口门槛 |

### 5. 常见审计错误

**✗ 错误1**：看到 `ctx.BlockTime()` 就标记 High，不区分使用场景
**✓ 正确做法**：先问"这个值的改变能否为某人带来>0的收益"

**✗ 错误2**：检查到有VRF集成就放心，不验证VRF是否真的在用
**✓ 正确做法**：搜索VRF调用处，确认返回值是否真的驱动了关键决策

**✗ 错误3**：假设验证者不会合谋（特别是小链）
**✓ 正确做法**：基于链的验证者数量和质押分布评估合谋难度

**✗ 错误4**：忽视"时间的离散性"（BlockTime通常按秒级，给了验证者调整空间）
**✓ 正确做法**：检查随机范围与时间粒度的比值（如100个选项却用秒级时间种子 = 风险）
