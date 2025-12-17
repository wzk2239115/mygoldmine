# Rust Blockhash 可预测性

**漏洞概述**  
Solana 程序中使用 `recent_blockhashes` 或 `RecentBlockhashes` sysvar 作为随机源。该值对所有验证者和前端节点可见，攻击者可在同一 slot 内提交交易，提前计算随机结果并选择性提交有利交易。

## Details

**典型代码模式：**
```rust
// 脆弱示例
let recent_blockhashes = &ctx.accounts.recent_blockhashes;
let blockhash_data = recent_blockhashes.to_account_info().data.borrow();
let hash_value = &blockhash_data[0..32];
let random_number = u64::from_le_bytes(hash_value[0..8].try_into().unwrap()) % 100;
```

**快速定位核心操作（L2-跳读）：**
- 搜索关键词：`recent_blockhashes`、`RecentBlockhashes`、`blockhash`
- 关注账户验证部分的 sysvar 引用：`account(address = sysvar::recent_blockhashes::ID)`
- 追踪 hash 值的数学运算：模运算、取余、切片操作
- 检查是否用于决策逻辑：抽奖、掉落、分配、游戏结果

**快速定位保护机制（L3-逐行读）：**
- 是否引入外部熵源：VRF、oracle、commit-reveal
- 是否有延迟确认机制：未来 slot 的 blockhash（注意：仍可预测）
- 是否限制单地址多次参与：仍不足以防护
- 是否使用 Solana VRF（如 Switchboard、Chainlink VRF）

## Classify

**判定为漏洞：**
- 直接影响资产分配、游戏胜负、NFT 稀有度等高价值决策
- 可预测性被用于不公平优势获取
- 经济激励足以支撑攻击成本（交易费、计算成本）

**判定为误报：**
- 随机数仅用于非关键 UI 展示或日志标记
- 结果不影响链上状态或资产
- 已通过 commit-reveal 或 VRF 方案消除可预测性

**判定为代码异味：**
- 使用 `Clock::unix_timestamp` 而非 blockhash（相似问题）
- 多个弱随机源组合但未引入真随机性
- 延迟机制不足以消除预测窗口

## Low risk

**以下场景可降级为 Low：**
- 随机结果仅影响极小额资产（< 0.1 SOL 量级）
- 需要跨多个 epoch 的长期预测（实际不可行）
- 存在外部审查机制或人工介入流程
- 程序已明确废弃或处于测试网环境
- 结合其他强制性时间锁或多签控制，攻击收益小于成本

## 审计专业技巧

### 1. 动态分析追踪

**交易模拟与链上数据对比：**
- 使用 `solana-cli simulate` 或 Anchor 测试框架在本地执行交易
- 观察同一 blockhash 下多次调用的结果：若完全相同 → **确定漏洞**；若有变化 → 可能涉及其他随机源
- 获取历史交易数据，检查同一 slot 内是否存在重复的"幸运"事件（如连续中奖）
- 对比 UI 显示的概率与链上实际结果的卡方检验

```rust
// 审计代码示例：检查是否真实使用了 blockhash
let blockhash = recent_blockhashes.to_account_info().data.borrow()[0..32].to_vec();
let derived_value = hash_with_blockhash(&blockhash);  // 链上计算
let ui_claimed_result = get_user_ui_result();  // 从交易日志提取
assert_eq!(derived_value, ui_claimed_result);  // 比对
```

### 2. 误报陷阱与识别

**常见误报场景：**

1. **VRF 假阳性**：代码中虽然有 blockhash 调用，但实际是在 VRF 回调中使用
   - 识别方法：检查调用栈是否经过 `derive_vrf` 或 oracle 验证环节
   - 真实案例：Switchboard VRF 的本地开发环境可能先调用 `recent_blockhashes`，再覆盖为真随机值

2. **隔离的随机数生成器**：使用 blockhash 初始化 PRNG，但 seed 经过哈希链强化
   - 识别方法：追踪 seed 来源，检查是否使用了 `sha256(blockhash || nonce || program_id)` 等复杂派生
   - 低风险指标：随机数派生层数 > 3 层，且包含用户不可控因子

