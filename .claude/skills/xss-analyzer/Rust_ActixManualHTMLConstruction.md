# Rust｜Actix/Rocket 手工构造 HTML 导致 XSS

## 基本信息

- **难度等级：** ★★★☆☆ (中级)
- **审计时间：** 15-30分钟（单个漏洞点）
- **先决知识：** Rust 字符串类型、Actix/Rocket 框架、HTML 编码、`ammonia` 库使用
- **复杂度评估：**
  - 简单场景（单个路由处理）：15-20分钟
  - 复杂场景（多个字符串拼接、嵌套响应）：30-45分钟

## 🚀 30秒快速清单

- [ ] 代码中是否使用字符串拼接（format!、to_string 等）构造 HTML 响应？
- [ ] 拼接的内容是否包含用户输入或从请求中提取的数据？
- [ ] 是否使用了 HTML 编码库（如 `html-escape`、`ammonia`）进行转义？
- [ ] 是否使用了模板引擎（Askama、Tera）而不是手工拼接？
- [ ] 是否对富文本内容进行了适当的净化和白名单限制？

**判断：** 如果第 1-2 个问题打勾且第 3 个未打勾，需要进行 L2+ 深度分析

## Details

### 漏洞成因
在 Actix-web、Rocket、Axum 等框架中，若使用 `format!`、`String::from`、`write!` 等方式手工拼接 HTML 并插入用户输入，而不是通过模板引擎（Tera、Handlebars）自动转义，会导致 XSS。

### 代码示例

**易受攻击的代码：**
```rust
async fn search(query: web::Query<HashMap<String, String>>) -> HttpResponse {
    let q = query.get("q").cloned().unwrap_or_default();
    let body = format!("<h1>Search: {}</h1>", q);
    HttpResponse::Ok().content_type("text/html").body(body)
}
```

**安全示例：**
```rust
use tera::{Context, Tera};

async fn search(tmpl: web::Data<Tera>, query: web::Query<HashMap<String, String>>) -> HttpResponse {
    let mut ctx = Context::new();
    ctx.insert("query", &query.get("q").cloned().unwrap_or_default());
    let body = tmpl.render("search.html", &ctx).unwrap(); // Tera 默认转义
    HttpResponse::Ok().content_type("text/html").body(body)
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `format!("<`, `write!(resp`, `body(format!`, `Html<String>`, `Response::new`。

**定位步骤：**
1. 搜索 HTML 拼接代码；
2. 跳读（L2）确认变量来源是否可控；
3. 检查是否使用模板引擎或 HTML 转义库。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- 模板引擎（Tera、Handlebars、Askama）；
- `markup::new`, `Html::from_html_unchecked` 等使用是否安全；
- `html_escape::encode_safe` 等转义函数；
- 返回 JSON 而非 HTML。

**定位技巧：**
- 逐行读（L3）确认每个插入点是否编码；
- 跨模块追踪（L4）字符串是否在多处复用。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 使用模板引擎或转义库 | **L0（快速跳过）** | 风险低 |
| 极少数手工拼接 | **L2（跳读）** | 快速修补 |
| 普遍使用 `format!` 插入输入 | **L3（逐行读）** | 高风险 |
| 字符串跨服务传递 | **L4（跨模块追踪）** | 需完整分析 |

## Classify

### 研判标准

#### 确认漏洞
1. 手工拼接 HTML 并插入用户可控数据；
2. 缺乏转义；
3. 可以构造 payload 执行脚本。

#### 误报
1. 内容为常量或后端已转义；
2. 响应不在浏览器渲染；
3. 页面仅内部调试使用。

#### 代码异味
1. 输出函数 scatter 在多处，缺少统一封装；
2. 依赖 `replace("<", "")` 等不可靠过滤；
3. 在脚本、属性上下文拼接变量。

## Low risk

### 低风险评级场景

#### 1. 功能仅内网使用
- 攻击面小，可暂降级。

#### 2. 输出作为日志或低敏信息
- 风险较低，但建议转义。

#### 3. 已计划引入模板引擎
- 明确时间表，暂降级并跟踪执行。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 内部访问 | 攻击面小 | 中 |
| 低敏信息 | 影响有限 | 低 |
| 改造计划明确 | 可暂缓 | 低 |
