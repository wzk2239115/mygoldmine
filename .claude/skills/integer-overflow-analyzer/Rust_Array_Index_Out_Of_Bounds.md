# Rust_Array_Index_Out_Of_Bounds

**漏洞类型**: 数组索引越界，使用计算结果作为数组索引时未使用边界检查

**Rust**

---

专注于这一垂直漏洞类型研判任务，从漏洞成因触发，编写该md文件，包含一下三个小标题，【注意语言精炼，表达简洁，可以作为审计小抄，仅专注于审计，不包含攻击与修复】：

## Details

**代码示例**：`arr[index]`、`slice[base + offset]`、`vec[i * width + j]`、`get_unchecked(index)` 在 unsafe 块中

### 核心操作定位技巧 (L1: 关键词扫描)

扫描数组/切片索引访问 `[index]` 和 `get_unchecked()`。Rust 默认进行边界检查（会 panic），但需防止 DoS。重点关注索引来自计算结果或用户输入的情况，以及 unsafe 块中使用 `get_unchecked()` 的代码。

**审计要点**：
- 检查索引表达式复杂度（算术运算、多个变量组合）
- 追踪索引值来源：是否来自用户输入、网络数据、文件读取
- 识别整数溢出风险：`i * width + j`、`base + offset` 这类计算
- 定位 unsafe 代码块：重点审计 `get_unchecked()`、`ptr::read()` 等直接访问

### 保护机制定位技巧 (L2: 跳读)

查找使用 `get()` 方法（返回 Option）、显式边界检查、或使用迭代器避免索引访问。检查 unsafe 块中的 `get_unchecked()` 是否有充分验证。

**审计检查清单**：
- `vec.get(index)` 是否返回 `Some/None` 被正确处理
- 是否存在 `index < vec.len()` 的边界检查
- unsafe 块中 `get_unchecked()` 前是否有多层验证
- 是否使用迭代器替代直接索引访问

## Classify

### 漏洞确认要点

**真实漏洞标志**：
- 索引来自不受信任的源（用户输入、网络包、文件内容），导致 panic（DoS）
- unsafe 块中 `get_unchecked()` 缺乏充分边界验证，可能导致内存安全问题
- 索引通过整数运算计算（乘法、加法）且未检查溢出：`row * width + col`、`base + offset * 2`
- 在处理动态大小的数据（如网络协议、文件格式）时，使用计算出的索引访问固定大小的数组

### 真实漏洞 vs 误报的区分经验

**误报案例 (可安全跳过)**：
1. 索引为循环变量，已通过循环条件隐式验证：`for i in 0..arr.len() { arr[i] }`
2. 使用 `vec.get(index)?` 并正确处理 None，或 `unwrap_or_else()` 提供安全默认值
3. 索引常数且在编译期可验证：`arr[5]`（其中数组长度 > 5）
4. 索引通过 Range 类型使用：`&arr[start..end]`，Range 已进行边界验证
5. 文档明确说明边界保证的 unsafe 函数被正确使用

**高风险漏洞案例**：
1. `buf[user_input as usize]` 或 `data[packet.length as usize]`，无边界检查
2. `unsafe { ptr.offset(delta).read() }`，其中 delta 未验证
3. `get_unchecked(index)` 前只有一层检查，但索引涉及多个变量计算
4. 在 WASM、嵌入式系统中，panic 导致程序直接崩溃，成为 DoS 攻击点
5. 循环中索引计算错误：`for i in 0..n { arr[i * 2] }` 当 n 未考虑宽度时

### 审计陷阱与技巧

- **陷阱1**：仅检查 `if index < arr.len()` 而忽视整数溢出。如 `index + offset`，应验证不会下溢（负数）或上溢
- **陷阱2**：假设类型转换安全。`len() as usize` 在 32 位系统可能截断，需追踪上下文
- **陷阱3**：panic 不总是漏洞。如果 panic 位置距离用户输入足够远（有多层验证），可能风险较低
- **技巧1**：追踪数据流，从索引反推至输入源，确认完整的验证链
- **技巧2**：对比 safe Rust（self-checking）vs unsafe 块的行为差异，找到转折点
- **技巧3**：查看类似代码的历史漏洞记录（CVE），判断是否为已知模式

## Low risk

### 安全的索引访问模式

