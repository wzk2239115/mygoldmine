**Move**  
常出现在涉及资源状态竞争的DeFi协议、治理提案投票或NFT铸造逻辑中，包括但不限于未隔离用户操作的原子性、允许公开读取待处理操作状态、或在模块中暴露可被抢先调用的公开入口函数： 
- NFT 铸造抢跑：NFT 铸造交易在内存池中可见，攻击者抢先提交交易优先铸造稀有 NFT，详见：Move_NFTMintFrontRunning.md 
## Details

**代码示例特征：**
```move
public entry fun mint_nft(account: &signer, token_id: u64) {
    let nft = NFT { id: token_id, rarity: calculate_rarity(token_id) };
    move_to(account, nft);
}
```
典型场景：公开入口函数直接使用区块链状态（如时间戳、区块高度）或可预测参数决定NFT稀有度，且无提交-揭示机制或时间锁保护。

**快速定位核心操作（L3：逐行读）：**
- 关注 `public entry fun` 铸造函数中的资源创建逻辑（`move_to`、`Resource::create`）
- 检查稀有度计算是否依赖公开可见参数（`token_id`、`timestamp::now_seconds()`、`block::get_current_block_height()`）
- 追踪 `acquires` 声明的全局状态读取，判断是否存在铸造顺序依赖
- 定位铸造数量上限检查（`assert!` 配合全局计数器）的原子性保护

**快速定位保护机制（L2：跳读）：**
- 扫描是否存在 `aptos_framework::randomness` 或 VRF 模块调用（链上随机数）
- 检查 `timestamp` 相关的时间窗口限制（白名单期、公开铸造期分离）
- 查找 `0x1::account::SignerCapability` 或白名单验证逻辑（限制调用者身份）
- 确认是否有两阶段提交（commit-reveal）模式：先提交哈希，后揭示原像
- 验证全局状态更新与资源转移是否在同一事务内完成（原子性）

## Classify

**确认为漏洞：**
- 稀有度由可预测参数（交易顺序、区块高度、简单哈希）直接决定，攻击者可通过提高Gas费抢跑
- 全局状态读取与铸造操作分离在不同事务中，导致TOCTOU（检查时与使用时）竞争
- 铸造数量检查使用非原子操作，允许并发交易绕过上限

**误报场景：**
- 稀有度由链上VRF或Aptos随机数模块生成，且随机数种子不可预测
- 铸造函数受严格白名单或签名验证保护，非公开可调用
- 存在时间锁或延迟执行机制，使内存池可见性失去意义

**代码异味：**
- 使用简单的 `hash(token_id)` 作为伪随机源（理论上可预测但成本较高）
- 铸造速率限制依赖区块时间戳而非不可操纵的链上随机性
- 缺少事件日志记录铸造顺序，难以事后追溯抢跑行为

## Audit Professional Techniques

**真实漏洞与误报区分经验：**

### 1. 随机数来源验证
- **真实漏洞案例**：调用 `hash(tx_sender + block_height)` 生成稀有度，攻击者通过发送多笔交易在同一区块内控制发送者地址，实现稀有度预测
- **误报排查**：检查是否使用 Aptos 官方 `randomness` 模块（仅在 Mainnet 可用），验证随机数是否通过 VRF 密钥和委托者签名生成，查阅合约部署日期确保 VRF 时间戳有效性
- **灰色地带**：使用 `timestamp::now_microseconds()` 作为种子的 `hash(tx_hash + timestamp)` 虽增加成本但理论可预测，需评估攻击经济性

### 2. 原子性与TOCTOU检查
- **真实漏洞案例**：全局计数器检查与资源创建分离，transaction A 检查计数 < 限制后发起，transaction B 插入并增加计数，A 继续执行导致总数超过限制
  ```move
  // 错误示例：分离操作
  public entry fun mint(account: &signer) acquires MintCounter {
      let counter = borrow_global_mut<MintCounter>(@contract);
      assert!(counter.count < MAX_SUPPLY, E_EXCEEDED);  // 检查点
      // ... 中间有其他操作
      counter.count = counter.count + 1;  // 使用点 (TOCTOU窗口)
  }
  ```
