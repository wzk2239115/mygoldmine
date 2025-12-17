# Go_Array_Index_Out_Of_Bounds

**漏洞类型**: 数组索引越界，使用计算结果作为数组或切片索引时未检查边界

**Go**

---

专注于这一垂直漏洞类型研判任务，从漏洞成因触发，编写该md文件，包含一下三个小标题，【注意语言精炼，表达简洁，可以作为审计小抄，仅专注于审计，不包含攻击与修复】：

## Details

**代码示例**：`arr[index]`、`slice[base + offset]`、`data[i * width + j]`、切片操作 `s[start:end]`

- **核心操作定位技巧** (L1: 关键词扫描)：扫描数组/切片索引访问操作 `[index]`，特别关注索引来自计算结果（加法、乘法）或用户输入的情况。检查索引类型（int/uint）、以及是否有负数风险。Go 会在运行时检查边界，但仍需防止 panic。

- **保护机制定位技巧** (L2: 跳读)：查找边界检查（`if index < len(arr)`、`if index >= 0`），使用安全的索引方式（先检查再访问），或使用 defer/recover 捕获 panic。检查索引计算是否可能溢出。

## Classify

判断是否为漏洞的要点：
- **确定漏洞**：索引来自不受信任的源，无边界检查，导致 panic 拒绝服务（DoS）
- **误报**：有显式边界检查、索引为常量或已验证、有 panic 恢复机制
- **代码异味**：索引通过算术运算计算，需确认不会越界

## 审计专业技巧与经验

### 1. 真实漏洞特征识别

**典型高危场景**：
- 用户输入直接作为索引：`arr[userInput]`、`data[parseInt(queryParam)]`
- 多级索引计算无中间检查：`matrix[row*width + col]` 当 row/col 来自网络请求
- 循环遍历中的累积计算：`offset += userValue; arr[offset]` 多次累加
- 跨包调用传递的索引：函数间参数传递导致上游检查失效
- 文件读取偏移量计算：`file.ReadAt(buf, offset)` offset 由用户指定
- Protocol Buffer 或 JSON 反序列化的数组索引：`struct.Items[index]` 直接来自外部数据

**高频漏洞实例**：
```go
// 实例1：HTTP 请求参数直接索引
id := r.URL.Query().Get("id")
idx := strconv.Atoi(id)  // 无上界检查
result := cache[idx]     // 越界访问

// 实例2：计算索引溢出
for i := 0; i < len(data); i++ {
    pos := i * stride + offset  // stride 大可能溢出
    process(arr[pos])
}

// 实例3：切片操作缺少验证
start := userParams["start"]
end := userParams["end"]
return data[start:end]  // start/end 无验证
```

### 2. 误报常见模式

**安全代码被误判**：
- 索引来自 `len()`、`cap()` 返回值：`arr[rand.Intn(len(arr))]`
- 边界检查后的安全访问：即使检查写法简洁也是安全的
- 使用内置函数保证安全：`sort.SearchInts()` 返回的索引
- 类型系统保证范围：byte 类型索引天然不超过 255
- 预定义枚举索引：`const (IDX_A = iota; IDX_B; IDX_C)` 不会越界

**常见误判案例**：
```go
// 安全但可能被标记：编译期常量索引
const ROW, COL = 3, 4
matrix[ROW][COL] = 100  // 误报，编译期确定

// 安全但外观可疑：panic recovery
defer func() {
    if recover() != nil {
        log.Println("bounds panic recovered")
    }
}()
arr[maybeOutOfBounds]  // panic 被处理，实际安全

// 安全但索引复杂：但已验证
if idx < len(arr) && idx >= 0 {
    x := (idx * 2 + 1) % len(arr)  // 虽然复杂，但已上界检查
}
```

### 3. 审计决策树

```
遇到 arr[index] 或 slice[start:end]
  ├─ 索引是否来自外部输入？
  │  ├─ YES → 是否有边界检查？
  │  │        ├─ NO → [确定漏洞] 标记为 High
  │  │        ├─ YES → 检查逻辑是否完全？
  │  │                 ├─ 只检查上界 → [代码异味] Medium
  │  │                 ├─ 完全检查 (< len && >= 0) → [Low Risk]
  │  │                 └─ 符号不对 (< 而非 <=) → [误报] 但需注意
  │  └─ NO → 索引如何产生？
  │           ├─ 常量或枚举 → [Low Risk]
  │           ├─ 数学计算 → 是否可能溢出或无效？
  │           │           ├─ YES → [Medium] 审查计算逻辑
  │           │           └─ NO → [Low Risk]
  │           └─ 库函数返回 → [Low Risk] (通常安全)
  └─ 是否有 panic recovery？
     ├─ YES → 评估 DoS 影响 → [Low Risk]
     └─ NO → [中高风险] 未捕获可导致服务崩溃
```

### 4. 深度审计技巧

**污点追踪**：
- 标记外部数据入口：HTTP 参数、文件读取、网络接收
- 跟踪数据流：经过多少次转换、是否在某处验证、是否被污染
- 识别洗白点：除了显式检查，还有隐式保证的场景

**复杂计算分析**：
- 识别整数溢出风险：`a * b` 当 a,b 来自用户且都很大
- 负数处理：Go 中 uint 类型无负数，但 int 类型有风险
- 循环累加陷阱：多轮循环中索引持续增长

**跨函数审计**：
- 追踪参数来源：被调用函数的索引参数是否来自外层
- 检查函数契约：文档是否说明参数范围要求
- 识别防御层级：是否依赖调用者检查还是内部防御

### 5. 常见混淆排查

| 代码模式 | 初判 | 深度分析 | 最终结论 |
|---------|------|--------|--------|
| `arr[i++]` 在循环中 | 可疑 | 循环条件决定，通常 `i < len(arr)` | 安全 |
| `data[someFunc()]` | 可疑 | someFunc() 返回值范围未知 | 需人工审查 |
| `slice[a:b]` a/b 无检查 | 高风险 | Go 自动边界检查不会越界但可能 panic | 影响可用性 |
| `arr[int(uint32Val)]` | 可疑 | 类型转换本身不验证范围 | 需确认 uint32Val 大小 |

## Low risk

- 索引为常量或明确在数组范围内
- 有显式边界检查（`if index < len(arr) && index >= 0`）
- 使用 `%` 取模确保索引在范围内
- 有 defer/recover 机制捕获 panic
- 使用 `slice[start:end]` 时验证 start 和 end
- 索引来自编译期已知的值或 len()/cap() 函数
- 通过类型系统保证范围的索引（如 byte 类型）

