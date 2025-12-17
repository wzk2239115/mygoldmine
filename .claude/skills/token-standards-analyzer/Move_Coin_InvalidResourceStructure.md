# Move Coin Invalid Resource Structure

## Details

**核心问题定位**：Move Coin 标准定义了特定的资源结构（Resource Struct）。常见缺陷包括：
- Coin 资源字段定义不符（缺少 `value: u128` 字段）
- 资源能力注解错误（应为 `key + store`，缺少或错误）
- 模块路径不符合规范（Coin 类型应在标准库中）
- 资源嵌套结构错误（如子资源不符合标准定义）

**代码示例位置定位**（L1：关键词扫描）：
- 搜索 `struct Coin<CoinType>` 的资源定义
- 检查资源能力标注：`has key, has store` 的完整性
- 验证字段定义：`value: u128` 是否存在且正确
- 确认泛型参数：是否正确使用了 `<CoinType>` 泛型

**保护机制识别**（L2：跳读）：
- 验证资源访问控制：是否限制了 Coin 的创建和销毁
- 检查字段修改逻辑：value 是否只能通过标准函数修改
- 确认是否存在对资源一致性的验证（如余额溢出检查）
- 审查资源转移逻辑：是否符合 Move 的 resource 安全模型
- 检查是否实现了对 CoinType 的约束（如必须是 key 资源）

## Classify

**理论研判标准**：

1. **确认为资源结构不符合**：
   - 结构体定义缺少必要字段（无 value 字段）
   - 资源能力完全错误（无 key 或 store 标注）
   - 结构名称不符（如 `Token` 代替 `Coin`）
   - 泛型约束完全不符（无泛型参数或约束错误）

2. **分别为代码异味**：
   - 结构体定义正确但额外字段过多（如添加了 name、decimal 字段）
   - 资源能力符合但缺少额外约束（如缺少 drop 禁用）
   - 字段类型接近但精度不符（如 u64 代替 u128）
   - 模块路径非标准但实现了等价功能

3. **排除误报**：
   - 项目实现了扩展的 Coin 结构，同时保留了标准兼容的 base 类型
   - 使用了代理资源实现了访问控制，但核心结构符合标准
   - 不同生态（Aptos vs Sui）有细微差异但都保留兼容

## Low risk

**低风险评级场景**：

- 资源结构正确但额外字段用于优化，不影响标准兼容性
- 能力标注正确但缺少非关键的额外能力
- 字段精度宽于标准（u256 vs u128），完全兼容
- 项目明确声明资源扩展，同时保证了标准库的互操作性

## 审计专业技巧

### 1. 资源结构合规的递进式验证

**第一层 - 结构签名检查**：
```
public struct Coin<phantom CoinType> has key, store {
    value: u128,
}
```
审计要点：
- `phantom` 关键字确认泛型为不占用内存（标准做法）
- `has key, store` 是否完整且顺序无关，但不能缺失任何一个
- `value` 字段必须是 `u128` 或更大的整数类型
- 不允许有其他数据字段（除了上述三项外）

**第二层 - 函数合约检查**：
- `deposit()` / `withdraw()` 函数是否通过 `value` 字段修改余额
- `transfer()` 实现是否遵循 Move 的资源线性性（资源不能复制/丢弃）
- `mint()` / `burn()` 的权限控制是否存在（是否仅限官方模块）

### 2. 真实漏洞案例分析

**案例一：隐藏字段导致的双重计账（高风险）**

真实漏洞代码：
```
struct Coin<phantom CoinType> has key, store {
    value: u128,
    cached_value: u64,  // ← 隐藏的余额字段！
}

public fun withdraw(coin: &mut Coin, amount: u64) {
    coin.value -= (amount as u128);
    // 但 cached_value 没有同步更新！
}
```
- **风险点**：两个余额字段不同步导致余额验证绕过
- **审计技巧**：搜索所有包含 "value" 关键字的字段，检查是否有多个数值字段
- **验证方法**：追踪 deposit/withdraw 中所有修改数值的操作，确保只操作一个字段

**案例二：能力标注缺失导致的资源复制（关键）**

