# Rust Solana 拍卖 MEV 漏洞审计

**漏洞概述**  
竞拍程序中出价信息对验证者可见，验证者可调整交易顺序优先执行特定出价，导致公平性受损。常见于NFT拍卖、资产清算拍卖、域名竞拍等场景。

## Details

**代码示例：易受攻击的拍卖程序**
```rust
pub fn place_bid(ctx: Context<PlaceBid>, amount: u64) -> Result<()> {
    let auction = &mut ctx.accounts.auction;
    let clock = Clock::get()?;
    
    require!(clock.slot < auction.end_slot, ErrorCode::AuctionEnded);
    require!(amount > auction.highest_bid, ErrorCode::BidTooLow);
    
    // 直接更新最高出价，信息完全透明
    auction.highest_bidder = ctx.accounts.bidder.key();
    auction.highest_bid = amount;
    
    Ok(())
}
```

**快速定位核心操作（L3：逐行读）**
- 查找 `place_bid`、`submit_bid`、`bid`、`auction` 等拍卖相关函数
- 关注出价更新逻辑：`highest_bid`、`current_bid`、账户余额变动
- 检查出价数据存储位置：是否立即写入链上账户（透明）vs 哈希承诺
- 审查slot/时间戳依赖：`Clock::get()?`、`clock.slot`、`clock.unix_timestamp`
- 追踪出价提交到结算的时间窗口：单slot完成 vs 多slot承诺揭示

**快速定位保护机制（L2：跳读 + L4：跨模块追踪）**
- **L2 跳读**：扫描是否存在 `commit`、`reveal`、`hash`、`secret` 关键词
- **L3 逐行读**：检查是否使用承诺揭示模式（commit-reveal）
  - 第一阶段：提交 `hash(bid_amount + secret)`
  - 第二阶段：揭示 `bid_amount` 和 `secret` 并验证哈希
- **L2 跳读**：查找加密相关调用：`solana_program::hash::hash`、`keccak256`
- **L4 跨模块追踪**：检查是否使用 Solana VRF 或延迟执行机制
  - 追踪 `switchboard_v2`、`pyth` 等预言机集成
  - 查找 `delayed_execution`、`time_lock` 等延迟机制
- **L1 关键词扫描**：搜索 `mev`、`front_run`、`sandwich` 等安全注释

## Classify

**判定为高危漏洞**
- 拍卖出价直接明文存储到链上账户，无任何隐私保护
- 结算逻辑完全依赖单个slot内的账户状态比较
- 验证者可见所有待处理出价交易并任意调整顺序
- 缺失承诺揭示、加密出价、VRF等抗MEV机制

**判定为误报**
- 已实现完整的commit-reveal两阶段提交，且揭示期足够长（>10 slots）
- 使用链下订单簿+链上批量结算，单个交易不可见出价细节
- 采用时间加权或随机选择而非单纯最高价中标
- 拍卖属于荷兰拍（降价拍），价格公开且递减，先到先得无抢跑空间

**判定为代码异味**
- 有承诺揭示机制但揭示期过短（1-2 slots），仍存在理论攻击窗口
- 出价哈希未绑定bidder地址，可被他人复制揭示
- 承诺阶段允许多次提交覆盖，可能泄露出价意图
- 依赖slot时间但未考虑slot时间漂移或验证者操纵

## Low risk

**以下情况可评为低风险**
- 拍卖金额上限极低（<0.1 SOL），MEV收益不足以覆盖攻击成本
- 拍卖仅限白名单参与且参与者数量≤3，共谋成本高于收益
- 结算价格取所有出价的中位数或加权平均，单笔抢跑影响有限
- 拍卖品为非流动性资产（如特定任务凭证），无法快速变现
- 已有链下监控告警机制，异常交易顺序会触发拍卖作废
- 出价需要质押高额保证金（>10x拍品价值），作恶成本远超收益
- 程序运行在测试网或实验性产品，未涉及真实资产价值

## 审计专业技巧与经验

### 真实漏洞与误报的区分方法

**核心区分要素**

**1. 承诺揭示模式的可信度评估**
- **真实漏洞**：计划使用commit-reveal但代码中commit函数从未调用，或揭示期设为0
  - 检查：搜索 `commit` 函数定义和调用点，验证call graph完整性
  - 反例：某些项目声称使用承诺揭示，但仅在初始化时写入注释，无实际实现
