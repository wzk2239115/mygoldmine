# PHP Twig 模板表达式注入

**漏洞成因**：Twig 模板引擎中用户输入直接嵌入模板表达式或过滤器，导致服务端模板注入（SSTI）。攻击者可通过 Twig 的表达式语言访问对象属性、调用方法或执行任意 PHP 代码，造成严重的安全风险。常见于邮件模板、用户自定义模板、报告生成等场景。

---

## Details

**代码示例**：
```php
// 危险：用户输入直接嵌入模板
$twig = new Twig_Environment(new Twig_Loader_String());
$userTemplate = $_POST['template'];
$html = $twig->render($userTemplate, ['data' => $data]);

// 危险：模板注入载荷
// userTemplate = "{{ _self.env.registerUndefinedFilterCallback(\"exec\") }}{{ \"id\"|id }}"

// 较安全：使用文件加载器加载预定义模板
$loader = new Twig_Loader_Filesystem('/safe/templates');
$twig = new Twig_Environment($loader);
$html = $twig->render('template.twig', ['data' => $data]);

// 较安全：禁用危险函数
$twig = new Twig_Environment($loader, [
    'autoescape' => true,
    'sandbox' => true  // 启用沙箱模式
]);
$twig->addExtension(new Twig_Extension_Sandbox());
```

**快速定位核心操作**：
- 关键词：`Twig_Loader_String`、`Twig_Loader_FileSystem`、模板渲染、用户模板处理
- 查看模板来源是否为用户可控（文件上传、请求参数、数据库字段）
- 检查是否使用了 Twig 沙箱或 autoescape 选项
- 追踪模板中可访问的全局变量和方法
- 关注是否存在自定义过滤器或全局函数被滥用

**快速定位保护机制**：
- 是否使用了文件系统加载器加载预定义模板
- 是否启用了 autoescape 选项
- 是否启用了沙箱模式（Sandbox 扩展）
- 是否限制了可用的过滤器和全局函数
- 是否禁用了对危险方法和属性的访问

**审计等级**：**L2-L3**
- **L2**：跳读模板加载和渲染代码，识别用户可控模板源
- **L3**：逐行分析 Twig 环境配置和安全选项

---

## Classify

**确认为漏洞**：
- 使用 `Twig_Loader_String` 或类似方式加载用户提供的模板内容
- 未启用 autoescape 或沙箱模式
- 模板可访问危险对象或调用危险方法
- 自定义过滤器或函数包含危险操作

**误报**：
- 模板完全由应用内部定义，从文件系统加载
- 所有用户输入都通过 locals 对象传递且被正确转义
- 启用了沙箱模式且正确配置

**代码异味**：
- Twig 环境配置不规范，暴露过多全局对象
- 自定义过滤器实现不规范，包含过多业务逻辑

---

## Low Risk

以下情况可评为低风险：
- **文件系统加载**：所有模板都从文件系统加载，用户无法上传或修改
- **完全沙箱化**：启用了 Sandbox 扩展并正确配置
- **输出转义**：启用了 autoescape 且对所有输出进行转义
- **内网应用**：仅由内部可信管理员编辑模板
- **受限的 locals**：模板仅能访问预定义的数据对象

**注意**：Twig 的灵活性高，需要多层防护确保安全。
