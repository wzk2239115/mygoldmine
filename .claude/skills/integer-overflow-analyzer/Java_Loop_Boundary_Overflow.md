# Java_Loop_Boundary_Overflow

**漏洞类型**: 循环边界条件计算不当，for/while 循环中使用可能导致溢出的表达式

**Java**

---

## Details

**代码示例**：`for (int i = 0; i <= size; i++)`、`while (counter < limit) { counter++; }`、`for (int i = start; i < start + userInput; i++)`

- **核心操作定位技巧** (L1: 关键词扫描)：扫描循环结构 `for/while`，重点检查：
  - 循环条件运算符：`<=`、`>=` 优先于 `<`、`>`（易越界）
  - 循环边界是否来自用户输入、网络、数据库等不受信源
  - 循环增量表达式：`i += userValue`、`i = i + offset` 等涉及运算的边界
  - 起始值 + 循环次数的组合：`i < start + count`（加法溢出）、`i < multiply * factor`（乘法溢出）
  - 集合大小参与运算：`i < list.size() + 1` 或 `i < len * 2`

- **保护机制定位技巧** (L2: 跳读)：
  - 循环前的范围检查：`if (limit > Integer.MAX_VALUE - offset)` 或 `if (limit < 0)`
  - 安全加法检查：`Math.addExact()`、自定义溢出检测方法
  - 类型提升防护：从 `long` 类型读取再转 `int` 时的验证
  - 增强 for 循环的使用（隐式迭代器、无手动边界控制）
  - 明确的固定次数循环限制（例如常量数组长度）

## Classify

**研判维度**：

1. **边界值来源链**：追踪循环条件变量从声明到使用的全链路
   - 编译期常量 → 低风险
   - 局部变量但有前置验证 → 需评估验证强度
   - 方法参数、返回值、外部输入 → 需溯源到入口点

2. **表达式复杂度分析**：
   - 单一边界值（`i < MAX`）→ 易判断
   - 计算型边界（`i < a + b`、`i < a * b`）→ 需深入分析溢出可能
   - 条件边界（`while (i < limit && !done)`）→ 检查所有路径

3. **漏洞确认清单**：
   - ✓ 边界是否可由攻击者控制？
   - ✓ 有无前置边界验证或超值检测？
   - ✓ 边界表达式计算是否存在数学溢出？
   - ✓ 溢出后循环是否会导致内存越界、无限循环或异常？
   - ✓ 是否使用了不安全的类型转换（long→int）？

**判断规则**：
- **确定漏洞**：边界来自外部输入 + 无验证 + 存在溢出风险 = 可导致缓冲区溢出或无限循环
- **误报**：边界为常量 OR 有完整范围验证 OR 使用增强循环 OR 使用 AtomicInteger 等线程安全且范围受限的类
- **代码异味**：循环边界计算复杂、中间变量众多但缺少注释、跨多个方法传递

## True Positive Examples

1. **用户输入直接参与循环边界**（高风险）：
   ```
   int userCount = Integer.parseInt(request.getParameter("count"));
   for (int i = 0; i <= userCount; i++) { /* 处理数据 */ }
   ```
   → `<=` 使用 + 无验证 + 用户可传 Integer.MAX_VALUE

2. **隐蔽的加法溢出**（中风险）：
   ```
   for (int i = start; i < start + length; i++) { ... }
   ```
   → 若 start=Integer.MAX_VALUE-5、length=100，则 start+length 溢出至负数，循环不执行或产生异常

3. **乘法导致的循环次数爆炸**（中风险）：
   ```
   int iterations = rows * cols; // rows=10000, cols=10000
   for (int i = 0; i < iterations; i++) { ... }
   ```
   → iterations 溢出至负数或小值，导致内存分配不足或安全检查被绕过

## False Positive Examples

1. **增强循环自动处理边界**（低风险）：
   ```
   for (Item item : items) { /* 处理 */ }
   ```
   → 迭代器内部管理边界，无用户控制

2. **明确验证后的边界使用**（低风险）：
   ```
   if (userCount <= 0 || userCount > 10000) throw new Exception();
   for (int i = 0; i < userCount; i++) { ... }
   ```
   → 前置验证充分，边界范围确定

3. **集合长度作为循环边界**（低风险）：
   ```
   byte[] buffer = new byte[1024];
   for (int i = 0; i < buffer.length; i++) { ... }
   ```
   → 集合长度已由JVM保证，无溢出风险

