# Rust_Signed_Unsigned_Conversion

**漏洞类型**: 有符号/无符号转换，i8/i16/i32/i64 与 u8/u16/u32/u64 之间的转换

**漏洞成因**

Rust 中有符号/无符号类型转换时，负数会被解释为巨大的正数值。常见问题包括：
- 有符号整数直接使用 `as` 转换为无符号类型，用于内存分配、长度校验、数组索引
- 有符号值来自外部输入（用户、网络、文件），未验证就转换为无符号
- 有符号无符号混合比较导致的符号扩展和边界绕过
- 在 unsafe 代码中进行有符号/无符号转换，指针运算可能越界
- FFI 调用中，有符号参数转换为无符号传入 C 函数
- 负数转无符号后用于切片索引、Vec 容量、内存操作等关键场景

---

## Details

### 代码示例

**危险模式1：负数转无符号导致缓冲区溢出**
```rust
fn process_data(data: &[u8], len: i32) {
    let size = len as usize;  // 负数转无符号：-1 → usize::MAX
    let mut buffer = vec![0u8; 256];
    if len >= 0 {
        buffer[..size].copy_from_slice(&data[..size]);  // size 可能超出256
    }
}

process_data(&user_input, -1);  // len 为 -1，转无符号后巨大
```

**危险模式2：有符号长度校验绕过**
```rust
fn read_file(size: i32) -> Result<Vec<u8>, Box<dyn std::error::Error>> {
    if size > 1000 {  // 检查：size <= 1000
        return Err("Too large".into());
    }
    let usize_val = size as usize;  // -1 转无符号：usize::MAX
    let mut buf = vec![0u8; usize_val];  // 分配超大内存导致 DoS
    Ok(buf)
}

read_file(-1);  // 通过有符号检查，但转无符号后是巨数
```

**危险模式3：数组索引越界**
```rust
fn get_array_element(index: i32, array: &[u8]) -> Option<u8> {
    let idx = index as usize;  // -5 转无符号：usize::MAX - 4
    if idx < array.len() {  // 无符号比较可能始终为真或假
        Some(array[idx])  // 越界访问
    } else {
        None
    }
}

let arr = [1, 2, 3, 4, 5];
get_array_element(-5, &arr);  // idx = usize::MAX - 4，未被正确拒绝
```

**危险模式4：有符号无符号混合比较**
```rust
fn validate_length(user_len: i32, max_len: u32) {
    if (user_len as u32) < max_len {  // 显式转换后比较，但未验证负数
        process(user_len);
    }
}

validate_length(-1, 100);  // -1 as u32 = u32::MAX，绕过检查
```

**危险模式5：unsafe 指针运算中的转换**
```rust
fn unsafe_buffer_access(offset: i32, data: *const u8, len: usize) -> u8 {
    unsafe {
        let safe_offset = offset as usize;  // 负数转无符号导致巨大偏移
        let ptr = data.add(safe_offset);  // 指针运算越界
        *ptr
    }
}

unsafe_buffer_access(-100, data_ptr, 1024);
```

**危险模式6：FFI 中的类型转换**
```rust
extern "C" {
    fn c_function(size: libc::size_t) -> *mut libc::c_void;
}

fn allocate_memory(size: i32) -> *mut libc::c_void {
    unsafe {
        c_function(size as libc::size_t)  // 负数转 size_t，无符号巨数
    }
}

allocate_memory(-1);  // 导致 C 函数分配巨大内存
```

### 快速定位核心操作 **[L1-L2]**

**关键词扫描 [L1]:**
- `as usize`, `as u32`, `as u64`, `as u16`, `as u8` 直接作用于有符号变量
- 有符号参数来源：用户输入、网络数据、文件读取、外部函数返回
- 有符号值用于：slice 索引、Vec 容量、内存分配、指针运算
- `unsafe` 块中的类型转换
- FFI 调用中的参数转换（`libc::size_t`、`c_uint` 等）
- 混合有符号无符号的比较：`(signed as unsigned) < unsigned_val`

**快速定位保护机制 [L2-L3]:**
- 有符号转无符号前是否验证非负：`if (signed_val >= 0)`
- 是否使用 `try_into()` 进行安全转换：`let u = signed_val.try_into()?`
- 是否在转换后再验证范围：`let u = signed_val as usize; if u <= MAX_SIZE`
- unsafe 块中的转换是否配合指针范围检查
- FFI 参数转换前是否验证有效范围
- 是否使用 `saturating_as` 或 `wrapping_as` 等有意转换

---

## Classify

**研判为真漏洞的特征：**
1. 有符号值直接使用 `as` 转无符号，未验证其非负，用于关键操作（内存分配、长度、索引）
2. 有符号值来源于外部输入（参数、网络、文件），可能为负数
3. 转换后的无符号值被用于切片索引、Vec 容量、指针偏移等敏感位置
4. 在 unsafe 块中转换，未进行指针范围验证
5. FFI 调用中传入无符号参数，负数值可导致 C 函数分配超大内存
6. 负数转无符号后导致的巨数会引发缓冲区溢出、DoS 或逻辑错误

**误报/代码异味的特征：**
- 有符号值来自内部计算，范围已被逻辑保证为非负（如循环计数器）
- 转换前显式验证了非负条件：`if val >= 0 { let u = val as usize; }`
- 使用 `try_into()` 进行安全转换，配合错误处理
- 有符号值的负数情况已在上游被过滤或断言
- 仅涉及非关键路径（日志、统计等）的转换
- 使用 `saturating_as` 或 `wrapping_as` 表示意图明确

---

## Low risk

**以下场景可评为低风险：**

1. **完整的非负性验证**
   - 有符号值在转换前显式检查：`if val >= 0 { let u = val as usize; }`
   - 或转换后再验证范围：`let u = val as usize; if u <= MAX_SIZE`
   - 负数情况已被明确处理（返回错误或提前 return）

2. **使用安全的转换方法**
   - 使用 `try_into()` 进行安全转换：`let u: usize = val.try_into()?;`
   - 使用 `TryFrom` trait 捕获转换失败
   - 使用 `checked_cast()` 或类似的库函数

3. **内部受控的有符号值**
   - 有符号值来自内部逻辑计算（如循环计数器 `for i in 0..len`）
   - 范围已在代码逻辑上限制，由 Rust 类型系统保证
   - 如：`let idx = loop_counter;`，loop_counter 由编程语言保证非负

4. **非关键路径的转换**
   - 有符号转无符号仅用于计数、统计、日志等非安全决策场景
   - 不影响切片索引、内存分配、指针运算等敏感操作

5. **显式意图的转换**
   - 使用 `wrapping_as` 或 `saturating_as` 表示意图明确的饱和/环绕
   - 注释明确说明为何转换安全

6. **受保护的 unsafe 块**
   - unsafe 块中的转换配合完整的指针范围检查
   - 如：`if offset >= 0 && offset as usize <= len { ... }`
   - 指针有效范围已由编程保证

7. **协议规范限制的值**
   - 协议规范中明确限制字段为非负（如 uint8、uint32）
   - 类型本身的范围已满足需求

