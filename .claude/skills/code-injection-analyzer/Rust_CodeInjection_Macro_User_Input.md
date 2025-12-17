# Rust 宏展开执行用户输入代码注入审计指南

## 漏洞成因

Rust 宏在编译时进行文本替换和代码生成，当宏的输入来自用户可控的数据源时，攻击者可通过精心构造的输入注入恶意代码片段。虽然 Rust 的类型系统和所有权机制提供了内存安全保障，但声明式宏（`macro_rules!`）和过程宏（`#[derive(...)]`、属性宏、函数宏）处理用户输入时仍可能导致代码注入。关键风险在于：宏参数经字符串拼接、模板渲染或不安全的代码生成后被展开为实际代码，或通过反序列化 serde 触发宏展开。

---

## Details

### 代码示例

**危险模式1：字符串拼接生成宏调用**
```rust
// 用户输入直接参与宏生成
fn unsafe_macro_from_input(user_code: &str) {
    let code = format!("println!(\"{}\")", user_code);
    // 若此代码被通过 syn/quote 解析执行，可能注入
}

// Proc macro 接收不安全的输入
#[proc_macro]
pub fn dangerous_macro(input: TokenStream) -> TokenStream {
    let input_str = input.to_string();
    let expanded = quote! {
        fn generated() {
            #input_str  // 直接展开用户输入为代码
        }
    };
    expanded.into()
}
```

**危险模式2：通过 serde 反序列化触发宏展开**
```rust
// serde 在反序列化时可触发派生宏逻辑
#[derive(Deserialize)]
struct Config {
    code: String,  // 用户输入
}

// 若派生宏对 code 字段进行特殊处理（如代码生成）则存在风险
let user_input = r#"{ "code": "std::process::Command::new(...)" }"#;
let config: Config = serde_json::from_str(user_input)?;
```

**危险模式3：宏参数中含有变量插值**
```rust
macro_rules! eval_unsafe {
    ($expr:expr) => {
        {
            let result = $expr;  // 若 $expr 来自用户输入且未被宏验证
            result
        }
    };
}

// 调用时直接传入用户控制的表达式
fn process_user_input(user_expr: &str) {
    let parsed: syn::Expr = syn::parse_str(user_expr).ok()?;
    // 若 parsed 被直接用于宏展开，可能执行任意代码
}
```

**危险模式4：通过 quote! 宏进行代码生成**
```rust
use quote::quote;
use syn::{parse_str, Expr};

#[proc_macro]
pub fn generate_from_user(input: TokenStream) -> TokenStream {
    let user_input = input.to_string();
    // 若直接将用户字符串内容嵌入到 quote! 中
    let expanded = quote! {
        fn run() {
            #user_input  // 危险：用户输入被直接插入代码
        }
    };
    expanded.into()
}
```

### 快速定位核心操作 (L1-L3)

**L1 关键词扫描**：
- 搜索 `#[proc_macro]`、`#[proc_macro_derive]`、`#[proc_macro_attribute]` 声明
- 搜索 `macro_rules!` 定义，特别是参数中包含 `expr`、`tt`（token tree）等宽泛类型
- 搜索 `quote!`、`quote_spanned!` 宏调用，观察是否嵌入了动态变量
- 搜索 `syn::parse`、`syn::parse_str` 等解析调用，输入是否来自外部源
- 搜索 `#[derive(Deserialize)]`、`#[serde(...)]` 结合派生宏的使用
- 搜索 `format!`、字符串拼接用于生成代码片段的模式
- 搜索 `TokenStream::from_str`、`proc_macro2::TokenStream` 的动态构造

**L2 跳读**：
- 定位 proc macro 或 macro_rules! 的输入参数，确认其来源
- 检查输入参数是否直接来自 HTTP 请求、文件、数据库、环境变量等外部源
- 追踪参数在宏中的流向：是否被解析（`syn::parse`）、转换、直接展开
- 检查是否存在字符串拼接、格式化或模板渲染操作（`format!`、`format_args!`）
- 检查 `syn::Expr`、`syn::Item` 等 AST 节点的构造方式是否涉及用户输入
- 观察 `quote!` 宏中是否使用了 `#var` 形式的变量插值，这些变量的来源是否可信

