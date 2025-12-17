# PHP_SSTI_Native_Eval_Include

**漏洞类型**: 原生 PHP 模板中使用 eval 或 include 执行用户输入

---

## Details

### 代码示例

**易受攻击的代码模式**:
```php
// 直接 eval 用户输入
$code = $_GET['template'];
eval($code);

// 包含用户可控文件
$file = $_GET['page'] . '.php';
include($file);

// 动态变量名
$var = $_GET['var'];
$$var = $_GET['value'];  // 变量覆盖

// create_function 动态创建函数
$func = create_function('$arg', $_POST['code']);
$func($data);

// preg_replace /e 修饰符
$pattern = $_GET['pattern'];
preg_replace("/$pattern/e", $_GET['replace'], $input);

// assert 执行代码
assert($_GET['expr']);
```

### 快速定位核心操作 **[L1-L2]**

**L1 关键词扫描**:
- 危险函数: `eval()`, `assert()`, `create_function()`, `preg_replace(/e)`
- 文件包含: `include()`, `require()`, `include_once()`, `require_once()`
- 动态执行: `call_user_func()`, `call_user_func_array()`, `$函数名()`
- 变量函数: `$$variable`, `${$variable}`
- 用户输入: `$_GET`, `$_POST`, `$_REQUEST`, `$_COOKIE`, `$_SERVER`

**L2 跳读定位**:
- 从用户输入追踪到危险函数调用
- 检查 include/require 路径是否包含用户输入
- 定位动态变量名或函数名的来源
- 搜索 eval 和 assert 的参数来源
- 关注字符串拼接后的代码执行

### 快速定位保护机制 **[L2-L4]**

**L2 跳读检测**:
- 输入验证: 白名单验证文件名或代码内容
- 路径限制: 使用 `basename()` 或 `realpath()` 验证
- 禁用函数: `disable_functions` 配置
- 沙箱环境: 使用 `open_basedir` 限制访问
- 安全模式: PHP 安全配置检查

**L3 逐行分析**:
- 危险函数使用:
  - eval/assert 是否接受用户输入
  - 是否有输入验证或过滤
  - 是否在禁用函数列表中
- 文件包含检查:
  - 路径是否完全或部分用户可控
  - 是否使用 basename 提取文件名
  - 是否验证文件扩展名
  - realpath 是否用于规范化路径
- 动态调用:
  - 函数名或变量名是否来自用户输入
  - 是否有函数名白名单
  - call_user_func 参数是否可控
- php.ini 配置:
  - disable_functions 是否包含危险函数
  - open_basedir 是否限制目录访问
  - allow_url_include 是否禁用

**L4 跨模块追踪**:
- 追踪从请求 → 路由 → 模板处理的数据流
- 检查全局配置文件的安全设置
- 验证中间件或过滤器的输入净化
- 检查框架层面的安全包装
- 追踪文件包含的完整路径构造

---

## Classify

### 漏洞判定标准

**确认为漏洞**:
- eval/assert 直接执行用户输入
- include/require 路径可被用户控制
- 动态函数调用且函数名来自用户输入
- 变量覆盖可影响关键逻辑
- preg_replace /e 修饰符参数可控

**误报判定**:
- 危险函数在 disable_functions 中被禁用
- 文件路径经过严格白名单验证
- 使用 basename + 白名单双重验证
- open_basedir 严格限制且无法绕过
- 代码在沙箱环境中运行且隔离完善

**代码异味**:
- 文件路径虽验证但使用黑名单
- 使用 basename 但未检查扩展名
- 动态调用虽有验证但不完整
- eval 虽限制但仍存在注入点
- 旧版 PHP 存在已知安全问题
- create_function 在 PHP 7.2+ 已废弃但仍在使用

---

## Low risk

### 低风险场景

**功能与权限隔离**:
- 功能仅限超级管理员使用
- 需要多重身份验证
- 部署在完全隔离的内网
- 实施严格的访问控制

**架构设计防护**:
- disable_functions 禁用所有危险函数
- open_basedir 严格限制目录
- 使用现代模板引擎替代原生 PHP
- 代码在受限容器中运行

**输入与输出保护**:
- 文件名严格字母数字白名单
- basename + 扩展名白名单双重验证
- 路径规范化后检查前缀
- 所有输入经过类型和格式验证

**监控与运行环保**:
- 文件系统只读挂载
- PHP 进程最低权限运行
- 完整审计日志
- WAF 检测代码执行特征
