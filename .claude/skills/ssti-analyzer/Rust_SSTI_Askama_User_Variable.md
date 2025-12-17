# Rust_SSTI_Askama_User_Variable

**漏洞类型**: Askama 模板引擎中用户可控变量导致的潜在注入

---

## Details

### 代码示例

**易受攻击的代码模式**:
```rust
// Askama 是编译时模板引擎，SSTI 风险较低
// 但不当使用仍可能导致问题

// 场景1：模板路径可控（编译时，风险极低）
use askama::Template;
#[derive(Template)]
#[template(path = "user.html")] // 编译时固定
struct UserTemplate {
    name: String, // 用户数据，但会被转义
}

// 场景2：HTML 未转义输出
#[derive(Template)]
#[template(source = "{{ content|safe }}", ext = "html")]
struct UnsafeTemplate {
    content: String, // 使用 safe 过滤器绕过转义
}

// 场景3：自定义过滤器不安全
#[derive(Template)]
#[template(source = "{{ data|custom_filter }}", ext = "html")]
struct CustomTemplate {
    data: String,
}
// 如果 custom_filter 实现不当

// 场景4：Include 路径（编译时固定）
// 模板中: {% include "template_name.html" %}
// Askama 在编译时解析，运行时不可控
```

### 快速定位核心操作 **[L1-L2]**

**L1 关键词扫描**:
- Template derive: `#[derive(Template)]`
- 模板属性: `#[template(...)]`, `path`, `source`, `ext`
- 过滤器: `|safe`, `|escape`, 自定义过滤器
- 用户输入: 结构体字段来自请求参数
- 配置: `askama.toml`, 自定义过滤器定义

**L2 跳读定位**:
- 检查 Template derive 的结构体
- 搜索 `|safe` 过滤器的使用
- 定位自定义过滤器的实现
- 追踪用户输入到结构体字段的赋值
- 关注模板 source 属性的使用

### 快速定位保护机制 **[L2-L4]**

**L2 跳读检测**:
- 编译时检查: Askama 在编译时验证模板
- 自动转义: 默认启用 HTML 转义
- 类型安全: Rust 的类型系统提供保护
- 模板固定: 模板路径在编译时确定
- 无动态模板: 运行时无法修改模板

**L3 逐行分析**:
- Template 配置:
  - path 是否硬编码在代码中
  - source 是否包含用户可控部分
  - ext 设置是否正确
- 结构体字段:
  - 字段类型是否安全（String vs &str）
  - 数据来源是否经过验证
  - 是否包含复杂类型或引用
- 过滤器使用:
  - 是否使用 `|safe` 绕过转义
  - 自定义过滤器实现是否安全
  - 过滤器链是否正确
- askama.toml:
  - escape 配置是否禁用
  - 自定义过滤器注册
  - 模板目录设置

**L4 跨模块追踪**:
- 追踪从请求 → 数据结构 → 模板渲染的流程
- 检查 Cargo.toml 中的 Askama 版本
- 验证自定义过滤器的安全性
- 检查模板文件的内容和语法
- 追踪数据从输入到模板字段的转换

---

## Classify

### 漏洞判定标准

**确认为漏洞**:
- 使用 `|safe` 过滤器输出用户可控数据
- 自定义过滤器实现不安全（未转义）
- template(source) 包含动态构造的模板字符串（极罕见）
- 复杂类型字段暴露了不安全的方法
- askama.toml 禁用了转义功能

**误报判定**:
- 模板完全在编译时确定
- 默认转义启用且无 `|safe` 使用
- 所有字段都是基本类型（String, i32 等）
- 自定义过滤器经过安全审计
- Askama 的编译时检查提供了足够保护

**代码异味**:
- 大量使用 `|safe` 过滤器
- 自定义过滤器未经安全审计
- 结构体包含复杂的嵌套类型
- 模板中使用了大量的条件和循环
- Askama 版本过低存在已知问题
- askama.toml 配置不当

---

## Low risk

### 低风险场景

**功能与权限隔离**:
- 模板仅用于内部页面
- 需要身份验证才能访问
- 用户输入受严格限制
- 基于角色的访问控制

**架构设计防护**:
- 完全依赖 Askama 的编译时检查
- 禁用或不使用 `|safe` 过滤器
- 结构体字段仅使用基本类型
- 实现完善的 CSP 策略

**输入与输出保护**:
- 所有输入经过 serde 验证和解析
- 使用 validator crate 验证数据
- 模板字段类型严格限制
- 自定义过滤器实现了适当转义

**监控与运行环保**:
- Rust 的内存安全提供基础保障
- 依赖定期安全扫描和更新
- 完整的请求日志
- 异常行为监控