**L3 逐行读**：
- 确认用户输入的确切来源（Web 请求、配置文件、网络协议、数据库等）
- 追踪输入从源头到宏参数的完整数据流，包括中间的转换步骤
- 验证是否存在输入验证、白名单检查、字符过滤
- 确认宏展开后的代码是否被编译执行，还是仅作文本处理
- 检查错误处理：输入解析失败时的行为（panic、返回 Err、继续执行）
- 分析宏的上下文：是否运行在编译时（proc macro）还是运行时（`syn::parse`）
- 检查是否使用了 `unsafe` 块，特别是与动态代码执行相关的部分

### 快速定位保护机制 (L2-L4)

**L2 跳读**：
- 检查输入参数在宏中的处理前是否有验证：`if`、`match`、`validate()`、`check_safety()`
- 搜索黑名单关键词：`unsafe`、`std::process`、`Command::new`、`system`、`eval`、`exec`、`exec!`
- 搜索白名单模式：`ALLOWED_IDENTIFIERS`、`PERMITTED_KEYWORDS`、`valid_tokens`、正则表达式检查
- 检查是否对 TokenStream 或 Expr 进行了结构验证（如 `syn::parse_str` 后的类型检查）
- 观察是否使用了来自 `syn` 或 `quote` 等安全库的构造函数

**L3 逐行读**：
- 分析白名单实现：是否完整覆盖所有允许的操作？可否被绕过（如注释、字符编码、大小写变体）？
- 分析黑名单实现：是否全面？可否使用字符串转义、连接（如 `std::` + `process`）、宏嵌套绕过？
- 检查 `syn::parse_str` 的错误处理：解析失败时是否直接 panic 或返回默认值？
- 分析 `quote!` 中的变量使用：哪些变量来自用户输入？是否直接作为代码插入？
- 检查是否对 TokenStream 进行了 `.to_string()` 再解析的操作（可能导致二次注入）
- 验证派生宏的字段属性处理（`#[serde(...)]`）是否存在代码生成逻辑

**L4 跨模块追踪**：
- 追踪自定义验证函数的实现：`validate_user_input()`、`sanitize_tokens()`、`is_safe_expression()` 等
- 检查是否有宏级别的输入验证框架或中间件
- 追踪 proc macro 或派生宏的依赖库（`syn`、`quote`、`darling` 等）是否使用了安全的 API
- 查找是否使用了 `proc_macro_error` 进行安全的错误报告
- 检查编译流程中是否使用了自定义的代码生成限制或沙箱
- 追踪是否有测试覆盖，特别是针对恶意输入的 fuzzing 或模糊测试
- 检查依赖版本是否已更新，是否存在已知的宏相关安全漏洞

---

## Classify

### 漏洞判定

- **用户输入直接被宏参数接收，未经验证即被 `quote!` 或字符串拼接展开为代码** → **确认漏洞**
  - 示例：`#[proc_macro] pub fn gen(input: TokenStream) { quote!(#input).into() }`，用户直接控制 input

- **通过 `syn::parse_str(user_input)` 解析后直接用于代码生成，无安全检查** → **确认漏洞**
  - 示例：`let expr: Expr = parse_str(user_input)?; quote!(#expr)` 直接展开为代码

- **声明式宏接受 `expr` 或 `tt` 类型的宽泛参数，且直接展开，无上下文限制** → **确认漏洞**
  - 示例：`macro_rules! run { ($code:expr) => { $code } }; run!(user_controlled_expr)`

- **派生宏或属性宏对 serde 属性、字段名进行代码生成，用户可通过 JSON/YAML 控制** → **确认漏洞**
  - 示例：通过反序列化为包含恶意字段名或属性的 struct，派生宏将其用于代码生成

- **宏展开后的代码被编译执行，且宏参数来自不可信源** → **确认漏洞**

### 误报判定

- **宏参数完全来自硬编码常量、编译时确定的值** → **误报**
  - 示例：`const SAFE_CODE: &str = "..."; macro_rules! m { () => { #SAFE_CODE } }`

- **虽然接收动态输入，但通过 `syn::parse_str` 后仅提取特定的 AST 节点类型（如仅允许 Ident）** → **误报**
  - 示例：`let ident: syn::Ident = parse_str(user_input)?; quote!(#ident)`（限制为标识符）

- **宏展开的结果仅用于编译期代码生成，最终代码不执行用户控制的操作** → **误报**
  - 示例：宏仅为结构体生成 Getters，不涉及命令执行或敏感操作

