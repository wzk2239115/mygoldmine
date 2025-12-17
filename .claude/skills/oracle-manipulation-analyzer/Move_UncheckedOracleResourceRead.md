# Move_UncheckedOracleResourceRead

**漏洞类型：** 预言机操纵 - 未检查的资源读取  
**适用场景：** Aptos/Sui 生态中的资产定价、抵押借贷、清算机制、奖励分配、保证金计算

## Details

### 代码示例特征

```move
// 典型漏洞模式：直接从全局资源读取价格数据
public fun calculate_value<CoinType>(amount: u64): u64 acquires PriceOracle {
    let oracle = borrow_global<PriceOracle<CoinType>>(@oracle_address);
    amount * oracle.price  // 直接使用未验证的价格
}

// 漏洞变种：读取后未检查时间戳
public fun get_asset_worth(asset_id: u64): u64 acquires OracleData {
    let data = borrow_global<OracleData>(@oracle);
    // 缺少：assert!(timestamp::now_seconds() - data.last_update < MAX_DELAY, E_STALE_PRICE);
    data.prices[asset_id]
}
```

### 快速定位核心操作 **[L2:跳读]**

**关键函数模式：**
- `borrow_global<Oracle*>()` / `borrow_global_mut<Oracle*>()` 后紧跟字段访问
- 搜索 `.price`、`.rate`、`.value` 等价格相关字段的直接读取
- 关注 `acquires` 声明中包含 Oracle/Price/Feed 等关键词的函数
- 追踪资源结构体定义中 `last_update`、`timestamp`、`expiry` 字段的使用位置

**审计切入点：**
1. 全局搜索 `acquires.*Oracle` 定位所有预言机资源访问点
2. 检查资源读取后是否存在数据校验逻辑（通常在 `assert!` 或 `if` 条件中）
3. 关注金融计算函数（calculate/compute/get_value/liquidate 等命名）

### 快速定位保护机制 **[L3:逐行读]**

**有效防护特征（存在即可降级风险）：**
- **时效性校验：** `assert!(now - oracle.updated_at <= MAX_STALENESS, ERROR_CODE)`
- **数值边界检查：** `assert!(price > MIN_PRICE && price < MAX_PRICE, E_INVALID)`
- **来源验证：** 检查 `signer` 或 `witness` 模式确保更新者权限
- **多源聚合：** 从多个预言机地址读取并取中位数/加权平均
- **熔断机制：** 价格波动超阈值时拒绝使用（需检查 `deviation` 或 `confidence` 字段）

**审计检查清单：**
```move
// 在资源访问后的3-10行内应出现：
let oracle = borrow_global<Oracle>(...);
// ✓ 时间戳检查
assert!(timestamp::now_seconds() - oracle.last_update < VALIDITY_PERIOD, E_STALE);
// ✓ 价格合理性
assert!(oracle.price > 0 && oracle.price < type_max_u128(), E_INVALID);
// ✓ 或封装在独立校验函数中
validate_oracle_data(&oracle);
```

**缺失防护的判定标准：**
- 资源读取与业务逻辑使用之间 **无任何** `assert!` 或条件分支
- 仅校验资源存在性（`exists<Oracle>(addr)`）但不检查内容
- 时间戳字段存在但从未被读取或比较

## Classify

### 确认为漏洞的条件
**同时满足以下所有条件：**
1. **关键业务路径：** 代码用于资产定价、清算判定、抵押率计算等直接影响资金安全的场景
2. **无有效校验：** 价格读取后未进行时效性、有效性、合理性任一检查
3. **外部依赖：** 预言机数据来源于合约外部（非模块内部管理的资源）
4. **可被利用：** 攻击者可通过控制预言机更新者（若无ACL）或利用时间窗口（若数据过期）获取不当利益

**典型漏洞场景识别：**
- 借贷协议直接用未校验价格判断抵押品价值 → 可恶意清算
- DEX使用过期预言机价格作为参考价 → 可套利
- 奖励分发依据未验证的资产价格 → 可超额领取

### 判定为误报的情况
1. **读写在同一事务：** 同一函数内先写入再读取（`move_to` 后立即 `borrow_global`）
2. **只读查询接口：** 函数标记为 `#[view]` 或仅用于前端展示无状态变更
3. **已有上层校验：** 调用方在使用返回值前已实施完整检查（需追踪调用链）
4. **测试/模拟代码：** 位于 `tests` 模块或注释标明为示例代码

### 代码异味（需进一步判断）
- **部分校验：** 仅检查时间戳但未验证价格范围，或反之
- **弱校验逻辑：** 允许的时间偏差过大（如 >24小时）或价格范围过宽
- **隐式信任：** 依赖注释声明"预言机可信"但无代码强制

## Low risk

### 降级为低风险的典型场景

1. **非核心业务使用：**
   - 价格数据仅用于前端UI展示推荐值（不影响链上状态）
   - 统计分析或日志记录用途
   - 功能已被标记废弃（deprecated）或处于测试阶段

2. **存在补偿性控制：**
   - 虽未校验预言机数据，但业务逻辑设置了保护性上限（如最大借款额度恒定）
   - 存在时间锁机制，价格变动无法立即生效
   - 多签或治理投票机制可及时撤销恶意操作

3. **影响范围受限：**
   - 单个用户资金受影响金额上限明确且较小
   - 漏洞利用需要同时满足多个苛刻前置条件（如需持有特定NFT且在特定时间窗口）
   - 攻击成本接近或高于潜在收益

4. **预言机信任模型明确：**
   - 项目文档明确声明使用可信预言机（如 Pyth/Switchboard）且有链下监控
   - 预言机更新者为项目方多签地址，有明确的事件日志和更新频率承诺
   - 存在应急暂停机制（emergency pause）可在发现异常时冻结合约

5. **技术限制场景：**
   - Move语言版本或平台限制导致某些校验无法实现，但有文档说明风险
   - 临时性中间状态（价格在同一事务内被后续逻辑覆盖）

**风险评级建议：** 当满足上述2项及以上，且经评估实际可利用难度高，可考虑降级为 Low，但需在报告中详细说明风险残留原因及监控建议。
