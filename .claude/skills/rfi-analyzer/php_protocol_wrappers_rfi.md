# PHP Protocol Wrappers 与 RFI

## 漏洞成因
PHP 协议包装器（`php://`、`data://`、`expect://` 等）与远程文件包含结合，当用户可控包含路径时，可通过特殊协议绕过本地文件限制执行任意代码。

---

## Details

### 代码示例

```php
// 危险示例 1: php://input 注入代码
include($_GET['page']);  // include 'php://input'
// POST 数据: <?php system($_GET['cmd']); ?>

// 危险示例 2: data:// URI 执行代码
include($_REQUEST['file']);  // include 'data://text/plain;base64,PD9waHAg...'

// 危险示例 3: expect:// 执行系统命令
include($user_input);  // include 'expect://id'

// 危险示例 4: 日志注入 + 包含 RCE
file_put_contents('/var/log/app.log', $_GET['msg']);
include($_GET['file']);  // include '/var/log/app.log' 包含注入的 PHP 代码
```

### 快速定位核心操作 (L2: 跳读)
- **关键函数**：`include`、`require`、`include_once`、`require_once`
- **用户输入来源**：`$_GET`/`$_POST`/`$_REQUEST`/`$_COOKIE`/`$_FILES`
- **协议支持检查**：
  - `allow_url_include=On`（支持 `http://`、`ftp://`）
  - `allow_url_fopen=On`（支持流协议）
  - PHP 编译是否启用 `php://` 支持
- **危险协议特征**：
  - `php://input` 或 `php://output`
  - `data://` URI
  - `expect://` 命令执行
  - `glob://` 文件枚举

### 快速定位保护机制 (L3: 逐行读)
- **协议限制**：检查是否禁用了伪协议
  - `disable_functions = system,exec,passthru`
  - `allow_url_include=Off` 配置检查
- **输入验证**：
  - `strpos($input, '://') === false`（禁止所有协议）
  - `parse_url()` 限制 scheme
  - 白名单文件名或模块名
- **路径限制**：
  - `basename()` 提取文件名
  - `realpath()` 解析真实路径
  - chroot 环境限制

---

## Classify

### 漏洞
- 用户输入可控包含路径，未过滤 `://` 或协议特征
- `allow_url_include=On` 或 `allow_url_fopen=On`
- PHP 环境支持危险协议（编译时未禁用）
- 日志注入 + 包含链路完整可用

### 误报
- 所有协议被明确禁用（`disable_functions` 包含 `php://` 处理函数）
- 用户输入经白名单严格验证（硬编码数组或预定义常量）
- 包含路径完全由服务器端生成，用户仅控制模块名后被 `basename()` 处理
- 环境配置 `allow_url_include=Off` 且不支持伪协议

### 代码异味
- 使用 `strpos()` 等弱校验协议（可被编码绕过）
- 包含逻辑跨多个文件，难以追踪完整数据流
- 日志存储路径可被包含函数访问但日志内容本身受限

---

## Low risk

- **协议全禁**：配置中禁用所有 URL 流（`allow_url_include=Off`、`allow_url_fopen=Off`）
- **严格白名单**：用户输入仅选择预定义模块，非直接指定路径
- **内容类型检查**：拉取内容后验证 MIME 类型（JSON/XML），非 PHP 代码
- **网络隔离**：应用无法访问外部 URL，仅限本地文件包含
- **沙箱运行**：PHP 运行在 open_basedir 受限的目录，无法访问系统敏感文件
- **签名验证**：包含前验证文件的加密签名或哈希值

---

## 审计重点

1. 搜索 `include/require` 后追踪变量来源
2. 检查 `php.ini` 相关配置
3. 验证协议过滤逻辑完整性
4. 追踪日志文件的生成与访问路径
5. 测试编码绕过（URL 编码、双编码等）
