# PHP_FileGetContentsSSRF

**漏洞类型**: file_get_contents() 直接读取用户提供的 URL，缺少协议和地址校验

---

## Details

### 代码示例

**易受攻击的代码模式**:
```php
// 场景1：直接读取用户输入URL
$url = $_GET['url'];
$content = file_get_contents($url); // 无任何验证
echo $content;

// 场景2：URL拼接用户参数
$path = $_POST['path'];
$data = file_get_contents("http://api.internal/" . $path); // 用户可控路径

// 场景3：使用流上下文
$opts = array('http' => array('method' => 'GET'));
$context = stream_context_create($opts);
$result = file_get_contents($_REQUEST['target'], false, $context); // 目标完全可控

// 场景4：cURL包装器
$remoteFile = $_GET['file'];
$ch = curl_init($remoteFile); // 同样存在SSRF风险
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
$data = curl_exec($ch);

// 场景5：fopen相关函数
$handle = fopen($_GET['url'], 'r'); // 同类风险
$content = stream_get_contents($handle);
```

### 快速定位核心操作 **[L1-L2]**

**L1 关键词扫描**:
- 危险函数: `file_get_contents(`, `fopen(`, `file(`, `readfile(`, `copy(`
- cURL系列: `curl_init(`, `curl_setopt(`, `curl_exec(`
- 流函数: `stream_get_contents(`, `stream_context_create(`
- 用户输入: `$_GET`, `$_POST`, `$_REQUEST`, `$_COOKIE`, `file_get_contents('php://input')`

**L2 跳读定位**:
- 从路由或入口文件扫描用户输入获取点
- 追踪变量从接收到传入文件读取函数之间的流转
- 重点关注: URL完整字符串、URL拼接、wrapper协议使用（`file://`、`php://`、`data://`）

### 快速定位保护机制 **[L2-L4]**

**L2 跳读检测**:
- URL白名单检查: `in_array($host, $allowedHosts)`, `preg_match('/^https:\/\/trusted\.com/', $url)`
- URL解析验证: `parse_url()` 然后检查 `scheme`、`host` 字段
- 协议限制: `strpos($url, 'http://') === 0` 或 `filter_var($url, FILTER_VALIDATE_URL)`

**L3 逐行分析**:
- 检查白名单实现是否可绕过（如 `strpos()` 可用 `http://evil.com@trusted.com` 绕过）
- 验证 `parse_url()` 是否对所有组件都做检查（避免解析差异绕过）
- 确认是否禁用了危险 wrapper（`allow_url_fopen`、`allow_url_include` 配置）
- 检查是否过滤内网IP段（`127.0.0.1`、`192.168.*`、`10.*`、`169.254.169.254`）

**L4 跨模块追踪**:
- 追踪自定义验证函数（如 `validateURL()`、`isExternalUrl()`）的完整实现
- 检查框架层或中间件是否有全局输入过滤
- 验证 `php.ini` 中的安全配置（`allow_url_fopen`、`open_basedir`）
- 检查是否使用HTTP代理并在代理层实施出站限制

---

## Classify

### 漏洞判定标准

**确认为漏洞**:
- 用户可完全控制传入 `file_get_contents()` 的URL且无验证
- 可访问内网资源（`127.0.0.1`、RFC1918地址段、云元数据服务）
- 可使用危险 wrapper 协议（`file://`、`php://filter`、`data://`、`expect://`、`phar://`）
- 保护机制存在已知绕过（如 `parse_url()` 与实际请求库解析差异）

**误报判定**:
- URL来自配置文件、环境变量或数据库硬编码，非运行时用户输入
- URL仅包含用户可控的 query 参数，协议和域名部分完全固定
- 存在严格白名单（精确域名匹配）+ 协议限制（仅 http/https）+ 私有IP过滤
- `allow_url_fopen = Off` 且代码路径不可达

**代码异味**:
- 有协议检查但未限制域名（如仅检查 `http://` 开头）
- 使用黑名单而非白名单（如禁止 `localhost` 但允许 `127.1`）
- 依赖 `$_SERVER['HTTP_REFERER']` 或客户端可控的 header 进行验证
- URL拼接逻辑分散在多个函数，难以确保所有路径都有保护

---

## Low risk

### 低风险场景

**应用场景受限**:
- 功能仅限管理员或高权限角色可访问
- 需要有效的会话认证且有严格的请求速率限制
- 响应内容不直接返回给用户，仅作内部处理或日志记录

**网络隔离保护**:
- 应用部署在隔离的 DMZ 区域，无法访问内网敏感服务
- Web服务器出口流量经过严格防火墙规则限制
- 使用反向代理且代理层实现了 SSRF 防护（如 Nginx 白名单代理）

**攻击面有限**:
- 仅允许获取特定资源类型（如图片，通过 `getimagesize()` 或 MIME 校验）
- 响应内容经过严格过滤，仅返回元数据而非完整内容
- 超时时间极短（`default_socket_timeout` < 2秒），难以进行慢速扫描
- 使用 `file_get_contents()` 的 `maxlen` 参数限制读取大小

**部分缓解措施**:
- 虽有可绕过风险，但需复杂条件配合（如特定PHP版本、特定解析库）
- 有完善的监控告警机制，可快速检测异常请求特征（如内网IP访问）
- URL经过多层编码或映射转换，攻击者难以直接控制最终目标
- 配置了 `open_basedir` 限制，即使 `file://` 可用也无法读取敏感路径
