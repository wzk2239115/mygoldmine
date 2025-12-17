# Rust 自定义反序列化器 UAF

**漏洞概述**  
在 Rust 中实现自定义 `Deserialize` trait 时,若 `unsafe` 代码中存在生命周期管理错误、所有权转移缺陷或原始指针误用,可能导致 Use-After-Free（UAF）漏洞。常见于手动内存管理、与 C FFI 交互、`transmute` 类型转换、`from_raw_parts` 构造切片等场景。

---

## Details

### 典型代码示例

**危险：自定义 Deserialize 中 unsafe 生命周期错误**
```rust
use serde::{Deserialize, Deserializer};
use std::slice;

struct Buffer {
    ptr: *mut u8,
    len: usize,
}

impl<'de> Deserialize<'de> for Buffer {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where D: Deserializer<'de> {
        let data = Vec::<u8>::deserialize(deserializer)?;
        let len = data.len();
        let ptr = data.as_ptr() as *mut u8;
        std::mem::forget(data); // 危险：忘记释放但保留指针
        Ok(Buffer { ptr, len }) // 触发点：返回悬垂指针
    }
}

// 使用时导致 UAF
impl Drop for Buffer {
    fn drop(&mut self) {
        unsafe {
            // 危险：双重释放或释放已释放内存
            Vec::from_raw_parts(self.ptr, self.len, self.len);
        }
    }
}
```

**危险：from_raw_parts 生命周期绑定错误**
```rust
impl<'de> Deserialize<'de> for CustomSlice<'de> {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where D: Deserializer<'de> {
        let bytes: &'de [u8] = Deserialize::deserialize(deserializer)?;
        unsafe {
            // 危险：假设字节对齐和有效性,构造引用
            let ptr = bytes.as_ptr() as *const MyStruct;
            let data = &*ptr; // 触发点：未验证内存布局
            Ok(CustomSlice { data })
        }
    }
}
```

**危险：transmute 配合外部数据**
```rust
impl<'de> Deserialize<'de> for RawData {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where D: Deserializer<'de> {
        let raw = Vec::<u8>::deserialize(deserializer)?;
        unsafe {
            // 危险：未验证长度/对齐,直接转换类型
            let data: Box<MyStruct> = std::mem::transmute(raw); // 触发点
            Ok(RawData { inner: data })
        }
    }
}
```

**危险：FFI 所有权转移错误**
```rust
#[repr(C)]
struct CData {
    ptr: *mut libc::c_void,
    size: usize,
}

impl<'de> Deserialize<'de> for CData {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where D: Deserializer<'de> {
        let data = Vec::<u8>::deserialize(deserializer)?;
        unsafe {
            let ptr = libc::malloc(data.len());
            std::ptr::copy_nonoverlapping(data.as_ptr(), ptr as *mut u8, data.len());
            // 危险：未正确管理 C 侧内存生命周期
            Ok(CData { ptr, size: data.len() }) // 触发点：谁负责释放?
        }
    }
}

// Drop 可能导致 double-free
impl Drop for CData {
    fn drop(&mut self) {
        unsafe { libc::free(self.ptr); } // 如果 C 侧已释放则 UAF
    }
}
```

**危险：临时对象引用逃逸**
```rust
impl<'de> Deserialize<'de> for RefHolder<'de> {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where D: Deserializer<'de> {
        let temp = String::deserialize(deserializer)?;
        let refer = temp.as_str(); // 危险：引用临时对象
        // temp 在函数结束时被 drop
        Ok(RefHolder { data: refer }) // 触发点：返回悬垂引用
    }
}
```

**危险：手动内存管理配合自定义 Visitor**
```rust
use serde::de::{Visitor, SeqAccess};

struct UnsafeVec {
    ptr: *mut i32,
    len: usize,
    cap: usize,
}

impl<'de> Visitor<'de> for UnsafeVecVisitor {
    type Value = UnsafeVec;
    
    fn visit_seq<A>(self, mut seq: A) -> Result<Self::Value, A::Error>
    where A: SeqAccess<'de> {
        unsafe {
            let mut ptr = libc::malloc(1024) as *mut i32; // 固定分配
            let mut len = 0;
            while let Some(value) = seq.next_element::<i32>()? {
                *ptr.add(len) = value; // 危险：未检查边界
                len += 1;
            }
            Ok(UnsafeVec { ptr, len, cap: 256 }) // 触发点：实际分配不匹配
        }
    }
}
```

