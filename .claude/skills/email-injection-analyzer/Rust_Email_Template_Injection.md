# Rust Email Template Injection

## Details

Rust 应用使用模板引擎（如 Tera、Handlebars、Askama）渲染邮件内容时，若用户输入直接嵌入模板未经转义，攻击者可注入模板指令。虽然 Rust 的类型系统提供了一定保护，但模板注入仍可能导致信息泄露或邮件内容篡改。

**代码示例与审计要点**

```rust
use tera::{Tera, Context};
use handlebars::Handlebars;

// 危险：用户输入拼接到模板字符串（Tera）
let template_str = format!("Hello {}, your code is: {{{{ code }}}}", user_name);
let mut tera = Tera::default();
tera.add_raw_template("email", &template_str).unwrap();
let html = tera.render("email", &context).unwrap();

// 危险：允许用户提供模板内容
let user_template = get_user_input();
let mut tera = Tera::default();
tera.add_raw_template("email", &user_template).unwrap();

// 危险：Handlebars 未转义
let mut handlebars = Handlebars::new();
handlebars.register_escape_fn(handlebars::no_escape);
handlebars.register_template_string("email", user_template).unwrap();
```

**快速定位核心操作 (L1: 关键词扫描)**
- 搜索 `tera::Tera`、`handlebars::Handlebars`、`askama::Template`
- 查找 `.add_raw_template()`、`.register_template_string()`、`.render()`
- 定位字符串拼接：`format!()`、`+` 拼接用户输入
- 检查 `.register_escape_fn()` 的使用

**快速定位保护机制 (L2: 跳读)**
- 检查是否使用默认转义（Tera、Handlebars 默认转义 HTML）
- 查找模板文件加载：`.add_template_file()`、`from_dir()`
- 搜索手动转义：`html_escape()`、自定义转义函数
- 查看是否禁用转义：`register_escape_fn(no_escape)`、`{{{ }}}` 语法

---

## Classify

**理论研判标准**

1. **确认为漏洞的标志**：
   - 用户输入直接拼接到模板字符串中
   - 允许用户提供完整的模板内容
   - 使用 `register_escape_fn(no_escape)` 禁用转义
   - 在 Handlebars 中使用 `{{{ }}}` 语法禁用转义
   - 可能导致模板逻辑篡改或信息泄露

2. **确认为误报的情况**：
   - 模板完全从文件系统加载，用户输入仅作为上下文数据
   - Tera 或 Handlebars 使用默认转义设置
   - 所有用户输入经过手动 HTML 转义
   - Askama 编译时模板（类型安全）

3. **代码异味判断**：
   - 使用 `{{{ }}}` 或 `| safe` 过滤器禁用转义
   - 模板中可访问敏感对象或函数
   - 转义仅在部分代码路径中执行

---

## Low risk

**这些情况应给予低风险评级**

1. **静态模板**：所有邮件模板从文件系统加载（`from_dir()`），用户输入仅作为数据变量

2. **编译时模板**：使用 Askama 的编译时模板，提供类型安全和自动转义

3. **自动转义**：Tera 或 Handlebars 使用默认转义设置，不使用 `no_escape`

4. **输入转义**：所有用户输入在传入模板前都经过 HTML 转义函数处理

5. **纯文本邮件**：仅发送纯文本邮件，不使用 HTML 模板，模板注入风险降低
