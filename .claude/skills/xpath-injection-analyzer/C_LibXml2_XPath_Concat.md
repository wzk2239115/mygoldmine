# C/C++ - libxml2 XPath 字符串拼接注入

## Details

### 漏洞成因
libxml2 提供的 `xmlXPathEvalExpression()` 或 `xmlXPathCompile()` 函数接收 XPath 表达式字符串参数。当用户输入直接拼接到这些表达式字符串中时（如通过 `sprintf()`, `strcat()` 或字符串构造函数），攻击者可以通过注入 XPath 语法字符（如 `'`, `"`, `or`, `and` 等）来改变查询语义，突破访问控制或提取非授权数据。

代码示例：
```c
char xpath_expr[512];
sprintf(xpath_expr, "//user[username='%s']", user_input);
xmlXPathObjectPtr result = xmlXPathEvalExpression(xpath_expr, ctx);
```

### 快速定位核心操作 (L1: 关键词扫描)
- `xmlXPathEvalExpression()`, `xmlXPathCompile()`, `xmlXPathCtxCompile()`
- `sprintf()`, `snprintf()`, `strcat()`, `strcpy()` 与 XPath 相关变量的组合
- `xmlChar*` 类型的动态字符串拼接
- `/`, `//`, `@`, `[`, `]`, `'`, `"`

### 快速定位保护机制 (L2-L3: 跳读到逐行读)
- **参数化方式** (L2) - 检查是否使用了 XPath 变量（`xmlXPathRegisterVariable()`），参数通过变量而非字符串拼接传入
- **输入验证** (L2) - 是否存在白名单验证（如字符集限制）或长度检查
- **转义处理** (L3) - 是否对引号、反斜线等特殊字符进行了正确的 XML 编码或 XPath 转义
- **跨模块追踪** (L4) - 追踪 `sprintf()` 的第二参数来源，确认其是否来自用户输入或外部数据源

## Classify

### 漏洞判定标准

**确认为漏洞**：
1. 用户输入通过 `sprintf()` 或 `strcat()` 等直接拼接到 XPath 表达式
2. 不存在任何 XPath 相关的转义或参数化处理
3. 调用了 `xmlXPathEvalExpression()` 等执行函数

**误报情况**：
- 虽然使用了字符串拼接，但拼接的内容不包含 XPath 语法关键字，仅为数据值（如数字 ID）
- 输入严格限制为允许列表（如仅允许数字字符）
- 使用 `xmlXPathRegisterVariable()` 注册变量，表达式本身不拼接用户输入

**代码异味**：
- 存在部分过滤（如只转义引号，但未转义其他 XPath 语法字符）
- 使用了自定义的转义函数，需验证其完整性

## Low risk

### 低风险评级场景

1. **固定 XPath 骨架** - 虽然拼接了用户输入，但拼接的内容仅为数值数据，XPath 语法完全由代码定义
   - 例：`sprintf(xpath, "//user[@id='%d']", user_id)` 其中 user_id 为整数

2. **严格的输入限制** - 用户输入经过严格白名单验证，只允许特定的预定义值或字符集
   - 例：仅允许 `[a-zA-Z0-9_]` 字符集

3. **非用户可控源** - XPath 表达式的动态部分来自内部系统配置或数据库，而非用户请求

4. **查询权限受限** - 即使注入成功，XPath 查询执行时的权限严格限制，无法访问敏感数据
