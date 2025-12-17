# PHP Unserialize POP Chain 漏洞

**漏洞概述**  
通过 `unserialize()` 函数将用户可控数据反序列化，触发对象魔术方法链（POP Chain），常出现在会话管理、缓存系统、Cookie 处理、API 数据交互等场景。攻击者构造恶意序列化字符串，利用现有类的魔术方法实现任意代码执行、文件操作、SQL 注入等。

---

## Details

### 典型代码示例

**场景1：直接 unserialize 用户输入**
```php
// 危险：直接反序列化 GET/POST 参数
$data = $_GET['data'];
$obj = unserialize($data);        // 触发点：用户完全可控

$userInfo = unserialize($_COOKIE['session']);  // 触发点：Cookie 可控
```

**场景2：Base64 编码后反序列化**
```php
// 危险：仅 Base64 编码不改变反序列化风险
$encoded = $_POST['payload'];
$decoded = base64_decode($encoded);
$obj = unserialize($decoded);     // 触发点：编码不是防护

// 常见于 JWT、Cookie、缓存 Key
$token = json_decode(base64_decode($_COOKIE['auth']), true);
$user = unserialize($token['data']);  // 触发点
```

**场景3：数据库/缓存中的序列化数据**
```php
// 危险：从数据库读取用户曾提交的序列化数据
$row = $db->query("SELECT serialized_data FROM cache WHERE id=" . $_GET['id']);
$data = unserialize($row['serialized_data']);  // 触发点：历史污染

// Redis/Memcached 缓存反序列化
$cached = $redis->get($_GET['key']);
$object = unserialize($cached);    // 触发点：缓存投毒
```

**场景4：Session 自定义处理器**
```php
// 危险：session.serialize_handler 不匹配
ini_set('session.serialize_handler', 'php');  // 写入用 php 格式
session_start();
$_SESSION['user'] = $_GET['name'];

// 另一脚本
ini_set('session.serialize_handler', 'php_serialize');  // 读取用 php_serialize
session_start();  // 触发点：格式混淆导致对象注入
```

**场景5：API 响应/Webhook 处理**
```php
// 危险：反序列化外部 API 返回数据
$response = file_get_contents($_POST['callback_url']);
$result = unserialize($response);  // 触发点：SSRF + 反序列化

// Webhook 处理
$payload = file_get_contents('php://input');
$event = unserialize($payload);    // 触发点：POST Body 可控
```

**场景6：文件上传后反序列化**
```php
// 危险：上传的文件内容被反序列化
$file = $_FILES['import']['tmp_name'];
$content = file_get_contents($file);
$data = unserialize($content);     // 触发点：文件内容可控
```

**场景7：常见 POP Chain Gadget 示例**
```php
// Gadget 1: __destruct 触发文件操作
class FileHandler {
    private $filename;
    private $content;
    
    function __destruct() {
        file_put_contents($this->filename, $this->content);  // 任意文件写入
    }
}

// Gadget 2: __wakeup 触发任意方法调用
class Logger {
    private $handler;
    private $method;
    
    function __wakeup() {
        $this->handler->{$this->method}();  // 动态方法调用
    }
}

// Gadget 3: __toString 触发代码执行
class Template {
    private $template;
    
    function __toString() {
        eval($this->template);   // 代码执行
        return "";
    }
}

// Gadget 4: __call 触发任意函数调用
class Proxy {
    private $callbacks = [];
    
    function __call($name, $args) {
        call_user_func_array($this->callbacks[$name], $args);  // 任意函数
    }
}

// Gadget 5: __get 触发属性链
class Config {
    private $data = [];
    
    function __get($name) {
        return $this->data[$name]->value;  // 触发下一个对象的 __toString
    }
}

// Gadget 6: __invoke 触发函数调用
class Executor {
    private $command;
    
    function __invoke() {
        system($this->command);  // 命令执行
    }
}

// Gadget 7: __set 触发链式调用
class Model {
    private $attributes = [];
    
    function __set($key, $value) {
        $this->attributes[$key] = $value;
        $this->save();  // 可能触发 SQL 注入或其他操作
    }
}

// Gadget 8: __isset 触发路径遍历
class Router {
    private $routes;
    
    function __isset($name) {
        return file_exists($this->routes[$name]);  // 文件探测
    }
}
```

