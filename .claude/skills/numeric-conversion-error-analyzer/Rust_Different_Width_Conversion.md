# Rust_Different_Width_Conversion

**漏洞类型**: 不同位宽转换，不同位宽整数类型之间的转换（i8/i16/i32/i64 与 i64/usize）

**漏洞成因**

Rust 中窄类型（i8、i16、i32）转换为宽类型（i64、usize）时，如果源类型是有符号的，会进行符号扩展。负数在转换后仍保持负值，导致在需要非负数的业务逻辑（如内存分配、切片索引、容量计算）中引发缓冲区溢出、整数下溢等安全问题。常见问题包括：
- 有符号窄类型直接转换为无符号宽类型，负数变成巨大正数
- 窄类型转为 usize 用于 Vec 容量、切片索引、指针偏移
- 有符号值来自外部输入，转换后未验证非负性
- 符号扩展导致的多级类型转换混乱
- 网络字节序转换后的有符号值直接使用
- unsafe 代码中的宽度转换，指针运算可能越界

---

## Details

### 代码示例

**危险模式1：有符号 i32 转换到 usize，用于内存分配**
```rust
fn allocate_buffer(size: i32) -> Vec<u8> {
    let alloc_size = size as usize;  // 负数转 usize：-1 → usize::MAX
    vec![0u8; alloc_size]  // 分配巨大内存或导致 OOM
}

allocate_buffer(-1);  // size = -1，转为 usize::MAX，导致 panic 或 DoS
```

**危险模式2：i16 转换到 usize 用于数组索引**
```rust
fn access_array(index: i16, data: &[u8]) -> Option<u8> {
    let idx = index as usize;  // -1 → usize::MAX
    if idx < data.len() {
        Some(data[idx])  // 越界访问
    } else {
        None
    }
}

let arr = [1, 2, 3, 4, 5];
access_array(-1, &arr);  // idx = usize::MAX，未被正确拒绝
```

**危险模式3：有符号字节转换到 usize**
```rust
fn process_data(size_byte: i8) {
    let size = size_byte as usize;  // -1 → usize::MAX
    let mut buffer = vec![0u8; 256];
    if size <= 256 {
        buffer[..size].fill(0xFF);  // size 可能超过 256
    }
}

process_data(-100);  // size = -100 as usize，是巨大正数
```

**危险模式4：多级转换导致符号混乱**
```rust
fn complex_conversion(short_val: i16) -> usize {
    let int_val = short_val as i32;  // 符号扩展：-100 → -100
    let long_val = int_val as i64;   // 符号扩展：-100 → -100
    let unsigned_val = long_val as usize;  // 有符号到无符号：-100 → usize::MAX - 99
    unsigned_val
}

complex_conversion(-100);  // 最终得到巨大正数
```

**危险模式5：网络协议中的有符号字段**
```rust
fn parse_packet(data: &[u8]) {
    let len_byte = data[0] as i8;  // 读取网络数据，可能是负值
    let len = len_byte as usize;  // 负数转 usize
    let payload = &data[1..1 + len];  // 越界访问
}

parse_packet(&[0xFF, 1, 2, 3]);  // 0xFF 作为 i8 是 -1，转为 usize::MAX
```

**危险模式6：unsafe 指针运算中的宽度转换**
```rust
fn unsafe_offset_read(base_ptr: *const u8, offset: i16, len: usize) -> u8 {
    unsafe {
        let safe_offset = offset as usize;  // 负数转 usize
        let ptr = base_ptr.add(safe_offset);
        *ptr
    }
}

unsafe_offset_read(ptr, -10, 1024);  // offset = -10 as usize = 巨大正数
```

**危险模式7：Vec::with_capacity 中的转换**
```rust
fn create_vec(capacity: i32) -> Vec<u8> {
    if capacity > 0 && capacity < 1_000_000 {  // 有符号检查
        Vec::with_capacity(capacity as usize)  // 正数情况下安全，但逻辑不完整
    } else {
        Vec::new()
    }
}

// 如果 capacity 为负，跳过检查就会导致 Vec::new() 而非 OOM
```

### 快速定位核心操作 **[L1-L3]**

