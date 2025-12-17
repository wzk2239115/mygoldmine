# Rust 代码注入：unsafe 块执行用户输入

## Details

### 漏洞成因

Rust 中的 `unsafe` 块绕过了编译器的内存安全检查，允许执行本质上危险的操作（如原始指针解引用、FFI 调用、可变静态变量访问等）。当 `unsafe` 块处理用户输入时，攻击者可能通过精心构造的输入触发内存安全漏洞、任意代码执行或系统崩溃。关键风险在于：(1) `unsafe` 代码的不安全性来自程序员的手工验证，而非编译器保证；(2) 用户输入的多样性可能超出开发者的预期；(3) FFI 调用涉及 C 库的漏洞继承问题。

### 代码示例

```rust
// 危险示例 1：FFI 调用中的用户输入
use std::ffi::CString;

extern "C" {
    fn system(cmd: *const i8) -> i32;
}

fn execute_command(user_cmd: &str) {
    // 未验证用户输入，直接传递给 C system() 函数
    let c_str = CString::new(user_cmd).unwrap();
    unsafe {
        system(c_str.as_ptr());  // 用户可注入 shell 命令
    }
}

// 危险示例 2：原始指针解引用
fn process_pointer(ptr_addr: u64, data: &[u8]) {
    // 用户输入的地址，无验证直接解引用
    let ptr = ptr_addr as *const u8;
    unsafe {
        // 可能导致读取任意内存或崩溃
        let _value = *ptr;
        std::ptr::copy_nonoverlapping(ptr, data.as_ptr() as *mut u8, data.len());
    }
}

// 危险示例 3：可变静态变量竞态条件
static mut COMMAND_BUFFER: [u8; 256] = [0; 256];

fn store_command(user_input: &str) {
    if user_input.len() > 256 {
        return;  // 长度检查不充分
    }
    unsafe {
        // 无锁保护，多线程环境下导致 TOCTOU 竞态
        let cmd_slice = &mut COMMAND_BUFFER[..user_input.len()];
        cmd_slice.copy_from_slice(user_input.as_bytes());
    }
}

// 危险示例 4：内存初始化不完全
fn parse_structured_data(user_data: &[u8]) -> MyStruct {
    let mut obj: MyStruct;
    unsafe {
        // 未初始化的内存读取
        obj = std::mem::MaybeUninit::uninit().assume_init();
        std::ptr::copy_nonoverlapping(
            user_data.as_ptr(),
            &mut obj as *mut MyStruct as *mut u8,
            user_data.len()
        );
    }
    obj
}
```

### 快速定位核心操作 `[L1:关键词扫描]`

**关键函数和模式识别：**
- 搜索关键字：`unsafe`、`extern "C"`、`FFI`、`*const`、`*mut`、`assume_init()`、`transmute()`、`copy_nonoverlapping()`
- 示例搜索模式：
  ```
  unsafe\s*{
  extern\s+"C"
  *const\s+\w+.*as\s+\*
  *mut\s+\w+.*as\s+\*
  transmute<.*>
  copy_nonoverlapping\(
  assume_init\(\)
  static\s+mut\s+
  ```

**危险标记：**
- `unsafe` 块中包含来自用户输入的变量
- FFI 调用（`extern "C"`）的参数来自用户数据
- 原始指针的地址、长度来自用户输入或不可信源
- 内存操作（`copy_nonoverlapping`、`write`、`read`）涉及用户数据
- 可变全局变量（`static mut`）在 `unsafe` 块中被修改

**详细定位技巧 `[L2:跳读]`：**
- 定位每个 `unsafe` 块后，回溯查找其参数、变量来源
- 追踪用户输入的传播路径到 `unsafe` 块的使用点
- 标记 `unsafe` 块中哪些操作依赖于用户数据的长度、大小或内容
- 检查是否存在多个 `unsafe` 块或嵌套的 `unsafe` 操作
- 对于 FFI 调用，需要理解底层 C 函数的行为和限制

### 快速定位保护机制 `[L3:逐行读]`

**输入验证层：**
- 搜索在 `unsafe` 块前的验证逻辑
  ```rust
  // 有效的保护示例
  if user_input.len() > MAX_LEN || !is_valid_format(user_input) {
      return Err("Invalid input");
  }
  unsafe { /* 使用 user_input */ }
  ```
- 检查是否有显式的长度、大小、格式验证
- 验证是否存在白名单检查或字符集限制
- 对于指针地址，检查是否验证了地址的有效性和可访问性

**内存安全保护：**
- 搜索关键字：`validate_ptr`、`is_valid_ptr`、`bounds_check`、`verify`
- 检查是否使用了 `Option<T>` 或 `Result<T, E>` 包裹 `unsafe` 操作
- 查看是否使用了安全包装（safe wrapper）来限制 `unsafe` 的使用范围
  ```rust
  // 安全包装示例
  pub struct SafeFFIWrapper;
  impl SafeFFIWrapper {
      pub fn safe_call(input: &str) -> Result<(), String> {
          // 在此进行充分验证
          validate_input(input)?;
          unsafe {
              // 内部 unsafe 调用
          }
          Ok(())
      }
  }
  ```

**环境隔离和权限控制：**
- 检查 `unsafe` 块是否在特定的、受限的上下文中执行
- 搜索是否有权限检查、身份验证等前置条件
- 查看是否使用了 sandboxing 或容器隔离来限制 `unsafe` 代码的影响

**类型安全保障 `[L4:跨模块追踪]`：**
- 追踪用户输入通过整个调用链的类型转换过程
- 检查在类型转换（如 `as *const T`）时是否存在类型不匹配
- 验证 `transmute()` 操作是否正确处理了类型兼容性
- 确认 `unsafe` 块的前置条件是否在调用者可以满足