**场景8：框架/库中的已知 Gadget**
```php
// Laravel <= 5.8.* （示例）
// 利用 Illuminate\Broadcasting\PendingBroadcast

// ThinkPHP 5.x（示例）
// 利用 think\Request + think\Model

// Symfony（示例）  
// 利用 Symfony\Component\Cache\Adapter\TagAwareAdapter

// Yii 2.x（示例）
// 利用 yii\db\BatchQueryResult

// Guzzle（示例）
// 利用 GuzzleHttp\Psr7\FnStream

// Monolog（示例）
// 利用 Monolog\Handler\SyslogUdpHandler

// SwiftMailer（示例）
// 利用 Swift_KeyCache_DiskKeyCache
```

---

### 快速定位核心操作的技巧

**L1 - 关键词扫描：**
- 反序列化函数：`unserialize(`
- 相关函数：`unserialize_callback_func`、`__unserialize()`（PHP 7.4+）
- 间接触发：`phar://` 协议（见 PHP_Phar_Deserialization.md）、`session_start()`（见 PHP_Session_Deserialization_RCE.md）

**L2 - 跳读定位数据来源：**
- 检查 `unserialize()` 的参数来源：`$_GET`、`$_POST`、`$_REQUEST`、`$_COOKIE`、`$_SERVER['HTTP_*']`
- 数据库/缓存读取：`$redis->get()`、`$memcache->get()`、`$db->query()` 结果、`file_get_contents()`
- 间接来源：API 回调、Webhook、文件上传内容、消息队列（RabbitMQ、Kafka）
- 检查是否有编码层：`base64_decode()`、`gzuncompress()`、`json_decode()` 后再 unserialize

**L3 - 逐行追踪数据流：**
- 跟踪用户输入从接收到传递给 `unserialize()` 的完整路径
- 检查中间处理：是否有签名校验（HMAC）、加密（`openssl_decrypt`）、格式校验
- 验证过滤逻辑：`preg_match('/^[OC]:\d+:/', $data)` 检测对象序列化、类名黑名单、`allowed_classes` 参数
- 确认数据持久化位置：数据库字段、缓存键、Session 文件、日志文件
- 检查是否存在二次注入：用户提交的序列化数据存储后被其他模块使用

**L4 - 跨模块追踪 POP Chain：**
- 全局搜索魔术方法：`function __destruct`、`function __wakeup`、`function __toString`、`function __call`、`function __get`、`function __set`、`function __isset`、`function __unset`、`function __invoke`、`function __clone`、`function __sleep`
- 识别危险操作：
  - 命令执行：`system`、`exec`、`shell_exec`、`passthru`、`popen`、`proc_open`、`pcntl_exec`、`` `cmd` ``、`mail` 第五参数
  - 文件操作：`file_put_contents`、`file_get_contents`、`unlink`、`rmdir`、`copy`、`rename`、`fwrite`、`include`、`require`
  - 代码执行：`eval`、`assert`、`create_function`、`preg_replace` `/e` 修饰符（PHP 5.x）、`call_user_func`、`call_user_func_array`、动态函数调用 `$func()`
  - SQL 操作：`$pdo->query()`、`mysqli_query()` 且参数拼接
  - 反射调用：`ReflectionClass`、`ReflectionMethod::invoke()`
- 检查第三方库依赖：`composer.json`、`vendor/` 目录版本、已知 CVE（phpggc 工具链库）
- 追踪属性链路：`$obj->prop1->prop2->dangerousMethod()`，绘制对象引用关系
- 关注 `__autoload`、`spl_autoload_register` 加载的类路径
- 检查类属性修饰符：`private` 属性序列化格式 `\x00ClassName\x00propertyName`，可能影响构造

---

### 快速定位保护机制的技巧

**L1 - 关键词扫描防护措施：**
- 类白名单：`unserialize($data, ['allowed_classes' => ['User', 'Session']])`（PHP 7.0+）
- 签名校验：`hash_hmac('sha256', $data, $secret)`、`hash_equals()`
- 加密保护：`openssl_encrypt()`、`sodium_crypto_secretbox()`
- 格式校验：`is_serialized()` 自定义函数、正则检测对象标识 `O:` 或 `C:`
- `disable_functions`：禁用危险函数
- Suhosin 扩展：`suhosin.executor.disable_eval`、`suhosin.serialize.filter`

