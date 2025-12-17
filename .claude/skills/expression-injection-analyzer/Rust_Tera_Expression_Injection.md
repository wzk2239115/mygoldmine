# Rust Tera 模板表达式注入

**漏洞成因**：Tera 模板引擎中用户输入直接嵌入模板表达式，导致服务端模板注入（SSTI）。攻击者可通过 Tera 的表达式访问对象属性、调用方法或执行 Rust 代码。常见于邮件模板、HTML 报告生成、用户自定义模板等场景。

---

## Details

**代码示例**：
```rust
// 危险：用户输入作为模板内容
use tera::Tera;

let user_template = request.body.template;
let mut tera = Tera::new("templates/*").unwrap();
tera.add_raw_template("user", &user_template)?;
let result = tera.render("user", &context)?;

// 危险：模板注入载荷
// user_template = "{{ config.database_password }}"
// user_template = "{% for item in env %}{{ item }}{% endfor %}"

// 较安全：使用文件加载器加载预定义模板
use tera::Tera;

let tera = Tera::new("templates/**/*.html")?;
let result = tera.render("template.html", &context)?;

// 较安全：限制模板访问的上下文
use tera::{Context, Value};

let mut context = Context::new();
context.insert("user_name", &user_name);  // 仅传递必要数据
// 不暴露 config、env 等危险对象
let result = tera.render("template.html", &context)?;
```

**快速定位核心操作**：
- 关键词：`add_raw_template`、模板渲染、用户模板处理、上下文对象
- 查看是否存在 `add_raw_template` 被用于加载用户提供的内容
- 检查模板上下文中暴露了哪些对象
- 追踪是否存在模板访问敏感属性的风险
- 关注是否使用了自定义过滤器或全局函数

**快速定位保护机制**：
- 是否使用文件系统加载器而非 `add_raw_template`
- 是否限制了模板可访问的上下文对象
- 是否禁用了危险的过滤器或方法访问
- 是否对模板内容进行了白名单验证
- 是否启用了自动转义

**审计等级**：**L2-L3**
- **L2**：跳读模板加载和渲染代码
- **L3**：逐行分析上下文对象和模板权限

---

## Classify

**确认为漏洞**：
- 使用 `add_raw_template` 加载用户提供的模板内容
- 模板上下文中暴露了敏感对象（配置、环境变量、系统对象）
- 不存在模板内容的白名单验证
- 允许访问对象的私有属性或调用危险方法

**误报**：
- 所有模板都从文件系统加载
- 用户仅能提供数据，不能编辑模板
- 上下文严格限制，仅包含展示数据
- 自动转义启用且配置完整

**代码异味**：
- 模板处理逻辑复杂，难以追踪变量来源
- 自定义过滤器实现不规范

---

## Low Risk

以下情况可评为低风险：
- **文件系统加载**：所有模板都从文件系统加载
- **受限上下文**：模板仅访问显式传递的安全数据
- **自动转义**：启用了自动 HTML 转义
- **内网模板编辑**：仅由内部可信开发者编辑
- **静态模板**：所有模板在部署时确定，运行时不修改

**注意**：使用 Rust 的类型系统可在编译期提供一定保护。