---

## Classify

### 确认为漏洞的必要条件

**漏洞判定流程：**

1. **用户输入可达 unsafe 块**：
   - 用户数据通过网络、文件、环境变量、命令行等渠道进入
   - 数据在经过零个或不充分的验证后到达 `unsafe` 代码
   - 输入影响 `unsafe` 操作的关键参数（指针地址、长度、内容）

2. **unsafe 操作的危险性评估**：
   - **FFI 调用**：调用的 C 函数本身是否存在漏洞（如缓冲区溢出、命令注入）
   - **内存操作**：是否可能导致越界读写、use-after-free、double-free
   - **类型转换**：`transmute()` 是否可能破坏类型安全不变式
   - **指针操作**：指针是否来自用户数据，是否进行了有效性检查

3. **验证充分性评估**：
   - **无验证**：用户输入直接传递 → 漏洞
   - **部分验证**：验证了部分属性但遗漏关键检查 → 可能是漏洞
   - **充分验证**：所有风险因素都被验证 → 低风险或误报

### 误报判定标准

- **用户输入在 unsafe 块前已完全验证**：
  - 白名单检查明确限制了可能的值范围
  - 长度和格式验证确保了数据的安全性
  - 类型转换时进行了完整的类型检查

- **unsafe 块处理的数据来自编译时常量或受信源**：
  - 配置文件中的值经过系统管理员审核
  - 硬编码的常量值
  - 内部数据结构生成的数据

- **unsafe 块被安全包装所保护**：
  - 存在公开的、经过充分验证的 API
  - 内部 `unsafe` 操作被限制在非公开的实现中
  - 所有公开接口都进行了充分的入参检查

- **FFI 调用的目标 C 函数已验证安全**：
  - C 函数不存在已知漏洞（如缓冲区溢出）
  - 参数经过充分的长度和有效性检查
  - 函数的返回值被正确处理

### 代码异味识别

- **多个连续的 unsafe 块**：表明可能需要更仔细的分析
- **深层的函数调用链**：用户输入通过多个函数传递到 `unsafe` 块
- **缺乏注释说明 unsafe 的必要性**：Rust 编译器要求 `unsafe` 操作前有安全性论证的注释
- **使用 `transmute()` 进行非平凡的类型转换**：风险更高
- **全局可变状态**（`static mut`）的使用：易导致线程安全问题
- **指针算术操作**（`offset`、`add`）：需要特别注意边界检查

---

## Low risk

### 低风险评级场景

**场景一：完整的输入验证和白名单**
- `unsafe` 块执行前，用户输入已通过严格的白名单验证
- 验证覆盖了所有可能的危险属性（长度、内容、格式、数值范围）
- 示例：在 FFI 调用前验证了命令字符串仅包含预期的命令选项
- 评级依据：验证确保了用户输入在安全范围内

**场景二：安全的 FFI 包装**
- `unsafe` FFI 调用被完整的安全包装所隐藏
- 公开 API 进行了充分的参数验证
- 底层 C 函数已验证无常见漏洞（如缓冲区溢出）
- 示例：使用 `std::ffi::CString` 的正确方式，验证了字符串长度和内容
- 评级依据：安全包装限制了 `unsafe` 代码的风险暴露

**场景三：受限的内存操作**
- 内存操作（如 `copy_nonoverlapping`）仅在已验证的缓冲区范围内进行
- 源和目标的大小、对齐、有效性都已明确检查
- 示例：复制操作前已验证了缓冲区边界
- 评级依据：边界检查消除了内存安全风险

**场景四：非用户可控的指针和地址**
- 指针地址、内存位置来自应用内部的可信数据结构
- 用户输入不影响指针的计算或解引用
- 示例：只有数据内容来自用户，指针来自内部对象
- 评级依据：攻击面被限制在数据而非地址

**场景五：严格的类型安全验证**
- 类型转换（如 `transmute()`）之前进行了完整的类型兼容性检查
- 转换后的数据被验证为合法的类型实例
- 示例：序列化/反序列化框架中的类型检查
- 评级依据：类型安全验证防止了类型混淆攻击

**场景六：隔离的执行上下文**
- `unsafe` 代码运行在沙箱、容器或低权限用户下
- 即使 `unsafe` 代码失败，损害范围也被限制
- 示例：在容器内运行 FFI 调用
- 评级依据：环境隔离限制了漏洞的影响范围

**场景七：非网络可达的输入源**
- 用户输入来自本地配置文件或应用内部存储
- 非通过网络或用户交互直接控制
- 示例：从数据库读取的配置参数
- 评级依据：攻击者无法通过常规网络通道控制输入

### 评级决策补充

- **部分验证的 FFI 调用**：如仅检查长度但未检查内容的有效性 → 中等风险或高风险
  - 例：验证了字符串长度但未检查是否包含命令注入字符

- **指针地址部分来自用户数据**：如虽验证了地址范围但未验证对齐 → 中等风险
  - 例：检查了地址不为 NULL 但未验证对齐和有效性

- **内存操作缺乏完整的边界检查**：仅检查了源或目标中的一个 → 中等风险或高风险
  - 例：验证了目标缓冲区大小但未验证源数据的实际大小

- **全局可变状态无锁保护**：`static mut` 在多线程环境中被访问 → 中等风险或高风险
  - 例：多个线程可能同时修改同一个 `static mut` 变量

- **复杂的类型转换链**：经过多层 `as` 或 `transmute()` → 需要详细分析
  - 例：用户输入经过多次类型转换后才用于 `unsafe` 操作
