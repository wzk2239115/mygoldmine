# Rust - 自定义 XPath 查询构建器不安全实现

## Details

### 漏洞成因
在 Rust 项目中，开发者可能实现自定义的 XPath 查询构建器以简化查询逻辑。若构建器未正确处理用户输入，而是直接通过字符串拼接或格式化将输入嵌入 XPath 表达式，将导致注入漏洞。尽管 Rust 的类型系统和生命周期管理提供内存安全，但逻辑层面的注入仍可能发生。自定义构建器往往缺乏安全审计，风险更高。常见于复杂的 XML 查询场景和 DSL 实现。

代码示例：
```rust
struct XPathBuilder {
    query: String,
}

impl XPathBuilder {
    fn new() -> Self {
        XPathBuilder { query: String::new() }
    }

    fn filter_by_user(&mut self, username: &str) -> &mut Self {
        self.query.push_str(&format!("//user[username='{}']", username));
        self
    }

    fn execute(&self, doc: &Document) -> Result<Value, Error> {
        evaluate_xpath(doc, &self.query)
    }
}

// 使用
let mut builder = XPathBuilder::new();
let result = builder.filter_by_user(&user_input).execute(&doc)?;
```

### 快速定位核心操作 (L1: 关键词扫描)
- 自定义 struct 名称包含 `Builder`, `Query`, `XPath`, `Selector`
- 方法名包含 `filter`, `where_`, `add_condition`, `build`
- `impl` 块中使用字符串拼接：`format!()`, `push_str()`, `+`
- 方法接收 `&str` 或 `String` 类型参数
- 最终调用 XPath 库：`evaluate_xpath()`, `compile()`

### 快速定位保护机制 (L2-L4)
- **Builder 验证** (L2 跳读) - 检查 Builder 方法内部是否有输入验证逻辑
- **类型约束** (L2 跳读) - 查找是否使用泛型约束或 trait bound 限制输入
- **转义方法** (L3 逐行读) - 检查 Builder 内部是否实现 `escape()` 或 `sanitize()` 方法
- **参数化实现** (L3 逐行读) - 验证是否使用参数化查询而非字符串拼接
- **跨模块追踪** (L4) - 从调用 Builder 的代码到最终 XPath 执行的完整链路分析

## Classify

### 漏洞判定标准

**确认为漏洞**：
1. 自定义 Builder 通过字符串拼接构造 XPath 表达式
2. Builder 方法接收用户输入且未验证或转义
3. 构建的表达式通过 XPath 库执行
4. 查询的 XML 数据包含敏感信息

**误报情况**：
- Builder 方法仅接收枚举类型或经过验证的参数
- Builder 内部实现了完整的转义逻辑
- Builder 使用参数化查询机制（如变量绑定）
- 所有调用点都对输入进行了严格验证

**代码异味**：
- Builder 的某些方法有验证，其他方法缺失
- 转义逻辑存在但不完整或使用黑名单
- Builder 既支持安全方法又支持不安全的字符串拼接
- 文档未明确说明安全使用方式

## Low risk

### 低风险评级场景

1. **泛型约束** - Builder 使用泛型约束限制输入类型
   - 例：`fn filter<T: Into<i32>>(&mut self, value: T) -> &mut Self`

2. **枚举参数** - Builder 方法仅接收枚举类型参数
   - 例：`fn sort_by(&mut self, field: SortField) -> &mut Self` 其中 `SortField` 为枚举

3. **内部转义** - Builder 内部实现完整的 XPath 转义逻辑
   - 例：所有字符串参数都经过 `escape_xpath()` 处理

4. **参数化实现** - Builder 使用类似 SQL prepared statement 的机制
   - 例：Builder 维护参数列表，最终生成参数化查询

5. **非敏感数据** - Builder 仅用于查询公开的配置或产品数据

6. **调用点验证** - 所有使用 Builder 的代码都对输入进行严格验证

7. **只读查询** - Builder 构建的查询仅用于数据读取

8. **编译时验证** - 使用 Rust 宏在编译时验证 XPath 表达式模板的安全性