**L2 - 跳读检查防护强度：**
```php
// 类白名单（有效，PHP 7.0+）
$options = ['allowed_classes' => ['stdClass', 'User']];
$obj = unserialize($data, $options);  // 仅允许指定类

// 签名校验（有效）
$expected = hash_hmac('sha256', $data, SECRET_KEY);
if (!hash_equals($expected, $_POST['signature'])) {
    die('Invalid signature');
}
$obj = unserialize($data);

// 格式黑名单（可能被绕过）
if (preg_match('/[OC]:\d+:/', $data)) {
    die('Object detected');  // 可能绕过：+ 号、空格、大小写
}

// 类名黑名单（不可靠）
if (strpos($data, 'eval') || strpos($data, 'system')) {
    die('Dangerous class');  // 绕过：命名空间、类混淆、属性名而非类名
}

// 仅检查数据类型（无效）
if (!is_string($data)) {
    die('Invalid type');  // 序列化数据本就是字符串
}
```

**L3 - 逐行分析防护有效性：**
- `allowed_classes` 是否包含可利用类（如 `Exception`、`SplFileObject`、`DirectoryIterator`）
- 签名算法强度：MD5/SHA1（碰撞风险）vs HMAC-SHA256（安全）
- 签名密钥来源：硬编码、环境变量、配置文件权限、是否泄露到前端
- 加密模式：ECB（不安全）vs GCM/CBC+HMAC（安全）、IV 是否随机
- 正则表达式严谨性：`/^[OC]:\d+:/` vs `/[OC]:\d+/`（前者更严格）
- 时间戳/Nonce 校验：防止重放攻击
- 数据来源信任边界：内网 API 是否也需要校验
- `unserialize` 错误处理：`@unserialize()` 抑制错误可能隐藏攻击

**L4 - 架构层全局防护：**
- PHP 配置：`disable_functions = system,exec,shell_exec,passthru,proc_open,popen,pcntl_exec,eval,assert`
- Suhosin/Hardened-PHP：`suhosin.executor.disable_eval = On`、`suhosin.executor.func.blacklist`
- Open_basedir 限制：`open_basedir = /var/www:/tmp`
- 使用 JSON 替代序列化：`json_decode($data, true)` 仅支持基本数据类型，无法实例化对象
- 数据签名 + 加密：`encrypt(sign($data))`，双重保护
- WAF 规则：检测 `O:` 或 `C:` 特征、常见 Gadget 类名（`think\Request`、`Illuminate\Broadcasting\PendingBroadcast`）
- 容器隔离：禁用不必要的系统调用（Seccomp）、只读文件系统
- 代码审计工具：RIPS、Psalm、PHPStan 静态分析
- 定期更新依赖：`composer update` 修复已知 Gadget CVE
- 使用不可序列化类：实现 `__sleep()` 返回空数组或抛出异常

---

## Classify

### 真实漏洞的判定标准
1. **外部可控数据**：`unserialize()` 的参数直接或间接来自用户输入（GET/POST/Cookie/Header/文件/数据库中的污点数据），且无有效签名或加密保护
2. **存在可利用 POP Chain**：代码库或第三方依赖中存在魔术方法链，能实现代码执行、文件操作、SQL 注入等危险操作，且属性可控
3. **无类白名单限制**：未使用 `allowed_classes` 参数（或白名单包含可利用类如 `Exception`、`SplFileObject`），允许任意类实例化
4. **防护机制缺失或可绕过**：无签名校验、签名密钥泄露、签名算法弱、加密可解密、正则黑名单不严谨、格式校验可绕过
5. **执行路径可达**：反序列化代码会实际执行（非测试/废弃代码），且攻击者可控制触发时机和次数

### 误报的典型特征
1. **数据源可信**：反序列化的数据完全来自服务端生成（如内部配置文件、服务端缓存），用户无法篡改原始数据
2. **强签名保护**：使用 HMAC-SHA256 签名且密钥安全管理（环境变量、密钥管理服务），攻击者无法伪造有效签名
3. **严格类白名单**：`allowed_classes` 仅包含安全的数据类（如 `stdClass`），或为 `false` 禁止所有对象实例化
4. **加密 + 签名**：数据先签名再加密，使用 AES-GCM 或 AES-CBC + HMAC，密钥不泄露
5. **无可用 POP Chain**：项目和所有依赖库中不存在可利用的魔术方法链，或 `disable_functions` 禁用所有危险操作
6. **不可达代码**：反序列化在废弃接口、内部测试工具或永远不执行的分支中
7. **使用 JSON 替代**：实际使用 `json_decode()` 而非 `unserialize()`，仅误报为序列化

