# PHP Insecure Session Config

## Details

### 代码示例

**php.ini / .htaccess 配置：**
```php
session.cookie_httponly = Off        // Cookie可被JS读取，易遭XSS窃取
session.cookie_secure = Off          // 允许HTTP传输，明文泄露风险
session.use_strict_mode = Off        // 接受未初始化SessionID，易被固定
session.use_only_cookies = Off       // 允许URL传参，日志/Referer泄露
session.cookie_samesite = None       // 无CSRF防护
session.gc_maxlifetime = 86400       // 会话存活时间过长
```

**代码层级设置：**
```php
ini_set('session.cookie_httponly', 0);
ini_set('session.cookie_secure', false);
session_set_cookie_params(0, '/', '', false, false);  // 参数4:secure, 参数5:httponly
setcookie(session_name(), session_id(), 0, '/', '', false, false);
```

**session_start()前未设置：**
```php
session_start();  // 直接启动，依赖php.ini默认配置
$_SESSION['user'] = $username;
```

### 快速定位核心操作

**（L1）关键词扫描：**
- `session.cookie_httponly`、`session.cookie_secure`、`session.use_strict_mode`
- `session_set_cookie_params`、`setcookie(session_name()`
- `ini_set.*session\.`

**（L2）跳读php.ini/.htaccess：**
- 直接查看Session段配置块，扫描Off/0/false值
- 检查.htaccess中php_value/php_flag指令

**（L3）逐行读session_start()前置代码：**
- 追溯ini_set/session_set_cookie_params调用位置
- 确认参数值（动态变量需回溯赋值）

### 快速定位保护机制

**（L1）关键词扫描：**
- `httponly.*=.*true`、`secure.*=.*true`
- `use_strict_mode.*=.*On`

**（L2）跳读配置文件/框架初始化：**
- 检查production环境配置覆盖
- Laravel: `config/session.php`中secure/http_only
- Symfony: `framework.session.cookie_secure`

**（L3）逐行读中间件/拦截器：**
- 自定义会话处理器SessionHandler实现
- 框架级session启动封装（如beforeAction钩子）

**（L4）跨模块追踪WAF/网关：**
- Nginx配置：`proxy_cookie_flags` 指令强制httponly
- CDN层：Cloudflare自动启用Secure标志
- API网关：Kong/APISIX的cookie改写插件

## Classify

**漏洞判定：**
- 存储敏感凭证的会话（登录态、权限Token）且无httponly/secure → 高危
- 生产环境显式关闭use_strict_mode → 中危会话固定风险
- HTTPS站点但secure=Off → 降级攻击窗口

**误报识别：**
- 测试环境配置（需结合部署上下文）
- 非认证会话（如匿名购物车、语言偏好）
- 已有上层网关统一加固（需验证实际HTTP响应头）

**代码异味：**
- 配置项分散在多处（php.ini + 代码动态设置）
- 使用已废弃函数session_register()关联配置
- 注释掉的安全配置残留

**研判流程：**
1. 确认会话用途（是否存储敏感信息）
2. 检查部署环境（HTTPS/内网/公网）
3. 验证实际响应头Set-Cookie标志（动态测试优先）
4. 排查补偿控制（WAF改写、双Token机制）

## Low risk

**业务场景：**
- 仅存储非敏感UI状态（主题、语言）
- 短生命周期临时会话（验证码、一次性Token）
- Stateless架构中的兼容性遗留配置（实际不使用Session）

**环境限制：**
- 纯内网系统（办公网/VPC内）且无外部接入
- 使用HTTPS + HSTS强制安全传输（可弥补secure=Off）
- 前置代理已统一注入httponly/secure标志（经实测验证）

**补偿措施到位：**
- 实施双Token验证（Session + CSRF Token）
- 短期轮换SessionID（每次请求regenerate）
- 同时使用JWT等无状态认证作为主要凭证
- 严格IP/UA绑定校验

**评级原则：**
- 缺乏httponly但有严格CSP阻止内联脚本 → 降为低危
- 缺乏secure但强制HSTS + 无HTTP监听端口 → 低危
- 多重配置缺陷但实际未激活会话机制 → 代码异味