误导的代码：
```
struct Coin<phantom CoinType> has store {  // ← 缺少 key！
    value: u128,
}

public fun copy_coin(coin: &Coin): Coin {
    Coin { value: coin.value }  // 可以编译！
}
```
- **风险点**：缺少 `key` 能力时，资源可能被意外复制
- **审计技巧**：直接查看是否存在显式的 `copy()` 或隐式复制操作
- **区分方法**：检查模块是否定义了 `Copy` 特征实现

### 3. 常见误报场景与区分

**误报场景 A：生态扩展型结构**

表面"异常"：
```
// Aptos 标准库
struct AptosCoin<phantom CoinType> has key, store {
    value: u128,
    metadata_id: ID,  // ← 看起来多出了一个字段
}
```

**是否为漏洞**：
- ✓ 检查 metadata_id 是否在标准扩展说明中
- ✓ 验证这个字段是否参与 value 修改逻辑
- ✗ 如果该字段是只读的元数据，则为合法设计

**判断依据**：
- 审查官方文档中 Coin 的标准定义版本
- 确认项目是否在 README 中声明了兼容版本号
- 跟踪该字段的所有读写操作（grep `metadata_id`）

**误报场景 B：代理模式下的多资源**

表面"异常"：
```
struct CoinHolder<phantom CoinType> has key {
    coins: vector<Coin<CoinType>>,
}

struct Coin<phantom CoinType> has store {  // ← 只有 store，没有 key
    value: u128,
}
```

**是否为漏洞**：
- ✓ 验证 Coin 结构是否被嵌套在具有 key 的资源中
- ✓ 检查 Coin 是否通过代理方式得到保护
- ✗ 如果整个系统设计围绕这种代理模式，则为合法

**判断依据**：
- 追踪 Coin 的创建位置，是否全部由 CoinHolder 管理
- 验证是否存在直接操作独立 Coin 的函数（应该没有）
- 检查公开接口是否都基于 CoinHolder 而非直接 Coin

### 4. 精准审计的"金三角"方法

**顶点 1 - 结构定义审查**（15% 工作量）：
- 快速扫描 struct 定义行（通常 5-10 行）
- 检查清单：能力标注 + 字段数量 + 泛型参数
- 结果：结构定义是否符合标准模板

**顶点 2 - 函数调用链追踪**（60% 工作量）：
- 从 public 函数入口（如 transfer）开始
- 追踪每个修改 value 的操作语句
- 验证：是否存在绕过、重复计算或遗漏的修改
- 检查：权限控制（谁能调用 mint/burn）

**顶点 3 - 资源生命周期验证**（25% 工作量）：
- Coin 的诞生：只能通过 mint（需权限）创建
- Coin 的转移：必须遵循 Move 的 resource move 语义
- Coin 的销毁：只能通过 burn（需权限）销毁
- 验证：整个生命周期中 value 是否始终守恒

### 5. 审计检查清单

| 检查项 | 快速验证 | 深度审计 |
|--------|---------|---------|
| **能力标注** | grep "has key, has store" | 验证 key 和 store 顺序组合、是否有额外能力 |
| **字段定义** | 字段数 ≤ 1，字段名 = value | value 类型是否 >= u128，是否存在隐藏字段 |
| **泛型约束** | 是否有 phantom 关键字 | CoinType 是否有额外约束（如 drop 禁用） |
| **访问控制** | mint/burn 是否有权限检查 | 权限机制是否通过能力或模块私有性实现 |
| **余额操作** | deposit/withdraw 是否修改 value | 所有修改是否原子且有验证（溢出检查）|
| **转移语义** | transfer 是否遵循资源线性性 | 是否实现了"消费"一个资源并产生新资源 |

### 6. 误报陷阱速记

1. **精度陷阱**：u64 != u128，但 u256 == u128 兼容，用 u128 as u256 转换无损
2. **能力陷阱**：只有 store 的结构可以被嵌入，但不能独立存储（需要 key）
3. **泛型陷阱**：phantom vs 非 phantom 都可以，区别是内存占用，不影响安全性
4. **模块陷阱**：标准库版本升级会改变 Coin 定义，需要对比对应版本文档
5. **兼容陷阱**：多个生态（Aptos/Sui/MoveBit）Coin 定义细微差异，需确认目标生态