- **误报风险**：仅因揭示期为3-5 slots就判定高危，需考虑实际攻击成本
  - 修正：计算最小套利规模 = 手续费成本 / 预期收益，若<0.01则风险有限

**2. 时间戳操纵 vs Slot依赖的误判**
- **真实漏洞**：直接依赖 `Clock::unix_timestamp` 且验证者可调整±25秒
  - 标志：找到 `block_timestamp` 或 `unix_timestamp` 直接用于出价比较
  - 验证：检查是否与 `Clock::slot` 结合（slot无法伪造，timestamp可伪造）
- **误报陷阱**：看到 `slot` 判定为安全，但忽视slot时间漂移（13秒变13.2秒）
  - 修正：时间漂移对短期拍卖（<10 slots）影响≤1%，需计算具体影响

**3. 链下订单簿的风险重新评估**
- **真实漏洞**：链下订单簿但聚合器合约直接读取链上最新价格而无批量签名验证
  - 危险信号：`call external_price_feed()` 后直接结算，无数据可用性验证
- **误报发生点**：链下订单簿+sgx/tee验证被误为完全去中心化
  - 现实评估：Chainlink oracle可被操纵（闪电贷），需评估抵押金比例

**4. 多签与权限的陷阱**
- **真实漏洞**：多签包含交易验证者自身，验证者可自行决议抢跑
  - 检查：遍历multisig成员列表，与已知验证者节点对比
  - 案例：某拍卖程序2-of-3多签中2人为同一实体下属验证者
- **误报案例**：看到multi-sig就判安全，忽视single point of failure（私钥泄露）

### 常见误报模式识别表

| 代码特征 | 快速判定 | 深度审查 | 结论 |
|---------|---------|---------|------|
| `hash(bid_amount)` 存储 | ✅ 有承诺 | 检查hash绑定bidder? | 若未绑定→可复制揭示→真漏洞 |
| `slot > end_slot` 检查 | ✅ 有时间锁 | slot能否被验证者跳过? | Solana不允许→误报 |
| `require!(signer == authority)` | ✅ 权限检查 | authority能否调整? | owner可upgrade→真漏洞 |
| `PDA-derived account` | ❌ 数据透明 | 账户内容是否加密? | 未加密→真漏洞 |

### 实战审计检查清单

**第一轮：5分钟快速评估**
- [ ] 搜索 `highest_bid` 或 `auction_state` 是否有public/global修饰
- [ ] 检查最近10笔交易的slot间距是否存在异常（<2秒聚合=红旗）
- [ ] 查阅项目TVL和单笔最大出价，计算MEV收益/攻击成本比

**第二轮：深度代码审查**
- [ ] 追踪出价从提交→结算的完整生命周期，画状态机图
- [ ] 对于每个时间戳或slot检查：谁能修改？修改权限边界在哪？
- [ ] 模拟攻击：假设验证者控制交易顺序，能否修改最终赢家？

**第三轮：链上行为验证**
- [ ] 查询3-5个历史拍卖，统计赢家bidder首次出现的slot
- [ ] 若赢家总在最后1-2 slots出现→高风险信号
- [ ] 检查是否存在"中标直接转账"模式（无escrow）→资金可能流向验证者

### 真实案例对比

**案例A：虚假的承诺揭示（真实漏洞）**
```rust
// 声称有commit-reveal但揭示函数无人调用
pub fn commit_bid(ctx: Context<CommitBid>, hash: [u8; 32]) -> Result<()> {
    auction.bid_hash = hash; // 存储但后续unused
    Ok(())
}
// ⚠️  实际结算直接使用高价出价，无reveal阶段
pub fn finalize_auction(ctx: Context<FinalizeAuction>) -> Result<()> {
    transfer_to_winner(highest_bidder); // 直接结算！
}
```

**案例B：真正安全的设计**
```rust
// Epoch A (slots 0-100): 接收commit
// Epoch B (slots 101-300): 必须在此期间reveal，逾期forfeit
// Epoch C (slots 301-310): 结算阶段，不再接受reveal
pub fn finalize_auction(...) {
    require!(clock.slot > reveal_end, AuctionNotEnded);
    let revealed_bids = filter_valid_reveals(); // 仅统计已valid的reveal
}
```

**判定差异**
- 案例A：误报风险0%，确实是漏洞（高危）
- 案例B：需验证reveal_end的实际可信度（中危→低危）
