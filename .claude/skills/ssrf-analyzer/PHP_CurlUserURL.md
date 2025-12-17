# PHP Curl User-Controlled URL SSRF

**漏洞类型**: cURL 库中直接使用用户输入的 URL，缺乏对目标地址的验证

**漏洞成因**

PHP 应用使用 cURL 库（`curl_init()`、`curl_exec()`）发起 HTTP 请求时，若将用户输入直接用作请求目标且未验证，攻击者可指向内网资源、元数据服务、本地文件，导致：

- 内网服务扫描与探测
- 云环境元数据泄露（AWS、GCP、Azure）
- 本地敏感文件读取（`file://` 协议）
- DNS 重绑定攻击
- 内网反向代理穿透

---

## Details

### 代码示例

**危险模式1：直接使用用户输入初始化 curl 请求**
```php
// ❌ 直接使用用户输入初始化curl请求
$url = $_GET['url'];
$ch = curl_init($url);  // 用户完全控制URL
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
$response = curl_exec($ch);
echo $response;  // 响应直接返回

// ❌ 变体：通过CURLOPT_URL设置
$ch = curl_init();
curl_setopt($ch, CURLOPT_URL, $_POST['target']);  // POST参数可控
curl_exec($ch);

// ❌ 高危模式：支持多个协议
curl_setopt_array($ch, [
    CURLOPT_URL => $userInput,
    CURLOPT_FOLLOWLOCATION => true,  // 允许跟随重定向
    CURLOPT_PROTOCOLS => CURLPROTO_HTTP | CURLPROTO_HTTPS | CURLPROTO_FTP
]);
```

**危险模式2：从用户输入构造 URL 的主机部分**
```php
// ❌ Host 由用户指定
$host = $_GET['host'];
$port = $_GET['port'] ?? 80;
$url = "http://{$host}:{$port}/api/data";

$ch = curl_init();
curl_setopt($ch, CURLOPT_URL, $url);
curl_exec($ch);

// 攻击者可指向：
// - http://127.0.0.1:8080
// - http://169.254.169.254:80 (AWS元数据)
// - http://10.0.0.1:3306 (内网数据库)
```

**危险模式3：不完整的黑名单检查**
```php
// ❌ 仅禁止127.0.0.1，但允许其他内网地址
$url = $_GET['url'];

if (strpos($url, '127.0.0.1') !== false || strpos($url, 'localhost') !== false) {
    die('Access denied');
}

// 攻击者可使用：
// - http://127.1 (八进制简写)
// - http://0 (等同127.0.0.1)
// - http://169.254.169.254
// - http://10.0.0.1
// - http://[::1] (IPv6本地回环)

$ch = curl_init($url);
curl_exec($ch);
```

**危险模式4：协议检查不完整或可被绕过**
```php
// ❌ 仅检查字符串前缀，大小写可绕过
$url = $_GET['url'];

if (!preg_match('/^https?:\/\//i', $url)) {
    die('Invalid protocol');
}

// 但 cURL 支持多种协议：file://、gopher://、dict://、ldap://、sftp://
// 且curl_setopt可显式允许危险协议

$ch = curl_init();
// 若设置了这行，可使用file://读取本地文件
curl_setopt($ch, CURLOPT_PROTOCOLS, CURLPROTO_HTTP | CURLPROTO_HTTPS | CURLPROTO_FILE);
curl_setopt($ch, CURLOPT_URL, $url);
curl_exec($ch);
```

**危险模式5：重定向跟随导致 SSRF 链**
```php
// ❌ 允许重定向，但重定向目标不验证
$url = $_GET['url'];

// 白名单检查
$whitelist = ['example.com', 'github.com'];
$parsed = parse_url($url);
if (!in_array($parsed['host'], $whitelist)) {
    die('Host not whitelisted');
}

$ch = curl_init();
curl_setopt($ch, CURLOPT_URL, $url);
curl_setopt($ch, CURLOPT_FOLLOWLOCATION, true);  // 允许跟随重定向
curl_setopt($ch, CURLOPT_MAXREDIRS, 5);  // 最多跟随5次
curl_exec($ch);

// 问题：example.com 可能302重定向到 http://127.0.0.1:9200
// 重定向目标不再验证，导致SSRF
```

**危险模式6：DNS 重绑定攻击**
```php
// ❌ 先验证IP，后请求时可能重新解析
$domain = $_GET['domain'];

// 验证DNS解析不是私网
$ip = gethostbyname($domain);
if (preg_match('/^(127\.|10\.|172\.16\.|192\.168\.|169\.254\.)/', $ip)) {
    die('Private IP rejected');
}

// 问题：在检查与请求之间，DNS可被重绑定
$ch = curl_init();
curl_setopt($ch, CURLOPT_URL, "http://{$domain}");
curl_exec($ch);
```

**危险模式7：响应内容泄露导致信息泄露**
```php
$url = $_GET['url'];

$ch = curl_init();
curl_setopt($ch, CURLOPT_URL, $url);
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
$response = curl_exec($ch);
$error = curl_error($ch);

// 响应直接返回给用户，可泄露内网信息
echo "Response: " . htmlspecialchars($response);
echo "Error: " . htmlspecialchars($error);  // 错误消息可能包含内网IP、服务名
```