- **输入经过严格的白名单验证，白名单本身不可被篡改** → **误报**
  - 示例：`static ALLOWED: &[&str] = &["op1", "op2"]; if !ALLOWED.contains(op) { panic!() }; quote!(#op)`

- **使用 `proc_macro_error` 或类似机制安全报错，确保错误不会泄露敏感信息** → **误报**
  - 示例：通过 `compile_error!` 报错，而非 panic 或输出原始输入

### 代码异味

- **黑名单检查（而非白名单）危险关键字如 `unsafe`、`Command`** → **需进一步测试**
  - 可能被绕过（如注释、字符编码、宏内嵌套、模块别名）

- **宏参数使用 `expr` 或 `tt` 等宽泛类型，但仅进行字符串级黑名单过滤** → **需检查完整性**
  - 示例：`if !input_str.contains("unsafe") { ... }` 无法防止多层嵌套或编码绕过

- **依赖第三方派生宏库（如 `serde`、`diesel`），未明确验证其安全性** → **需追踪依赖**
  - 示例：使用 `#[serde(default)]` 或自定义属性时，应检查库的版本和安全公告

- **编译期与运行期混淆**：宏展开用于编译期，但参数来自运行时数据源** → **架构风险**
  - 示例：虽然宏本身无法在运行时执行，但通过持久化的代码生成（如 build.rs）可能被利用

- **使用 `unsafe` 块但未充分文档化其安全边界** → **需人工复核**

### 审计等级

- **L0**：宏仅使用硬编码常量，无用户输入接触，快速跳过
- **L1**：存在 proc macro 或 macro_rules! 定义，进行关键词扫描确认输入来源
- **L2**：发现用户输入流向宏参数，跳读数据流和初步防护机制
- **L3**：确认存在代码生成或展开操作，逐行读取验证逻辑和 AST 处理
- **L4**：需追踪多文件、多层宏嵌套的数据流，以及第三方派生宏库的实现

---

## Low risk

### 低风险场景

- **严格的输入白名单**：通过 `match` 或 `if-else` 仅允许预定义的字符串、标识符、操作符，如 `const ALLOWED_OPS: &[&str] = &["add", "sub", "mul"];`，且白名单在代码中硬编码

- **限制宏参数类型**：使用 `syn::Ident`、`syn::Path`、`syn::Type` 等具体 AST 节点类型替代 `expr` 或 `tt`，并通过 `syn::parse_str` 严格解析，如 `let ident: syn::Ident = parse_str(input)?;`

- **仅编译期代码生成，无运行时执行**：宏展开仅生成类型定义、函数签名、常量，不涉及命令执行、文件操作、网络请求等敏感操作

- **完整的 AST 验证**：对 `syn::parse_str` 后的 AST 进行结构化验证，如仅允许特定的表达式类型（`Expr::Binary`、`Expr::Call` 等），拒绝 `Expr::Unsafe`、宏调用等

- **派生宏隔离**：派生宏仅为预定义的字段生成代码，不依赖字段名或属性值进行代码生成，字段名通过 Rust 标识符规则天然限制

- **使用 `proc_macro_error` 进行安全报错**：所有错误通过 `compile_error!` 或 `emit_error!` 报告，避免直接 panic 或输出原始输入

- **完整的单元测试和 Fuzzing**：对宏参数进行了大量测试，包括边界情况、特殊字符、长输入，以及使用 `cargo-fuzz` 进行自动化模糊测试

- **依赖版本管理**：所有依赖通过 `Cargo.lock` 锁定版本，定期运行 `cargo audit` 检查已知漏洞，派生宏库（如 `serde`、`diesel`）版本最新

### 注意事项

即使满足低风险条件，仍应在审计报告中说明：
- 宏展开本身属于高级功能，即使当前实现相对安全，仍建议定期复核，特别是在升级依赖库时
- 应明确文档记录哪些宏参数来自用户，哪些来自硬编码，以防未来维护者误判
- 建议在 proc macro 的入口处添加防御性的检查，如 `assert!` 验证输入结构
- 如需从外部源（如 HTTP、数据库、配置文件）接收宏参数，应优先考虑使用非宏的替代方案（如 Builder 模式、配置库、插件系统），而非直接通过宏处理
- 对于派生宏，应限制自定义属性的解析，避免通过属性进行隐式的代码生成
