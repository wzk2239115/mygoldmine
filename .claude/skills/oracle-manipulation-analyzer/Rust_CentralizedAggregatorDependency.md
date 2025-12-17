# Rust 中心化聚合器依赖 (Centralized Aggregator Dependency)

**漏洞概述**  
常出现在基于 Solana 或 Substrate 的 DeFi 项目中，协议完全依赖单一中心化聚合器服务获取价格数据，无冗余机制或降级方案，导致聚合器服务下线、延迟、或作恶时协议完全瘫痪或价格操纵。

---

## Details

**典型代码示例：**

```rust
// Solana 程序直接依赖单一 Pyth/Switchboard 账户
pub fn get_price(price_account: &AccountInfo) -> Result<u64> {
    let price_feed = PriceFeed::try_from_slice(&price_account.data.borrow())?;
    // 直接返回聚合器价格，无校验、无备份源
    Ok(price_feed.price)
}

pub fn execute_swap(
    ctx: Context<Swap>,
    amount: u64,
) -> Result<()> {
    // 唯一价格源，无可用性检查
    let price = get_price(&ctx.accounts.oracle_account)?;
    // 基于单一价格执行关键逻辑
    let output = amount * price / PRECISION;
    // ...
}
```

```rust
// Substrate pallet 依赖单一外部 oracle 账户
impl<T: Config> Pallet<T> {
    pub fn fetch_price(asset_id: AssetId) -> Result<Price, DispatchError> {
        // 从 storage 读取唯一授权聚合器地址
        let oracle = Self::oracle_provider()
            .ok_or(Error::<T>::OracleNotConfigured)?;
        // 无重试、无备份源、无降级逻辑
        T::PriceOracle::get_price(oracle, asset_id)
    }
}
```

**快速定位核心操作技巧 (L3: 逐行读)**  
- 搜索 `PriceFeed`、`Aggregator`、`get_price`、`oracle_account`、`price_feed` 等关键字
- 定位价格获取函数，检查是否仅调用**单一账户/单一接口**
- 确认是否存在 `match`、`if oracle_a.is_err() { try oracle_b }` 等多源切换逻辑
- 检查是否有 `last_updated_slot`、`staleness_threshold` 等时效性校验

**快速定位保护机制技巧 (L4: 跨模块追踪)**  
- 寻找 `fallback_oracle`、`secondary_feed`、`backup_price_source` 等备份源配置
- 检查 `circuit_breaker`、`price_deviation_check`、`staleness_guard` 等熔断机制
- 追踪 `oracle_account` 的传入路径，确认是否可动态切换或由治理配置多个源
- 查看 `is_oracle_healthy()`、`validate_price_freshness()` 等健康检查函数
- 跨模块检查是否有独立的 `OracleRegistry` 或 `PriceAggregator` 模块实现多源聚合

---

## Classify

**漏洞判定依据：**
- 价格获取逻辑硬编码单一 oracle 账户地址，无备份机制
- 无时效性检查（如 `slot` 或 `timestamp` 过期判断）
- 无价格合理性验证（如偏差阈值、波动熔断）
- 单点故障可导致核心功能（借贷清算、交易定价）完全失效

**误报排除：**
- 项目明确声明为测试环境或 PoC，非生产部署
- 存在治理快速切换 oracle 的应急机制（需验证响应时间 < 攻击窗口）
- 价格数据仅用于非关键功能（如前端展示、统计分析）

**代码异味（需上下文研判）：**
- 有多源配置但实际未启用（配置项存在但默认为空）
- 有降级逻辑但条件过于宽松（如允许使用 1 小时前的陈旧价格）
- 备份源与主源实质为同一服务商的不同端点（仍为单点风险）

---

## Low risk

**以下场景可评为低风险：**

1. **非关键路径调用**：价格数据仅用于事件日志、前端展示、历史统计等非状态变更场景
2. **存在有效降级方案**：
   - 协议有 TWAP（时间加权平均价）作为备用定价机制
   - 存在手动价格输入通道且有快速多签授权机制（需验证响应时间）
3. **时间窗口限制**：
   - 依赖单一源但有严格时效性检查（如价格更新间隔 < 1 slot）
   - 聚合器本身具有高可用性 SLA（如 Pyth Network 的去中心化验证网络）
4. **金额上限保护**：单次操作金额上限极低，即使价格操纵损失也可控
5. **测试网/沙盒环境**：明确标注为非生产环境的实验性功能

**注意：即使评为低风险，仍需在审计报告中建议实现冗余机制，单点依赖始终是架构缺陷。**