### 代码异味的识别
1. **弱签名/加密**：使用 MD5、SHA1 签名（可碰撞），或 Base64 编码（非加密）作为防护
2. **黑名单过滤**：检测 `O:`、`C:` 字符串但未考虑变种（大小写、`+` 号、空格、URL 编码）
3. **类名黑名单**：基于字符串匹配禁止特定类名，可通过命名空间、继承、别名绕过
4. **部分保护**：仅对 Cookie 进行签名，对 POST 参数无校验
5. **密钥硬编码**：签名/加密密钥直接写在代码中或配置文件提交到 Git
6. **时间窗口风险**：数据存储到数据库后未再校验签名，可能被数据库注入篡改
7. **存在潜在 Gadget**：魔术方法中有危险操作但当前未被利用，随依赖更新可能变为可利用
8. **依赖过期**：使用已知存在 POP Chain CVE 的旧版本库（Laravel 5.7、ThinkPHP 5.0.x、Yii 2.0.37 前）
9. **混合序列化格式**：同一应用不同模块使用不同 `session.serialize_handler`，可能导致格式混淆

---

## Low Risk

### 低风险场景的评判依据

**完善的密码学保护**
- 使用 HMAC-SHA256 或更强算法签名，且密钥通过 KMS/Vault 管理，定期轮换
- 加密使用 AES-256-GCM 或 ChaCha20-Poly1305（AEAD 模式），IV/Nonce 随机生成且不重复
- 签名和加密密钥分离，使用 `sign(encrypt(data))` 或 `encrypt(sign(data))` 模式
- 时间戳 + Nonce 机制防止重放攻击，服务端记录已消费 Token

**严格的类白名单**
- `allowed_classes` 仅包含纯数据类（DTO），无魔术方法或仅简单 getter/setter
- 白名单动态生成且经过安全审计，定期扫描新增类
- 使用 `allowed_classes => false` 完全禁止对象实例化，仅允许数组和标量

**数据源完全可信**
- 反序列化数据由服务端内部生成（如缓存预热、定时任务），不涉及用户输入
- 数据存储在隔离的内部缓存（如进程内存、Redis 私有实例），用户无网络访问权限
- 使用 UUID 或高熵随机字符串作为缓存键，用户无法枚举

**无可用攻击链**
- 项目和所有第三方库（包括传递依赖）无已知 POP Chain Gadget
- 魔术方法仅用于简单日志记录或 DTO 序列化，无文件/网络/数据库操作
- `disable_functions` 禁用所有命令执行函数（`system,exec,shell_exec,passthru,proc_open,popen,pcntl_exec`）
- `open_basedir` 限制文件访问范围，无法写入敏感路径（`/var/www/html`、`/tmp/.sess`）

**架构层安全隔离**
- 运行在容器中且使用 Seccomp 限制系统调用（禁止 `execve`、`fork`）
- 文件系统只读挂载（除日志目录），即使写入 Webshell 也无法执行
- SELinux/AppArmor 强制访问控制，禁止 PHP 进程执行外部命令
- 网络隔离：Web 服务器无互联网出站权限，无法下载远程 Payload

**替代方案采用**
- 使用 JSON/MessagePack/Protobuf 替代 PHP 序列化，仅传输基本数据类型
- 使用 JWT（HS256/RS256）且正确校验签名，Payload 仅包含基本类型字段
- 对象存储采用 ID 引用而非序列化整体对象（如用户 ID 而非 User 对象）

**业务场景限制**
- 功能仅对内部运维/管理员开放，需要 VPN + 双因素认证
- 反序列化操作有严格的速率限制和审计日志，异常访问触发告警
- 功能处于下线计划中，已迁移新架构（微服务 + gRPC）
- 即使触发反序列化，因环境限制（无网络、无可写目录、强沙箱）无法达成实际危害