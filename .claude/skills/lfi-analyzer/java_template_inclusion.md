# Java 模板引擎动态包含漏洞 (Template Inclusion)

## Details

### 代码示例

**JSP 动态包含：**
```java
// 漏洞代码
String template = request.getParameter("page");
<jsp:include page="<%= template %>" />
// 或
request.getRequestDispatcher(template).include(request, response);
```

**Velocity：**
```java
String tmplPath = request.getParameter("template");
Template t = velocityEngine.getTemplate(tmplPath);  // 用户可控路径
t.merge(context, writer);
```

**FreeMarker：**
```java
String tmplName = request.getParameter("view");
Template template = cfg.getTemplate(tmplName);  // 用户可控
template.process(dataModel, out);
```

**Spring View Resolver：**
```java
@RequestMapping("/view")
public String viewPage(@RequestParam String page) {
    return page;  // 直接返回用户输入作为视图名
}
```

### 快速定位核心操作技巧 (L2-L3)

**关键方法特征：**
- JSP: `<jsp:include>`、`RequestDispatcher.include()`、`RequestDispatcher.forward()`、`pageContext.include()`
- Velocity: `VelocityEngine.getTemplate()`、`Template.merge()`
- FreeMarker: `Configuration.getTemplate()`、`Template.process()`
- Thymeleaf: `TemplateEngine.process()` + 动态模板名
- Spring: Controller 方法返回值直接使用用户输入（无 `redirect:`/`forward:` 前缀）

**跳读策略：**
- 搜索 `getTemplate(`、`include(`、`forward(`
- 追踪 Controller 返回值是否拼接用户输入
- 关注 `@RequestParam`/`@PathVariable` 直接流向视图名

### 快速定位保护机制技巧 (L1-L2)

**白名单验证 (L1)：**
```java
// 搜索关键词：whitelist, allowed, valid
Set<String> allowedTemplates = Set.of("home", "about", "contact");
if (!allowedTemplates.contains(template)) { ... }
```

**路径规范化检查 (L2)：**
```java
// 关键词：normalize, canonical, resolve
Path resolved = basePath.resolve(template).normalize();
if (!resolved.startsWith(basePath)) { ... }
```

**扩展名限制 (L1)：**
```java
// 关键词：.endsWith, extension
if (!template.endsWith(".vm") || template.contains("..")) { ... }
```

**模板引擎配置 (L2)：**
- FreeMarker: `setTemplateLoader()` 限定目录、`setNewBuiltinClassResolver(SAFER_RESOLVER)`
- Velocity: `file.resource.loader.path` 配置受限路径
- 查看配置类或 XML 配置文件

## Classify

### 确认为漏洞
- 用户输入直接或拼接后传入模板路径，无验证或仅客户端验证
- 可读取任意模板文件导致信息泄露（包含敏感配置/代码）
- RFI 场景：允许加载远程模板（如 HTTP/FTP 协议）
- 模板引擎配置允许访问文件系统或类加载器

### 判定为误报
- 硬编码模板路径，用户输入仅影响模板内数据
- 严格白名单校验（枚举值、Map 映射）且白名单内容安全
- 用户输入仅用于目录内文件选择且有路径规范化+前缀校验
- 模板加载器已限定为 ClasspathResourceLoader 且无路径穿越

### 代码异味
- 使用黑名单过滤（`.contains("..")`, `replace("../", "")`）：可能被绕过
- 仅检查扩展名但不检查路径穿越
- 依赖正则匹配但规则不够严格（如 `^[a-zA-Z0-9]+$` 但允许多级路径）
- 配置中允许多个模板路径且包含敏感目录

## Low risk

### 低风险场景评估

- **受限模板目录**：模板仅存放于独立目录，目录内无敏感文件，且配置明确限定该目录
- **只读信息泄露**：仅能读取前端模板文件（HTML/CSS），不包含后端逻辑或配置
- **内部管理功能**：需管理员权限且已有强认证/授权机制，影响面有限
- **二次验证存在**：后续流程中有业务逻辑再次验证用户身份或操作合法性
- **容器化隔离**：应用运行在严格权限隔离的容器中，可访问文件范围极小
- **日志监控完善**：异常模板访问有实时告警和审计日志，可快速响应