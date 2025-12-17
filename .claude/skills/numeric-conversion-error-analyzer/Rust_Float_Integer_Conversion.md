# Rust_Float_Integer_Conversion

**漏洞类型**: 浮点与整型转换，f32/f64 与整数类型之间的转换

**漏洞成因**

Rust 中浮点数向整型转换时，会产生精度丢失、数值截断、溢出等问题。常见于：
- 浮点数直接使用 `as` 强制转换为整型，忽略小数部分
- 浮点数用于切片索引、Vec 容量、内存分配等关键场景
- 浮点数表示范围超出整型可表示范围时的溢出处理（超出 i32/i64 范围转换结果未定义）
- 浮点计算（加乘除）中精度丢失，舍入误差在后续逻辑中放大
- NaN、Infinity 等特殊值的转换未加校验
- 通过数学函数结果的浮点转整，未验证返回值
- unsafe 代码中的浮点转整用于指针运算

---

## Details

### 代码示例

**危险模式1：浮点直接转整作为切片大小/索引**
```rust
fn process_buffer(size: f64) {
    let buf_size = size as usize;  // 精度丢失：3.9 → 3，并且非负检查不足
    let mut buffer = vec![0u8; 256];
    if size > 0.0 {
        buffer[..buf_size].fill(0);  // 实际需要足够大小，但可能下溢或越界
    }
}

process_buffer(3.9);  // 转为 3，可能不满足需求
process_buffer(-100.5);  // 转为 usize::MAX（因为负数到无符号转换）
```

**危险模式2：浮点数超出整型范围**
```rust
fn process_coordinate(x: f64) {
    let coord = x as i32;  // x > i32::MAX 时截断或未定义行为
    let mut array = vec![0i32; 256];
    if x < 256.0 {
        array[coord as usize] = 42;  // 超出范围导致越界
    }
}

process_coordinate(1e10);  // 远超 i32::MAX (2.1e9)
```

**危险模式3：浮点用于 Vec 容量初始化**
```rust
fn initialize_vec(expected_size: f32) -> Vec<u8> {
    let size = expected_size as usize;
    let mut vec = Vec::with_capacity(size);  // 精度丢失导致容量不足
    vec.resize(1000, 0);  // 实际需要 1000，但容量可能 < 1000
    vec
}

initialize_vec(1000.1);  // 转为 1000，但浮点精度可能导致下溢
```

**危险模式4：NaN/Infinity 未检查**
```rust
fn handle_measurement(value: f64) {
    if value > 0.0 {
        let size = value as usize;  // NaN 或 Infinity 转换为 0
        let mut arr = vec![0u8; size];
        // NaN → 0，可能导致容量为 0 的向量
    }
}

let nan_val = f64::NAN;
handle_measurement(nan_val);  // size = 0，逻辑错误

let inf_val = f64::INFINITY;
handle_measurement(inf_val);  // size 可能为 usize::MAX 或 0
```

**危险模式5：精度丢失导致权限判断错误**
```rust
fn check_permission(level: f64) {
    let int_level = level as i32;
    if int_level == 3 {  // 3.9 被截断为 3
        grant_admin_access();  // 权限绕过
    }
}

check_permission(3.9);  // 本应拒绝，但因截断被接受
```

**危险模式6：Math 函数返回浮点转整的权限问题**
```rust
fn handle_discount(price: f64, percentage: f64) -> i32 {
    let discount = (price * percentage / 100.0) as i32;  // 精度丢失累积
    discount
}

let price = 100.0;
let percent = 33.33;
handle_discount(price, percent);  // 结果可能有舍入误差
```

**危险模式7：unsafe 中的浮点转整指针运算**
```rust
fn unsafe_offset_access(base_ptr: *const u8, offset: f32, len: usize) -> u8 {
    unsafe {
        let safe_offset = offset as usize;  // 负浮点转无符号，或超范围
        let ptr = base_ptr.add(safe_offset);
        *ptr
    }
}

unsafe_offset_access(ptr, -10.5, 1024);  // 转为 usize::MAX - 10
```

