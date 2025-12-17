# Vyper 预言机回退机制缺失

常出现在基于 Vyper 编写的借贷协议、稳定币或期权合约中，主预言机失败时无备用价格源，导致协议功能瘫痪或资金冻结。

## Details

**代码示例：**

```vyper
# 脆弱模式：单一预言机依赖无回退
interface PriceOracle:
    def getPrice(token: address) -> uint256: view

oracle: public(PriceOracle)

@external
def liquidate(user: address):
    price: uint256 = self.oracle.getPrice(COLLATERAL_TOKEN)  # 调用失败直接回退整个交易
    collateral_value: uint256 = self.collateral[user] * price / 10**18
    if collateral_value < self.debt[user]:
        self._seize_collateral(user)
```

**快速定位核心操作技巧（L3：逐行读）：**
- 搜索价格获取函数：`getPrice`、`latestAnswer`、`latestRoundData`、`consult`、`read_price`
- 检查预言机调用点：是否存在单一 `interface` 调用且无 `try/except` 或条件分支
- 追踪价格使用链：`liquidate`、`borrow`、`mint`、`swap` 等关键金融操作中的价格依赖

**快速定位保护机制技巧（L2：跳读）：**
- 查找回退逻辑：搜索 `fallback_oracle`、`secondary_source`、`backup_price` 等变量
- 检查异常处理：Vyper 0.3+ 中查找 `raw_call` 返回值检查或多个 `staticcall` 调用
- 验证价格合理性检查：`assert` 价格范围、时间戳新鲜度、是否存在默认值返回逻辑（如 `if price == 0: price = self.last_valid_price`）

## Classify

**判定为漏洞：**
- 单一预言机失败导致核心功能（清算/提款/铸币）永久不可用且无治理暂停机制
- 预言机返回 0 或异常值时无验证直接使用于资产定价
- 依赖链下预言机但无链上价格快照/时间锁备份

**判定为误报：**
- 协议设计明确单一可信预言机（如官方治理控制的预言机）且具备紧急暂停功能
- 价格获取失败时有明确的交易回退提示，且协议状态不受影响（如只读查询）
- 存在链下监控 + 快速治理响应机制，且历史无预言机停机记录

**判定为代码异味：**
- 存在备用预言机但未在文档中说明切换条件
- 回退机制依赖治理多签但响应时间过长（>24h）

## Low risk

**以下场景可评为低风险：**
- 预言机失败仅影响非关键功能（如前端展示价格、统计数据查询）且不涉及资金操作
- 协议具备经过测试的紧急暂停机制（circuit breaker），可在预言机异常时自动冻结操作
- 使用多个独立预言机源的中位数/均值且至少需要 N/2+1 个正常响应（类 Chainlink 聚合）
- 依赖的预言机具有极高可用性保障（如 Chainlink、Pyth）且合约内有价格时效性验证（heartbeat 检查）
- 仅在测试网部署或资金规模 <$10k 的实验性协议

## 审计专业技巧

### 现场区分真实漏洞与误报的关键要点

**1. 追踪资金流向（Risk Assessment第一步）**

在确定缺失回退机制是否构成漏洞前，必须明确回答：
- 预言机调用失败是否会导致用户资金被锁定或被强制转移？
- 是否存在清算/铸币等敏感操作直接依赖这个单点预言机？
- 协议TVL规模与备用机制成本比例是否合理？（小规模测试协议可接受单点）

真实漏洞案例：MakerDAO 预言机故障导致 $400M+ DAI 无法正确定价，清算系统陷入瘫痪 → 回退机制缺失致直接经济损失。

误报案例：某协议仅在 `view` 函数中调用预言机获取显示价格，失败时返回前次缓存值，不影响状态变更 → 属于代码异味而非关键漏洞。

**2. 检查隐性备用机制（常见遗漏点）**

Vyper 合约中回退机制可能以下列方式隐含：
```vyper
# 上次有效价格缓存（L1开发常忽视）
last_valid_price: public(uint256)
last_update_time: public(uint256)

@internal
def _safe_get_price() -> uint256:
    current_time: uint256 = block.timestamp
    # 隐性回退：如果新调用失败，时间戳不更新，外层逻辑可识别价格陈旧
    try:
        new_price: uint256 = staticcall self.oracle.getPrice(self.token)
        self.last_valid_price = new_price
        self.last_update_time = current_time
        return new_price
    except:
        # 显式回退或隐性返回陈旧价格
        return self.last_valid_price if current_time - self.last_update_time < STALENESS_THRESHOLD else 0
```