**危险模式8：使用 CURLOPT_CUSTOMREQUEST 导致请求方法混淆**
```php
// ❌ 请求方法由用户指定
$method = $_GET['method'];  // 用户可指定DELETE、PUT等
$url = $_GET['url'];

$ch = curl_init();
curl_setopt($ch, CURLOPT_URL, $url);
curl_setopt($ch, CURLOPT_CUSTOMREQUEST, $method);  // GET、POST、DELETE等
curl_exec($ch);

// 攻击者可用 DELETE 删除内网服务的资源
```

### 快速定位核心操作 **[L1-L2]**

**关键词扫描:**
- 函数调用：`curl_init()`、`curl_exec()`、`curl_setopt()`、`curl_setopt_array()`
- 参数选项：`CURLOPT_URL`、`CURLOPT_CUSTOMREQUEST`、`CURLOPT_POSTFIELDS`、`CURLOPT_PROTOCOLS`
- 参数来源：`$_GET`、`$_POST`、`$_REQUEST`、`$_SERVER['HTTP_*']`、`$_COOKIE`、数据库查询
- URL 处理：`` `http://{$...}` ``、字符串拼接、`parse_url()`

**快速定位保护机制 [L2-L3]**

- **协议限制**：
  - 搜索 `CURLOPT_PROTOCOLS`、`parse_url(...)[scheme]`、正则 `/^https?:/i`
  - 检查是否仅允许 `http`、`https`（应排除 `file://`、`gopher://` 等）

- **IP/域名验证**：
  - 搜索 `in_array()`、`preg_match()`、`gethostbyname()`、`CURLOPT_RESOLVE`
  - 检查白名单或黑名单的完整性（注意 IP 变形：127.1、0、十进制等）

- **重定向防护**：
  - 搜索 `CURLOPT_FOLLOWLOCATION`、`CURLOPT_MAXREDIRS`
  - 检查是否禁用（值为 `false`、`0`）或在重定向后再次验证

- **审计等级**：
  - **L1**: 存在白名单/过滤关键字 → 跳读实现
  - **L2**: 有基础验证但可能不完整 → 逐行审查绕过方式
  - **L3**: 白名单逻辑复杂但跨模块 → 追踪所有调用点
  - **L4**: DNS 重绑定防护或使用库自动防护

---

## Classify

**确认为真漏洞的特征:**
1. URL 参数完全来自用户输入，无任何验证
2. 验证缺失或可被绕过（黑名单不完整、协议检查错误、IP 变形未考虑）
3. 支持危险协议（`file://`、`gopher://`、`dict://` 等）
4. 可跟随重定向至内网地址
5. 存在 DNS 重绑定风险（验证后可重新解析）
6. 请求方法可由用户指定（DELETE、PUT 等）
7. 响应直接返回或错误消息泄露内网信息

**误报判定:**
- URL 硬编码或来自可信配置文件，非运行时用户输入
- 仅路径参数可控，`scheme` 和 `host` 完全硬编码
- 存在严格的白名单：精确匹配 + 协议限制 + IP 验证 + 重定向禁止
- 使用 `CURLOPT_RESOLVE` 预定义 IP 映射防护 DNS 重绑定
- 功能仅限高权限用户访问

**代码异味:**
- 使用黑名单而非白名单
- 白名单检查使用字符串 `strpos()` 而非 `parse_url()` + `in_array()`
- 验证仅检查 `127.0.0.1`、`localhost`，未覆盖其他私网段
- 未显式限制协议，依赖 cURL 默认行为
- 重定向处理不当，允许跟随但不重新验证

---

## Low risk

**以下场景可评为低风险:**

1. **严格的白名单防护**
   - 使用 `in_array($host, $whitelist, true)` 精确匹配
   - 显式设置 `CURLOPT_PROTOCOLS => CURLPROTO_HTTPS` 仅限 HTTPS
   - 重定向禁用：`curl_setopt($ch, CURLOPT_FOLLOWLOCATION, false)`
   - 或使用 `CURLOPT_RESOLVE` 预定义 IP 映射防护 DNS 重绑定

2. **内网资源访问受网络层限制**
   - 应用运行在隔离环境，防火墙显式禁止访问内网敏感段
   - 元数据服务地址被防火墙阻止

3. **仅允许特定操作**
   - 仅支持 GET 请求，不允许 DELETE、PUT 等修改操作
   - 超时时间极短（<3s），难以进行端口扫描
   - 响应大小限制，防止加载超大文件

4. **响应内容控制**
   - 响应内容不直接返回给用户，仅用于内部处理
   - 错误消息经过过滤，不泄露内部信息（IP、服务名）

5. **功能访问受限**
   - 此功能仅限管理员或高权限用户
   - 有严格的速率限制和审计日志

6. **使用标准库自动防护**
   - 使用经过安全审计的 cURL 版本和 PHP 版本
   - 或使用 Composer 包提供的安全包装库（如 Guzzle）

**审计重点场景对照表:**

| 攻击场景 | 检查点 | 利用方式 |
|--------|------|--------|
| **内网探测** | 无 IP 限制 | 遍历 `10.0.0.0/8` 访问内网服务 |
| **元数据泄露** | 支持 HTTP、无 IP 过滤 | 访问 `169.254.169.254`（AWS/GCP 元数据） |
| **文件读取** | 无协议限制 | `file:///etc/passwd` |
| **本地服务接管** | 允许跟随重定向 | 302 重定向到 `http://127.0.0.1:9000` |
| **DNS 重绑定** | 无 IP 锁定 | 第一次解析外网 IP，cURL 前重绑至 127.0.0.1 |
| **请求方法混淆** | `CURLOPT_CUSTOMREQUEST` 可控 | DELETE 删除内网资源 |