### 快速定位核心操作 **[L1-L2]**

**关键词扫描 [L1]:**
- `as i32`, `as u32`, `as i64`, `as usize`, `as i16`, `as u8` 直接作用于 `f32`/`f64` 变量
- 浮点变量用于：切片索引、Vec 容量、循环计数、内存分配
- 浮点来源于：用户输入、API 返回、网络数据、Math 函数结果（`sqrt`, `pow`, `sin` 等）
- 浮点计算（`+`、`*`、`/`）后立即转整
- 条件判断中浮点与整数常数比较
- `unsafe` 块中的浮点转整用于指针操作
- FFI 调用中的浮点参数转换

**快速定位保护机制 [L2-L3]:**
- 转换前是否检查：`f64::is_nan()`, `f64::is_infinite()`, `f64::is_finite()`
- 是否验证浮点值在目标整型范围：`if val >= i32::MIN as f64 && val <= i32::MAX as f64`
- 是否使用安全转换方法：`val.to_int_checked()` 或 TryFrom trait
- 是否对浮点计算启用舍入模式和异常检查
- 是否进行了非负性验证（特别是转 usize 时）：`if val >= 0.0`
- unsafe 块中是否配合指针范围检查

---

## Classify

**研判为真漏洞的特征：**
1. 浮点数直接强制转整无检查，用于敏感操作（切片索引、Vec 容量、内存分配）
2. 浮点值来源于外部输入（参数、用户请求、网络数据），转换后无再验证
3. 浮点计算中可能发生精度丢失或舍入误差，用于权限、数量等安全决策
4. 未检查 NaN/Infinity，直接转整后用于关键参数
5. 浮点值可能超出目标整型范围（如 1e20 > i32::MAX），转换后行为未定义
6. unsafe 块中浮点转整用于指针偏移，未进行指针范围验证

**误报/代码异味的特征：**
- 浮点值来自内部计算且范围明确受控（如 `angle = atan2(y, x)` 范围固定在 [-π, π]）
- 转换前明确验证了有效性：`if f64::is_finite(val) && val >= 0.0 && val < MAX as f64`
- 仅涉及日志、显示、统计用途，不影响权限或资源分配
- 使用 TryFrom 并捕获 `TryFromFloatError`
- 使用安全转换方法如 `round()` 替代直接强制转换
- 浮点值由内部控制流保证范围（如模运算后的结果）

---

## Low risk

**以下场景可评为低风险：**

1. **完整的有效性检查**
   - 转换前显式检查：`if f64::is_finite(val) && val >= 0.0 && val < 1e9`
   - 检查整型范围：`if val >= i32::MIN as f64 && val <= i32::MAX as f64`
   - 转换为 usize 时额外检查非负：`if val >= 0.0`
   - 负数情况已被明确处理

2. **内部计算结果的受控转换**
   - 浮点来自内部算法（非外部输入），其范围已限制
   - 如：`let degree = angle.to_degrees();` 范围为 [-180, 180]，可直接转为 i32
   - 错误不会导致安全后果（仅显示值或日志）

3. **使用安全转换方法**
   - 使用 TryFrom trait：`let val: i32 = f64_val.try_into()?;`
   - 使用 `checked_cast()` 或类似库函数
   - 配合错误处理和范围验证

4. **特殊值验证**
   - 转换前检查 NaN/Infinity：`if f64::is_finite(val)`
   - 使用 `to_int_checked()` 等返回 Option 的方法

5. **非关键路径的转换**
   - 浮点转整仅用于统计、计数、日志等非敏感场景
   - 不影响切片访问、权限判断、内存分配等敏感操作

6. **受保护的 unsafe 块**
   - unsafe 块中的浮点转整配合完整的指针范围检查
   - 如：`if offset >= 0.0 && (offset as usize) <= len`
   - 指针有效范围已由编程保证

7. **协议规范的静态限制**
   - 协议规范中明确限制浮点范围（如值固定在 0-360 范围内）
   - 类型本身的范围已满足需求

