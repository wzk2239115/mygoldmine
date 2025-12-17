# Rust_Integer_Arithmetic_Overflow

**漏洞类型**: 整数运算溢出，Rust 默认在调试模式下检查溢出，但发布模式下需使用 checked_* 方法

**Rust**

---

专注于这一垂直漏洞类型研判任务，从漏洞成因触发，编写该md文件，包含一下三个小标题，【注意语言精炼，表达简洁，可以作为审计小抄，仅专注于审计，不包含攻击与修复】：

## Details

**代码示例**：`let result = a + b`、`let size = width * height`、`wrapping_add()`、`saturating_mul()`

- **核心操作定位技巧** (L1: 关键词扫描)：扫描算术操作符 `+`、`-`、`*`。Rust 在 debug 模式下会 panic，但 release 模式下会回绕。关注是否使用 `checked_*`、`saturating_*`、`wrapping_*` 方法。检查运算结果用于内存分配、数组索引的情况。

- **保护机制定位技巧** (L2: 跳读)：查找溢出安全方法（`checked_add()`、`saturating_mul()`、`overflowing_sub()`），使用 `overflow-checks = true` 编译选项，或使用更宽的类型。检查是否对 `Option<T>` 返回值进行处理。

## Classify

判断是否为漏洞的要点：
- **确定漏洞**：release 模式下使用普通算术运算，无溢出检查，结果参与关键操作
- **误报**：使用 `checked_*` 方法并处理 None、有明确范围验证、仅在 debug 模式运行
- **代码异味**：使用 `wrapping_*` 方法，需确认回绕行为是否预期

## Low risk

- 使用 `checked_*` 方法并正确处理 None
- 使用 `saturating_*` 方法（饱和运算）
- 编译配置启用 `overflow-checks = true`
- 操作数为常量或已验证范围
- 使用 `overflowing_*` 并检查溢出标志

## 审计专业技巧

### 1. 上下文感知的风险评估
- **内存分配触发点**：`Vec::with_capacity(width * height)`、`vec![0; size]`，溢出导致分配失败或过度分配
- **索引操作**：`arr[index]` 或 `arr.get(offset + len)`，溢出导致越界访问
- **循环边界**：`for i in 0..count * 2`，溢出改变循环范围
- **缓冲区操作**：`slice.copy_from_slice(data[start..start + len])`，溢出破坏边界计算

### 2. 调试模式 vs 发布模式区分
- **真实漏洞特征**：Cargo.toml 中 `[profile.release]` 无 `overflow-checks = true`，且代码仅在 release 构建场景下运行
- **误报标志**：整数运算仅出现在测试代码、示例程序，生产环节被删除
- **检查路径**：追踪完整编译链，确认目标二进制确实禁用溢出检查

### 3. Option/Result 处理的陷阱
- **真实漏洞**：`checked_add().unwrap()` 或 `checked_mul().expect()`，违反了安全检查意图
- **隐性漏洞**：`let result = checked_add(...);` 后直接使用 `result`（未解包），编译错误但代码审计时易遗漏
- **条件路径**：`if let Some(val) = checked_add(...) { use val }` 正确，但存在 else 分支未处理的情况

### 4. 类型转换环节的溢出
- **隐性风险点**：`(a as u32) + (b as u32)`，as 转换本身可能丢失信息，需追踪源类型范围
- **审计建议**：关注 i64/usize 向 u32 的转换，特别是网络数据包大小、文件长度字段
- **通过操作**：如先转为 u64 再运算可避免溢出

### 5. 真实案例区分
- **真漏洞示例**：
  ```rust
  let size = width * height;  // release 模式下无保护
  let buf = vec![0u8; size];  // 溢出时分配异常行为
  ```
- **假漏洞示例**：
  ```rust
  let size = width.checked_mul(height)
    .ok_or("overflow")?;  // 正确处理
  let buf = vec![0u8; size];
  ```

### 6. 常见误报场景
- **常量折叠**：`const N: usize = 100 * 200;` 编译时计算，溢出则编译失败（不是运行时漏洞）
- **测试文件中的运算**：`#[cfg(test)]` 块内的运算不影响发布版本
- **已验证范围**：
  ```rust
  if x < 1000 && y < 1000 {
    let result = x * y;  // 最大 1000*1000，不会溢出 u32
  }
  ```
- **饱和/回绕的预期用途**：密码学中 `wrapping_add` 用于循环加法，需验证是否确实为设计意图

### 7. 深度审计检查清单
- [ ] 运算结果是否用于 `Vec::with_capacity()` 或 `alloc()`
- [ ] 运算结果是否用于数组/切片索引
- [ ] 运算结果是否用于循环计数器或范围
- [ ] `as` 转换是否可能丢失数据（特别是向下转换）
- [ ] 所有 `checked_*` 调用是否都有 `Ok/Some` 路径处理
- [ ] 编译配置中是否显式设置 `overflow-checks`
- [ ] 输入数据来源（用户输入 vs 常量）是否需要验证
- [ ] 是否存在多步运算中间溢出（如 `(a * b) + c`）

