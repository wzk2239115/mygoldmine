# Rust_SSTI_Tera_Unescaped_Input

**漏洞类型**: Tera 模板引擎中用户输入未转义导致的注入

---

## Details

### 代码示例

**易受攻击的代码模式**:
```rust
// Tera 是运行时模板引擎，需要注意安全配置

// 场景1：禁用自动转义
use tera::{Tera, Context};
let mut tera = Tera::new("templates/**/*").unwrap();
tera.autoescape_on(vec![]); // 禁用所有自动转义

// 场景2：使用 safe 过滤器
let mut context = Context::new();
context.insert("user_input", &req.param("data"));
// 模板中: {{ user_input | safe }}

// 场景3：模板字符串包含用户输入
let template_str = format!("Hello {{}}", req.param("name"));
tera.add_raw_template("dynamic", &template_str).unwrap();

// 场景4：模板路径用户可控（有限风险）
let template_name = req.param("template");
tera.render(&format!("{}.html", template_name), &context).unwrap();

// 场景5：Context 包含复杂对象
context.insert("obj", &dangerous_object); // 可能暴露方法
```

### 快速定位核心操作 **[L1-L2]**

**L1 关键词扫描**:
- Tera 类: `Tera::new()`, `Tera::default()`
- 渲染方法: `.render()`, `.render_str()`, `.add_raw_template()`
- Context: `Context::new()`, `.insert()`
- 过滤器: `| safe`, `| escape`
- 配置: `.autoescape_on()`, `.autoescape_off()`

**L2 跳读定位**:
- 从用户输入追踪到 Context.insert()
- 检查 autoescape 配置
- 搜索 `| safe` 过滤器使用
- 定位 add_raw_template 的模板来源
- 关注 render 的模板名称参数

### 快速定位保护机制 **[L2-L4]**

**L2 跳读检测**:
- 自动转义: autoescape_on 默认启用
- 模板白名单: 模板名称白名单验证
- Context 限制: 仅插入安全的基本类型
- 模板预加载: 使用 Tera::new() 预加载
- 输入验证: 数据经过验证后插入 Context

**L3 逐行分析**:
- Tera 初始化:
  - autoescape_on 是否包含所有文件类型
  - 模板目录是否受限
  - 是否使用了安全的默认配置
- Context 内容:
  - insert 的值类型（String vs 复杂对象）
  - 是否包含用户可控的危险对象
  - 数据是否经过验证和类型转换
- 过滤器使用:
  - 模板中是否使用 `| safe`
  - 自定义过滤器实现是否安全
  - 过滤器链配置是否正确
- 模板加载:
  - 是否使用 add_raw_template（危险）
  - render 的模板名是否可控
  - 模板文件路径是否验证

**L4 跨模块追踪**:
- 追踪从请求 → Context构建 → 模板渲染的流程
- 检查全局 Tera 实例的配置
- 验证自定义过滤器和函数的实现
- 检查模板文件的内容
- 追踪模板名称和路径的构造

---

## Classify

### 漏洞判定标准

**确认为漏洞**:
- autoescape 被禁用或配置不当
- 使用 `| safe` 输出用户可控数据
- add_raw_template 使用用户输入
- Context 包含危险对象或未验证数据
- 模板名称可被用户控制导致路径遍历

**误报判定**:
- autoescape 启用且配置正确
- 无 `| safe` 使用或仅用于可信数据
- 模板全部预加载，名称经白名单验证
- Context 仅包含基本类型数据
- 所有输入经过严格验证

**代码异味**:
- 大量使用 `| safe` 过滤器
- autoescape 配置复杂或不清晰
- Context 包含复杂的业务对象
- 自定义过滤器未经安全审计
- 模板名称通过字符串拼接构造
- Tera 版本过低存在已知问题

---

## Low risk

### 低风险场景

**功能与权限隔离**:
- 模板渲染仅限内部使用
- 需要强身份验证
- 功能部署在隔离环境
- 严格访问控制

**架构设计防护**:
- 强制启用 autoescape
- 模板全部预加载并缓存
- Context 仅包含安全的 DTO
- 实现 CSP 策略

**输入与输出保护**:
- 模板名称严格白名单验证
- 禁止使用 add_raw_template
- Context 数据经过类型验证
- 所有用户输入转义后插入

**监控与运行环保**:
- 模板文件权限严格控制
- 依赖定期安全扫描
- 完整审计日志
- 实时监控异常访问
