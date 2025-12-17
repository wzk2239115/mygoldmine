# Python - lxml XPath 字符串拼接注入

## Details

### 漏洛成因
lxml 库的 `XPath()` 类接收 XPath 表达式字符串。当用户输入直接通过 f-string、`format()` 或 `+` 拼接到表达式时，会导致 XPath 注入。lxml 广泛用于 web 爬虫和 XML 数据处理。

代码示例：
```python
from lxml import etree
user_search = request.args.get('q')
tree = etree.parse('data.xml')
xpath_expr = f"//product[name='{user_search}']"
results = tree.xpath(xpath_expr)
```

### 快速定位核心操作 (L1: 关键词扫描)
- `lxml.etree`, `etree.parse()`, `tree.xpath()`
- `XPath()` 类的使用
- f-string、`.format()`、`%` 等字符串拼接
- 特殊符号：`//`, `@`, `[`, `]`, `'`, `"`

### 快速定位保护机制 (L2-L3: 跳读到逐行读)
- **参数化方式** (L2) - 检查是否使用 lxml 的 `XPath(namespaces={})` 配合变量绑定
- **输入验证** (L2) - 是否存在白名单验证或 `re.match()` 验证
- **转义处理** (L3) - 是否使用了 `html.escape()` 或自定义转义
- **跨模块追踪** (L4) - 追踪用户输入来源

## Classify

**确认为漏洞**：
- 用户输入直接拼接到 lxml XPath 表达式
- 无转义或参数化

**误报情况**：
- 拼接内容为非 XPath 语法数据
- 输入经过严格白名单验证
- 仅查询预定义 XML 结构

**代码异味**：
- 自定义转义函数不完整

## Low risk

- 固定表达式模板，仅拼接数值
- 严格的输入限制
- 查询数据无敏感信息
