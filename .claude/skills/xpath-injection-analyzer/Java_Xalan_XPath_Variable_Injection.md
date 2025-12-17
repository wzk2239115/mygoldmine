# Java - Xalan XPath 变量注入

## Details

### 漏洞成因
Apache Xalan 是一个 XSLT 和 XPath 处理器。虽然 Xalan 支持参数化的变量绑定（`setVariable()`），但如果应用开发者错误地将用户输入作为变量值直接传递而未进行验证，或在绑定前进行了 XPath 语法拼接，仍可能导致注入。关键在于变量值本身是否被当作 XPath 表达式的一部分。

代码示例：
```java
XPathEvaluator evaluator = new XPathEvaluatorImpl();
evaluator.setVariable(QName.valueOf(userInput), new XString("value"));
String result = (String) evaluator.eval(expr, context);
```

### 快速定位核心操作 (L1: 关键词扫描)
- `org.apache.xalan`, `XPathEvaluator`, `setVariable()`, `QName`
- `getVariableOrParam()`, `eval()`, `evaluate()`
- 变量赋值操作，特别是涉及用户输入的
- XPath 特殊符号在变量名或值中

### 快速定位保护机制 (L2-L3: 跳读到逐行读)
- **变量用法** (L2) - 确认变量是在 XPath 表达式中如何被使用的
- **输入验证** (L2) - 变量名和值是否都进行了验证
- **表达式构造** (L3) - 检查 XPath 表达式骨架是否存在字符串拼接
- **跨模块追踪** (L4) - 追踪用户输入如何流向 `setVariable()` 调用

## Classify

**确认为漏洞**：
- 用户输入作为变量名直接传递给 `setVariable()`
- 或在调用前进行了 XPath 拼接
- 未进行输入验证

**误报情况**：
- 变量名来自代码定义，仅值来自用户
- 值经过严格白名单验证
- 表达式完全参数化

**代码异味**：
- 混合使用字符串拼接和变量绑定

## Low risk

- 变量完全由代码定义
- 用户输入严格限制
- 权限沙箱限制
