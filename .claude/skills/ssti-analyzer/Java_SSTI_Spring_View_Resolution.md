# Java_SSTI_Spring_View_Resolution

**漏洞类型**: Spring MVC 视图解析时用户输入作为视图名称或模板路径

---

## Details

### 代码示例

**易受攻击的代码模式**:
```java
// Controller 直接返回用户输入作为视图名
@GetMapping("/view")
public String getView(@RequestParam String view) {
    return view;  // 用户可控视图名称
}

// ModelAndView 视图名用户可控
@RequestMapping("/page")
public ModelAndView showPage(String template) {
    return new ModelAndView(template);
}

// 字符串拼接构造视图名
@GetMapping("/render")
public String render(@PathVariable String name) {
    return "templates/" + name;  // 路径拼接
}

// redirect 或 forward 前缀用户可控
@PostMapping("/redirect")
public String doRedirect(@RequestParam String target) {
    return "redirect:" + target;  // 重定向目标可控
}

// 视图解析器配置不当
ViewResolver resolver = new InternalResourceViewResolver();
resolver.setPrefix("/WEB-INF/views/");
resolver.setSuffix(request.getParameter("ext"));  // 后缀可控
```

### 快速定位核心操作 **[L1-L2]**

**L1 关键词扫描**:
- Controller 注解: `@Controller`, `@RestController`, `@RequestMapping`, `@GetMapping`, `@PostMapping`
- 返回类型: `String`, `ModelAndView`, `View`
- 用户输入: `@RequestParam`, `@PathVariable`, `@RequestBody`, `HttpServletRequest`
- 视图前缀: `redirect:`, `forward:`
- 配置类: `ViewResolver`, `InternalResourceViewResolver`, `ThymeleafViewResolver`

**L2 跳读定位**:
- 从 Controller 方法追踪返回的字符串来源
- 检查返回值是否包含用户输入或字符串拼接
- 定位 ModelAndView 构造函数的视图名参数
- 搜索 redirect:/forward: 后的目标是否可控
- 关注 ViewResolver 的 prefix/suffix 配置

### 快速定位保护机制 **[L2-L4]**

**L2 跳读检测**:
- 视图白名单: 检查返回值是否在预定义列表中
- 路径限制: ViewResolver 的 prefix/suffix 固定配置
- 输入验证: 视图名经过正则或枚举验证
- 使用枚举: 视图名从 enum 中选择
- 重定向验证: redirect 目标域名白名单检查

**L3 逐行分析**:
- Controller 返回值:
  - 是否直接返回请求参数
  - 是否通过字符串拼接构造
  - 是否从数据库或配置加载（需追踪来源）
- ViewResolver 配置:
  - prefix 和 suffix 是否固定在配置文件
  - 是否限制了视图文件的目录范围
  - order 属性设置是否正确
- 视图名验证:
  - 是否有白名单或正则校验
  - 是否使用枚举类型限定可选视图
  - 是否检查路径遍历字符如 `..`
- 重定向安全:
  - redirect 目标是否验证域名
  - 是否使用 RedirectView 并设置 contextRelative
  - forward 目标是否限制在应用内部

**L4 跨模块追踪**:
- 追踪从请求 → Controller → 视图解析的完整流程
- 检查 Spring 配置文件中的全局 ViewResolver 设置
- 验证是否有拦截器或过滤器进行安全检查
- 检查是否使用了 Spring Security 的视图保护
- 追踪视图名称的数据流，确认是否有中间验证

---

## Classify

### 漏洞判定标准

**确认为漏洞**:
- Controller 方法直接返回用户输入作为视图名
- 视图名通过字符串拼接包含用户可控部分
- redirect/forward 目标完全由用户输入决定
- ViewResolver 的 suffix 或 prefix 可被用户影响
- 可通过路径遍历访问任意模板文件

**误报判定**:
- 视图名从枚举类型中选择，用户仅控制选择逻辑
- 返回值经过严格的白名单验证
- ViewResolver 配置完全固定且限制目录
- 使用了 Spring Security 的视图访问控制
- 视图名虽可选但范围严格限制在安全模板集合内

**代码异味**:
- 视图名虽经验证但使用黑名单过滤
- 字符串拼接构造路径如 `"views/" + name`
- redirect 目标验证不完善，可能绕过
- ViewResolver 链配置复杂，优先级不明确
- 使用了自定义 ViewResolver 但安全性未知
- 返回 ModelAndView 但视图名来自不可信数据源

---

## Low risk

### 低风险场景

**功能与权限隔离**:
- 视图选择功能仅限管理员访问
- 需要强身份验证和授权
- 功能部署在内部管理系统
- 实施了严格的基于角色的视图访问控制

**架构设计防护**:
- 使用枚举类型严格限定可访问视图
- ViewResolver 完全固定 prefix/suffix
- 实现了自定义 ViewResolver 进行安全检查
- 使用 Spring Security 的方法级安全注解

**输入与输出保护**:
- 视图名经过严格的字母数字白名单验证
- 使用正则表达式限制视图名格式
- redirect 目标使用域名白名单验证
- 路径规范化后检查是否在允许目录

**监控与运行环保**:
- 完整的审计日志记录所有视图访问
- 实时监控异常视图解析请求
- Web 应用防火墙检测路径遍历攻击
- 视图文件目录权限严格限制
