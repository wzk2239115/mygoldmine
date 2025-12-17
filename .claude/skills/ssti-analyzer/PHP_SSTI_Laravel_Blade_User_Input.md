# PHP_SSTI_Laravel_Blade_User_Input

**漏洞类型**: Laravel Blade 模板中用户输入直接渲染或模板路径可控

---

## Details

### 代码示例

**易受攻击的代码模式**:
```php
// 用户输入作为模板内容
use Illuminate\Support\Facades\Blade;
$template = request()->input('template');
echo Blade::compileString($template);

// 使用原始输出语法
// Blade 模板: {!! $userInput !!}
return view('page', ['userInput' => request('data')]);

// 视图名称用户可控
$viewName = request('view');
return view($viewName);

// 动态 @php 指令
// Blade 模板: @php eval($userCode) @endphp
return view('template', ['userCode' => request('code')]);

// 自定义 Blade 指令未转义
Blade::directive('custom', function ($expression) {
    return "<?php echo $expression; ?>";  // 未转义
});
```

### 快速定位核心操作 **[L1-L2]**

**L1 关键词扫描**:
- Blade 方法: `Blade::compileString()`, `Blade::render()`, `view()`
- 输出语法: `{!! !!}` (未转义), `{{ }}` (转义)
- 指令: `@php`, `@include`, `@extends`, `@directive`
- 用户输入: `request()`, `Request::input()`, `$request->get()`
- 自定义指令: `Blade::directive()`, `Blade::component()`

**L2 跳读定位**:
- 从请求输入追踪到 `compileString()` 或 `view()`
- 检查模板中的 `{!! !!}` 原始输出
- 定位视图名称是否来自用户输入
- 搜索 `@php` 指令中的代码来源
- 关注自定义 Blade 指令的实现

### 快速定位保护机制 **[L2-L4]**

**L2 跳读检测**:
- 自动转义: 使用 `{{ }}` 代替 `{!! !!}`
- 视图白名单: 视图名称白名单验证
- 禁用指令: 移除或限制 `@php` 指令
- 输入验证: 严格的输入类型和格式检查
- CSP 策略: Content-Security-Policy 头部

**L3 逐行分析**:
- Blade 编译:
  - 是否使用 compileString 处理用户输入
  - Blade::render 的模板来源
  - 编译缓存是否可被污染
- 输出方式:
  - `{{ }}` 自动 HTML 转义（安全）
  - `{!! !!}` 原始输出不转义（危险）
  - `{{{ }}}` 在旧版本中双重转义
- 视图加载:
  - view() 参数是否用户可控
  - 是否有视图名称白名单
  - 路径是否可遍历
- 自定义指令:
  - Blade::directive 实现是否安全
  - 是否对指令参数进行转义
  - 是否限制了可用指令集
- @php 指令:
  - 模板中是否使用 @php 执行代码
  - @php 内容是否来自用户输入

**L4 跨模块追踪**:
- 追踪从路由 → 控制器 → 视图的数据流
- 检查 Blade 服务提供者的全局配置
- 验证视图文件存储位置和权限
- 检查中间件的输入过滤
- 追踪视图组件和包含的安全性

---

## Classify

### 漏洞判定标准

**确认为漏洞**:
- Blade::compileString() 接受用户输入
- 模板中使用 `{!! !!}` 输出用户数据
- view() 的视图名称完全由用户控制
- @php 指令执行用户可控代码
- 自定义指令未对参数转义

**误报判定**:
- 模板完全预定义，用户仅控制通过 `{{ }}` 输出的值
- 视图名称经过严格白名单验证
- 所有用户输入在传入视图前已转义
- 禁用了 @php 指令的使用
- 自定义指令实现了完善的转义机制

**代码异味**:
- 虽用 `{{ }}` 但视图结构可被用户影响
- 视图名称通过字符串拼接构造
- 大量使用 `{!! !!}` 原始输出
- 自定义指令未经安全审计
- 在 Blade 模板中混用 PHP 代码
- 视图缓存机制可能被利用

---

## Low risk

### 低风险场景

**功能与权限隔离**:
- 视图选择仅限管理员使用
- 需要强身份验证
- 功能在内部系统中
- 严格的访问控制

**架构设计防护**:
- 强制使用 `{{ }}` 自动转义
- 视图名称从枚举中选择
- 禁用 @php 指令
- 实现完善的 CSP 策略

**输入与输出保护**:
- 视图名称严格白名单验证
- 所有变量强制使用 `{{ }}`
- 禁止在模板中执行PHP代码
- 输入经过类型和格式验证

**监控与运行环保**:
- 视图文件权限严格控制
- Blade 编译缓存目录只读
- 完整审计日志
- WAF 检测模板注入