**危险：条件编译与 unsafe 组合**
```rust
#[cfg(feature = "fast_deser")]
impl<'de> Deserialize<'de> for FastStruct {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where D: Deserializer<'de> {
        let bytes: &[u8] = Deserialize::deserialize(deserializer)?;
        unsafe {
            // 危险：Feature gate 后缺少审计,假设已验证
            let ptr = bytes.as_ptr() as *const FastStruct;
            Ok(std::ptr::read(ptr)) // 触发点：未检查长度/对齐
        }
    }
}
```

**危险：共享状态与 interior mutability**
```rust
use std::cell::UnsafeCell;

struct SharedBuffer {
    data: UnsafeCell<Vec<u8>>,
}

impl<'de> Deserialize<'de> for SharedBuffer {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where D: Deserializer<'de> {
        let vec = Vec::<u8>::deserialize(deserializer)?;
        Ok(SharedBuffer { data: UnsafeCell::new(vec) })
    }
}

// 危险：多线程访问可能导致数据竞争后 UAF
unsafe impl Sync for SharedBuffer {} // 触发点：错误声明线程安全
```

---

### 快速定位核心操作的技巧

**L1: 关键词扫描**
- `unsafe` 块（特别是在 `impl Deserialize` 内）
- 原始指针操作：`*const`、`*mut`、`as_ptr()`、`as_mut_ptr()`
- 内存操作：`std::ptr::read`、`std::ptr::write`、`copy_nonoverlapping`、`from_raw_parts`
- 类型转换：`transmute`、`transmute_copy`、`std::mem::forget`
- C FFI：`libc::malloc`、`libc::free`、`#[repr(C)]`
- 生命周期标记：`<'de>` 在自定义 `Deserialize` 实现中
- Drop trait：`impl Drop` 配合手动内存管理

**L2: 跳读识别高风险模式**
- **裸指针与生命周期**：`'de` 生命周期参数的结构体包含 `*mut T` 字段
- **forget 模式**：`std::mem::forget` 后保留指针引用
- **FFI 边界**：反序列化结果传递给 `extern "C"` 函数或从 C 代码接收指针
- **Visitor 自定义**：实现 `Visitor` trait 且包含 `unsafe` 块
- **条件 unsafe**：`#[cfg(...)]` 条件编译包裹的 `unsafe` 代码（审计易遗漏）
- **泛型 + unsafe**：泛型类型 `T` 在 `unsafe` 块中通过 `transmute` 转换
- **测试覆盖缺失**：自定义 `Deserialize` 但 `tests/` 中无相关 Miri 测试

**L3: 逐行追踪生命周期与所有权**
- **引用来源验证**：`&'de [u8]` 是否确实绑定到反序列化数据源的生命周期
- **临时对象检查**：局部变量（`let temp = ...`）是否被引用后返回
- **所有权转移路径**：`Vec` → `into_raw_parts` → `from_raw_parts` 是否配对
- **双重释放风险**：同一指针在 `Drop` 和其他代码路径中被多次释放
- **对齐要求**：`#[repr(C)]` 结构体是否匹配 C 侧布局（使用 `std::mem::align_of` 验证）
- **长度一致性**：`from_raw_parts(ptr, len, cap)` 的三个参数是否来自可信源
- **悬垂指针传播**：返回的结构体字段是否包含已释放内存的指针

**L4: 跨模块追踪内存管理**
- **全局 unsafe 审计**：`rg "unsafe" --type rust` 枚举所有 unsafe 块
- **Drop 实现矩阵**：列出所有实现 `Drop` 的类型及其释放逻辑
- **Miri 测试覆盖**：CI 中是否运行 `cargo +nightly miri test`
- **静态分析工具**：使用 `cargo-geiger` 检测 unsafe 代码比例
- **Fuzzing 配合 sanitizer**：`cargo fuzz` + AddressSanitizer 检测 UAF
- **依赖 unsafe 溯源**：第三方 crate 的 `unsafe` 代码是否通过反序列化触发
- **宏展开审计**：`cargo expand` 检查 `#[derive(Deserialize)]` 生成的代码

---

### 快速定位保护机制的技巧

**L1: 关键词扫描防护措施**
- `#![forbid(unsafe_code)]`：模块级禁止 unsafe（但可能仅部分模块启用）
- `std::mem::ManuallyDrop`：显式管理生命周期,防止自动 drop
- `Pin<T>`：固定内存位置,防止移动后引用失效
- `PhantomData<&'de [u8]>`：正确绑定生命周期参数
- `zerocopy` crate：安全的零拷贝反序列化（`FromBytes`、`AsBytes`）
- `validator` + `#[validate]`：字段验证但不直接防 UAF

