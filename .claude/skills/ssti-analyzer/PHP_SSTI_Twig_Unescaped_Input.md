# PHP_SSTI_Twig_Unescaped_Input

**漏洞类型**: Twig 模板引擎中用户输入未经转义直接渲染

---

## Details

### 代码示例

**易受攻击的代码模式**:
```php
// 用户输入作为模板内容
$loader = new \Twig\Loader\ArrayLoader([]);
$twig = new \Twig\Environment($loader);
$userTemplate = $_GET['template'];
echo $twig->createTemplate($userTemplate)->render([]);

// 使用 raw 过滤器输出未转义内容
$template = $twig->createTemplate('{{ name|raw }}');
echo $template->render(['name' => $_POST['username']]);

// 禁用自动转义
$twig = new \Twig\Environment($loader, [
    'autoescape' => false
]);

// 模板文件路径用户可控
$templateName = $_GET['template'] . '.twig';
echo $twig->render($templateName, $data);

// include/extends 路径来自用户输入
// 模板中: {% include var %}
$twig->render('page.twig', ['var' => $_GET['include']]);
```

### 快速定位核心操作 **[L1-L2]**

**L1 关键词扫描**:
- 类和方法: `Twig\Environment`, `createTemplate()`, `render()`, `display()`
- 过滤器: `|raw`, `|escape`, `|safe`
- 标签: `{% include %}`, `{% extends %}`, `{% embed %}`
- 配置: `autoescape`, `strict_variables`
- 用户输入: `$_GET`, `$_POST`, `$_REQUEST`, `$_COOKIE`

**L2 跳读定位**:
- 从用户输入追踪到 `createTemplate()` 或 `render()`
- 检查模板字符串是否包含用户输入
- 搜索 `|raw` 过滤器的使用
- 定位 autoescape 配置是否为 false
- 关注 include/extends 路径是否可控

### 快速定位保护机制 **[L2-L4]**

**L2 跳读检测**:
- 自动转义: `autoescape` 是否启用（默认启用）
- 模板白名单: 模板名称是否经过验证
- 沙箱模式: 使用 `Twig\Extension\SandboxExtension`
- 安全策略: `Twig\Sandbox\SecurityPolicy` 配置
- 模板加载器: `FilesystemLoader` 限制路径

**L3 逐行分析**:
- Environment 配置:
  - `autoescape` 设置（默认 true 为安全）
  - `strict_variables` 是否启用
  - `cache` 配置是否可被污染
- 模板来源:
  - 是否接受用户提交的完整模板字符串
  - render() 的模板名是否用户可控
  - Loader 配置是否限制路径
- 过滤器使用:
  - 是否使用 `|raw` 输出用户数据
  - 是否自定义了不安全的过滤器
  - escape 过滤器是否被正确应用
- 沙箱配置:
  - SecurityPolicy 是否限制了标签、过滤器、方法
  - 是否禁用了危险的标签如 include
  - 允许的方法和属性白名单是否安全

**L4 跨模块追踪**:
- 追踪从请求 → 控制器 → 模板渲染的数据流
- 检查全局 Twig 配置文件
- 验证模板文件存储位置和权限
- 检查是否有中间件进行输入过滤
- 追踪自定义扩展和过滤器的实现

---

## Classify

### 漏洞判定标准

**确认为漏洞**:
- 用户输入直接作为 `createTemplate()` 参数
- 设置 `autoescape => false` 禁用自动转义
- 使用 `|raw` 过滤器输出用户可控数据
- 模板名称可被用户完全或部分控制导致路径遍历
- 未启用沙箱且可访问危险方法

**误报判定**:
- 模板完全预定义，用户仅控制变量值（自动转义）
- 启用了 SandboxExtension 且策略严格
- 模板名称经过白名单验证
- FilesystemLoader 限制在安全目录
- 所有用户输入在传入前已转义

**代码异味**:
- 虽启用 autoescape 但大量使用 `|raw`
- 模板路径通过拼接构造
- 自定义过滤器或扩展未经安全审计
- 沙箱策略配置不完整
- Twig 版本过低存在已知漏洞
- 模板中使用复杂的宏和嵌套包含

---

## Low risk

### 低风险场景

**功能与权限隔离**:
- 模板渲染仅限管理员使用
- 需要多重身份验证
- 功能部署在内部系统
- 实施严格访问控制

**架构设计防护**:
- 启用 SandboxExtension 和严格策略
- 强制启用 autoescape
- 模板全部预编译和缓存
- 使用 FilesystemLoader 限制目录

**输入与输出保护**:
- 模板名称严格白名单验证
- 禁止使用 `|raw` 过滤器
- 所有变量强制转义
- 路径规范化后检查前缀

**监控与运行环保**:
- 模板文件权限严格控制
- 完整审计日志
- 实时监控异常模板访问
- WAF 检测 Twig 注入特征