4. **常量或编译期计算的边界**（低风险）：
   ```
   final int LIMIT = 1000;
   for (int i = 0; i < LIMIT; i++) { ... }
   ```
   → 常量值固定，无计算风险

## Advanced Audit Techniques

- **类型追踪**：当循环条件涉及 `long` 到 `int` 的隐式转换时，追踪 long 值的上界
- **符号执行思路**：手动模拟边界表达式在极端输入下的计算结果（MAX_VALUE ± 1、MIN_VALUE 等）
- **污点传播**：追踪参数从入口（HTTP、文件、数据库）到循环条件的完整路径，识别中途是否存在净化步骤

## Low risk patterns

- 循环次数为编译期常量
- 使用增强 for 循环或迭代器遍历集合
- 循环条件使用 `<` 而非 `<=`，且边界已验证
- 明确的循环限制（`for (int i = 0; i < 1000; i++)`）
- 大循环遍历集合时，集合长度可信且通过 `.length` 或 `.size()` 获取
- 循环边界通过 `Math.min()`、`Math.max()` 等安全方法限定
- 使用 `AtomicInteger` 或其他原子类型管理循环计数器（隐含边界保护）

## Common Confusion Points

### 1. 真正的漏洞 vs 虚假报警

**常见误判场景**：
- 审计工具报告 `for (int i = 0; i <= arr.length - 1; i++)` 为越界风险
  → 实际上 `arr.length - 1` 已经通过减法得到安全的上界，`<=` 在此并无风险
- 关注点应该是：减法是否可能产生负数、是否经过验证

### 2. 多层验证的识别

**误报常见原因**：
```java
if (userInput > 0 && userInput < 100) {
    for (int i = 0; i < userInput; i++) { ... }
}
```
→ 有范围验证，即使 userInput 来自外部也是安全的

**真实风险**：
```java
if (userInput > 0) {  // 仅验证 > 0
    for (int i = 0; i < userInput; i++) { ... }
}
```
→ 缺少上界验证，userInput 可能是 Integer.MAX_VALUE

### 3. 隐式溢出的识别

**隐藏较深的风险**：
```java
// 案例：两个小数字相乘产生大溢出
int pageSize = 100;      // 来自常量或配置
int pageNum = userInput;  // 来自用户输入
for (int i = 0; i < pageNum * pageSize; i++) { ... }
```
→ 虽然 pageSize 看似受控，但 pageNum 可传 Integer.MAX_VALUE

### 4. 类型混合的陷阱

**long 到 int 的隐式降级**：
```java
long totalSize = readFromDB();  // 可能是 Long.MAX_VALUE
for (int i = 0; i < totalSize; i++) { ... }  // 隐式转 int
```
→ totalSize 自动转 int 可能产生负数，导致循环不执行或异常

**识别技巧**：观察循环计数器与边界的类型差异，追踪类型转换点

## Audit Checklist for Loop Boundaries

| 检查项 | 低风险 | 高风险 |
|------|-------|-------|
| 边界来源 | 常量、集合长度 | 用户输入、外部数据 |
| 验证覆盖 | 范围检查完整 | 缺少验证或仅单向检查 |
| 运算符 | `<` 、`>` | `<=`、`>=` 配合复杂边界 |
| 表达式 | 单一变量 | 加法、乘法、组合运算 |
| 类型一致性 | int-int、long-long | int-long 混用、隐式转换 |
| 溢出风险 | 数学上不可能溢出 | 边界接近 MIN/MAX_VALUE |

## Pattern Recognition in Real Code

**待审计代码的快速判断流程**：
1. 扫描循环语句行，识别是否为 `for/while` 结构
2. 确定循环边界的直接来源（变量名、表达式）
3. 向上溯源变量赋值：是否来自用户、网络、文件
4. 检查赋值前是否存在验证或转换：`Math.abs()`、`Math.min()`、类型转换等
5. 计算表达式复杂度：若涉及加减乘除，手动模拟极端值场景
6. 判断溢出后是否有防护：catch 异常、循环条件二次检查等

## Severity Assessment Rules

- **Critical**：边界无验证 + 来自 HTTP 参数 + 直接用于数组下标或内存分配
- **High**：边界部分验证 + 涉及运算溢出风险 + 循环次数较大
- **Medium**：边界有验证但不完整 + 边界计算复杂但最终受限
- **Low**：边界为常量或已验证 + 循环次数明确有限 + 无额外运算
- **Info**：代码异味，使用了不推荐的模式但无直接风险

