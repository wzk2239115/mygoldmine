# PHP JWT Missing Signature Verify

## 漏洞成因
JWT 解码时未调用签名验证方法或显式跳过验证步骤，导致接受任意伪造的令牌。

## Details

### 代码示例
```php
// 漏洞示例1：直接base64解码不验证签名
$parts = explode('.', $jwt);
$payload = json_decode(base64_decode($parts[1]), true);
$userId = $payload['sub'];

// 漏洞示例2：使用第三方库但跳过验证
use Firebase\JWT\JWT;
JWT::$leeway = 60;
$decoded = JWT::decode($jwt, null, []); // 密钥为null

// 漏洞示例3：自定义解码未实现验证
function parseJWT($token) {
    list($header, $payload, $signature) = explode('.', $token);
    return json_decode(base64_decode($payload), true); // 仅解码不验证
}
```

### 快速定位核心操作 (L1: 关键词扫描 + L3: 逐行读)
- **L1 关键词**：搜索 `JWT::decode`、`base64_decode`、`json_decode`、`explode('.'`、自定义函数名含 `parseJWT`/`decodeJWT`/`verifyJWT`
- **定位技巧**：关注认证中间件、登录后接口、权限校验入口处的 token 处理逻辑
- **核心判断**：检查是否存在签名验证步骤（HMAC 计算、RSA 验签、调用库的验证方法）

### 快速定位保护机制 (L2: 跳读 + L4: 跨模块追踪)
- **L2 跳读重点**：
  - 检查 `JWT::decode` 第二参数是否为有效密钥（非 null/空字符串）
  - 检查是否调用 `hash_hmac` 或 `openssl_verify` 进行签名对比
  - 检查自定义函数是否返回验证状态布尔值
- **L4 跨模块追踪**：
  - 追踪密钥来源：配置文件、环境变量、密钥管理服务
  - 追踪验证失败的异常处理：是否捕获 `SignatureInvalidException`
  - 追踪中间件链：验证逻辑是否在权限检查前执行

## Classify

### 漏洞判定
- **确认漏洞**：完全不进行签名验证，直接使用 payload 数据用于权限判断或敏感操作
- **误报排除**：仅用于日志记录、非敏感数据展示且不影响业务逻辑
- **代码异味**：
  - 在开发/测试环境跳过验证但生产环境正常
  - 验证逻辑存在但通过注释/条件判断被禁用
  - 验证在代码后续流程补上但逻辑割裂

### 研判要点
1. **数据流追踪**：解码后的数据是否直接用于 `$_SESSION`、数据库查询、权限判断
2. **异常处理**：是否捕获验证失败但未中断业务流程（如 try-catch 后继续执行）
3. **框架差异**：某些框架可能在中间件层统一验证，需跨文件确认

## Low risk

### 低风险场景
1. **功能隔离**：JWT 仅用于前端状态同步，后端通过 Session 独立验证身份
2. **二次验证**：虽未验证签名，但通过数据库对比 token 有效性（如白名单机制）
3. **只读操作**：解码数据仅用于非关键展示（用户昵称、头像）且不涉及权限变更
4. **内网环境**：仅在完全可信网络环境使用且无外部暴露接口
5. **临时令牌**：短效 token（<5分钟）且配合其他强验证机制（如短信验证码）

## 审计专业技巧

### 一级审计（代码层面）
#### 1. 密钥参数检查
```php
// ❌ 漏洞：密钥为空
JWT::decode($jwt, '', ['HS256']);
$decoded = JWT::decode($jwt, null, ['HS256']);

// ❌ 漏洞：密钥获取失败未处理
$key = getSecret(); // 可能返回 false/null
JWT::decode($jwt, $key, ['HS256']);

// ✅ 安全：显式密钥验证
if (!$key || strlen($key) < 32) {
    throw new Exception("Invalid secret key");
}
JWT::decode($jwt, $key, ['HS256']);
```

#### 2. 异常处理模式识别
```php
// ❌ 漏洞：捕获异常但继续执行
try {
    $payload = JWT::decode($jwt, $secret, ['HS256']);
} catch (Exception $e) {
    $payload = json_decode(base64_decode(explode('.', $jwt)[1]), true);
}
$userId = $payload['sub'];

// ✅ 安全：异常终止流程
try {
    $payload = JWT::decode($jwt, $secret, ['HS256']);
} catch (Exception $e) {
    http_response_code(401);
    exit("Unauthorized");
}
$userId = $payload['sub'];
```

#### 3. 条件判断陷阱
```php
// ❌ 漏洞：调试模式下跳过验证
if (DEBUG_MODE) {
    $payload = json_decode(base64_decode(explode('.', $jwt)[1]), true);
} else {
    $payload = JWT::decode($jwt, $secret, ['HS256']);
}

// ❌ 漏洞：特定用户或路径下跳过验证
if (isAdminUser() || $_GET['bypass']) {
    $payload = parseJWTUnsafe($jwt);
}

// 📌 审计要点：这些仍属漏洞，需要在所有代码路径完整验证
```