审计时需搜索：`last_`前缀变量、缓存相关注释、时间戳检查逻辑。

**3. Vyper 版本特性导致的误判**

- **Vyper 0.2.x**：无 `try/except` 支持，但可能通过 `raw_call` + 返回值检查实现回退
- **Vyper 0.3.0+**：支持 `try/except`，但异常处理不当仍可导致调用链中断
- **常见误报**：审计报告称"没有 `try/except`"但忽视了 `staticcall` 返回值校验或多链路回退

```vyper
# Vyper 0.3+ 的正确检查方式
success: bool
result: Bytes32
success, result = raw_staticcall(...)
if not success:
    # 真正的回退逻辑
    return self.cached_price
```

**4. 时间维度的真实性检验**

漏洞的严重性取决于恢复时间：
- **高严重性**：预言机中断需 >48h 通过治理恢复，且期间核心功能完全瘫痪
- **中等严重性**：存在回退但回退价格陈旧（>7天）导致清算延迟
- **低风险**：回退价格最近更新于 <1h，且存在自动暂停清算的时间锁

查看代码中的时间常量：
```vyper
# 检查 STALENESS_THRESHOLD、MAX_PRICE_AGE、TIMEOUT 等
MAX_PRICE_AGE: constant(uint256) = 3600  # 1小时 → 低风险
MAX_PRICE_AGE: constant(uint256) = 604800  # 7天 → 高风险
```

**5. 混合验证技巧（L1.5：半精读）**

对疑似误报的情况，执行以下三步快速验证：

步骤1：全局搜索所有与价格相关的外部调用
```bash
grep -n "getPrice\|latestAnswer\|raw_call" src/
# 统计调用点数 < 5个 → 可能确实缺回退；> 10个 → 高概率存在隐性保护机制
```

步骤2：追踪失败异常向上传播
- 调用失败是否会立即导致交易 `revert`？还是被封装在 `try/except` 中？
- 即使交易 `revert`，用户是否能重新调用或管理员能暂停操作？

步骤3：检查治理/紧急机制
- 是否存在 `pause()`、`emergency_shutdown()` 等保护函数？
- 权限是否足够去中心化（多签 >3 of 5）还是单人管理员（高风险）？

**6. 实际案例区分表**

| 场景 | 代码特征 | 漏洞度 | 备注 |
|------|--------|------|------|
| 单预言机 + try/except 空块 | `try: price=oracle() except: pass` | 严重 | 异常被忽视，等同无回退 |
| 单预言机 + cached_price 返回 | `except: return self.cached_price` | 中等 | 取决于缓存年龄；需验证更新频率 |
| 单预言机 + 自动暂停 | 异常→触发 `circuit_breaker()` | 低风险 | 关键；需验证暂停逻辑工作 |
| 多预言机聚合 + N/2+1 | Chainlink 聚合器模式 | 低风险 | 业界标准；高可用性 |
| 单预言机 + 管理员更新 | 依赖人工干预切换预言机 | 高风险 | 中心化，响应延迟高 |

**7. 最常见的误报来源（避坑清单）**

- ❌ 混淆"预言机调用异常"与"价格异常值"：前者需回退，后者需范围验证
- ❌ 忽视 Chainlink 等标准预言机内部已实现高可用：只要合约正确集成就无需额外回退
- ❌ 遗漏查看 `interface` 定义：可能已在上层抽象中实现回退
- ❌ 过度关注代码行数：小于 100 行的简单协议单点预言机可接受；大型 DeFi 协议必须多源
- ❌ 忽视历史可用性数据：某预言机过去 12 个月无中断 > 文档中的"紧急暂停承诺"

**8. 撰写高质量报告的检查清单**

当报告此类问题时，必须包含：
- [ ] 是否影响资金操作（清算/提款）还是仅展示数据？
- [ ] 预言机失败时协议状态是否安全（能否人工恢复或自动回滚）？
- [ ] 过去 12 个月预言机实际可用性数据（从服务商公开页面）
- [ ] 对标协议（如 Aave、Curve）的相同场景处理方式
- [ ] 修复建议的 gas 成本估算（某些高cost回退方案可能不可行）
