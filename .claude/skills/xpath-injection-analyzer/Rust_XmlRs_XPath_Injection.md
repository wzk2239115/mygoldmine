# Rust - xml-rs 和 xpath 库注入

## Details

### 漏洞成因
`xml-rs` 是 Rust 的纯 Rust XML 解析库，常与 XPath 库（如 `sxd-xpath`）组合使用。当用户输入通过字符串拼接（`format!()`, `String::from()` + 操作）直接嵌入 XPath 表达式时，攻击者可注入 XPath 语法字符来改变查询逻辑。Rust 的内存安全和类型系统虽然防止缓冲区溢出，但无法阻止逻辑层面的注入攻击。常见于 XML 配置解析、SOAP 客户端和文档查询。

代码示例：
```rust
use xml::reader::{EventReader, XmlEvent};
use sxd_xpath::evaluate_xpath;
use sxd_document::parser;

fn query_xml(category: String) -> Result<Vec<String>, Box<dyn std::error::Error>> {
    let xml_data = std::fs::read_to_string("products.xml")?;
    let package = parser::parse(&xml_data)?;
    let doc = package.as_document();

    let xpath_query = format!("//product[@category='{}']", category);
    let result = evaluate_xpath(&doc, &xpath_query)?;

    Ok(vec![result.string()])
}
```

### 快速定位核心操作 (L1: 关键词扫描)
- `use xml::reader`, `use xml::EventReader`, `XmlEvent`
- `use sxd_xpath`, `evaluate_xpath()`, `compile()`
- `use sxd_document::parser`, `parser::parse()`
- 字符串拼接：`format!()`, `+`, `String::push_str()`, `concat!()`
- XPath 特征：`//`, `@`, `[`, `]`, `'`, `"`, `and`, `or`, `not()`
- 数据源：`actix_web::Query`, `rocket::Form`, `axum::extract::Query`

### 快速定位保护机制 (L2-L4)
- **验证函数** (L2 跳读) - 查找 `regex` crate 使用, `validator` crate, 自定义验证函数
- **类型转换** (L2 跳读) - 检查 `FromStr`, `TryFrom`, `str::parse()` 的使用
- **枚举模式** (L2 跳读) - 查找 `match` 表达式或 `if let` 的枚举值验证
- **转义实现** (L3 逐行读) - 检查自定义转义函数，验证是否处理所有特殊字符
- **中间件层** (L4) - 从 Web 框架的提取器到 XPath 查询的数据流分析

## Classify

### 漏洞判定标准

**确认为漏洞**：
1. 用户可控数据通过字符串拼接嵌入 XPath 表达式
2. 未实施有效的验证、转义或参数化机制
3. 表达式通过 XPath 库执行查询
4. 查询的 XML 数据包含敏感信息

**误报情况**：
- 拼接的数据来自编译时常量或配置文件
- 用户输入通过严格的类型系统约束（如枚举类型）
- 输入经过 `str::parse()` 转换为数值类型且检查错误
- XML 数据为公开的静态文档

**代码异味**：
- 自定义转义函数但未处理所有 XPath 特殊字符
- 使用 `String::replace()` 进行部分字符替换
- 输入验证逻辑分散在多个函数或模块
- 在 `unsafe` 块中处理字符串操作

## Low risk

### 低风险评级场景

1. **强类型解析** - 输入通过 `FromStr` 或 `TryFrom` 转换为非字符串类型
   - 例：`let id: u32 = input.parse().map_err(|_| Error::Invalid)?;`

2. **正则白名单** - 使用 `regex` crate 进行严格验证
   - 例：`let re = Regex::new(r"^[a-zA-Z0-9]+$")?; re.is_match(input)`

3. **枚举匹配** - 使用 Rust 枚举类型限制输入值
   - 例：`enum Field { Name, Email } impl FromStr for Field { ... }`

4. **非敏感数据** - XML 数据为公开的配置或产品列表

5. **只读查询** - XPath 仅用于数据读取，不涉及认证或授权

6. **框架验证** - Web 框架的验证器或提取器已过滤输入

7. **结果后处理** - 查询结果经过权限检查或数据脱敏

8. **编译时检查** - 使用宏或 const 泛型在编译阶段验证输入模式