### 二级审计（数据流追踪）
#### 关键风险点
| 风险操作 | 漏洞表现 | 审计建议 |
|---------|--------|--------|
| 直接用于数据库查询 | `SELECT * FROM users WHERE id = {$jwt['sub']}` | 追踪 SQL 注入风险，验证身份绕过 |
| 权限判断依赖 | `if ($jwt['role'] == 'admin')` | 确认是否有会话验证、IP 检查配合 |
| 敏感操作授权 | 转账、删除账户、改密码 | 必须有签名验证 + 二次认证 |
| 跨域请求处理 | CORS 头配合无签名 JWT | 检查 CSRF token、SameSite cookie |

#### 数据流追踪示例
```php
// ❌ 漏洞链：无签名验证 + 权限变更
$token = $_GET['token'];
$payload = json_decode(base64_decode(explode('.', $token)[1]), true);
$userId = $payload['sub'];

// 直接改变数据库权限
$db->update('users', ['role' => 'admin'], ['id' => $userId]);

// 检查点：$payload 来自何处？是否验证？→ 直接base64解码，无验证
// 结果：攻击者可伪造 token 给自己赋予 admin 权限
```

### 三级审计（真实案例 vs 误报）

#### 案例 1：真实漏洞 - Laravel Passport 密钥泄露后的失效验证
```php
// 场景：开发者设置 JWT_SECRET=""（空密钥）
// .env: JWT_SECRET=

$key = env('JWT_SECRET', 'default-secret');
// 当 env 返回空时，密钥为空字符串
$decoded = JWT::decode($jwt, $key, ['HS256']);
// 任何人都可伪造 token

// 🔍 审计技巧：
// 1. 检查 .env.example 和 deploy 脚本确认密钥初始化
// 2. 搜索 'JWT_SECRET' 的所有引用
// 3. 测试：用空密钥能否生成有效 token
```

#### 案例 2：误报 - Laravel 中间件层验证
```php
// 代码看似无签名验证
public function parseToken($request) {
    $token = $request->bearerToken();
    return jwt_decode($token, null, []); // 看起来没验证！
}

// ❌ 误判：以为漏洞了
// ✅ 实际：在 middleware 的 handle() 中
public function handle($request, $next) {
    try {
        $payload = $this->auth->check(); // 调用了 Auth 服务
    } catch (TokenExpiredException $e) {
        return unauthorized();
    }
}

// Auth 服务中实际进行验证
public function check() {
    $token = request()->bearerToken();
    return JWT::decode($token, config('app.key'), ['HS256']);
}

// 🔍 审计技巧：跨文件追踪中间件链条，确认验证在何处执行
```

#### 案例 3：误报 - 前后端分离且 Session 验证
```php
// 看似无签名验证的解码
$payload = json_decode(base64_decode(explode('.', $jwt)[1]), true);
$userId = $payload['sub'];

// ❌ 初步判定：漏洞
// ✅ 实际审计结果：检查后续验证
$this->validateSessionToken($userId, $jwt); // 数据库查询验证

// 或
if (!isset($_SESSION['user_id']) || $_SESSION['user_id'] != $userId) {
    throw new UnauthorizedException();
}

// 🔍 审计技巧：
// 1. 检查 $jwt 是否存储在数据库白名单中
// 2. 确认 Session 是否由独立的、更安全的机制管理
// 3. 验证 token 是否与会话 ID 绑定
```

### 四级审计（环境 & 配置检查）
```bash
# 1. 检查密钥管理
grep -r "JWT.*SECRET\|JWT.*KEY" .env* config/ | grep -v ".example"

# 2. 检查异常捕获中是否有偷偷解码的行为
grep -A 5 "catch.*Exception" src/ | grep -E "json_decode|base64_decode"

# 3. 检查单元测试中是否有跳过验证的 mock
grep -r "JWT::decode.*null\|jwt.*\[\]" tests/

# 4. 检查是否存在调试/开发模式的条件判断
grep -r "DEBUG\|DEVELOPMENT\|env.*==.*dev" src/ | grep -B 2 -A 2 "JWT\|token"
```

## 真实漏洞与误报的分界点

### ✅ 确认为真实漏洞的标志
1. **完整链路无验证**：从 token 接收到业务数据使用，全程无签名验证
2. **影响敏感操作**：权限变更、资金转账、账户注销等关键功能
3. **可直接利用**：不需要其他漏洞配合，单独即可被利用
4. **默认风险**：在常见配置下就能被利用，非极端边界条件

### ❌ 排除的误报场景
1. **多层验证机制**：JWT 无验证但有会话验证、API Key 验证等独立防御
2. **只读非敏感数据**：仅用于展示用户昵称、头像等公开信息
3. **框架隐式保护**：某些框架在底层自动进行验证，代码表面上看不出
4. **防御深度防御**：即使 JWT 伪造，后续还有业务逻辑层防御（如权限表查询验证）