# Rust_FFI_Type_Conversion

**漏洞类型**: FFI 类型转换，FFI 调用中的类型转换问题

**漏洞成因**

Rust 通过 FFI（Foreign Function Interface）调用 C/C++ 函数时，需要进行类型转换。FFI 边界的类型转换容易出现问题：

- C 函数返回的类型与 Rust 期望类型不匹配，隐式转换导致数据丢失
- C 中的有符号/无符号整数与 Rust 的转换错误
- 指针大小不一致（32 位 C 库与 64 位 Rust）
- C 返回的错误码被错误地转换为布尔值或成功状态
- C 函数参数的长度/大小由返回值指定，转换错误导致缓冲区溢出
- C 库的 ABI 假设未被满足，导致栈损坏或数据解释错误
- C 函数返回的指针被错误地转换或使用
- 回调函数的类型签名不匹配，导致参数误解

---

## Details

### 代码示例

**危险模式1：C 函数返回值转换的符号混用**
```rust
extern "C" {
    fn c_read_data(size: u32) -> i32;  // C 返回有符号：-1 表示错误
}

fn read_wrapper(size: u32) -> usize {
    let result = unsafe { c_read_data(size) };
    result as usize  // -1 → usize::MAX，误认为成功读取大量数据
}

let bytes_read = read_wrapper(100);  // -1 被转换为 usize::MAX
// 后续使用 bytes_read 作为长度导致溢出
```

**危险模式2：错误码检查后的类型转换**
```rust
extern "C" {
    fn process_packet(data: *const u8, len: u32) -> i32;  // 返回错误码
}

fn process_unsafe(data: &[u8]) -> bool {
    let result = unsafe { process_packet(data.as_ptr(), data.len() as u32) };
    result as bool  // 非零值被转为 true，但 -1 也是非零，意义不同
}

// C 约定：0 = 成功，-1 = 严重错误，1-99 = 警告
let success = process_unsafe(&[1, 2, 3]);  // 警告码被认为成功
```

**危险模式3：C 函数大小字段的转换**
```rust
extern "C" {
    fn get_buffer_size() -> u32;
}

unsafe fn allocate_c_buffer() -> Vec<u8> {
    let size = get_buffer_size();
    let mut vec = vec![0u8; size as usize];
    vec
}

// C 库返回 u32::MAX 表示失败，但 Rust 转换为有效大小
let buffer = unsafe { allocate_c_buffer() };  // 分配 2GB 内存
```

**危险模式4：指针转换中的假设不成立**
```rust
extern "C" {
    fn c_get_data() -> *const u8;
}

fn get_data_from_c() -> &'static [u8] {
    let ptr = unsafe { c_get_data() };
    unsafe { std::slice::from_raw_parts(ptr, 100) }  // 假设指针有效且指向 100 字节
}

// C 库可能返回临时栈指针，返回后失效
let data = get_data_from_c();  // data 指向已释放内存
```

**危险模式5：C 库 size_t 与 usize 的转换**
```rust
#[repr(C)]
struct CResult {
    data_ptr: *const u8,
    size: u32,  // C 中是 size_t，可能为 u64
}

unsafe fn copy_c_result(result: &CResult) -> Vec<u8> {
    std::slice::from_raw_parts(result.data_ptr, result.size as usize).to_vec()
}

// 32 位编译的 C 库，size 超过 4GB，转换后截断
let vec = unsafe { copy_c_result(&c_result) };
```

**危险模式6：回调函数参数类型不匹配**
```rust
extern "C" {
    fn register_callback(callback: extern "C" fn(i32) -> i32);
}

fn my_callback(value: i32) -> i32 {  // 应该是 i64 或其他类型
    value + 1
}

fn setup_callback() {
    unsafe { register_callback(my_callback) };
}

// C 库传递 i64，但 Rust 期望 i32，高位被截断
```

**危险模式7：C 函数返回状态的逻辑反转**
```rust
extern "C" {
    fn c_check_permission(user_id: u32) -> i32;  // 0 = 无权限，1 = 有权限
}

fn has_permission(user_id: u32) -> bool {
    unsafe { c_check_permission(user_id) != 0 }  // 正确
}

fn has_permission_wrong(user_id: u32) -> bool {
    let result = unsafe { c_check_permission(user_id) } as u8;  // 转换可能改变语义
    result > 0  // 如果返回负数，as u8 可能出现意外
}
```

**危险模式8：C 数组长度由另一返回值指定**
```rust
extern "C" {
    fn c_get_array(out_len: *mut u32) -> *const i32;
}

unsafe fn get_array() -> Vec<i32> {
    let mut len: u32 = 0;
    let ptr = c_get_array(&mut len);
    let len_usize = len as usize;  // 长度转换，无上限检查
    std::slice::from_raw_parts(ptr, len_usize).to_vec()
}

// C 库返回长度为 u32::MAX，转换为 usize 后申请巨量内存
let array = unsafe { get_array() };
```

