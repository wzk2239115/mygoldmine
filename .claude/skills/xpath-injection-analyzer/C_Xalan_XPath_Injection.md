# C/C++ - Xalan XPath 注入

## Details

### 漏洞成因
Xalan C++ 是一个 XSLT 和 XPath 处理器。当通过 `XPathEvaluator` 或 `XPathFactory` 创建 XPath 表达式时，如果用户输入直接拼接到表达式字符串中，会导致 XPath 注入。Xalan 会解析整个 XPath 表达式，包括注入的恶意语法，从而改变查询逻辑。

代码示例：
```cpp
XalanDOMString query = "//employee[@salary > ";
query += userInput + "]";
XPathEvaluator evaluator;
XPathProcessorImpl processor;
XPathExpression* expr = processor.createMatchPattern(query);
```

### 快速定位核心操作 (L1: 关键词扫描)
- `XPathEvaluator`, `XPathFactory`, `XPathProcessor`, `XPathExpression`
- `createMatchPattern()`, `createExpression()`, `evaluate()`
- `XalanDOMString` 与用户输入的拼接操作
- `+`, `+=`, `append()` 等字符串操作
- XPath 特殊符号：`[`, `]`, `(`, `)`, `'`, `"`, `@`, `/`, `//`

### 快速定位保护机制 (L2-L3: 跳读到逐行读)
- **参数化方式** (L2) - 检查是否使用变量绑定而非直接拼接（Xalan 的变量支持）
- **输入验证** (L2) - 是否存在白名单验证或类型检查
- **转义处理** (L3) - 是否对特殊字符进行了正确的转义（需注意 Xalan 特定的转义规则）
- **跨模块追踪** (L4) - 追踪 `userInput` 的来源，确认是否来自网络请求或用户交互

## Classify

### 漏洞判定标准

**确认为漏洞**：
1. 用户输入直接拼接到 Xalan XPath 表达式字符串
2. 不存在参数化绑定或输入转义
3. 表达式通过 `createMatchPattern()` 或 `createExpression()` 编译执行

**误报情况**：
- 虽然有字符串拼接，但仅拼接了不包含 XPath 语法的数据（如整数 ID）
- 输入严格限制为允许列表
- 使用了 Xalan 的变量机制传递用户数据

**代码异味**：
- 存在自定义的转义函数，需验证其完整性
- 使用了复杂的字符串操作，难以确定是否存在绕过

## Low risk

### 低风险评级场景

1. **固定表达式模板** - XPath 骨架完全由代码定义，仅拼接非语法数据
   - 例：`query = "//salary[. > " + integerId + "]"`

2. **严格白名单** - 用户输入仅限于预定义的静态值集合

3. **离线处理** - XPath 处理仅用于分析内部、已验证的 XML 文档

4. **查询沙箱** - XPath 执行的 XML 文档仅包含非敏感数据或权限受限
