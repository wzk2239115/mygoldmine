# Rust_SSTI_Custom_Macro_User_Input

**漏洞类型**: Rust 自定义模板宏中用户输入作为模板内容导致代码注入

---

## Details

### 代码示例

**易受攻击的代码模式**:
```rust
// 使用 proc_macro 动态生成代码（极少见但理论存在）
// 注意：Rust 的类型安全和编译时特性使传统 SSTI 很难出现
// 此场景主要涉及不安全的动态代码生成

// 场景1：动态生成模板（非标准，仅用于说明）
use std::fs;
let user_template = req.body_string().unwrap();
// 假设有不安全的动态编译机制
unsafe_compile_template(&user_template);

// 场景2：format! 宏滥用（有限风险）
let user_input = get_query_param("field");
let output = format!("{}", user_input); // 相对安全，但可能导致其他问题

// 场景3：eval crate 使用（极不推荐）
use eval::eval;
let code = request.get_param("code");
eval(code).unwrap(); // 极其危险

// 场景4：自定义模板字符串处理
let template_str = user_input;
custom_template_render(template_str); // 取决于实现
```

### 快速定位核心操作 **[L1-L2]**

**L1 关键词扫描**:
- 危险 crate: `eval`, 不安全的动态编译库
- 宏使用: `macro_rules!`, `proc_macro`
- 不安全代码: `unsafe`, `std::mem::transmute`
- 用户输入: `request.body()`, `params.get()`, `query()`
- 字符串操作: `format!`, `write!`, `println!`

**L2 跳读定位**:
- 搜索 `eval` crate 或类似动态执行库
- 检查是否有自定义的模板字符串解析
- 定位 unsafe 块中的代码生成逻辑
- 追踪用户输入到字符串处理的流程
- 关注 proc_macro 的使用场景

### 快速定位保护机制 **[L2-L4]**

**L2 跳读检测**:
- 类型系统: Rust 的强类型系统天然防护
- 编译时检查: 大多数注入在编译时即被阻止
- 无 eval: 标准 Rust 不支持动态代码执行
- 输入验证: 使用 serde 等库进行类型安全解析
- 模板引擎: 使用安全的模板库如 Askama、Tera

**L3 逐行分析**:
- Crate 依赖:
  - 是否使用了 `eval` 或类似的不安全 crate
  - 模板引擎 crate 的安全配置
  - 是否有自定义的不安全模板处理
- 代码生成:
  - proc_macro 是否处理用户输入
  - build.rs 中是否有动态代码生成
  - 是否有运行时代码编译
- 字符串处理:
  - format! 等宏的参数来源
  - 是否有字符串拼接后执行的逻辑
  - 自定义模板解析器的实现
- unsafe 块:
  - unsafe 代码是否涉及字符串处理
  - 是否有内存不安全操作
  - FFI 调用是否安全

**L4 跨模块追踪**:
- 追踪从 HTTP 请求 → 路由 → 处理函数的数据流
- 检查 Cargo.toml 中的危险依赖
- 验证模板文件的加载和编译过程
- 检查 build 脚本的安全性
- 追踪自定义宏和 proc_macro 的实现

---

## Classify

### 漏洞判定标准

**确认为漏洞**:
- 使用 `eval` crate 执行用户输入
- 自定义模板引擎处理用户可控代码
- unsafe 块中进行不安全的字符串到代码转换
- proc_macro 在运行时处理用户输入
- FFI 调用传递未验证的用户输入

**误报判定**:
- 使用标准 Rust 模板库且配置安全
- 仅使用 format! 等安全宏处理字符串
- 所有用户输入经过类型安全的 serde 解析
- 模板完全在编译时确定
- Rust 的类型系统提供了足够保护

**代码异味**:
- 使用了不常见的动态代码执行 crate
- 大量 unsafe 代码且未经审计
- 自定义模板解析器实现复杂
- 字符串拼接后传递给不安全函数
- 使用了过时或不安全的依赖
- build.rs 中有复杂的代码生成逻辑

---

## Low risk

### 低风险场景

**功能与权限隔离**:
- 功能仅限管理员使用
- 需要强身份验证
- 部署在隔离环境
- 严格访问控制

**架构设计防护**:
- 使用安全的模板引擎如 Askama
- 完全依赖 Rust 的类型系统
- 禁用或移除 eval 等危险 crate
- 模板在编译时验证

**输入与输出保护**:
- 所有输入经过 serde 类型安全解析
- 使用 validator crate 验证数据
- 模板内容完全静态定义
- 输出经过适当的转义处理

**监控与运行环保**:
- 应用在受限容器中运行
- 依赖定期安全扫描
- 完整审计日志
- 实时监控异常行为
