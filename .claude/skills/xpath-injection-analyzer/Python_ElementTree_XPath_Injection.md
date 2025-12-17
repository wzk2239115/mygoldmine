# Python - ElementTree XPath 注入

## Details

### 漏洞成因
Python 内置的 `xml.etree.ElementTree` 模块支持基础 XPath 查询。当用户输入直接拼接到 XPath 表达式时，虽然 ElementTree 的 XPath 支持有限，但仍可被利用来访问非授权数据或改变查询结果。

代码示例：
```python
import xml.etree.ElementTree as ET
search = request.form['query']
root = ET.parse('data.xml').getroot()
xpath = f".//item[title='{search}']"
results = root.findall(xpath)
```

### 快速定位核心操作 (L1: 关键词扫描)
- `xml.etree.ElementTree`, `ET.parse()`, `root.findall()`
- `.find()`, `.iterfind()`, `fromstring()`
- 字符串拼接：f-string, `.format()`, `+`
- XPath 符号：`.//`, `/`, `@`, `[`, `]`

### 快速定位保护机制 (L2-L3: 跳读到逐行读)
- **参数化方式** (L2) - 检查是否使用 `attrib` 过滤而非字符串拼接
- **输入验证** (L2) - 白名单验证或类型检查
- **转义处理** (L3) - 是否正确转义特殊字符
- **跨模块追踪** (L4) - 用户输入来源

## Classify

**确认为漏洞**：
- 用户输入直接拼接到 XPath
- 无验证或转义

**误报情况**：
- 拼接内容为非 XPath 数据
- 严格白名单验证
- 静态 XML 文档

**代码异味**：
- 部分过滤

## Low risk

- 固定模板，仅拼接数值
- 严格限制
- 非敏感数据
