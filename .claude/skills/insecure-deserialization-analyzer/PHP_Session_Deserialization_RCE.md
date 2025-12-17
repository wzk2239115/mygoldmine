# PHP Session 反序列化 RCE

**漏洞概述**  
常出现在会话管理中，因不同 `session.serialize_handler` 配置不一致导致的反序列化漏洞。PHP 提供三种序列化引擎（`php`/`php_serialize`/`php_binary`），当写入和读取使用不同引擎时，可触发非预期的反序列化，配合 POP Chain 实现 RCE。

---

## Details

### 典型代码示例

**场景1：serialize_handler 不一致触发漏洞**
```php
// 页面A：上传处理器使用 php_serialize
ini_set('session.serialize_handler', 'php_serialize');
session_start();
$_SESSION['upload'] = $_POST['data']; // 用户可控内容

// 页面B：读取处理器使用 php
ini_set('session.serialize_handler', 'php');
session_start(); // 触发反序列化，将 php_serialize 格式按 php 格式解析
```

**场景2：自定义 Session Handler 直接调用 unserialize**
```php
class RedisSessionHandler implements SessionHandlerInterface {
    public function read($id) {
        $data = $this->redis->get("session:$id");
        return unserialize($data); // 危险：直接反序列化 Redis 数据
    }
}
session_set_save_handler(new RedisSessionHandler());
```

**场景3：session_decode() 手动解码**
```php
// 从数据库恢复会话
$sessionData = $db->query("SELECT data FROM sessions WHERE id='$sid'")->fetch();
session_decode($sessionData); // 危险：未验证数据来源
```

**场景4：文件上传与 session.upload_progress 结合**
```php
// php.ini: session.upload_progress.enabled = On
// 攻击者构造 multipart/form-data，PHP 自动写入 session
// <input name="PHP_SESSION_UPLOAD_PROGRESS" value="|O:4:\"Evil\":1:{...}">
// 若存在 handler 不一致，触发反序列化
session_start(); 
```

**场景5：session.save_path 可控导致包含**
```php
// 危险配置
ini_set('session.save_path', $_GET['path']); // 攻击者可指定路径
session_start(); // 读取指定路径下的 session 文件并反序列化
```

**场景6：跨应用共享 session 目录**
```php
// 应用A和应用B共享 /tmp/sessions/
// 应用A: ini_set('session.serialize_handler', 'php_serialize');
// 应用B: ini_set('session.serialize_handler', 'php'); // 不一致
session_start(); // 应用B读取应用A写入的 session 时触发漏洞
```

---

### 快速定位核心操作的技巧

**L1: 关键词扫描**
- `session_start()`、`session_decode()`、`session_regenerate_id()`
- `ini_set('session.serialize_handler')`、`session.serialize_handler` 配置
- `SessionHandlerInterface`、`session_set_save_handler()`
- `session.upload_progress.enabled`
- 自定义 handler 中的 `unserialize()`

**L2: 跳读识别配置差异**
- 检查 `php.ini`、`.htaccess`、`ini_set()` 中的 `session.serialize_handler` 设置
- 查找不同文件或模块中是否使用不同的 handler
- 识别 `php` vs `php_serialize` vs `php_binary` 的混用
- 检查框架配置（Laravel `config/session.php`、Symfony `framework.yaml`）

**L3: 逐行追踪数据流**
- 确认 `$_SESSION` 赋值的数据是否可控（`$_POST`、`$_GET`、`$_COOKIE`、上传文件名）
- 检查 session 数据写入路径（`session.save_path`）是否可控
- 分析自定义 handler 的 `read()`/`write()` 方法实现
- 追踪 `session_decode()` 的输入来源（数据库、Redis、文件、API）

**L4: 跨模块追踪 POP Chain**
- 识别项目中可用的魔术方法链：`__destruct()`、`__wakeup()`、`__toString()`
- 检查常见危险类：`SplFileObject`、`SimpleXMLElement`、框架特有 Gadget
- 分析自动加载的类（`composer` 依赖、`include_path`）
- 追踪 `eval()`、`assert()`、`system()` 等危险函数的调用链

---

### 快速定位保护机制的技巧

**L1: 关键词扫描防护措施**
- `session.serialize_handler` 全局统一配置
- `session_set_save_handler()` 的自定义实现中的验证逻辑
- `session.upload_progress.cleanup = On`
- `session.use_strict_mode = 1`（严格模式，拒绝未初始化的 session ID）
- `open_basedir` 限制 `session.save_path`

