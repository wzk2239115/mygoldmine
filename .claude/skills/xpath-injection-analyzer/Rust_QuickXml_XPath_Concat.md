# Rust - quick-xml 和 sxd-xpath 组合注入

## Details

### 漏洞成因
Rust 的 `quick-xml` 是高性能的 XML 解析库，常与 `sxd-xpath` 或 `sxd-document` 库组合进行 XPath 查询。当用户输入通过字符串拼接（`format!()`, `+`, `String::push_str()`）直接嵌入 XPath 表达式时，尽管 Rust 的所有权系统和类型安全提供一定保护，但字符串层面的注入仍然可能发生。攻击者可注入 XPath 语法元素来改变查询逻辑。常见于配置解析、XML API 客户端和数据查询服务。

代码示例：
```rust
use sxd_document::parser;
use sxd_xpath::{evaluate_xpath, Context};

fn search_user(username: &str) -> Result<String, Box<dyn std::error::Error>> {
    let xml = std::fs::read_to_string("users.xml")?;
    let package = parser::parse(&xml)?;
    let document = package.as_document();

    let query = format!("//user[username='{}']", username);
    let context = Context::new();
    let value = evaluate_xpath(&document, &query)?;

    Ok(value.string())
}
```

### 快速定位核心操作 (L1: 关键词扫描)
- `use quick_xml`, `use sxd_xpath`, `use sxd_document`
- `evaluate_xpath()`, `Factory::new()`, `compile()`
- `parser::parse()`, `Context::new()`
- 字符串拼接：`format!()`, `+`, `String::push_str()`, `&format!()`
- XPath 特征：`//`, `@`, `[`, `]`, `'`, `"`, `and`, `or`
- 数据源：HTTP 库（`actix-web`, `rocket`, `axum`）的请求参数提取

### 快速定位保护机制 (L2-L4)
- **输入验证** (L2 跳读) - 查找 `regex::Regex`, `str::parse()`, 自定义 `validate()` 函数
- **类型约束** (L2 跳读) - 检查是否使用 `FromStr` trait 进行类型转换
- **枚举验证** (L2 跳读) - 查找 `match` 语句或 `Vec::contains()` 的枚举值检查
- **转义函数** (L3 逐行读) - 检查自定义 `escape_xpath()` 函数，验证特殊字符处理
- **跨模块追踪** (L4) - 从 HTTP handler 到 XPath 查询的完整数据流，检查中间处理层

## Classify

### 漏洞判定标准

**确认为漏洞**：
1. 用户可控数据通过字符串拼接嵌入 XPath 表达式
2. 未实施有效的输入验证或转义机制
3. 表达式通过 `evaluate_xpath()` 或相关函数执行
4. 查询的 XML 数据包含敏感信息（用户凭证、权限、配置）

**误报情况**：
- 拼接的数据来自常量或配置文件
- 用户输入通过 `regex::Regex` 严格验证
- 输入通过 `str::parse::<i32>()` 等方法强制转换为数值类型
- XML 数据为公开的静态资源

**代码异味**：
- 存在自定义转义函数但未覆盖所有 XPath 特殊字符
- 使用 `str::replace()` 进行黑名单过滤
- 输入验证逻辑分散在多个模块中
- 使用 `unsafe` 块处理字符串，可能绕过类型检查

## Low risk

### 低风险评级场景

1. **类型解析** - 输入通过 `str::parse()` 转换为整数或其他非字符串类型
   - 例：`let id: i32 = id_str.parse()?;`

2. **正则验证** - 使用 `regex::Regex` 进行严格白名单验证
   - 例：`let re = Regex::new(r"^[a-zA-Z0-9]+$")?; if !re.is_match(input) { return Err(...) }`

3. **枚举匹配** - 输入限制为预定义的枚举值
   - 例：`match field { "name" | "email" => ..., _ => return Err(...) }`

4. **非敏感数据** - XML 数据为公开的产品目录或配置文件

5. **只读查询** - XPath 仅用于数据检索，不涉及身份验证或授权

6. **中间件保护** - Web 框架的认证或验证中间件已过滤输入

7. **结果过滤** - 查询结果经过权限检查或数据脱敏

8. **编译时验证** - 使用宏或 const 泛型在编译时验证输入格式
