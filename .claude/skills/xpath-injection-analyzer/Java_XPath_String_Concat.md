# Java - XPath 字符串直接拼接

## Details

### 漏洞成因
Java 的 `javax.xml.xpath.XPath` 类通过 `compile()` 或 `evaluate()` 方法接收 XPath 表达式字符串。当用户输入直接通过字符串拼接（`+`, `String.format()`, `StringBuilder` 等）参与表达式构造时，攻击者可注入 XPath 语法字符改变查询逻辑。此问题普遍存在于用户身份验证（XML 用户数据库）和数据搜索等场景。

代码示例：
```java
String userInput = getUserInput();
String xpath = "//user[username='" + userInput + "']";
XPath xp = XPathFactory.newInstance().newXPath();
NodeList nodes = (NodeList) xp.evaluate(xpath, doc, XPathConstants.NODESET);
```

### 快速定位核心操作 (L1: 关键词扫描)
- `XPathFactory.newInstance()`, `XPath`, `evaluate()`, `compile()`
- 字符串拼接：`+`, `String.format()`, `StringBuilder.append()`, `String.concat()`
- XPath 特殊符号出现在字符串中：`'`, `"`, `[`, `]`, `or`, `and`
- 来自 `HttpServletRequest`, `Scanner` 等源的数据流

### 快速定位保护机制 (L2-L3: 跳读到逐行读)
- **参数化方式** (L2) - 检查是否使用 `setVariable()` 将参数作为变量而非拼接
- **输入验证** (L2) - 是否存在白名单验证或类型检查（如仅允许字母数字）
- **输出编码** (L3) - 是否正确转义了引号和特殊字符（需确认转义完整性）
- **跨模块追踪** (L4) - 追踪用户输入的来源（网络请求参数、文件输入等）

## Classify

### 漏洞判定标准

**确认为漏洞**：
1. 用户输入通过字符串拼接直接参与 XPath 表达式
2. 不存在参数化绑定或有效的转义
3. 调用了 `evaluate()` 或 `compile()` 方法执行

**误报情况**：
- 虽然有字符串拼接，但拼接的仅是非 XPath 语法的数据（如纯数值）
- 输入通过正则表达式或白名单严格验证
- 使用 `setVariable()` 将用户数据作为 XPath 变量传递
- XPath 表达式完全由代码定义，无动态部分

**代码异味**：
- 存在自定义的转义函数，需验证其正确性
- 使用了 `replaceAll()` 等替换操作处理输入，但可能不完整

## Low risk

### 低风险评级场景

1. **固定 XPath 模板** - 拼接内容为非 XPath 语法数据
   - 例：`"//user[@id='" + userId + "']"` 其中 userId 为验证过的整数

2. **严格的输入白名单** - 用户输入仅限于预定义值
   - 例：仅允许 `[a-zA-Z0-9_]` 字符集

3. **非生产环境** - 代码仅在测试、开发或内部工具中使用

4. **权限沙箱** - XPath 执行权限严格限制，无法访问敏感数据