**完全安全的做法**：
- 使用 `get()` 或 `get_mut()` 返回 Option，显式处理 None 情况（match 或 if let）
- 使用迭代器（`iter()`、`enumerate()`）代替直接索引，由 Rust 保证安全
- 索引为编译期常量或被循环条件完全约束：`for (i, item) in arr.iter().enumerate()`
- 使用 Range 类型进行切片：`&arr[start..end]`，Rust 自动验证边界

**条件安全的做法**：
- 显式边界检查：`if index < arr.len() { arr[index] }`
- 多层验证链完整：验证来源 → 类型转换 → 边界检查 → 使用
- unsafe 块中充分的文档注释说明边界保证的先决条件
- 在测试中覆盖边界情况（empty、single element、max size）

### 审计实战速查

**快速甄别流程**：
1. 发现 `[index]` 或 `get_unchecked()` → 标记为关注点
2. 逆向追踪 index 的来源：常量？循环变量？用户输入？
3. 若来自输入，检查是否有边界验证。无则 **RISK**；有则评估验证强度
4. 若在 unsafe 块中，检查文档和注释，验证前置条件是否被满足

**审计时间节省技巧**：
- 按优先级扫描：unsafe 块 > 网络协议处理函数 > 图像/视频解码库 > 其他
- 对于库代码，检查 CHANGELOG 和 Issues 中是否有过相似漏洞报告
- 识别常见风险库：图像处理（image crate）、压缩（flate2）、网络（tokio）等

**常见误报来源**：
- `slice.get(i)?` 已处理：看似危险，实际安全（Option 被正确传播）
- 使用了库函数的 safe API（如 `Vec::get`）但审计工具误报
- 索引计算看似复杂，但实际上被编译器或 Rust 类型系统保证安全

### 索引越界相关的整数问题

**关键交集点**：
- 索引计算涉及乘法时，需同时检查整数溢出和边界检查
- 例：`offset * item_size + base` 可能同时触发两类漏洞
- 审计时应合并考虑，而非孤立地评估边界检查

**context 场景**：
- 网络协议解析：packet offset 来自网络，必须验证
- 图像/视频处理：width、height、stride 来自文件头，易被精心构造
- 内存池分配：chunk 索引来自参数，需严格验证

## 审计案例速览

### 案例1：网络包解析中的索引越界

```
// 高风险：payload_offset 来自网络包
fn parse_packet(data: &[u8], payload_offset: u16) {
    let payload = &data[payload_offset as usize..];  // ⚠️ 无边界检查
}

// 审计要点：
// - payload_offset 来自不受信任的网络源
// - 无 if payload_offset < data.len() 检查
// - as usize 转换可能溢出
// 结论：真实漏洞，DoS 风险
```

### 案例2：图像处理中的二维索引计算

```
// 高风险：row、col、width 来自图像头
fn get_pixel(buf: &[u8], row: u32, col: u32, width: u32) -> u8 {
    let idx = row * width + col;  // 可能整数溢出
    buf[idx as usize]             // 可能越界
}

// 审计要点：
// - row * width 未检查溢出
// - 即使溢出，强制转为 usize，可能导致截断
// - 无 idx < buf.len() 验证
// 结论：真实漏洞，内存安全问题
```

### 案例3：safe 模式下的正确使用

```
// 低风险：已正确处理
fn safe_access(vec: &[i32], index: usize) -> Option<i32> {
    vec.get(index).copied()  // get() 返回 Option，已处理
}

// 审计要点：
// - 使用 get() 而非 [] 索引
// - Option 被正确传播
// 结论：安全，无需继续深入
```

### 案例4：unsafe 块中的验证不足

```
// 高风险：验证不足
unsafe {
    if idx < buf.len() {
        *buf.as_ptr().add(idx)  // 仅一层检查，但 add() 可能指向有效范围外
    }
}

// 审计要点：
// - 只检查了长度，未检查对齐
// - add() 参数未验证
// 结论：需深入分析指针算术，可能为真实漏洞
```

## 审计检查清单总结

**快速评分**（用于优先级排序）：
- 得分 3+（高风险）：unsafe + 计算索引 + 来自输入 = 必审
- 得分 2（中风险）：safe Rust + 计算索引 + 来自输入 = 审查验证
- 得分 1（低风险）：常量索引、已验证、迭代器模式 = 可跳过

**最后检查**：
- 是否有单元测试覆盖边界情况（索引 = 0、len-1、len、len+1）
- 是否有集成测试用恶意输入测试该功能
- 相关漏洞是否在 CHANGELOG 中被修复记录
