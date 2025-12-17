# Rust_Array_Index_Conversion

**漏洞类型**: 数组索引转换，数组和切片索引中的类型转换

**漏洞成因**

Rust 中使用有符号整数计算数组或切片索引时，若中间转换或强制转换处理不当，负数会被误解释为巨大的正数，导致越界访问。常见问题包括：
- 有符号整数直接转换为 usize 用于切片索引
- 有符号整数计算结果转换为 usize，未验证非负性
- 整数溢出导致索引值异常
- 指针偏移计算中使用有符号值，未进行边界检查
- 循环计数器或索引计算中的类型混用
- unsafe 代码中的索引计算，未进行指针范围验证

---

## Details

### 代码示例

**危险模式1：有符号整数直接作为切片索引**
```rust
fn process_slice(index: i32, data: &[u8]) -> Option<u8> {
    Some(data[index as usize])  // index 为负数时越界访问
}

let buffer = vec![1, 2, 3, 4, 5];
process_slice(-1, &buffer);  // index = -1 as usize = usize::MAX，panic
```

**危险模式2：有符号到无符号的隐式索引转换**
```rust
fn copy_with_offset(offset: i32, src: &[u8], dst: &mut [u8]) {
    if offset > 0 {
        let off = offset as usize;
        dst.copy_from_slice(&src[off..]);  // offset 可能超出 src.len()
    }
}

let src = [1, 2, 3, 4, 5];
let mut dst = vec![0u8; 10];
copy_with_offset(100, &src, &mut dst);  // off = 100，越界
```

**危险模式3：计算后转换未验证**
```rust
fn calculate_index(a: i32, b: i32) -> usize {
    ((a + b) % 256) as usize  // a + b 可能溢出，结果异常
}

let table = vec![0u8; 256];
let idx = calculate_index(i32::MAX, 100);
println!("{}", table[idx]);  // 可能越界
```

**危险模式4：循环中的类型混用**
```rust
fn iterate_with_signed_index(data: &[u8]) {
    for i in -10i32..data.len() as i32 {  // i 为负时越界
        if i >= 0 {
            println!("{}", data[i as usize]);
        }
    }
}

iterate_with_signed_index(&[1, 2, 3]);  // 循环包含负数索引
```

**危险模式5：指针偏移中的有符号计算**
```rust
fn unsafe_offset_access(base_ptr: *const u8, offset: i32, len: usize) -> u8 {
    unsafe {
        let ptr = base_ptr.offset(offset as isize);  // 未验证 offset 范围
        *ptr
    }
}

let data = [1, 2, 3, 4, 5];
unsafe {
    unsafe_offset_access(data.as_ptr(), -100, 5);  // offset 超出范围
}
```

**危险模式6：用户输入的索引未验证**
```rust
fn get_user_data(index: i32, data: &[u8]) -> u8 {
    if index < 100 {  // 仅检查上界，未检查下界
        data[index as usize]  // 负数绕过检查
    } else {
        0
    }
}

get_user_data(-5, &[1, 2, 3]);  // -5 < 100，转为 usize::MAX - 4，越界
```

**危险模式7：多级索引计算**
```rust
fn nested_index(base: i32, delta: i32, matrix: &[Vec<u8>]) -> u8 {
    let row = (base + delta) as usize;  // 未验证加法结果
    let col = base as usize;  // 负 base 转 usize
    matrix[row][col]
}

let matrix = vec![vec![1, 2, 3]];
nested_index(-1, 0, &matrix);  // row = -1 as usize，col = -1 as usize
```

### 快速定位核心操作 **[L1-L3]**

**关键词扫描 [L1]:**
- 切片索引操作：`data[index as usize]`, `data[idx]` 其中 idx 为有符号类型
- 有符号到 usize 的转换：`as usize` 作用于 `i32`, `i16`, `i8` 等
- 指针偏移：`ptr.offset(signed_val as isize)`, `ptr.add(val as usize)`
- 循环中的索引：`for i in start..end` 其中 start 为负或是有符号类型
- 用户输入的索引：函数参数、网络数据、文件内容
- 索引计算操作：加、减、乘、除可能导致溢出或负数

**快速定位保护机制 [L2-L3]:**
- 索引使用前是否检验范围：`if index >= 0 && index < data.len()`
- 是否使用 `get()` 等安全方法：`data.get(index as usize)?`
- 转换前是否验证非负：`if index >= 0`
- 是否使用 `try_into()` 进行安全转换
- 循环条件是否明确排除负数：`for i in 0..len`
- unsafe 块中的指针操作是否有范围检查
- 是否使用 `checked_add`, `checked_sub` 等进行安全计算

---

## Classify

**研判为真漏洞的特征：**
1. 有符号整数直接转换为 usize 用于切片索引，无任何范围检查
2. 有符号整数计算结果转换为 usize，未验证非负性
3. 索引值来源于外部输入（参数、网络、用户输入），可能为负数
4. 整数计算（加、减、乘、除）可能溢出，转换后用于索引
5. 指针偏移中使用有符号值，未进行边界验证
6. 循环条件中允许负数遍历数组，条件检查不完整

**误报/代码异味的特征：**
- 索引来源为无符号类型（`u32`, `usize`），无符号转换问题
- 索引转换前存在严格的范围检查：`if idx >= 0 && idx < data.len()`
- 使用 `get()` 等安全索引方法：`data.get(idx as usize)?`
- 使用 `try_into()` 进行安全转换，配合错误处理
- 循环计数器为无符号类型，条件明确为 `i < len`
- 指针偏移仅对已验证的范围内的值进行

---

## Low risk

**以下场景可评为低风险：**

1. **范围已限制的索引操作**
   - 索引在使用前已通过验证：`if index >= 0 && index < data.len()`
   - 循环计数器为无符号类型：`for i in 0..data.len()`
   - 数组访问明确受限于已验证的边界

2. **使用安全的索引方法**
   - 使用 `get()` 方法：`data.get(index as usize)?`
   - 使用 `get_mut()` 进行可变访问
   - 使用迭代器而非索引：`for item in data.iter()`
   - 使用 `slice` 操作：`data[start..end]` 其中 start、end 已验证

3. **安全的类型转换**
   - 转换前显式检查非负：`if index >= 0 { let u = index as usize; }`
   - 使用 `try_into()` 进行安全转换：`let u: usize = index.try_into()?;`
   - 使用 `TryFrom` trait 捕获转换失败

4. **内部受控的索引**
   - 索引来自内部计算，范围已被逻辑保证为非负
   - 如：`for i in 0..len { ... }` 中的 i 自动为非负
   - 计数器初值为 0，只进行递增操作

5. **safe 方法的使用**
   - 使用 Rust 标准库的安全方法而非直接索引
   - 编译器会进行边界检查，防止越界

6. **非关键路径的操作**
   - 索引操作仅用于读取，不会导致数据修改
   - 越界后不会导致 panic（使用 Option 返回）

7. **编译期已知的静态索引**
   - 索引值为编译期常数
   - 编译器可以在编译期验证索引的有效性