**L2: 跳读检查生命周期绑定**
```rust
// 安全：使用 PhantomData 正确标记生命周期
struct SafeSlice<'de> {
    data: &'de [u8],
    _marker: PhantomData<&'de [u8]>,
}

// 安全：使用 ManuallyDrop 控制释放时机
struct ControlledDrop {
    data: ManuallyDrop<Vec<u8>>,
}

impl Drop for ControlledDrop {
    fn drop(&mut self) {
        unsafe {
            // 显式释放,防止双重 drop
            ManuallyDrop::drop(&mut self.data);
        }
    }
}

// 安全：zerocopy 零拷贝验证
use zerocopy::{FromBytes, AsBytes};

#[derive(FromBytes, AsBytes)]
#[repr(C)]
struct SafeStruct {
    field: u32,
}

fn safe_deserialize(bytes: &[u8]) -> Option<&SafeStruct> {
    SafeStruct::ref_from(bytes) // 编译期验证对齐和大小
}
```

**L3: 逐行分析内存安全边界**
- **ManuallyDrop 配对**：每个 `ManuallyDrop::new` 是否对应 `ManuallyDrop::drop`
- **Pin 使用正确性**：`Pin<Box<T>>` 是否确保 T 不移动（配合 `!Unpin`）
- **借用检查器辅助**：尽量避免 unsafe,让编译器验证生命周期
- **RAII 封装**：unsafe 代码封装在安全接口后,不暴露原始指针
- **单元测试 + Miri**：关键函数必须通过 Miri 的 UAF/leak 检测
- **文档注释**：`/// # Safety` 明确说明 unsafe 前提条件

**L4: 全局内存安全保障**
- **CI 强制 Miri**：`.github/workflows/` 中包含 `cargo +nightly miri test`
- **Fuzzing 持续运行**：OSS-Fuzz 或自建 fuzzing 基础设施
- **AddressSanitizer**：`RUSTFLAGS="-Z sanitizer=address"` 编译并测试
- **依赖审计**：`cargo-geiger` 检查依赖中的 unsafe 比例
- **代码审查检查清单**：
  - 所有 unsafe 块必须附带 Safety 注释
  - 自定义 Deserialize 必须通过 Miri 测试
  - Drop 实现必须审查双重释放风险
  - FFI 边界必须明确所有权转移规则
- **类型系统强化**：
  - 优先使用 `Cow<'de, [u8]>` 而非裸指针
  - 使用 `&'de [u8]` 而非 `(*const u8, usize)` 组合
  - 用 `Box<[T]>` 而非 `Vec` + `into_raw_parts` 管理堆内存

---

## Classify

### 漏洞（True Positive）判定条件
1. **unsafe 代码存在**：自定义 `Deserialize` 实现包含 `unsafe` 块且操作原始指针或内存
2. **生命周期错误**：返回的引用/指针绑定到已释放的临时对象或栈内存
3. **所有权转移缺陷**：`forget` 或 `into_raw_parts` 后未正确配对 `from_raw_parts`,或重复释放
4. **可达性确认**：代码路径可通过正常反序列化触发（非死代码）
5. **实际危害**：可导致程序崩溃、内存损坏、信息泄露（读已释放内存）、或 RCE（覆盖函数指针）

### 误报（False Positive）判定条件
1. **无 unsafe 代码**：使用 `#[derive(Deserialize)]` 且未自定义实现,依赖 serde 生成的安全代码
2. **生命周期正确**：`PhantomData` 正确绑定,借用检查器验证通过,无编译警告
3. **RAII 封装完善**：`ManuallyDrop`/`Pin` 正确使用,所有资源在 `Drop` 中安全释放
4. **Miri 测试通过**：关键路径通过 `cargo miri test` 且无 UAF/leak 报告
5. **零拷贝库**：使用 `zerocopy`、`bytemuck` 等编译期验证内存布局的库
6. **代码不可达**：仅在测试代码或 `#[cfg(test)]` 中,或已废弃的 feature gate 后

