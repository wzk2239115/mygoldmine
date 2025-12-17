# 不安全反序列化绕过秘笈

## 核心漏洞

**PHP Object Injection**：`unserialize()`反序列化用户数据触发magic方法（`__destruct`、`__wakeup`、`__toString`）
```php
$user = unserialize($_COOKIE['user_data']);  // 危险
// 攻击：恶意序列化对象在反序列化时执行gadget chain
```

**Python Pickle RCE**：`pickle.loads()`直接执行反序列化数据中的代码
```python
class RCE:
    def __reduce__(self):
        return (os.system, ('cmd',))
```

**Java Commons Collections**：利用InvokerTransformer、LazyMap等gadget实现RCE，使用ysoserial生成CC1-CC7链

## 绕过技术

### 1. 类型混淆
- 修改序列化属性类型（字符串→数组），绕过类型检查
- 利用PHP弱比较（`==`）的类型转换漏洞

### 2. Magic Method滥用
- `__wakeup()` 在PHP 5.6.25前可通过修改属性数量跳过
- `__toString()` → `__call()` 链式触发不同类的方法

### 3. 白名单绕过
- 使用完全限定命名空间：`O:10:"App\\User":...` 绕过简单名称过滤
- 版本号不匹配被忽略

### 4. Session处理器不一致
PHP三种handler (php_serialize/php/php_binary)混用时，通过cookie写入恶意数据到session，在序列化字符串前加`|`标记：
```
|O:6:"Logger":1:{s:4:"file";s:20:"/var/www/shell.php";}
```

### 5. 字符串逃逸
利用`str_replace`长度变化逃逸序列化边界：
```
原始：s:5:"hello" → str_replace('l','ll') → s:5:"hellllo"
长度不匹配导致字符串逃逸，注入恶意序列化数据
```

### 6. JSON原型污染
```javascript
JSON.parse('{"constructor":{"prototype":{"isAdmin":true}}}')
// 污染所有对象的原型链
```

## 快速检测

**关键词**：unserialize()、pickle.loads()、ObjectInputStream、无白名单、session.serialize_handler、str_replace、$_COOKIE混用$_SESSION、Commons Collections类、MySQL JDBC自动反序列化

**测试顺序**：
1. 反序列化入点（Cookie/请求体）
2. Gadget chain分析（框架已知链）
3. Payload生成与RCE测试
4. Session处理器漏洞
5. 字符串逃逸漏洞
6. Java URLDNS检测、CC1-CC7链
7. MySQL JDBC、Tomcat Session反序列化

## 利用工具

- **ysoserial**：Java CC链/URLDNS payload生成
- **phpggc**：PHP POP chain生成
- **marshalsec**：Java反序列化工具