**L2: 跳读检查一致性**
```php
// 安全实践：全局统一 handler
// 在入口文件或 auto_prepend_file 中设置
ini_set('session.serialize_handler', 'php_serialize');

// 检查 handler 一致性
if (ini_get('session.serialize_handler') !== 'php_serialize') {
    die('Session handler mismatch detected');
}
```

**L3: 逐行分析防护强度**
- 验证自定义 handler 是否对数据进行签名校验（HMAC）
- 检查 `unserialize()` 前是否有 `allowed_classes` 参数（PHP 7.0+）
- 确认 session 数据是否加密存储（`sodium_crypto_secretbox`）
- 分析 `session.save_path` 是否为固定值且权限正确（0700）

**L4: 跨模块验证全局防护**
- 检查 WAF/中间件是否过滤 session 相关攻击特征
- 验证框架级别的 session 安全配置（加密、签名、HttpOnly、SameSite）
- 确认是否使用安全的 session 存储（数据库、Redis + 认证）
- 检查 PHP 版本是否包含 session 相关安全修复（PHP 5.5.2+ 修复了 upload_progress 竞争）

---

## Classify

### 真实漏洞的判定标准
1. **Handler 不一致**：存在多处 `session.serialize_handler` 配置且值不同，或不同模块使用不同引擎
2. **数据可控性**：`$_SESSION` 的赋值来源可被攻击者控制（用户输入、上传文件名、外部 API）
3. **无签名保护**：session 数据未使用 HMAC 或数字签名验证完整性
4. **存在 POP Chain**：项目中存在可利用的魔术方法链，或依赖包含已知 Gadget（如 Monolog、Guzzle、Symfony）

### 误报的典型特征
1. **Handler 全局统一**：所有 `session_start()` 前均使用相同的 `serialize_handler` 配置
2. **Session 数据只读**：`$_SESSION` 仅读取，未赋值用户可控数据
3. **强制签名校验**：自定义 handler 在反序列化前验证 HMAC-SHA256 签名且密钥安全
4. **不可达代码**：存在 handler 不一致但代码路径永不执行（如被注释、测试代码、feature flag 关闭）

### 代码异味的识别
1. **混用 handler 但无明显攻击面**：配置不一致但 `$_SESSION` 未存储用户输入
2. **依赖第三方 session 库**：使用框架 session 但未明确配置 handler（依赖默认值）
3. **session 数据存储外部化**：使用 Redis/Memcached 但未加密/签名，潜在中间人攻击风险
4. **upload_progress 未关闭**：`session.upload_progress.enabled = On` 且存在文件上传功能，竞争条件风险

---

## Low Risk

### 低风险场景的评判依据

**强制加密与签名**
- Session 数据序列化后使用 `openssl_encrypt()` 加密 + HMAC-SHA256 签名
- 密钥存储在环境变量或密钥管理服务（AWS KMS、HashiCorp Vault）
- 签名验证失败时拒绝反序列化且记录安全日志

**严格的 Handler 管理**
- 通过 `auto_prepend_file` 在所有脚本执行前强制设置统一 handler
- 使用配置管理工具（Ansible、Chef）确保 `php.ini` 一致性
- CI/CD 流程中检查 `ini_set('session.serialize_handler')` 的一致性

**限制 unserialize 可用类**
```php
// PHP 7.0+ 安全实践
$data = unserialize($sessionData, ['allowed_classes' => ['User', 'Cart']]);
```

**隔离环境与监控**
- Session 处理运行在独立容器且禁用危险函数（`disable_functions`）
- 使用只读文件系统，session 数据存储在内存或加密卷
- 部署 RASP（Runtime Application Self-Protection）监控反序列化行为
- 启用 PHP opcache.protect_memory 防止内存篡改

**Session ID 严格管理**
- `session.use_strict_mode = 1`（拒绝攻击者提供的 session ID）
- `session.cookie_httponly = 1` + `session.cookie_secure = 1` + `session.cookie_samesite = Strict`
- 定期 `session_regenerate_id(true)` 防止固定攻击
- Session ID 熵值足够（`session.sid_bits_per_character >= 5`）

**业务逻辑限制**
- Session 仅存储基础类型（字符串、整数、布尔值），不存储对象
- 攻击成功后因网络隔离无法外联或访问敏感资源
- 应用处于维护模式，计划迁移到 JWT 或加密 Cookie 方案

**协议与版本限制**
- PHP 7.2+ 使用 `session_set_save_handler()` 时强制实现 `SessionUpdateTimestampHandlerInterface`
- 使用 `php_serialize` handler（相对安全，无分隔符歧义）
- 框架强制加密 session（Laravel encrypted cookies、Symfony framework.session.cookie_secure）