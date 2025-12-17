# Java - JDOM XPath 注入

## Details

### 漏洞成因
JDOM 框架通过 `XPath.selectNodes()` 和 `XPath.selectSingleNode()` 方法处理 XPath 查询。当用户输入直接拼接到 XPath 表达式时，会导致 XPath 注入漏洞。JDOM 常用于 XML 配置管理和文档处理。

代码示例：
```java
Document doc = builder.build(xmlFile);
String search = request.getParameter("q");
XPath xpath = XPath.newInstance("//item[title='" + search + "']");
List results = xpath.selectNodes(doc);
```

### 快速定位核心操作 (L1: 关键词扫描)
- `org.jdom.XPath`, `XPath.newInstance()`, `selectNodes()`, `selectSingleNode()`
- `SAXBuilder`, `Document` 相关操作
- 字符串拼接：`+`, `String.format()`, `StringBuilder`
- XPath 特殊符号：`[`, `]`, `'`, `"`, `//`, `@`, `text()`

### 快速定位保护机制 (L2-L3: 跳读到逐行读)
- **参数化方式** (L2) - 检查是否使用了 `addVariable()` 传递参数
- **输入验证** (L2) - 是否存在白名单或类型检查
- **转义处理** (L3) - 是否正确转义了引号和特殊字符
- **跨模块追踪** (L4) - 追踪表达式参数的来源

## Classify

**确认为漏洞**：
- 用户输入直接参与 JDOM XPath 表达式构造
- 无参数化绑定或转义

**误报情况**：
- 拼接的仅是非 XPath 语法数据
- 输入通过严格白名单验证
- 使用 `addVariable()` 方式传递参数

**代码异味**：
- 自定义的转义函数可能不完整
- 复杂的字符串操作

## Low risk

- 固定 XPath 骨架，仅拼接数值
- 严格的输入限制
- 内部使用，无外部用户输入
