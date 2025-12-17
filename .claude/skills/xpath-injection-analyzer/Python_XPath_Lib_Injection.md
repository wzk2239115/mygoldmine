# Python - xpath 库注入

## Details

### 漏洞成因
第三方 `xpath` 库用于解析和执行 XPath 表达式。当用户输入直接参与表达式字符串构造时，会导致注入漏洞。此库为 XPath 操作提供了编程接口，若未验证输入会导致严重风险。

代码示例：
```python
import xpath
user_input = input('Enter search: ')
expr = f"//record[data='{user_input}']"
result = xpath.find(expr, xml_tree)
```

### 快速定位核心操作 (L1: 关键词扫描)
- `import xpath`, `xpath.find()`, `xpath.parse()`
- `xpath.compile()`, `xpath.evaluate()`
- 字符串拼接，XPath 表达式
- 特殊符号出现在表达式中

### 快速定位保护机制 (L2-L3: 跳读到逐行读)
- **输入验证** (L2) - 白名单或类型检查
- **表达式转义** (L3) - 是否转义了引号和特殊字符
- **跨模块追踪** (L4) - 输入来源

## Classify

**确认为漏洞**：
- 直接拼接到 xpath 表达式
- 无验证

**误报情况**：
- 非 XPath 数据拼接
- 严格白名单
- 内部使用

**代码异味**：
- 部分过滤

## Low risk

- 固定模板
- 严格限制
- 非敏感数据
