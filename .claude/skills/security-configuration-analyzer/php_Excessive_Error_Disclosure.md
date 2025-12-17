# PHP 过度错误披露（Excessive Error Disclosure）

## Details

### 代码示例

**php.ini / .htaccess 配置**
```php
; 直接暴露详细错误信息
display_errors = On
error_reporting = E_ALL
expose_php = On

; 会话配置缺陷
session.cookie_httponly = Off
session.cookie_secure = Off
session.use_strict_mode = Off

; 危险功能开启
allow_url_include = On
allow_url_fopen = On
```

**代码中动态设置**
```php
// 生产环境开启错误显示
ini_set('display_errors', '1');
ini_set('display_startup_errors', '1');
error_reporting(E_ALL);

// 未过滤错误信息输出
try {
    $conn = new PDO("mysql:host=$host;dbname=$db", $user, $pass);
} catch (PDOException $e) {
    die("Connection failed: " . $e->getMessage());  // 暴露数据库信息
}

// 文件操作直接抛出错误
$file = fopen("/etc/passwd", "r") or die("Unable to open file!");
```

**Apache .htaccess**
```apache
php_flag display_errors on
php_value error_reporting -1
php_flag expose_php on
```

### 快速定位核心操作（L1 - L2）

**（L1：关键词扫描）配置文件全局搜索**
- `display_errors`、`display_startup_errors`、`error_reporting`
- `expose_php`、`log_errors`、`error_log`
- `session.cookie_httponly`、`session.cookie_secure`
- `allow_url_include`、`allow_url_fopen`

**（L2：跳读）代码中动态设置**
- 搜索 `ini_set()`、`ini_alter()`、`error_reporting()` 调用
- 关注 `catch` 块中的 `getMessage()`、`getTraceAsString()` 直接输出
- 检查 `die()`、`exit()` 中是否包含敏感错误信息
- 查找 `trigger_error()`、`user_error()` 在生产代码中的使用

**（L2：跳读）环境判断缺失**
- 确认是否有 `getenv('APP_ENV')`、`$_SERVER['SERVER_NAME']` 环境判断
- 检查错误配置是否仅在开发环境生效

### 快速定位保护机制（L1 - L3）

**（L1：关键词扫描）正确配置特征**
```php
display_errors = Off          // 生产环境必须关闭
log_errors = On              // 记录到文件而非输出
error_log = /var/log/php_errors.log
session.cookie_httponly = On  // 防止 XSS 窃取 cookie
session.cookie_secure = On    // 强制 HTTPS
```

**（L2：跳读）自定义错误处理**
- 搜索 `set_error_handler()`、`set_exception_handler()` 注册
- 确认自定义处理器是否过滤敏感信息（文件路径、SQL语句、堆栈跟踪）
- 检查是否区分开发/生产环境输出不同错误详情

**（L3：逐行读）错误响应内容**
- 追踪异常捕获后的输出内容：是否包含 `$e->getMessage()`、`__FILE__`、`__LINE__`
- 验证 JSON API 错误响应：`{"error": "Internal Server Error"}` vs `{"error": "Query failed: ..."}`
- 确认数据库连接失败、文件操作失败是否返回泛化错误

**（L3：逐行读）日志记录机制**
- 确认 `error_log()` 调用存在且路径安全（非 Web 可访问）
- 检查日志文件权限配置（应为 600 或 640）
- 验证敏感数据（密码、令牌）在记录前是否脱敏

## Classify

**真实漏洞判定**
- 生产环境 `display_errors=On` 且无环境隔离：直接暴露路径、SQL、逻辑细节
- 异常信息未过滤直接返回给客户端：数据库连接字符串、内部 IP、版本信息
- `expose_php=On` 且服务器版本存在已知漏洞：信息泄露辅助进一步攻击
- Session cookie 配置缺陷且存在 XSS：cookie 可被盗取

**误报判定**
- 仅在明确的开发环境（localhost、*.dev 域名）开启详细错误
- 错误信息已通过白名单过滤（仅返回错误码而非原始消息）
- 配置文件为模板或示例文件（.example、.dist 后缀），实际部署时会替换
- 测试代码或注释掉的配置（被 `#` 或 `;` 注释）

**代码异味判定**
- 有自定义错误处理但过滤不彻底：仍泄露部分非关键信息（如模块名称）
- 错误日志记录到 Web 可访问目录但文件权限正确（403 拦截）
- `error_reporting` 级别过高但 `display_errors` 已关闭：无直接危害但不规范
- Session 配置在非敏感系统中偏弱：无高价值数据但不符合最佳实践

## Low risk

**应评为低风险的场景**
- **纯静态站点**：无数据库交互、无用户认证，错误信息泄露价值极低
- **内网隔离环境**：仅内部人员可访问，且已有严格网络隔离和访问控制
- **沙箱/演示系统**：明确标识为测试环境，不包含真实生产数据
- **错误信息已部分脱敏**：虽显示错误但已移除路径、版本号、SQL 语句等关键细节
- **仅泄露非敏感配置**：如 `expose_php` 但系统已全面加固，版本信息价值有限
- **有效的 WAF/IDS 防护**：虽然配置不当，但外层已有强防御规则阻止信息利用
- **极低流量内部工具**：使用频率低、用户范围小、无外部暴露的管理后台