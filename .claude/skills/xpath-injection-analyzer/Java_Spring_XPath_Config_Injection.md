# Java - Spring XPath 配置注入

## Details

### 漏洞成因
Spring 框架在 XML 配置解析、依赖注入配置验证等场景使用 XPath。如果 Spring 应用动态生成或修改 XML 配置文件，并允许用户输入参与 XPath 表达式构造，则可能导致注入漏洞。这在自定义的配置解析器或动态 bean 生成中较为常见。

代码示例：
```java
String beanName = request.getParameter("bean");
String xpath = "//bean[@name='" + beanName + "']";
NodeList nodes = evaluator.evaluate(xpath, doc);
```

### 快速定位核心操作 (L1: 关键词扫描)
- Spring 配置相关类：`XmlBeanDefinitionReader`, `BeanDefinitionParser`
- XPath 操作：`evaluate()`, `selectNodes()`, `compile()`
- 字符串拼接与 Spring bean 定义相关
- XML 命名空间处理

### 快速定位保护机制 (L2-L3: 跳读到逐行读)
- **配置来源** (L2) - 确认 XPath 是否用于解析用户上传或动态生成的 XML
- **表达式构造** (L2) - 是否存在字符串拼接
- **Spring 安全功能** (L3) - 是否利用了 Spring 的安全验证机制
- **跨模块追踪** (L4) - 追踪 bean 定义的来源和验证方式

## Classify

**确认为漏洞**：
- 用户输入参与动态生成的 XPath 表达式
- 无输入验证

**误报情况**：
- XPath 表达式完全来自代码，无用户输入
- XML 配置为静态文件
- 使用了 Spring 的标准 bean 定义机制

**代码异味**：
- 动态 bean 生成但使用了部分验证

## Low risk

- 固定的配置模板
- 仅修改非关键属性
- 权限验证严格
