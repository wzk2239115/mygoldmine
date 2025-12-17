# Rust_Loop_Boundary_Issue

**漏洞类型**: 循环边界条件问题，for 循环中使用可能导致溢出的表达式

**Rust**

---

专注于这一垂直漏洞类型研判任务，从漏洞成因触发，编写该md文件，包含一下三个小标题，【注意语言精炼，表达简洁，可以作为审计小抄，仅专注于审计，不包含攻击与修复】：

## Details

**代码示例**：`for i in 0..count`、`for i in start..start+length`、`while counter < limit`、`(0..size).for_each()`

- **核心操作定位技巧** (L1: 关键词扫描)：扫描范围表达式（`start..end`、`start..=end`）和循环边界条件。关注边界表达式中的算术运算（`start + length`）。检查范围端点来自用户输入或计算结果的情况。

- **保护机制定位技巧** (L2: 跳读)：查找边界上限验证、使用 `min(count, MAX_ITERATIONS)` 限制范围、或使用迭代器的 `take()` 方法限制迭代次数。检查边界计算是否使用 `checked_add()` 防止溢出。

## Classify

判断是否为漏洞的要点：
- **确定漏洞**：循环边界来自不受信任的源，边界计算可能溢出，导致超长循环（DoS）或 panic
- **误报**：边界有明确限制、使用 `take()` 限制迭代、边界计算使用安全方法
- **代码异味**：边界表达式包含算术运算，需确认不会溢出

## Low risk

- 范围端点为常量或有明确上限
- 使用 `checked_add()` 计算范围端点
- 使用 `iter().take(n)` 限制迭代次数
- 边界值经过范围验证
- 循环体轻量级（无资源消耗）

## 审计专业技巧

### 真实漏洞特征识别

**漏洞触发条件三角形**：
1. **输入来源**：边界值来自网络、文件、用户输入等不受信任源
2. **计算风险**：范围端点通过加法、乘法等无保护算术运算得出
3. **风险后果**：导致超长循环（DoS）、内存消耗、panic 或业务逻辑绕过

**真实漏洞案例特征**：
- `for i in 0..user_input.len() + buffer_size`（无溢出检查，两个可控数据相加）
- `let end = start + calculated_length;` 后直接用于 `start..end`（未验证端点大小关系）
- `while idx < limit && idx < data.len()` 但 `limit` 来自用户计算（看似安全但短路评估有漏洞）
- `(0..iterations).for_each(|i| { expensive_op(i) })`，其中 `iterations` 无上限验证

### 常见误报排查清单

**情形1：使用安全方法**
- ✓ `checked_add()`、`saturating_add()`、`wrapping_add()` 后用于循环上限
- ✓ `min(user_value, MAX_SAFE_LIMIT)` 明确限制范围
- ✓ `.take(MAX_ITERATIONS)` 链式限制迭代次数
- ✗ `unwrap_or()` 返回很大的默认值（伪安全）

**情形2：隐式长度限制**
- ✓ `for item in &vec` 或 `vec.iter()`（受 vec 实际长度限制）
- ✓ `for i in 0..self.size`（self.size 在初始化时已验证）
- ✗ `for i in 0..self.size` 但 `self.size` 可被内部方法修改为用户输入（隐性漏洞）

**情形3：双层边界验证**
- ✓ `if len <= MAX_SIZE { for i in 0..len { } }`（条件保护）
- ✓ `for i in 0..std::cmp::min(len, MAX_SIZE)`（函数保护）
- ✗ `for i in 0..(len.min(MAX_SIZE))` 但 `len` 在循环中被修改（竞态条件）

### 深度审计技巧

**按优先级分层审计**：
1. **P0 - 直接风险**：`start + user_input`、`user_input * factor`、`user_input as usize`
2. **P1 - 间接风险**：计算后的值虽然经过一次检查，但来源链路不清（追踪定义）
3. **P2 - 上下文风险**：循环体包含 `allocate()`、`read()` 等昂贵操作（即使范围小也有风险）

**信息流追踪建议**：
- 反向追踪边界表达式的所有输入：`for i in 0..a+b`，检查 `a` 和 `b` 的定义
- 检查中间计算变量是否经过验证：`let boundary = parse(input); for i in 0..boundary`
- 验证函数参数约束：`fn process(count: usize)` 调用者是否有隐式假设

**循环体风险加权**：
- **轻量级**：简单赋值、比较（风险低即使迭代多）
- **中等**：数组访问、简单计算（风险中等，需要循环次数合理）
- **重量级**：内存分配、I/O 操作、递归调用（即使迭代 1000 次也可能是漏洞）

### 实战判断示例

**案例A**：`for i in 0..(start + len)`
- 输入源：`start` 和 `len` 来自用户
- 判断：**风险** ❌ 未检查溢出或合理上限
- 建议确认：是否存在 `len = std::cmp::min(len, MAX_SAFE_SIZE)` 或 checked 操作

**案例B**：`for i in 0..self.buffer.len()`
- 输入源：来自内部容器
- 判断：**安全** ✓ 受实际容器长度限制
- 建议确认：`self.buffer` 是否可被外部改变（setter 方法验证）

**案例C**：`let iterations = user_count.saturating_add(10); for i in 0..iterations`
- 输入源：`user_count` 来自用户
- 判断：**有条件安全** ⚠️ 使用了 saturating 保护溢出，但无上限检查
- 建议确认：是否需要 `.min(MAX_ITERATIONS)` 防止 DoS

