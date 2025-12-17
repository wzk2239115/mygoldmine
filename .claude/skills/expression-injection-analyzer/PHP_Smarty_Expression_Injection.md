# PHP Smarty 模板表达式注入

**漏洞成因**：Smarty 模板引擎中用户输入直接嵌入模板表达式，导致服务端模板注入（SSTI）。Smarty 具有强大的表达式能力，攻击者可通过模板语法执行 PHP 代码、访问文件系统、执行系统命令等恶意操作。常见于邮件模板、用户模板定制、报告生成等场景。

---

## Details

**代码示例**：
```php
// 危险：用户输入作为模板内容
$smarty = new Smarty();
$userTemplate = $_POST['template'];
$smarty->display('string:' . $userTemplate);  // 直接执行用户模板

// 危险：模板注入载荷
// userTemplate = "{system('id')}"
// userTemplate = "{$_SERVER['REQUEST_URI']}"
// userTemplate = "{php}echo file_get_contents('/etc/passwd');{/php}"

// 较安全：使用文件系统加载模板
$smarty = new Smarty();
$smarty->setTemplateDir('/safe/templates');
$smarty->display('template.tpl');

// 较安全：禁用 PHP 标签和限制功能
$smarty = new Smarty();
$smarty->deny_modifiers = array('regex_replace');  // 禁用危险修饰符
$smarty->default_modifiers = array('escape:"html"');  // 默认转义
```

**快速定位核心操作**：
- 关键词：`string:`、`display`、`fetch`、用户模板处理、`{php}` 标签、`{system()}` 函数调用
- 查看是否存在 Smarty 的 `string:` 加载器被用于用户输入
- 检查是否启用了 PHP 标签和危险修饰符
- 追踪模板中可访问的全局变量
- 关注是否禁用了危险修饰符如 `regex_replace`

**快速定位保护机制**：
- 是否使用文件系统加载器而非字符串加载器
- 是否禁用了 `{php}` 标签
- 是否禁用了危险修饰符
- 是否启用了默认的 HTML 转义
- 是否限制了模板可访问的全局变量

**审计等级**：**L2-L3**
- **L2**：跳读模板加载代码，识别 `string:` 加载器的使用
- **L3**：逐行分析 Smarty 配置和安全选项

---

## Classify

**确认为漏洞**：
- 使用 Smarty 的 `string:` 加载器加载用户提供的内容
- 启用了 `{php}` 标签或内置代码执行函数
- 未禁用危险修饰符（如 `regex_replace`）
- 模板可直接访问全局变量或调用 PHP 函数

**误报**：
- 所有模板都从文件系统加载
- 用户仅能提供数据，不能定义模板内容
- 严格禁用了所有危险功能

**代码异味**：
- Smarty 配置不规范，暴露过多全局对象
- 使用了自定义插件但缺少安全审查

---

## Low Risk

以下情况可评为低风险：
- **文件系统加载**：所有模板都从文件系统加载
- **功能限制**：禁用了 `{php}` 标签和所有危险修饰符
- **输出转义**：启用了默认 HTML 转义
- **内网模板编辑**：仅由内部可信用户编辑模板
- **受限变量**：模板仅能访问显式传递的数据对象

**注意**：Smarty 的强大能力也意味着更高的安全风险，需要严格配置。