### 代码异味（Code Smell）判定条件
1. **过度 unsafe**：可用安全抽象（如 `Cow`、`Box`）但选择手动管理指针
2. **缺少 Safety 注释**：`unsafe` 块未说明前提条件（对齐、非空、有效生命周期）
3. **条件编译 unsafe**：`#[cfg(feature = "...")]` 包裹的 unsafe 代码,易被审计遗漏
4. **复杂生命周期**：多个 `'de` 相关生命周期参数且逻辑复杂,难以验证正确性
5. **缺乏测试**：自定义 `Deserialize` 无对应单元测试或 Miri 测试
6. **FFI 文档缺失**：与 C 代码交互但未明确所有权转移规则（谁分配/谁释放）
7. **Drop 不对称**：实现 `Drop` 但释放逻辑与构造逻辑不对称（如分配 1024 字节但释放按 `len` 释放）

### 研判技巧
- **向上追溯数据流**：反序列化数据 → unsafe 操作 → 返回值 → 使用位置（是否悬垂）
- **生命周期标注审查**：手工验证 `'de` 参数是否确实覆盖所有引用字段
- **Miri 快速验证**：`cargo +nightly miri test --test 可疑函数` 快速检测 UAF
- **对比生成代码**：`cargo expand` 对比自定义实现与 `#[derive(Deserialize)]` 生成代码
- **压力测试**：大量反序列化 + 随机 drop,观察是否触发 double-free
- **Fuzzing 驱动**：编写 fuzz target 专门测试自定义 Deserialize,配合 ASan

---

## Low Risk

### 低风险场景判定

**完全避免 unsafe 代码**
- 所有结构体使用 `#[derive(Deserialize)]`,无自定义实现
- 项目启用 `#![forbid(unsafe_code)]`,编译器强制禁止 unsafe
- 依赖库无 unsafe 代码（使用 `cargo-geiger` 验证）

**正确的生命周期管理**
- 使用 `Cow<'de, [u8]>` 而非裸指针,由类型系统保证生命周期
- `PhantomData<&'de T>` 正确标记所有借用关系
- 借用检查器无警告,所有生命周期参数由编译器验证

**零拷贝安全库**
- 使用 `zerocopy` crate 的 `FromBytes` trait,编译期验证内存布局
- 使用 `bytemuck` 的 `Pod` trait,确保 zero-copy 安全性
- 使用 `rkyv` 的零拷贝反序列化（无需解析直接访问）

**严格的测试覆盖**
- 所有自定义 `Deserialize` 必须通过 Miri 测试（`cargo +nightly miri test`）
- CI/CD 强制运行 AddressSanitizer（`RUSTFLAGS="-Z sanitizer=address"`）
- Fuzzing 持续运行覆盖反序列化路径（`cargo-fuzz` + libFuzzer）

**RAII 与安全封装**
- unsafe 代码封装在私有模块,仅暴露安全 API
- 使用 `ManuallyDrop` 显式控制释放时机,防止自动 drop
- `Drop` trait 实现经过严格审查,确保无双重释放

**架构层隔离**
- 反序列化在独立沙箱进程执行（使用 `seccomp`、`landlock` 限制系统调用）
- 内存限制：使用 cgroup 限制进程内存,防止 exploit 扩大影响
- 监控异常：捕获 SIGSEGV 信号,记录崩溃栈（`backtrace` crate）

**代码审计保障**
- 代码审查清单强制检查所有 unsafe 块的 Safety 注释
- 定期运行 `cargo-geiger` 审计 unsafe 代码比例趋势
- 依赖更新自动检测（`cargo-audit` + Dependabot）

**已知安全实现**
- 仅反序列化固定布局的 `#[repr(C)]` 结构体且经过 `zerocopy` 验证
- 使用 `serde_bytes` 的 `ByteBuf` 而非手动管理 `Vec<u8>`
- FFI 边界使用 `Box::into_raw` / `Box::from_raw` 配对,明确所有权转移

**业务逻辑限制**
- 反序列化数据仅用于只读查询,不修改全局状态
- 数据源完全可信（内部服务生成,经过签名验证）
- 即使发生 UAF,沙箱环境无法利用（只读文件系统、无网络、无敏感数据）

**降级评估建议**
- 即使低风险,也应在每个 unsafe 块添加详细 Safety 注释
- 定期审计第三方 crate 的 unsafe 代码更新（订阅 RustSec Advisory）
- 推动重构：用 `Cow`/`Box` 替换裸指针,用安全抽象替换 unsafe
- 文档记录为何需要 unsafe（性能关键路径、FFI 必需等）
