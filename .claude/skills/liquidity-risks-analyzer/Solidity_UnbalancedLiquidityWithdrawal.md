# Solidity 不平衡流动性提取漏洞审计指南

**漏洞类型**：流动性风险 - 不平衡流动性提取  
**影响范围**：AMM 兑换、流动性提供与移除、单边质押收益池  
**核心问题**：允许不按比例提取流动性，破坏池子平衡导致价格扭曲

## Details

**典型代码模式**：
```solidity
function removeLiquidity(uint amount0, uint amount1) external {
    _burn(msg.sender, liquidity);
    _safeTransfer(token0, msg.sender, amount0); // 未验证比例
    _safeTransfer(token1, msg.sender, amount1); // 未验证比例
}
```

**快速定位核心操作** (L3: 逐行读)：
- 关注 `removeLiquidity`、`withdraw`、`burn` 等函数
- 检查 `amount0/amount1` 参数是否由用户直接指定而非公式计算
- 验证是否存在 `reserve0/reserve1` 比例校验逻辑
- 追踪 LP token 销毁量与资产提取量的关系公式

**快速定位保护机制** (L2: 跳读)：
- 搜索 `reserve0 * amount1 == reserve1 * amount0` 等比例验证
- 查找 `getAmountOut` 或 `quote` 函数调用确保按池比例计算
- 检查是否有 `K = reserve0 * reserve1` 不变量验证
- 确认是否调用 `_update()` 同步储备量与余额

## Classify

**确认为漏洞**：
- 用户可自定义两种资产提取数量且无比例校验
- LP token 销毁与资产转出无强制关联公式
- 可通过构造参数使池内资产比例严重失衡（偏离市场价超过滑点保护范围）

**判定为误报**：
- 虽允许指定数量但在内部重新按 `liquidity/totalSupply * reserve` 计算实际转账额
- 存在滑点保护且阈值合理（通常 0.5%-5%）
- 单边提取但有额外抵押物或保险机制覆盖风险

**代码异味**：
- 比例验证存在但精度损失可能导致微小偏差累积
- 仅校验单边比例而未验证 K 值不变量
- 缺少最小流动性锁定（MINIMUM_LIQUIDITY）导致精度攻击

## Low risk

**低风险场景**：
- 池子规模极大（>$10M TVL）且允许偏差极小（<0.01%），经济上不可行
- 仅限白名单地址调用，且已通过链下验证
- 存在时间锁或多签保护，恶意操作可被及时取消
- 池子设计为单资产池或稳定币池，价格本身就应保持 1:1
- 已集成价格预言机实时校验，偏离阈值自动暂停提取

## 审计专业技巧

### 1. 真实漏洞的三层识别法

**第一层：参数控制权检查**
```solidity
// 误报示例：参数由调用者指定但最终金额由公式计算
function removeLiquidity(uint liquidity, uint min0, uint min1) external {
    uint amount0 = liquidity * reserve0 / totalSupply;  // 自动计算
    uint amount1 = liquidity * reserve1 / totalSupply;  // 自动计算
    require(amount0 >= min0 && amount1 >= min1, "slippage");
}

// 真实漏洞：两个金额完全由用户指定
function removeLiquidityUnsafe(uint amount0, uint amount1) external {
    _burn(msg.sender, liquidity);
    token0.transfer(msg.sender, amount0);
    token1.transfer(msg.sender, amount1);
    // 无任何比例验证 → 实际漏洞
}
```

**第二层：资产转出与销毁的关联性验证**
- 真实漏洞：LP token 销毁与资产提取无强制公式，销毁 1 个 LP 可能提取 100 个资产
- 误报案例：销毁 1 个 LP 时，自动转出对应比例资产，即使参数名称暗示可自由指定

**第三层：经济激励分析**
- 攻击成本 vs 获利空间：若偏离 1 个 Wei，交易成本已超过收益，则实际风险极低
- 前置依赖：是否需要提前拥有大量 LP token？若需要，则需同时拥有向池中投入巨资的历史记录

### 2. 常见误报陷阱

**陷阱 A：错误识别滑点保护为漏洞**
```solidity
// 这不是漏洞，这是有效的滑点保护
function removeLiquidity(
    uint liquidity,
    uint minAmount0,
    uint minAmount1
) external {
    (uint amount0, uint amount1) = _getAmountsOut(liquidity);
    require(amount0 >= minAmount0 && amount1 >= minAmount1, "slippage");
    // minAmount0/minAmount1 限制偏差范围，即使 amount0/amount1 由公式计算
}
```

审计注意：分析调用者是否能绕过 `minAmount0/minAmount1` 的约束
- 若无法绕过 → 非漏洞
- 若可通过 flashloan 操纵价格绕过 → 真实漏洞

**陷阱 B：混淆"单边提取"与"不平衡提取"**
- 单边提取（正常设计）：提取仅一种资产，但通过自动 swap 保持池子 K 值不变
- 不平衡提取（漏洞）：同时提取两种资产但数量比例与池子失配，破坏 K 值

区分方法：检查 `K = reserve0 * reserve1` 在提取前后是否守恒

### 3. 实战复核清单

**代码审查三问**：

1. **"用户真的能指定两个金额吗？"**
   - 确认函数签名中两个金额参数是否都可被用户控制
   - 检查是否存在内部重写逻辑（如 amount0 由调用者参数指定，但 amount1 由公式计算）

2. **"LP token 销毁与资产转出有强制关系吗？"**
   ```solidity
   // 伪代码检查模式
   uint lpTokensToburn = /* 来自参数 */;
   uint asset0ToTransfer = lpTokensToBurn * reserve0 / totalSupply;
   uint asset1ToTransfer = lpTokensToBurn * reserve1 / totalSupply;
   // 若 asset0ToTransfer 与 asset1ToTransfer 都不依赖用户参数 → 安全
   ```

3. **"发生过测试套件失败的报告吗？"**
   - 检查 PR 历史、issue tracker 中是否有人报告过提取不平衡的问题
   - 真实漏洞往往有历史线索（已披露的 CVE、修复 commit）

### 4. 链上数据分析辅助

**识别漏洞的统计方法**：
- 分析历史提取交易日志，计算实际转出金额与理论值偏离
- 若发现大量提取满足 `amount0 * price1 ≈ amount1 * price0`（即平衡提取），则倾向于认为设计正常
- 若发现提取总是极度不平衡（如 99% 单边），则可能是：
  - (a) 设计允许单边但内部平衡（非漏洞）
  - (b) 真实漏洞但未被大规模利用

### 5. 与相似漏洞的对比

**与"流动性闪电贷漏洞"区别**：
- 本漏洞：无法提取超过实际持有的资产，只能重新分配
- 闪电贷漏洞：可借入大额资产后立即返还，中间可操纵价格

**与"前置运行（MEV）"区别**：
- 本漏洞：影响 LP 提供者本身
- MEV 漏洞：影响交易员，与提取机制无关

### 6. 报告标准

**确认为 Critical 的必要条件**：
- 用户可指定不平衡金额 ✓
- 无滑点保护或保护可绕过 ✓
- 实测证明可损害 >5% TVL ✓
- 无白名单或多签防护 ✓

**降低为 Medium 的合理情况**：
- 存在 >2% 滑点保护 ✓
- 池子规模 >$50M 且偏差 <0.1% ✓
- 有历史交易证明设计合理 ✓