3. **测试/模拟环境中的 blockhash**：测试网或本地验证器的 blockhash 虽然可见但无利益相关
   - 识别方法：通过程序初始化检查 `cluster: mainnet-beta` 的约束
   - 示例：`#[cfg(feature = "prod")]` 仅在生产环境才启用随机逻辑

**确认误报的检查清单：**
- [ ] 是否存在 external VRF/oracle 集成（Chainlink、Switchboard、Pyth）
- [ ] 随机值是否在程序执行前已经固定（来自 oracle 账户而非实时读取）
- [ ] 是否有明确的隔离环境标签（`testnet`, `devnet` 专用逻辑）
- [ ] 随机数结果是否经过累积哈希或盐值强化

### 3. 真实漏洞的确认签名

**必须同时满足以下条件才是高风险漏洞：**

```
条件组 A（可预测性）：
✓ 使用 recent_blockhashes/Clock 作为主随机源
✓ 未引入外部不可预测因子
✓ 随机值在交易签署前可计算

条件组 B（经济激励）：
✓ 结果影响 > 0.01 SOL 价值的资产转移
✓ 攻击成本（交易费 ~ 5000 lamports）< 预期收益
✓ 无需大量前置交易（成本指数级）

条件组 C（可执行性）：
✓ 攻击者可在同一 slot 内提交多个交易
✓ 或能够预测未来 N 个 slot 的 blockhash（N ≤ 256）
✓ 不需要破坏其他用户的交易或等待 epoch 转换
```

### 4. 实地审计案例对比

**案例 1：真实漏洞（Marble Finance 彩票）**
- 特征：使用 `recent_blockhashes` 直接 modulo 计算中奖号码
- 确认：通过回放相同 blockhash，得到相同中奖号，且链上存在连续中奖地址
- 风险：每次彩票参与 0.1-1 SOL，月交易量 > 100 万 SOL
- 结论：**Critical**

**案例 2：误报（某 NFT 抽签合约）**
- 表面特征：使用 `Clock::unix_timestamp` % 10000
- 看似漏洞原因：时间戳可预测
- 实际情况：随机结果仅用于生成链上事件日志，NFT 分配由人工审查决定
- 确认方式：检查 NFT mint 历史与随机事件无关联
- 风险：**Info/Low**

**案例 3：设计缺陷（某游戏的 seed 重复）**
- 特征：虽然引入了 VRF，但使用相同 seed 多次调用导致结果相同
- 确认：同一地址多次参与得到完全相同的随机值
- 修复：确保每次调用 VRF 时传入唯一 nonce（如交易签名中的字节）
- 风险：**High**

### 5. 审计工具与命令

```bash
# 快速检索 blockhash 使用模式
grep -r "recent_blockhashes\|RecentBlockhashes" ./programs --include="*.rs"

# 追踪随机数在决策中的使用（通过 @ 符号）
grep -r "% \|/ \|>> \|<< " ./programs --include="*.rs" -B 2 -A 2 | head -50

# 检查是否包含 VRF 导入
grep -r "vrf\|oracle\|Switchboard\|Chainlink" ./Cargo.toml ./programs

# 分析交易日志中的数值分布
solana logs | grep "random\|seed\|hash" | awk '{print $NF}' | sort | uniq -c | sort -rn
```

### 6. 与开发者沟通的要点

**避免陷入的讨论：**
- ❌ "我们用了 sha256 哈希就很安全了" → 指出 blockhash 本身仍可被验证者预知
- ❌ "我们限制了单地址的参与次数" → 可以通过派生地址规避限制
- ❌ "只有 0.01 SOL，没有利益" → 累积千次交易后成本收益比改善

**确认安全的关键问题：**
1. "随机值在哪个交易步骤被计算？能否在签署前预测？"
2. "是否依赖了验证器签名或 Oracle 的不可伪造性？"
3. "历史数据中是否观察到非随机分布？"
