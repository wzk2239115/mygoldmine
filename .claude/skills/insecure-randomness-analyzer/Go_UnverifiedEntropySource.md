# Go_UnverifiedEntropySource

**漏洞类型：** 不安全随机性 - 未验证的熵源  
**适用范围：** Cosmos SDK、Tendermint/CometBFT 链上应用

## Details

**典型代码模式：**

```go
// 案例1：直接使用外部输入作为随机种子
func (k Keeper) DrawLottery(ctx sdk.Context, msg MsgDrawLottery) error {
    seed := msg.UserSeed  // 用户可控输入
    rand.Seed(seed)
    winner := rand.Intn(len(participants))
    // ...
}

// 案例2：使用消息 Hash 作为随机源
func (k Keeper) RandomSelect(ctx sdk.Context, txHash []byte) {
    seed := binary.BigEndian.Uint64(txHash[:8])
    rand.Seed(int64(seed))
    // ...
}

// 案例3：混合使用未验证的多个输入
func GenerateRandom(userInput string, nonce uint64) int {
    data := append([]byte(userInput), sdk.Uint64ToBigEndian(nonce)...)
    hash := sha256.Sum256(data)
    return int(binary.BigEndian.Uint64(hash[:8]))
}
```

**快速定位核心操作（L2-L3 审计等级）：**
- 搜索 `rand.Seed()` / `rand.New()` / `math/rand` 包调用，查看种子来源
- 追踪 Keeper 方法中所有涉及"选择"、"抽取"、"分配"逻辑的随机数生成
- 检索 `binary.BigEndian.Uint64()` + `msg.` 字段的组合使用
- 关注 `txHash`、`msg.Sender`、`msg.*Seed` 等用户可控字段被用于计算的场景
- 查找 `crypto/sha256` 或 `crypto/sha512` 后直接截取字节作为随机数的模式

**快速定位保护机制（L3-L4 审计等级）：**
- 验证是否使用了链原生随机性模块（如 `x/random` 模块、VRF 集成）
- 检查是否有 Commit-Reveal 方案：先提交承诺（commit），后续区块揭示（reveal）
- 确认熵源是否包含**未来不可预测**的元素（如未来区块 hash、签名聚合值）
- 查看是否有 Beacon 服务调用（外部 VRF oracle）或阈值签名验证
- 检查是否对外部输入进行了时间锁定、质押惩罚等经济制约
- 确认多轮交互场景下是否每轮独立验证熵源新鲜度

## Classify

**漏洞判定标准：**
- 熵源完全来自用户可控输入（msg 字段、函数参数）→ **高危漏洞**
- 使用当前交易 hash 或当前区块已知字段（height、time、proposer）→ **中危漏洞**
- 混合使用可预测和不可预测源，但可预测部分占主导 → **中危漏洞**

**误报识别：**
- 随机数仅用于非关键场景（UI 展示、日志标识、临时 nonce）
- 已实施 Commit-Reveal 且正确验证时间窗口和惩罚机制
- 使用了经过审计的链原生 VRF 或阈值签名方案，且验证逻辑完整

**代码异味：**
- 使用 `time.Now().UnixNano()` 作为种子（在链上环境可预测）
- 代码中存在 `TODO: replace with VRF` 等注释
- 多处重复实现简易随机逻辑而未封装统一熵源管理

## Low risk

**低风险场景：**
1. **有质押锁定机制**：参与者需提前质押资产，操纵成本超过预期收益
2. **多方共同贡献熵源**：需要 2/3+ 验证者合谋才能预测结果（需验证实现正确性）
3. **经济激励不足**：随机结果的影响金额小于单次交易 gas 费用
4. **仅影响体验**：随机性用于非金融场景（如游戏角色外观、排序展示）
5. **测试网环境**：明确标注为实验性功能且主网不会启用
6. **时间跨度保护**：Commit 和 Reveal 之间间隔足够多的区块（>=100），且有超时惩罚机制

## 审计专业技巧

### 真实漏洞vs误报的核心区分方法

**关键问题1：谁控制了熵源的所有输入？**
- **真实漏洞**：单个用户或验证者可独立控制全部输入（如仅使用 msg.UserSeed）
- **误报信号**：需要多方参与且难以完整操纵（如区块 hash + 签名聚合 + VRF）

示例对比：
```go
// 明确漏洞 - 用户完全控制
seed := msg.CustomSeed // 攻击者选择任意值
rand.Seed(int64(seed))

// 可能误报 - 需深入分析
seed := ctx.BlockHeight() + msg.Nonce // ctx.BlockHeight() 是链共识达成的
// 若 msg.Nonce 是注册时的唯一标识且无法修改，风险大幅降低
```

**关键问题2：攻击者的成本-收益比是否合理？**

审计检查清单（按成本递增）：
1. **零成本操纵**（现场漏洞）：
   - 直接修改交易字段即可改变结果
   - 风险等级：**高**（无论金额）

2. **单笔交易成本**（gas+滑点）：
   - 攻击者提交专门构造的交易
   - 判断标准：gas 成本 < 预期收益的 50%？若是则为真漏洞

