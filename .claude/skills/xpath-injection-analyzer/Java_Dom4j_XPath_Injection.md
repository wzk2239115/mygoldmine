# Java - dom4j XPath 注入

## Details

### 漏洞成因
dom4j 框架的 `selectNodes()`, `selectSingleNode()` 等方法接收 XPath 表达式字符串。当用户输入直接拼接到表达式中时，会导致 XPath 注入。dom4j 广泛用于 XML 配置解析和数据查询，此类漏洞可能影响应用的核心业务逻辑。

代码示例：
```java
Document doc = SAXReader.read(xmlFile);
String userInput = request.getParameter("search");
Element result = (Element) doc.selectSingleNode("//product[name='" + userInput + "']");
```

### 快速定位核心操作 (L1: 关键词扫描)
- `dom4j.Document`, `SAXReader`, `selectNodes()`, `selectSingleNode()`
- `XPath` 相关操作：`createXPath()`, `evaluate()`
- 字符串拼接操作：`+`, `String.format()`, `StringBuilder`
- XPath 语法符号：`[`, `]`, `'`, `"`, `//`, `@`

### 快速定位保护机制 (L2-L3: 跳读到逐行读)
- **参数化方式** (L2) - 检查是否使用 `setVariable()` 或其他参数化方式
- **输入验证** (L2) - 白名单验证或类型检查
- **转义处理** (L3) - 是否对特殊字符进行了正确转义
- **跨模块追踪** (L4) - 追踪 XPath 表达式参数来源

## Classify

**确认为漏洞**：
- 用户输入直接拼接到 dom4j XPath 表达式
- 调用 `selectNodes()` 等执行方法

**误报情况**：
- 拼接内容为非 XPath 语法数据
- 输入经过严格白名单验证
- 使用参数化方式

**代码异味**：
- 存在部分过滤或自定义转义函数

## Low risk

- 固定表达式模板，仅拼接数值数据
- 严格的输入白名单
- 内部系统使用，无外部输入
