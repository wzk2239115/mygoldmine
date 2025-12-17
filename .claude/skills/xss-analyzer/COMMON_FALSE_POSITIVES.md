# 常见误报识别库 - XSS 审计中的假阳性

> **用途：** 帮助审计员区分真正的漏洞和误报
> **预期效果：** 减少 30-40% 的误报，提高审计效率

---

## 通用误报

### 1. 常量 `innerHTML` 不是漏洞
```javascript
// ✅ 安全：常量不受用户控制
const html = "<h1>Welcome</h1>";
document.getElementById('header').innerHTML = html;

// ❌ 漏洞：变量受用户控制
const userInput = new URLSearchParams(window.location.search).get('msg');
document.getElementById('header').innerHTML = userInput;
```
**检查方法：** 追踪变量来源，区分常量与用户输入。

---

### 2. 框架模板转义 ≠ 所有情况安全
```jsx
// ✅ 安全：React JSX 自动转义
function Welcome({ userName }) {
  return <h1>Welcome, {userName}!</h1>;
}

// ❌ 漏洞：绕过框架转义
const html = `<p>${userName}</p>`;
document.getElementById('content').innerHTML = html;
```
**检查方法：** 验证是否使用框架模板语法，检查是否混用原生 DOM API。

---

### 3. 管理后台仍需防护
```java
// ❌ 漏洞：存储型 XSS 在后台触发
String userId = request.getParameter("id");
out.write("<p>User: " + userId + "</p>");
```
**原因：** 攻击者可通过前台注入数据库，管理员访问后台时被触发。

---

### 4. JSON API 需检查前端使用方式
```java
// ✅ API 返回 JSON 本身安全
@GetMapping("/api/data")
public ResponseEntity<?> getData() {
    return ResponseEntity.ok(user);
}

// ❌ 但如果前端这样用就危险
document.getElementById('content').innerHTML = data.html;
```

---

### 5. URL 前缀检查不足够
```javascript
// ❌ 不完全安全：可绕过
if (url.startsWith('/')) {
  window.location = url;  // redirect=/javascript:alert(1)
}

// ✅ 正确做法：完整白名单
const allowed = ['/home', '/profile', '/settings'];
if (allowed.includes(url)) window.location = url;
```

---

## 前端框架误报

### 6. Vue：`v-text` 安全，`v-html` 需净化
```vue
<!-- ✅ 安全：文本内容 -->
<div v-text="userInput"></div>

<!-- ❌ 不安全：HTML 需净化 -->
<div v-html="userInput"></div>
```

---

### 7. React 属性自动转义，但 `dangerouslySetInnerHTML` 不会
```jsx
// ✅ 安全：属性自动转义
const title = '\"><img onerror="alert(1)"';
return <img alt={title} />;

// ❌ 危险：显式使用 HTML
return <div dangerouslySetInnerHTML={{ __html: userInput }} />;
```

---

### 8. Angular：Pipe 处理后仍需验证
```typescript
// ✅ 安全：默认转义
<div>{{ userInput | uppercase }}</div>

// ❌ 危险：未净化的 HTML
<div [innerHTML]="userInput"></div>
```

---

## 后端防护误报

### 9. SQL 参数化 ≠ XSS 防护
```java
// ✅ 防止 SQL 注入
String query = "SELECT * FROM users WHERE id = ?";
stmt.setInt(1, userId);

// ❌ 但仍需转义输出
out.write("<p>Hello " + name + "</p>");  // 需要 htmlspecialchars

// ✅ 正确做法
out.write("<p>Hello " + htmlEscape(name) + "</p>");
```
**原则：** SQL 参数化 ≠ HTML 转义，两个独立的防护机制。

---

### 10. ORM 只负责查询，不负责转义
```python
# ❌ ORM 不能防护输出
{{ user.bio }}  # 如果包含 HTML，仍会直接输出

# ✅ 需要在模板层转义
{{ user.bio | escape }}
```

---

### 11. 输入验证 ≠ 输出编码
```php
// ❌ 验证长度，但未转义
if (strlen($_GET['name']) < 100) {
    echo "Hello " . $_GET['name'];
}

// ✅ 正确做法
echo "Hello " . htmlspecialchars($_GET['name'], ENT_QUOTES, 'UTF-8');
```

---

## 数据流误报

### 12. 自有 API 仍需前端防护
```javascript
// ❌ 不要假设来自自己的 API 就安全
const data = await fetch('/api/data').then(r => r.json());
document.getElementById('content').innerHTML = data.html;

// ✅ 前后端应有独立防护
document.getElementById('content').textContent = data.html;
```
**原因：** 后端 API 可能存在存储型 XSS 漏洞。

---

### 13. 在数据源头防护，不要依赖使用点
```java
// ❌ 认为"只在一个地方用"就不用防护
// 但 API 可能被移动端、第三方使用
@GetMapping("/articles/{id}")
public String getArticle(@PathVariable Long id) {
    Article article = articleRepository.findById(id);
    return article.content;  // 需要在源头防护
}
```

---

## 框架防护混淆

### 14. Django `|safe` 需要真实处理过的内容
```django
<!-- ❌ 未处理就标记为安全 -->
{{ user_input|safe }}

<!-- ✅ 确认真的处理过 -->
{{ markdown_output|safe }}  <!-- 确认 Markdown 库已净化 -->
```

---

### 15. Spring Security XSS 保护 ≠ 代码级防护
```java
// ❌ 误认为配置就够了
config.headers().xssProtection();

// ✅ 仍需在代码中显式转义
out.write(htmlEscape(userInput));
```
**原因：** X-XSS-Protection 是浏览器功能，后端代码仍需转义。

---

### 16. Thymeleaf `th:utext` 取决于内容是否净化
```html
<!-- ✅ 安全：已净化内容 -->
<p th:utext="${cleanedContent}"></p>

<!-- ❌ 危险：未净化内容 -->
<p th:utext="${userInput}"></p>
```

---

## 快速检查清单

| 场景 | 误判方式 | 实际情况 | 检查方法 |
|------|--------|--------|--------|
| 常量字符串 | "这是 innerHTML" | ✅ 安全 | 追踪变量来源 |
| 框架模板 | "框架已转义" | ✅ 安全* | 检查混用 DOM API |
| 管理后台 | "只有内部用" | ❌ 漏洞 | 检查存储型 XSS 风险 |
| JSON 返回 | "JSON 格式安全" | ⚠️ 检查前端使用 | 检查 innerHTML 等 |
| SQL 参数化 | "防止所有注入" | ⚠️ 只防 SQL 注入 | 检查 HTML 转义 |
| 输入验证 | "验证了长度" | ❌ 未防 XSS | 需要输出转义 |
| 自有 API | "来自自己系统" | ⚠️ 仍需防护 | 前后端独立防护 |
| 框架防护 | "框架有保护" | ⚠️ 需代码防护 | 检查显式转义 |

---

## 核心原则

1. **区分机制**
   - SQL 参数化 ≠ HTML 转义
   - 输入验证 ≠ 输出编码
   - 框架防护 ≠ 代码防护

2. **多层防护**
   - 后端转义 + 前端转义
   - 输入点防护 + 输出点防护

3. **信任但验证**
   - 不要假设数据"受信"
   - 不要假设框架"处理了一切"
   - 在你能控制的地方防护
