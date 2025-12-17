---
name: general
description: 会话管理和身份认证通用漏洞模式快速参考 - 所有涉及用户认证的项目必审
---

# 会话管理和身份认证通用漏洞模式快速参考

任何涉及用户身份认证和会话管理的应用都必须审计以下漏洞模式。

---

## 1. 会话令牌生成缺陷

**风险**：会话劫持、身份冒充

**危险代码示例**
```java
Random rand = new Random();
String sessionId = String.valueOf(rand.nextInt(10000));  // 危险！
```

```python
import random, time
random.seed(time.time())
session_id = str(random.randint(1000000, 9999999))  # 危险！
```

**安全标准**
- 使用密码学安全随机数生成器（SecureRandom、secrets、crypto.randomBytes）
- 长度至少 32 字节（256 位）

**快速定位**：`new Random()`、`Math.random()`、`random.random()`、`rand()`、`mt_rand()`

---

## 2. 会话令牌存储和传输缺陷

**风险**：会话劫持、XSS 攻击、MITM 攻击、篡改

**危险代码示例**
```java
Cookie cookie = new Cookie("sessionId", sessionId);
response.addCookie(cookie);  // 缺少安全属性！
```

```python
response.set_cookie('user_role', 'admin')  // 客户端可修改！
req.session.role = 'admin'  // 敏感数据存储在会话中
```

**安全标准**
- Cookie 设置 `HttpOnly`、`Secure`、`SameSite` 属性
- 会话数据由服务端存储（仅 Cookie 存储 Session ID）
- JWT 需要正确签名和验证

**快速定位**：`addCookie`、`set_cookie`、`res.cookie` 后检查 `httpOnly`、`secure`、`sameSite`

---

## 3. 会话固定攻击

**风险**：登录前后会话 ID 不变，攻击者可冒充用户

**危险代码示例**
```java
@PostMapping("/login")
public String login(Authentication auth, HttpSession session) {
  User user = (User) auth.getPrincipal();
  session.setAttribute("user", user);  // 使用同一会话 ID！
  return "redirect:/dashboard";
}
```

**安全标准**
- 登录后必须调用 `invalidate()` 清除旧会话
- 登录后必须创建新的会话 ID
- 登出时也要清除会话

**快速定位**：登录处理代码中检查 `invalidate()`、`session.clear()`

---

## 4. 会话超时处理不当

**风险**：会话永不过期或超时后仍可使用

**危险代码示例**
```java
HttpSession session = request.getSession(true);
// 未设置 setMaxInactiveInterval，会话永不过期！
```

**安全标准**
- 设置合理的会话超时（15-60 分钟）
- 超时后必须清除会话数据
- 检查超时时必须调用 `invalidate()`

**快速定位**：`setMaxInactiveInterval`、`PERMANENT_SESSION_LIFETIME`、`maxAge`

---

## 5. 认证绕过漏洞

**风险**：无效密码可被接受，未认证用户可访问受保护资源

**危险代码示例**
```python
def verify_password(user_input, stored_hash):
  if user_input == stored_hash:  # 时序不安全！
    return True
```

```java
@GetMapping("/admin")
public String adminPanel() {  // 未检查认证状态！
  return "admin/dashboard";
}
```

**安全标准**
- 密码比较使用恒定时间函数（hmac.compare_digest、BCrypt 等）
- 所有受保护资源必须检查认证状态
- 使用认证装饰器或中间件（@PreAuthorize、@login_required 等）

**快速定位**：`equals()`、`==`、`===` 密码比较；受保护端点缺少 `@PreAuthorize`、`@login_required`

---

## 6. 权限验证绕过

**风险**：用户可访问不属于他的资源或执行未授权的操作

**危险代码示例**
```java
@GetMapping("/user/{userId}")
public User getUser(@PathVariable Long userId) {
  // 未验证 userId 是否属于当前用户！
  return userRepository.findById(userId).orElse(null);
}
```

**安全标准**
- 所有资源访问必须验证权限
- 用户只能访问自己的资源（除非有管理员权限）
- 使用权限检查注解（@PreAuthorize 等）

**快速定位**：API 端点中缺少权限验证的资源访问

---

## 7. 密码重置漏洞

**风险**：令牌可预测、无过期时间、流程可绕过

**危险代码示例**
```python
# 可预测的令牌
reset_token = str(random.randint(100000, 999999))
# 或使用 userId 作为令牌
reset_token = String.valueOf(userId)
```

**安全标准**
- 令牌必须使用密码学安全随机数生成（secrets.token_urlsafe、SecureRandom 等）
- 令牌必须有过期时间（1-2 小时）
- 验证令牌后必须清除所有旧会话
- 令牌应该只能使用一次

**快速定位**：`random.randint`、`Math.random()`、`userId` 作为令牌；缺少过期时间检查

---

## 8. 多因素认证（MFA）绕过

**风险**：MFA 步骤可被跳过，令牌可重放

**危险代码示例**
```python
@app.route('/login', methods=['POST'])
def login():
  if verify_credentials(username, password):
    session['user_id'] = user.id  # 缺少 MFA 验证！直接登录了
    return redirect('/dashboard')
```

**安全标准**
- 验证密码后必须进行 MFA 验证（不能跳过）
- MFA 令牌必须有过期时间
- MFA 令牌只能使用一次（防重放）
- MFA 失败多次后应该限制重试次数

**快速定位**：登录处理代码中缺少 MFA 验证步骤或无防重放机制

---

## 9. 并发会话控制不足

**风险**：账户被盗用时，多个攻击者可同时使用该账户

**危险代码示例**
```python
@app.route('/login', methods=['POST'])
def login():
  if verify_credentials(username, password):
    session['user_id'] = user.id  # 未检查该用户是否已有其他活跃会话！
    return redirect('/dashboard')
```

**安全标准**
- 限制每个用户的并发会话数（建议为 1）
- 新登录时清除旧会话
- 可选：为用户提供"其他地方登录了"的警告

**快速定位**：登录处理代码中缺少并发会话检查

---

## 10. 会话注销不当

**风险**：注销后令牌仍有效，重定向可被利用

**危险代码示例**
```python
@app.route('/logout')
def logout():
  session.clear()  # 仅清除客户端，服务端会话仍有效！
  redirect_to = request.args.get('redirect_url')
  return redirect(redirect_to)  # 开放重定向！
```

**安全标准**
- 注销后必须调用 `session.invalidate()` 清除服务端会话
- 注销后必须删除 Cookie
- 重定向目标必须使用白名单验证（防开放重定向）

**快速定位**：注销代码中缺少 `invalidate()` 或 `session.clear()`；重定向缺少白名单验证

---

## 快速检查清单

**会话令牌** - 加密安全随机数，≥32字节，HttpOnly/Secure/SameSite 属性
**会话固定** - 登录后调用 invalidate()，创建新会话
**会话超时** - 15-60分钟超时，超时后清除会话
**认证** - 密码用恒定时间比较，所有受保护资源检查认证状态
**权限** - 所有资源访问验证权限，用户只能访问自己的资源
**密码重置** - 安全随机令牌，1-2小时过期，只能使用一次，重置后清除旧会话
**MFA** - 必须验证，令牌有过期时间和防重放机制
**并发会话** - 限制并发会话数（建议为1），新登录清除旧会话
**注销** - 清除服务端会话，删除 Cookie，重定向白名单验证
**审计日志** - 记录登录/注销/失败事件
