**Move - 错失内联（Missed Inlining）**  
简单函数未标记为 `inline`，增加不必要的函数调用开销，降低Gas效率。常见于资源操作辅助函数、getter/setter、简单数学运算等场景。

## Details

**代码示例：**
```move
// 未内联的简单getter - 每次调用产生额外栈帧
public fun get_balance(account: &Account): u64 {
    account.balance
}

// 未内联的简单断言包装
public fun assert_authorized(addr: address, cap: &AdminCap) {
    assert!(cap.owner == addr, ERROR_NOT_AUTHORIZED);
}

// 热路径中频繁调用的简单计算
public fun calculate_fee(amount: u64): u64 {
    amount * FEE_RATE / 10000
}
```

**快速定位核心操作（L2-跳读）：**
- 扫描函数体 ≤ 5行且无控制流分支的public函数
- 关注高频调用场景：热路径交易逻辑、循环内调用、资源借用后的连续访问
- 检查函数调用链：`swap() -> get_reserve() -> borrow_global()` 中间层是否可内联
- 使用 `move disassemble` 查看字节码，识别 `Call` 指令密集区域

**快速定位保护机制（L1-关键词扫描）：**
- 搜索 `inline` 关键字，统计覆盖率（内联函数数/简单函数总数）
- 检查编译优化配置：`Move.toml` 中 `[profile]` 是否启用优化级别
- 审查是否存在内联限制注释：`// Cannot inline due to recursion`
- 验证测试用例中是否有Gas benchmark对比

## Classify

**漏洞：**  
- 在DeFi交易核心路径（swap、liquidate、flashloan）中，未内联的简单计算/检查函数被循环调用，导致Gas显著超过竞品
- 存在明确的Gas优化承诺（文档声明"低Gas设计"），但实际内联率<30%

**代码异味：**  
- 通用工具函数未内联，但调用频次低（<5次/交易）
- 函数体简单（1-3行）但加了 `public(friend)` 可见性，考虑模块间复用而未内联
- 开发阶段代码，TODO注释标记"待优化内联"

**误报：**  
- 函数包含复杂控制流（match、loop、多层if）不适合内联
- 递归函数或间接递归调用链
- 函数体包含 `borrow_global_mut` 等全局状态操作（编译器可能拒绝内联）
- 跨模块调用且目标模块不可见（无法跨边界内联）

## Low risk

- **非热路径函数**：仅在初始化、管理操作中调用，用户交易不涉及
- **Gas开销已明确披露**：文档或注释中说明"优先可读性，后续版本优化"
- **调用深度浅**：整个交易调用栈 ≤ 3层，函数调用开销占比 < 5%
- **存在功能权衡**：保持非内联以便调试/事件追踪，且项目明确说明
- **硬件补偿充分**：链上Gas价格极低（如测试网）或区块Gas限制宽松，优化收益不足100Gas

## 审计专业技巧

### 1. 真实漏洞识别经验

**特征组合判定法**（优先级递减）：
- **关键信号**：同一交易调用栈内，简单函数被递归调用或在循环中连续调用（如`for i in 0..n { fee += calculate_fee(amounts[i]) }`），且函数体 ≤ 3行
- **Gas差异验证**：通过 `move test` 生成Gas report，对比内联vs非内联版本的Gas消耗，差异 > 200Gas/交易则为真实问题
- **竞品对标**：与同类DeFi协议（如Uniswap Move版本、Delphi等）对比类似操作Gas成本，超高10%以上为红旗
- **代码评审路径**：检查提交历史，若PR中明确宣传"Gas优化"但关键函数未标记 `inline`，属于承诺不符

**实战案例**：
```move
// 真实漏洞案例：Curve-like协议的 get_dy() 在价格点击中频繁调用
public fun get_dy(i: u64, j: u64, dx: u64): u64 {
    let rates = borrow_global<Rates>(CURVE_ADDR);
    (dx * rates[i] / rates[j])  // 3行逻辑，每个交易点击调用
}
// 漏洞影响：1000笔点击交易 × 150Gas额外调用开销 = 150000Gas浪费
// 修复：添加 public inline fun
```

### 2. 误报排除清单

**编译器限制识别**（调用 `move build -v` 观察警告）：
- 函数使用 `borrow_global_mut<T>` 时，编译器主动拒绝内联以保证借用检查安全性
- 函数包含资源销毁操作（`move x` 后立即drop）的参数，Move编译器出于资源生命周期跟踪会禁用内联
- 跨模块访问private字段的函数（如模块B调用模块A的getter），声明边界阻止跨模块内联

**调用链分析法**：
```move
// 误报例：assert_unique_signer() 虽然简单，但在多签验证中调用多次
// 但其内部调用了 Event::emit()，编译器认为有边界效应而拒绝内联
public fun assert_unique_signer(signers: &vector<address>, target: address) {
    assert!(vector::contains(signers, &target), ERR_NOT_SIGNER);
    Event::emit(SignerValidated { addr: target }); // 事件发出 - 内联障碍
}
```

### 3. Gas成本精细化估算

**Per-call开销分解**：
- Move虚拟机函数调用固定开销：**80-120 Gas**（取决于参数数量和返回值）
- 栈帧分配：**30-50 Gas**
- 局部变量初始化：**10-20 Gas/变量**
- **判定阈值**：若函数体本身 < 150Gas，内联收益至少15-20%

**批量计算工具**：
```
审计检查清单：
□ 列出所有 <5行的public函数
□ 统计这些函数每个交易的总调用次数
□ 按公式估算：potential_saving = call_count × per_call_cost × avg_gas_price
□ 若日均potential_saving > 100 USDC，升级为High issue
```

### 4. 实战区分决策树

```
问题：发现未内联的简单函数
├─ 是否在文档/代码注释中明确说明"非优化代码"？
│  ├─ YES → Low Risk（已充分披露）
│  └─ NO → 继续
├─ 函数调用频次是否 < 3次/交易？
│  ├─ YES → Low Risk（收益 < 300Gas）
│  └─ NO → 继续
├─ 是否包含 borrow_global_mut 或资源drop操作？
│  ├─ YES → 误报（编译器限制）
│  └─ NO → 继续
├─ 是否在循环/递归调用栈中被调用？
│  ├─ YES → True Positive（升级为Medium/High）
│  └─ NO → Low Risk
```

### 5. 常见陷阱与规避方案

| 陷阱 | 规避方案 |
|------|--------|
| 误认为所有简单函数都应内联 | 检查函数是否暴露public接口供外部依赖，内联会改变符号可见性 |
| 忽视模块设计的封装性 | 评估内联带来的单元测试复杂度增加是否值得 |
| 假设编译器自动优化 | 在 `Move.toml` 检查优化level是否为 `release`（默认可能是debug） |
| 仅看Gas忽视可维护性 | 若函数作为公共API被多个模块调用，保持非内联便于版本升级 |

### 6. 审计报告建议措辞

**High issue写法**：
> 函数 `get_reserve()` 在swap核心路径中每次被调用，函数体仅2行。根据Gas report，去除该函数调用的开销可减少约180Gas/交易。建议添加 `inline` 关键字。

**Low risk写法**：
> 函数 `validate_timestamp()` 虽未内联但调用深度浅（仅在初始化调用），每交易开销<100Gas，相对可接受。
