# Rust_Vec_Capacity_Overflow

**漏洞类型**: Vec 容量计算溢出，Vec::with_capacity() 或 Vec::reserve() 使用用户输入作为容量参数

**Rust**

---

## Details

**代码示例**：`Vec::with_capacity(size)`、`vec.reserve(additional)`、`Vec::from_raw_parts(ptr, len, cap)`

### 核心审计定位技巧（L1: 关键词扫描）

1. **快速定位目标操作**：
   - 扫描 `Vec::with_capacity()`、`vec.reserve()`、`vec.resize()` 等容量相关方法
   - 关注 `Vec::from_raw_parts()` 的 capacity 参数使用
   - 搜索 `Vec::new()` 后紧跟 reserve 调用的模式

2. **容量参数数据流追踪**：
   - 容量参数来源：用户输入、网络数据、文件读取、计算结果
   - 重点关注乘法运算计算容量（如 `width * height`、`row * col * sizeof(T)`）
   - 留意多步计算的中间溢出（如先加后乘）

3. **隐蔽性高危模式**：
   - 间接传参：`calculate_size()` → `with_capacity()`
   - 类型隐式转换：`u32` → `usize` 的转换点
   - 通过配置文件/环境变量间接获得的容量值

### 保护机制定位技巧（L2: 跳读验证）

1. **直接防护检查**：
   - 使用 `try_reserve()` 并正确处理 `Err` 分支（不能忽略错误）
   - 容量计算使用 `checked_mul()`、`checked_add()` 等 Checked 方法
   - 显式上限验证：`if cap > MAX_CAPACITY { return Err(...) }`

2. **间接防护评估**：
   - 流式处理/迭代器代替大数组分配
   - 分块加载数据，而非一次性分配
   - 使用 `std::mem::size_of::<T>()` 验证元素大小影响

3. **上下文保护**：
   - 容量来自已验证的配置文件
   - 经过白名单限制的枚举值
   - 来自受信任的内部库而非外部输入

## Classify

### 漏洞确定条件

**High Risk - 确定漏洞**：
- 容量直接来自用户输入，无任何验证
- 乘法计算容量，未使用 `checked_mul()`（如 `vec.with_capacity(height * width)`）
- 使用 `panic!()` 处理分配失败，无 try_reserve()
- 存在明显的 usize 溢出风险（如 u32 转 usize 后直接用）

### 误报区分经验

**实际误报案例 1 - 安全的乘法**：
```rust
// 误报：看起来有乘法，实际安全
let max_rows = 1000usize;
let max_cols = 1000usize;
let cap = max_rows * max_cols; // 最大 1_000_000，可控范围
vec.reserve(cap);
```
**区分点**：两个操作数都是常量或已限制的最大值，乘积在内存范围内

**实际误报案例 2 - try_reserve 正确处理**：
```rust
// 误报：已正确使用 try_reserve
let user_size: usize = parse_input()?;
vec.try_reserve(user_size).map_err(|_| Error::CapacityError)?;
```
**区分点**：Err 分支被正确处理，不会 panic 或默默忽略

**实际漏洞案例 1 - 二维数据的经典溢出**：
```rust
// 真实漏洞：二维矩阵未验证
let width: usize = input.width;  // 用户输入
let height: usize = input.height; // 用户输入
let vec = Vec::with_capacity(width * height); // 无检查！可 usize 溢出
```

**实际漏洞案例 2 - 间接计算的溢出**：
```rust
// 真实漏洞：通过计算得到的容量
let elem_size = 1024usize;
let count: usize = user_provided_count;
let buffer = Vec::with_capacity(count * elem_size); // 溢出可能！
```

### 审计关键判断

1. **数据流清晰性**：
   - 如果无法追踪容量来源→倾向误报（内部常量）
   - 如果来源于函数参数→倾向真漏洞（可能来自用户）

2. **防护深度**：
   - 单层检查（如只有 if 判断）可能不够→需要 checked_* 方法
   - try_reserve() 返回 Result 但被 `.unwrap()` 忽略→仍是漏洞

3. **场景合理性**：
   - 网络协议解析的容量字段→极高风险
   - 文件格式头部定义的大小→极高风险
   - 内部数据结构预定义的大小→低风险

## Low risk

- 使用 `try_reserve()` 或 `try_with_capacity()` 并正确处理 Result
- 容量有明确上限（如 `vec.reserve(user_size.min(MAX_SIZE))`）
- 容量计算使用 `checked_mul()` 等安全整数运算
- 使用流式处理、迭代器或生产者-消费者模式代替大 Vec
- 容量来自已验证的配置文件或编译时常量
- 元素类型大小经过验证（如 `assert!(size_of::<T>() <= MAX_ELEM_SIZE)`）

## 审计实战经验

### 常见混淆点

1. **usize 溢出 vs 内存耗尽**：
   - usize 溢出导致容量值异常（可能变为0或小值）→可能触发 panic 或静默失败
   - 合法但极大的容量值→导致 OOM，系统 kill 进程，属于 DoS 漏洞

2. **panic 是否属于漏洞**：
   - 使用 `with_capacity()` 分配失败直接 panic→属于漏洞（Denial of Service）
   - 但如果是服务启动时的静态配置 panic→通常不算安全漏洞

3. **多态性陷阱**：
   - 泛型函数 `fn make_vec<T>(cap: usize) -> Vec<T>` 看起来安全
   - 但调用处可能传入危险的 cap 值，需追踪调用链

### 审计优先级排序

**P0 - 立即标记**：
- 网络包解析中的 capacity 字段未验证（如 `Vec::with_capacity(packet.size as usize)`）
- 文件头部定义的数组大小直接用作容量
- 用户 HTTP 请求参数直接或简单转换后用作容量

**P1 - 重点审视**：
- 计算得到的容量，计算过程中存在乘法操作
- 来自反序列化数据的容量值
- 使用 `alloc()` 或底层内存 API 配合 capacity 参数

**P2 - 正常审视**：
- 内部模块间的容量传递，已有边界检查
- 容量来自配置，但配置本身需信任评估

### 类型转换陷阱

```
关键转换点：
- u8/u16/u32 → usize：在 32 位系统可能溢出
- i32/i64 → usize：有符号转无符号的风险
- 浮点数 → usize：可能产生 NaN 转换异常
```

**审计建议**：
- 追踪所有强制转换和隐式转换
- 即使转换本身无溢出，下游的乘法仍可能溢出
- 寻找 `as usize` 关键字，特别是在 for 循环或容量计算附近

