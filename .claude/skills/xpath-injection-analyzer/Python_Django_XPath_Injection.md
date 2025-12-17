# Python - Django XPath 注入

## Details

### 漏洞成因
Django 应用在处理 XML 数据时，如使用 lxml 或 ElementTree，若用户输入直接拼接到 XPath 表达式，会导致注入漏洞。常见于 Django 视图函数处理 XML 配置或数据查询的场景。

代码示例：
```python
from django.http import HttpRequest
from lxml import etree

def search_xml(request):
    query = request.GET.get('q')
    xpath = f"//product[name='{query}']"
    results = etree.parse('data.xml').xpath(xpath)
    return render(request, 'results.html', {'items': results})
```

### 快速定位核心操作 (L1: 关键词扫描)
- Django views、`request.GET`、`request.POST`
- lxml 或 ElementTree 操作
- 字符串拼接与 XPath
- XML 处理库

### 快速定位保护机制 (L2-L3: 跳读到逐行读)
- **请求验证** (L2) - Django 的 form 验证或 `clean_data`
- **表达式构造** (L2) - 是否直接拼接了 request 数据
- **参数化** (L3) - 是否使用了参数化 XPath
- **跨模块追踪** (L4) - 追踪请求参数流向

## Classify

**确认为漏洞**：
- Django 请求参数直接拼接到 XPath
- 无 Django 层验证

**误报情况**：
- 使用 Django form 验证
- 白名单验证
- 静态 XML

**代码异味**：
- 部分验证

## Low risk

- Django form 严格验证
- 固定模板
- 非敏感数据
