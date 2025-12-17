# Go_Loop_Boundary_Issue

**漏洞类型**: 循环边界条件问题，for 循环中使用可能导致溢出的表达式或条件

**Go**

---

专注于这一垂直漏洞类型研判任务，从漏洞成因触发，编写该md文件，包含一下三个小标题，【注意语言精炼，表达简洁，可以作为审计小抄，仅专注于审计，不包含攻击与修复】：

## Details

**代码示例**：`for i := 0; i < count; i++`、`for i := start; i < start + length; i++`、`for range make([]int, size)`

- **核心操作定位技巧** (L1: 关键词扫描)：扫描 for 循环的边界条件，特别关注边界表达式中的算术运算（`start + length`）。检查循环变量类型（int/uint）、边界值来源（用户输入、计算结果）、以及循环体内的资源消耗。

- **保护机制定位技巧** (L2: 跳读)：查找边界上限验证、使用 `min(count, maxIterations)` 限制循环次数、或使用 context 超时机制。检查边界表达式是否可能溢出导致无限循环或跳过循环。

## Classify

判断是否为漏洞的要点：
- **确定漏洞**：循环边界来自不受信任的源，边界计算可能溢出，导致超长循环（DoS）或意外行为
- **误报**：边界有明确限制、来自已验证的配置、使用 context 超时控制
- **代码异味**：边界表达式包含算术运算，需确认是否会溢出

## Low risk

- 循环边界为常量或有明确上限
- 边界值经过范围验证
- 使用 context 或超时机制防止长时间运行
- 循环体轻量级（无资源消耗）
- 边界来自可信配置

## 审计专业技巧

### 真实漏洞特征识别

**运算溢出导致的循环异常**：当循环边界包含算术运算（如 `start + length`）时，特别关注：
- 边界值来自用户输入或网络请求
- 未进行溢出检查，例如 `end := start + length` 在 `start` 和 `length` 都很大时可能溢出至负数或很小的值
- 例：`for i := offset; i < offset + size; i++` 当 `offset + size` 溢出时，条件可能始终为假或变为无限循环

**资源消耗与DoS风险**：
- 循环体内分配内存、建立连接、读写文件等重操作
- 未设置超时，例如直接遍历用户提供的大小数组而无 context.WithTimeout
- 无迭代次数限制，当边界计算错误时会导致长时间运行

**类型转换隐患**：
- 边界涉及 `int` 和 `uint` 混合运算，例如 `for i := 0; i < len(data) + userOffset; i++`
- `userOffset` 为 `int` 且为负值时，加法可能溢出或产生意外结果
- 显式类型转换而未验证，例如 `int(userInput)` 可能超出边界范围

### 误报排除清单

**低风险情况**：
1. **硬编码常量边界**：`for i := 0; i < 100; i++` 或 `for i := 0; i < len(data); i++`，即使 data 来自输入，使用 len() 内置函数也是安全的
2. **明确的验证检查**：如 `if size > maxSize { return error }` 后再使用 `size`
3. **context 超时防护**：`select { case <-ctx.Done(): return }` 或 `time.After()` 限制单次操作时间
4. **容错机制**：`count := min(userCount, maxLimit)` 使用安全的限制函数

**常见误报陷阱**：
- 看到循环变量递增就误认为有问题，但若边界是常量或受信源，则无风险
- 看到 `for range` 就担心无限循环，但 Go 的 range 遍历字节数组时长度是固定的，不会溢出
- 未深入检查流程中的早期验证，导致误判为漏洞

### 审计决策流程

**第一步 - 边界来源识别**：
```
用户输入 → 高风险，需深入审查
网络请求参数 → 高风险，需深入审查
配置文件 → 中风险，确认配置源是否可信
常量/硬编码 → 低风险，一般无需审查
```

**第二步 - 运算复杂度分析**：
```
简单赋值 (i < count) → 低风险
单层算术 (i < start + offset) → 中风险，需检查溢出
嵌套运算或条件 → 高风险，需深入分析
```

**第三步 - 资源消耗评估**：
```
循环体为简单对比/赋值 → 低风险
循环体含 I/O 或内存分配 → 中风险，关注迭代次数
循环体含网络请求或文件操作 → 高风险，必须有超时和限制
```

**第四步 - 保护机制检查**：
```
有超时/context控制 → 降低一个风险级别
有迭代次数限制 → 降低一个风险级别
有范围验证 → 降低一个风险级别
无保护 → 风险级别不变
```

### 实战案例对比

**真实漏洞案例**：
```go
// 漏洞：用户输入的 size 直接用作循环边界
func processData(userSize int, data []byte) {
    for i := 0; i < userSize; i++ {
        if i < len(data) {
            process(data[i])
        }
    }
}
// 风险：userSize 可为任意大值，导致 DoS 或长时间计算
```

**误报案例**：
```go
// 安全：虽然使用了用户输入，但有明确限制
func processData(userSize int, data []byte) error {
    if userSize < 0 || userSize > maxAllowedSize {
        return errors.New("invalid size")
    }
    for i := 0; i < userSize; i++ {
        if i < len(data) {
            process(data[i])
        }
    }
}
// 分析：userSize 已被验证，风险消除
```

**边界溢出案例**：
```go
// 高风险：offset + length 可能溢出
func readRange(offset, length int, data []byte) {
    end := offset + length // 可能溢出至负数或小值
    for i := offset; i < end; i++ {
        if i < len(data) {
            process(data[i])
        }
    }
}
// 修复思路：验证 offset + length 不溢出，或使用 uint 类型
```

### 审计检查清单

- [ ] 循环边界来源是否为不受信源？
- [ ] 边界计算是否涉及算术运算且未验证溢出？
- [ ] 循环体内是否有资源消耗操作（I/O、内存、网络）？
- [ ] 是否有超时或迭代次数限制？
- [ ] 是否存在类型转换且未进行范围检查？
- [ ] 若使用 `range` 动态创建的切片，切片大小是否受控？
- [ ] 边界条件逻辑是否正确（`<`, `<=`, `<`, `>=` 的选择）？

