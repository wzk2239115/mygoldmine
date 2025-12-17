# PHP_SSTI_Smarty_User_Variable

**漏洞类型**: 使用 Smarty 模板引擎时将用户可控的数据作为模板变量，导致模板表达式注入

---

## Details

### 代码示例

**易受攻击的代码模式**:
```php
// 直接将用户输入赋值为模板变量
$smarty = new Smarty();
$user_input = $_GET['content'];
$smarty->assign('content', $user_input);
$smarty->display('template.tpl');

// 模板中使用用户可控的变量名
$smarty->assign($_GET['var_name'], $_GET['var_value']);
$smarty->display('template.tpl');

// 通过 array 直接传入用户数据
$smarty->assign($_POST);  // 直接赋值所有 POST 数据
$smarty->display('template.tpl');

// 动态模板渲染，用户可控模板名称
$smarty->display($_GET['template']);

// 模板文件包含用户可控路径
$template = 'views/' . $_GET['page'] . '.tpl';
$smarty->display($template);
```

### 快速定位核心操作 **[L1-L2]**

**L1 关键词扫描**:
- 模板分配函数: `assign()`, `assignByRef()`, `assign_by_ref()`
- 模板显示方法: `display()`, `fetch()`, `render()`
- 用户输入获取: `$_GET`, `$_POST`, `$_REQUEST`, `$_COOKIE`, `$_FILES`
- 直接赋值: `$smarty->assign(...)`, `extract()`, `compact()`
- 模板文件访问: `display()`, `fetch()`, `getTemplate()`

**L2 跳读定位**:
- 从用户输入获取点追踪到 `assign()` 的参数
- 检查 `assign()` 中变量名是否来自用户输入
- 关注是否直接使用 `$_POST`, `$_GET` 等全局数组
- 搜索模板文件名或路径是否可由用户控制

### 快速定位保护机制 **[L2-L4]**

**L2 跳读检测**:
- 输入验证: `preg_match()`, `in_array()`, 验证变量名白名单
- 模板安全配置: `$smarty->security = true`, 开启安全模式
- 资源限制: `$smarty->setTemplateDir()`, 限制模板目录
- 转义处理: `$smarty->escape_html`, 启用 HTML 转义

**L3 逐行分析**:
- 赋值方式检查:
  - 是否使用了白名单方式赋值变量
  - `assign()` 中变量名是否为硬编码常量
  - 是否直接使用 `extract()` 或 `$smarty->assign($_POST)`
- Smarty 配置检查:
  - 是否启用了 `$smarty->security = true` 安全模式
  - `$smarty->setTemplateDir()` 是否限制了模板目录
  - 是否配置了 `$smarty->allowedDirectories` 白名单
  - 是否禁用了危险的 PHP 函数如 `eval()`, `system()`
- 模板文件路径:
  - 模板名称是否来自用户输入
  - 路径拼接是否使用了用户输入
  - 是否有路径遍历防护如 `basename()` 限制

**L4 跨模块追踪**:
- 追踪用户输入从请求 → 赋值 → 模板渲染的完整数据流
- 检查中间件或框架层是否做了输入验证
- 验证是否有全局的 Smarty 配置文件限制危险操作
- 检查是否在控制器层有输入白名单
- 追踪变量在多个模板中的使用

---

## Classify

### 漏洞判定标准

**确认为漏洞**:
- 用户输入直接通过 `assign()` 赋值为模板变量
- 在 Smarty 模板中用户可以注入表达式如 `{$smarty.version}`
- 关闭了安全模式且允许访问 PHP 函数
- 用户可以通过变量名注入访问系统信息或执行代码
- 模板路径可由用户控制，导致任意文件包含

**误报判定**:
- 仅将明确定义的数据结构赋值，用户输入仅作为值而非变量名
- 启用了 Smarty 安全模式且配置了严格的资源限制
- 使用了白名单方式只允许特定的变量被赋值
- 模板文件完全由开发者预定义，用户无法控制模板名称
- 所有用户输入都经过验证和转义

**代码异味**:
- 虽然启用了安全模式但配置过于宽松
- 使用 `extract()` 或 `$smarty->assign($_POST)` 赋值
- 模板文件名使用字符串拼接包含部分用户输入
- 变量赋值时使用了黑名单而非白名单过滤
- 模板中直接访问 `$smarty` 对象或全局变量

---

## Low risk

### 低风险场景

**功能与权限隔离**:
- 模板渲染功能仅限管理员或特权用户使用
- 用户数据仅能作为模板显示的内容，不能修改模板逻辑
- 功能被完全隔离在内部系统，非公网可访问

**架构设计防护**:
- 明确启用 `$smarty->security = true` 安全模式
- 模板内容完全由开发者预定义
- 使用严格的模板白名单，用户只能选择预定义的模板
- 所有用户输入仅作为模板变量值而非变量名

**输入与输出保护**:
- 用户输入被严格白名单验证
- 赋值时仅使用硬编码的变量名，不依赖用户输入
- 启用了 `$smarty->escape_html` 自动转义
- 所有敏感变量都被隐藏在模板不可访问的范围

**监控与运行环保**:
- Smarty 模板目录权限限制严格，仅开发者可写
- 禁用了危险的 Smarty 插件和函数
- 部署环境隔离，无系统命令执行权限
- 有完整的日志审计和异常检测机制