3. **质押+锁定期成本**：
   - 需要提前锁定大额资产
   - 判断标准：锁定期 >= 100 个块 + 惩罚机制完整？若是倾向误报

4. **多方合谋成本**（超过 1/3 验证者）：
   - 需要贿赂多个独立参与者
   - 判断标准：法律管辖下难以执行？可标记为低风险

**关键问题3：熵源的预测时间窗口有多大？**

```go
// 案例分析：不同的预测窗口

// 场景A - 可预测（当前块已知）
seed := sha256.Sum256(ctx.BlockHeader().DataHash)
// 预测窗口：0秒（攻击者在提交交易前已知 DataHash）

// 场景B - 部分可预测（来自未来块）
seed := sha256.Sum256([]byte(ctx.BlockID().Hash))
// 但攻击者可在 N 个块前通过 MEV 操控或验证者贿赂来操纵
// 预测窗口：N 秒（网络出块时间 × N）

// 场景C - 难以预测（使用未来块+验证者签名）
commitment := sha256.Sum256(append(
    futureBlockHash,      // N 块后的 hash，难以预测
    validatorSignature,   // 签名在块提议时已确定
))
// 预测窗口：需要破解签名或贿赂验证者（成本极高）
```

### 常见误报陷阱与识别

**陷阱1：「使用了 hash 函数就觉得安全」**
- **表现**：代码用 sha256 处理种子就认为足够随机
- **真相**：hash 只是混淆手段，若输入完全可控则无效
- **识别方式**：追踪 hash 的所有输入来源，最终必须有不可控的链状态

**陷阱2：「看起来是多方贡献」但实际单点故障**
```go
// 误报案例：看似多方但都来自同一块
seed := sha256.Sum256(append(
    ctx.TxHash(),         // 当前交易 hash - 攻击者可控
    ctx.BlockHeight(),    // 来自同一块
    msg.UserInput,        // 用户输入
))
// 风险：三个源都来自同一交易/块，等同于单点控制
```

**陷阱3：「Commit-Reveal 实现不完整」**
- **常见缺陷**：缺少时间锁（无最小 reveal 块延迟）
- **判断方法**：查看 Reveal 逻辑是否有 `require(blockHeight >= commitHeight + MIN_BLOCKS)`
- **真实案例**：Cosmos NFT 彩票模块早期版本缺少此检查 → 实际漏洞

**陷阱4：「使用了 VRF 但验证逻辑有缺陷」**
```go
// 虚假安全感：
vrfOutput := VerifyVRF(msg.Proof)
if vrfOutput == 0 { return nil } // 只验证存在性，未验证新鲜度
winner := vrfOutput % len(participants)

// 正确做法应该：
vrfOutput := VerifyVRF(msg.Proof, ctx.BlockHeight())
if vrfOutput.BlockHeight < ctx.BlockHeight() - 1 {
    return errors.New("stale VRF")
}
```

### 现场调查技巧

**技巧1：从价值流反向追溯**
- 问题：这个随机数决定谁获得多少价值？
- 方法：在支付/铸币代码处下断点，回溯随机数来源
- 实例：假设随机函数决定 NFT 属性，属性决定价格 → 倒推风险

**技巧2：测试可复现性**
```bash
# 在本地测试网运行相同交易参数多次
for i in {1..5}; do
  tx_result=$(./simd tx mymodule draw-lottery \
    --from alice \
    --seed="0x123456" \
    --dry-run --from=alice)
  echo "Run $i: $(echo $tx_result | grep winner)"
done

# 若多次结果相同 → 种子完全确定 → 真实漏洞
# 若各不相同 → 存在不可控源（可能有防护）
```

**技巧3：检查历史交易模式**
- 查询链上历史：特定用户的随机结果是否异常集中获胜
- 工具：`blockscout API` + 统计分析
- 异常指标：某用户赢率 > 平均 50%，且提交交易间隔规律 → 强烈怀疑操纵

**技巧4：询问开发者的假设**
推荐问题清单：
- 这个随机函数是否认为验证者不可信？（若是 → 需要额外验证）
- 是否存在攻击者提前 N 个块知晓结果的窗口？（若是 → 需量化 N）
- 若攻击成本为 X，最大收益是多少？（若 X << 收益 → 真漏洞）
- Commit-Reveal 的超时惩罚机制是否已上线？（若否 → 仍是漏洞）

### 报告级别判定流程

```
检查 VRF/Beacon 是否使用？
  ├─ 是 → 检查验证逻辑 → 通过则 LOW，否则 MEDIUM
  └─ 否 → 继续

检查是否 Commit-Reveal？
  ├─ 是 → 检查时间锁 >= 100块 + 惩罚机制 → 通过则 LOW，否则 MEDIUM
  └─ 否 → 继续

熵源是否 100% 由单用户控制？
  ├─ 是 → HIGH
  └─ 否 → 继续

熵源是否包含当前块已知的字段？
  ├─ 是 → 检查金额 < gas费？ 是则 LOW，否则 MEDIUM
  └─ 否 → LOW（未来块信息难以操纵）
```
