# PHP Email Template Injection

## Details

PHP 应用使用模板引擎（如 Twig、Smarty、Blade）渲染邮件内容时，若用户输入直接嵌入模板未经转义，攻击者可注入模板指令。这可能导致服务器端模板注入（SSTI）、敏感信息泄露、远程代码执行或邮件内容篡改。

**代码示例与审计要点**

```php
// 危险：用户输入直接拼接到模板字符串（Twig）
$loader = new \Twig\Loader\ArrayLoader([
    'email' => "Hello " . $_POST['name'] . ", your code is: {{ code }}"
]);
$twig = new \Twig\Environment($loader);
$html = $twig->render('email', ['code' => $secretCode]);

// 危险：允许用户提供模板内容
$templateStr = $_POST['emailTemplate'];
$loader = new \Twig\Loader\ArrayLoader(['email' => $templateStr]);
$html = $twig->render('email', $data);

// 危险：Blade 模板注入
$blade = view('emails.welcome')->with('name', $_GET['name'])->render();
```

**快速定位核心操作 (L1: 关键词扫描)**
- 搜索 `new \Twig\Environment`、`new Smarty()`、`view()` (Laravel Blade)
- 查找模板渲染：`->render()`、`->display()`、`->fetch()`
- 定位字符串拼接到模板：`"... " . $_POST['x']`、动态模板内容
- 检查邮件发送前的模板处理

**快速定位保护机制 (L2: 跳读)**
- 搜索自动转义：`autoescape` 选项、`{% autoescape %}`
- 查找手动转义：`htmlspecialchars()`、`htmlentities()`、`e()` 辅助函数
- 检查模板是否从文件加载：`FilesystemLoader`、`view('path.to.template')`
- 查看沙箱模式：`SandboxExtension`、`SecurityPolicy`

---

## Classify

**理论研判标准**

1. **确认为漏洞的标志**：
   - 用户输入直接拼接到模板字符串中
   - 允许用户提供完整的模板内容
   - 模板引擎未启用自动转义
   - 可通过输入 `{{_self.env.registerUndefinedFilterCallback("exec")}}` 等测试注入
   - 能执行任意 PHP 代码或访问敏感对象

2. **确认为误报的情况**：
   - 模板完全从文件系统加载，用户输入仅作为上下文变量
   - Twig 启用了 `autoescape` 选项
   - Blade 自动转义（`{{ $var }}` 而非 `{!! $var !!}`）
   - 使用沙箱模式限制模板功能

3. **代码异味判断**：
   - 使用 `{!! $var !!}` 或 `|raw` 过滤器禁用转义
   - 模板中可访问 `_self`、`app` 等全局对象
   - 转义仅在部分代码路径中执行

---

## Low risk

**这些情况应给予低风险评级**

1. **静态模板**：所有邮件模板从文件系统加载（`FilesystemLoader`），用户输入仅作为数据变量

2. **自动转义**：Twig 启用 `autoescape` 或 Blade 使用 `{{ }}` 语法自动转义

3. **沙箱模式**：Twig 配置 `SandboxExtension` 限制可用标签、过滤器和函数

4. **输入转义**：所有用户输入在传入模板前都经过 `htmlspecialchars()` 转义

5. **纯文本邮件**：仅发送纯文本邮件，不使用 HTML 模板，模板注入风险降低