- **误报排查**：验证计数器更新与资源创建在同一事务作用域内，检查 `acquires` 是否在函数开头独占锁定全局状态，搜索是否有 `move_to()` 在更新前执行
- **审计技巧**：在 Aptos 中追踪 `BorrowMut` 的生命周期，确认在资源转移前已完成计数增加

### 3. 白名单与权限验证的伪阳性
- **真实漏洞案例**：白名单检查使用 `vector::contains()` 但向量在链上可见且铸造函数公开，攻击者通过交易溯源直接观察白名单地址列表
- **误报排查**：
  - 白名单是否存储在非公开资源内（`struct{ whitelist: vector<address> }` 包装在具有访问控制的资源中）
  - 验证白名单检查逻辑是否通过 Merkle Tree（仅暴露根值）而非完整列表
  - 确认铸造函数是否需要特定签名验证（通过 `&Signer` 的地址限制），而非仅检查输入参数
- **灰色地带**：使用 `SignerCapability` 但允许转移或委托，需追踪能力的实际流向

### 4. 时间锁与延迟执行的有效性
- **真实漏洞案例**：时间锁检查仅限制立即执行，但攻击者在 N 个区块后通过高Gas抢跑其他用户的延迟交易
  ```move
  // 风险示例：时间锁存在但无交易排序保护
  public entry fun claim_after_delay(account: &signer) acquires RewardData {
      let reward = borrow_global_mut<RewardData>(signer::address_of(account));
      assert!(timestamp::now_seconds() >= reward.unlock_time, E_LOCKED);
      transfer_reward(account, reward.amount);
  }
  ```
- **误报排查**：
  - 时间锁是否阻止内存池中的交易可见性（实际上无法阻止，但可评估内存池价值）
  - 检查是否有基于区块号的额外限制（增加时间成本）
  - 验证奖励计算是否依赖 `first_come_first_served` 机制（导致真正的抢跑风险）
- **审计建议**：即使有时间锁，仍需评估时间窗口内的竞争（如果有限额奖励）

### 5. 经济激励与成本-收益分析
- **真实漏洞识别**：计算 `(稀有NFT价值差 - Gas成本 - 滑点) > 攻击者收益` 判断是否现实威胁
  - 示例：高级NFT与普通NFT市场差价为 10 SOL，但单次抢跑Gas为 0.1 SOL，差价充足
  - 若差价 < Gas成本 × 10，则威胁等级降低但仍需记录
- **误报排查**：
  - NFT 所有权确认：是否真实可转让且有流动性市场
  - 验证 Gas 价格计算是否基于实际网络费用（避免过时估算）
  - 检查批量铸造成本是否随数量指数增长（DeFi协议常见）
- **案例**：某 NFT 铸造协议 Premium 版本价格为 1 APTOS，抢跑 Gas 为 0.01 APTOS，但 Premium NFT 实际市场价 1.2 APTOS（考虑交易费），风险等级为中等

### 6. 事件日志与可追踪性
- **真实漏洞信号**：缺少 mint 事件日志（`event::emit(MintEvent{ ... })`）难以链下验证铸造顺序，攻击者覆盖痕迹
- **误报排查**：即使有日志，检查是否可被伪造（确认发射点在核心逻辑内，不可绕过）
- **审计技巧**：使用 Aptos 区块浏览器追踪特定 mint 事件的 `transaction_version` 和 `event_index`，确认顺序一致性

### 7. 网络层隐私技术的绕过
- **真实漏洞**：即使采用 MEV 保护（如 threshold encryption），若未同步应用层验证，仍可在链上观察 mint 资源的创建
- **误报排查**：验证 MEV 方案是否由 Aptos 基础设施级别实现（目前 Aptos 无原生 MEV 保护），用户级应用层加密不足

## Low risk

**以下情况可评为低风险：**
- NFT铸造为平权设计（所有NFT属性相同），无稀有度差异驱动抢跑动机
- 铸造成本远高于稀有NFT潜在价值差，经济激励不足
- 协议采用荷兰拍卖或动态定价机制，抢跑者需承担更高成本
- 铸造仅限私有网络或许可链，内存池不公开可见
- 存在Gas价格上限或统一Gas费机制，无法通过出价竞争优先级
- 采用成熟的链上随机数方案（Aptos randomness module）且版本为最新
- 白名单与权限通过 Merkle Tree 或零知识证明实现，完全隐藏用户身份
