# Python ldap3 过滤器拼接

## Details

### 代码示例
Python `ldap3` 库在过滤器拼接时未转义会导致注入：

```python
from ldap3 import Server, Connection, ALL

# 危险示例1：基本的过滤器拼接
def authenticate(username, password):
    conn = Connection(server, user=admin_dn, password=admin_pw)
    # 危险：f-string拼接
    search_filter = f"(&(uid={username})(userPassword={password}))"
    conn.search('dc=example,dc=com', search_filter)
    return conn.entries

# 危险示例2：使用format方法
def search_users(name, email):
    # 危险：字符串format拼接
    filter_str = "(&(cn=*{}*)(mail=*{}*))".format(name, email)
    conn.search(base_dn, filter_str, attributes=['dn', 'cn'])

# 危险示例3：字符串拼接
def find_by_dept(department):
    # 危险：使用+拼接
    search_filter = "(department=" + department + ")"
    conn.search(base_dn, search_filter)

# 危险示例4：Flask应用中的注入
from flask import request

@app.route('/search')
def search():
    username = request.args.get('username')
    email = request.args.get('email')
    # 危险：直接使用用户输入
    filter_str = f"(&(uid={username})(mail={email}))"
    conn.search(base_dn, filter_str)
    return jsonify([entry.entry_to_json() for entry in conn.entries])
```

### 快速定位核心操作的技巧
**L1：关键词扫描** - 搜索以下特征：
- `from ldap3 import`, `Connection`, `Server`
- `.search()`, `.add()`, `.modify()` 方法
- `request.args.get`, `request.form.get`, `request.json.get` Flask输入
- f-string：`f"..."`, `.format()`, `+` 字符串拼接
- LDAP过滤器模式：`"(&"`, `"(|"`, `"(uid="`

重点检查文件：
```
app/ldap_utils.py
services/directory_service.py
views/auth_views.py
api/users.py
```

### 快速定位保护机制的技巧
**L2：跳读** - 检查防护迹象：
- `ldap3.utils.conv.escape_filter_chars()`函数调用
- `ldap3.utils.dn.escape_rdn()`对DN的转义
- 输入验证：`re.match()`, 白名单检查
- 自定义转义函数

**L3：逐行读** - 验证防护完整性：
```python
from ldap3.utils.conv import escape_filter_chars

# 检查点1：是否使用转义函数
safe_username = escape_filter_chars(username)
search_filter = f"(uid={safe_username})"

# 检查点2：是否所有输入都转义
safe_uid = escape_filter_chars(username)
dept = department  # 未转义！
filter_str = f"(&(uid={safe_uid})(dept={dept}))"

# 检查点3：是否使用了参数化接口（ldap3没有，需手动转义）
```

关键检查点：
- 过滤器字符串中的所有动态部分
- 是否使用`escape_filter_chars()`
- DN操作是否使用`escape_rdn()`

## Classify

### 漏洞判定规则
- **明确漏洞**：`.search()`的filter参数直接包含未转义的用户输入
- **高危信号**：
  - f-string或`.format()`拼接用户输入
  - Flask/Django视图中直接使用请求参数
  - 认证函数中的过滤器拼接
- **误报排除**：
  - 使用`escape_filter_chars()`转义所有输入
  - 输入经过正则或白名单验证
  - 输入来自配置文件或常量

### 风险评估
- **高风险**：认证绕过、目录完整遍历
- **中风险**：限定条件注入
- **低风险**：查询范围受限，返回属性白名单化

## Low risk

### 低风险评级的情形

1. **输入白名单验证**
   - 使用`re.match(r'^[a-zA-Z0-9]+$', username)`
   - 仅允许预定义值

2. **属性返回限制**
   - `search()`的`attributes`参数限制返回字段
   - 如`attributes=['cn', 'displayName']`

3. **Base DN范围限制**
   - base DN限定为非敏感OU
   - 无法访问管理员账户

4. **输入长度限制**
   - `username[:16]`截断输入
   - 长度不足以构造注入payload