**危险模式9：C 函数返回指针的对齐假设**
```rust
extern "C" {
    fn c_get_aligned_buffer() -> *const u64;
}

fn read_u64_from_c() -> u64 {
    let ptr = unsafe { c_get_aligned_buffer() };
    unsafe { *ptr }  // 假设指针对齐到 8 字节
}

// C 库实际返回随意对齐的指针
let value = read_u64_from_c();  // 未定义行为
```

**危险模式10：C 字符串转换的长度溢出**
```rust
extern "C" {
    fn c_get_string() -> *const i8;
    fn c_get_string_len() -> u32;
}

unsafe fn get_rust_string() -> String {
    let len = c_get_string_len() as usize;
    let c_str = c_get_string();
    String::from_utf8_lossy(std::slice::from_raw_parts(c_str as *const u8, len)).into_owned()
}

// 返回长度为 u32::MAX，转换为 usize 后溢出
let s = unsafe { get_rust_string() };
```

### 快速定位核心操作 **[L1-L2]**

**关键词扫描:**
- FFI 函数签名：`extern "C" { fn ... }`、`#[link(...)]`
- 返回值转换：`as usize`、`as bool`、`as i32` 作用于 C 函数返回值
- 指针转换：`as *const T`、`as *mut T`、`from_raw_parts()`
- 长度/大小处理：返回值作为 `slice` 长度或 `Vec::with_capacity()` 参数
- 错误码检查：`!= 0`、`< 0`、`== -1` 与类型转换混合
- 回调注册：`register_callback()`、`set_handler()` 等
- C 类型映射：`c_uint`、`c_int`、`size_t` 等 libc 类型的使用
- 指针来源验证：来自 C 的指针是否需要 FFI 边界验证

**快速定位保护机制 [L2-L3]**
- 是否检查返回值范围：`if result < 0 || result > MAX { return Err(...) }`
- 是否区分错误码与成功值：文档中明确说明 C 函数的返回值含义
- 是否验证转换后的指针有效性：`if ptr.is_null() { return Err(...) }`
- 是否检查大小字段的合理性：`if size > MAX_ALLOCATION_SIZE { return Err(...) }`
- 是否使用 bindgen 生成的安全包装而非直接 FFI
- 是否在返回值用于关键操作前做二次验证
- 回调函数签名是否与 C 库声明完全一致
- 是否有 FFI 调用的文档说明和类型映射注释

---

## Classify

**研判为真漏洞的特征：**

1. C 函数返回值直接转换后用于关键操作（内存分配、索引、长度），无范围检查
2. 错误码与成功返回值未被区分，或转换时改变了语义
3. C 函数返回指针直接用于 `from_raw_parts()`，未检查对齐/有效性
4. 回调函数的类型签名与 C 库期望不匹配，参数会被误解
5. 大小/长度参数来自 C 返回值，无上限检查
6. 指针转换假设了对齐或有效期，但 C 库未保证
7. C 中的 `size_t` 被直接转为 `u32`，在 64 位系统上截断

**误报/代码异味的特征：**
- C 函数返回值明确为布尔值或固定错误码，转换后再验证
- 使用 bindgen 生成的安全包装或类型化接口
- 有详细的 FFI 文档注释说明返回值含义和类型映射
- 返回值在使用前都有显式的范围检查
- 指针返回值经过有效性验证（非空、对齐检查）
- 回调函数通过宏或类型系统保证签名正确
- 来自 C 的长度参数有上限检查

---

## Low risk

**以下场景可评为低风险：**

1. **返回值的明确验证**
   - 返回值在使用前检查：`if result < 0 { return Err(...) }`
   - 成功/失败码明确分离：`if result == 0 { /* success */ } else { /* error */ }`
   - 返回值用于内存操作前验证范围

2. **类型映射的明确文档**
   - FFI 函数签名有详细注释说明 C 类型与 Rust 类型的对应关系
   - 错误码含义和范围已文档化
   - 指针生命周期和所有权在文档中清晰说明

3. **使用生成的安全包装**
   - 使用 bindgen 生成的包装，避免手工 FFI 声明
   - 使用社区维护的 sys crate（如 `libc`、`winapi`）
   - 使用高级库（如 `libssh2-rust`）替代低级 FFI

4. **指针验证完整**
   - 返回指针经过非空检查：`if ptr.is_null() { return Err(...) }`
   - 指针对齐已验证：`assert_eq!(ptr.align_offset(align), 0)`
   - 指针返回的数据有生命周期保证或显式复制

5. **回调函数安全**
   - 回调函数通过类型系统保证签名正确（如 trait 对象）
   - 回调签名与 C 库声明完全一致
   - 回调参数类型映射在文档中明确说明

6. **大小字段的验证**
   - 来自 C 的长度/大小在使用前检查上限
   - 向下转换（如 u64 → u32）前检查值范围
   - 申请内存前验证 C 返回的大小

7. **FFI 边界隔离**
   - FFI 调用限制在专门的模块或 crate 内
   - 返回值进入 Rust 后立即包装为安全类型
   - 所有 unsafe 代码已通过 Miri 或代码审查验证