**关键词扫描 [L1]:**
- 窄类型转宽类型：`i8 as usize`, `i16 as i64`, `i32 as usize`, `i16 as u32`
- 有符号到无符号转换：`i32 as u32`, `i64 as usize`
- 内存操作涉及转换值：`vec![...]`, `Vec::with_capacity()`, `[index]`, `ptr.add()`
- 用户输入来源：函数参数、网络数据、文件读取
- 网络字节序处理：`u32::from_be_bytes()`, `i32::from_le_bytes()` 后的转换
- 类型强制转换操作：`as` 关键字作用于有符号值

**快速定位保护机制 [L2-L3]:**
- 转换前是否验证非负：`if size_val >= 0`
- 是否检查上界：`if size_val <= MAX_SIZE`
- 是否使用 `try_into()` 进行安全转换：`let u = size_val.try_into()?`
- 是否使用 `TryFrom` trait 捕获溢出
- 对于 usize 转换，是否进行了完整范围检查
- 是否使用 `saturating_as` 或 `wrapping_as` 表示故意转换
- unsafe 块中转换是否配合指针范围检查

---

## Classify

**研判为真漏洞的特征：**
1. 有符号窄类型直接转换为无符号宽类型（如 `i32 as usize`），用于关键操作（内存分配、索引），无任何范围检查
2. 转换后的值来源于外部输入（参数、网络、文件），可能为负数
3. 转换后的值被用于 Vec 容量、切片索引、指针偏移等敏感位置
4. 多级转换导致的符号混乱，最终用于内存操作
5. 网络协议中未验证的有符号字段直接转换为 usize 后用于数据访问
6. 在 unsafe 块中转换，未进行指针范围验证

**误报/代码异味的特征：**
- 源类型本身是无符号（`u32`, `u16`），不存在符号扩展问题
- 转换前存在严格的范围检查：`if val >= 0 && val <= MAX_SIZE`
- 转换后的值仅用于只读操作（日志、比较）
- 数据来自内部计算且范围已被逻辑保证为非负（如循环计数器）
- 使用 `try_into()` 进行安全转换，配合错误处理
- 使用 `saturating_as` 或 `wrapping_as` 表示有意转换
- 多级转换中每级都进行了范围验证

---

## Low risk

**以下场景可评为低风险：**

1. **源类型控制**
   - 从源头使用无符号整数类型（`u32`, `u16`, `u8`），完全避免符号扩展
   - 数据来自可信的内部系统或硬编码值，不经过用户输入

2. **完整的范围验证**
   - 转换前显式检查非负：`if val >= 0`
   - 转换前检查上界：`if val <= MAX_SAFE_SIZE`
   - 转换为 usize 时完整验证：`if val >= 0 && val <= isize::MAX as i64`
   - 负数情况已被明确处理（返回错误或 panic）

3. **使用安全的转换方法**
   - 使用 `try_into()` 进行安全转换：`let u: usize = val.try_into()?;`
   - 使用 `TryFrom` trait 捕获转换失败
   - 使用 `checked_cast()` 或类似库函数
   - 配合错误处理和异常捕获

4. **非关键路径的转换**
   - 转换后的值仅用于比较、日志、统计等非敏感场景
   - 不影响 Vec 分配、切片索引、指针运算等敏感操作

5. **显式意图的转换**
   - 使用 `wrapping_as` 或 `saturating_as` 表示意图明确的溢出处理
   - 注释明确说明为何转换安全
   - 转换后立即进行验证

6. **受保护的 unsafe 块**
   - unsafe 块中的转换配合完整的指针范围检查
   - 如：`if offset >= 0 && offset as usize <= len { ... }`
   - 指针有效范围已由编程保证

7. **内部受控的值**
   - 有符号值来自内部逻辑计算（如循环计数器 `for i in 0..len`）
   - 范围由 Rust 类型系统保证为非负
   - 数据流明确可控，不经过网络或用户输入

8. **协议规范限制**
   - 协议规范中明确限制字段范围为非负（如标准协议中字段为 uint32）
   - 类型本身的范围已满足需求
   - 数据来源经过验证已符合协议规范