### 8. 审计实战陷阱规避
- **字节序列处理**：网络协议解析中，`u16` 或 `u32` 从字节数组读取后立即用于计算，需关注边界
- **格式化字符串**：某些日志库中 `format!("{}", size)` 涉及的尺寸计算，虽不直接漏洞但可追踪来源
- **Unsafe 块内的运算**：`unsafe { ptr.offset(index * element_size) }`，溢出导致内存越界，风险等级最高
- **trait 实现中的隐性运算**：`impl Iterator for MyStruct` 中的 `next()` 涉及计数器加法，容易被忽略

### 9. 审计效率优化
- **快速排除法**：扫描整个文件查找 `checked_`、`saturating_`、`wrapping_` 关键词出现频率，高频率通常代表代码质量好
- **增量审计**：关注修改历史中新增的算术操作，而非全量代码
- **工具联动**：配合 clippy 的 `integer_arithmetic` lint 输出，但需手工验证假正例
- **依赖库风险**：检查 `Cargo.toml` 中第三方库是否已知存在整数溢出漏洞（CVE 数据库查询）

### 10. 误报与真实漏洞的最终判断标准
- **确定为漏洞**：(1) release 模式下运行 (2) 无溢出检查 (3) 运算结果用于关键操作 (4) 输入可控
- **确定为误报**：满足以下任一条件 (1) 代码在测试/示例中 (2) 操作数为编译时常量 (3) 有明确范围验证 (4) 使用 checked_* 并正确处理异常路径
- **需要进一步分析**：(1) 使用 `wrapping_*` 需确认意图 (2) `as` 转换需追踪源类型 (3) 依赖库函数需查看源码

## 真实案例与误报对比

### 真实漏洞案例
```rust
// 案例 1：内存分配漏洞
pub fn allocate_buffer(width: u32, height: u32) -> Vec<u8> {
    let size = width * height;  // overflow in release mode
    vec![0u8; size as usize]    // 分配失败或异常
}

// 案例 2：索引溢出 (unsafe)
pub fn slice_access(data: &[u8], offset: u32, len: u32) {
    let end = offset + len;  // 无检查
    unsafe {
        std::ptr::copy_nonoverlapping(
            data.as_ptr().add(offset as usize),
            ptr,
            end as usize
        );
    }
}
```

### 误报案例 (安全代码)
```rust
// 案例 1：正确使用 checked_*
pub fn safe_allocate(width: u32, height: u32) -> Result<Vec<u8>, String> {
    let size = width
        .checked_mul(height)
        .ok_or("overflow")?;
    Ok(vec![0u8; size as usize])
}

// 案例 2：编译时常量
const WIDTH: usize = 100;
const HEIGHT: usize = 200;
const BUFFER_SIZE: usize = WIDTH * HEIGHT;  // 编译时计算，溢出则编译失败

// 案例 3：范围验证
pub fn verified_operation(a: u8, b: u8) {
    if (a as u32) <= 200 && (b as u32) <= 200 {
        let result = (a as u32) * (b as u32);  // 最大 200*200，安全
    }
}
```

## 审计遇见的常见难点

### 难点 1：库函数的隐性溢出
许多标准库和第三方库函数内部涉及整数运算但不暴露给用户，需要关注：
- `String::from_utf8_lossy()` 的内部 buffer 大小计算
- `Vec::resize()` 和 `Vec::reserve()` 的容量计算
- `Iterator::zip()` 处理的长度比较

**审计建议**：查看上游库的已知 CVE，不需要逐一审计库源码。

### 难点 2：条件编译和特性门
```rust
#[cfg(feature = "safe")]
let result = checked_add(...)?;

#[cfg(not(feature = "safe"))]
let result = a + b;  // 潜在漏洞，需检查默认特性配置
```

**审计建议**：检查 Cargo.toml 的 `default-features`，确认危险路径是否在默认启用。

### 难点 3：宏展开中的运算
某些宏可能隐藏算术操作，`cargo expand` 可用于查看展开后代码。

### 难点 4：异步上下文中的竞态条件
多线程环境下，两次检查之间可能发生数据变化，需关注：
```rust
if checked_size <= MAX {
    // 并发修改 checked_size 的场景
    allocate(checked_size);
}
```

## 防御优先级（从高到低）
1. **使用 checked_* 方法** - 显式处理，优先级最高
2. **类型宽化** - `u32 * u32` 改为 `u64 * u64`
3. **范围验证** - 先验证输入范围再运算
4. **编译配置保护** - `overflow-checks = true` 作为备选
5. **饱和运算** - `saturating_*` 仅用于已验证的特定场景
6. **回绕运算** - `wrapping_*` 仅用于密码学等特殊需求

