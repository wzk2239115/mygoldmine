# Python-ldap 注入

## Details

### 代码示例
`python-ldap` 是Python的传统LDAP库，使用不当会导致注入：

```python
import ldap

# 危险示例1：基本认证注入
def authenticate(username, password):
    conn = ldap.initialize('ldap://localhost')
    conn.simple_bind_s('cn=admin,dc=example,dc=com', 'adminpw')

    # 危险：直接拼接过滤器
    search_filter = f"(&(uid={username})(userPassword={password}))"
    result = conn.search_s('dc=example,dc=com', ldap.SCOPE_SUBTREE, search_filter)

    return len(result) > 0

# 危险示例2：使用%格式化
def search_users(name, department):
    # 危险：%格式化拼接
    filter_str = "(&(cn=*%s*)(department=%s))" % (name, department)
    result = conn.search_s(base_dn, ldap.SCOPE_SUBTREE, filter_str)
    return result

# 危险示例3：DN注入
def get_user_by_uid(uid):
    # 危险：DN拼接
    dn = f"uid={uid},ou=users,dc=example,dc=com"
    try:
        result = conn.search_s(dn, ldap.SCOPE_BASE, '(objectClass=*)')
        return result[0]
    except ldap.NO_SUCH_OBJECT:
        return None

# 危险示例4：modify操作的DN注入
def update_user_email(username, new_email):
    # 危险：DN未转义
    dn = f"uid={username},ou=users,dc=example,dc=com"
    mod_attrs = [(ldap.MOD_REPLACE, 'mail', new_email.encode('utf-8'))]
    conn.modify_s(dn, mod_attrs)
```

### 快速定位核心操作的技巧
**L1：关键词扫描** - 搜索以下特征：
- `import ldap`, `ldap.initialize()`
- `.search_s()`, `.search_st()`, `.search_ext_s()`
- `.simple_bind_s()`, `.bind_s()`
- `.modify_s()`, `.add_s()`, `.delete_s()`
- f-string拼接：`f"..."`, `%` 格式化，`+` 拼接

重点检查文件：
```
ldap_client.py
auth/ldap_auth.py
utils/directory.py
services/user_service.py
```

### 快速定位保护机制的技巧
**L2：跳读** - 检查防护迹象：
- `ldap.filter.escape_filter_chars()` 函数
- 自定义转义函数
- 正则验证：`re.match()`
- 白名单检查

**L3：逐行读** - 验证防护完整性：
```python
import ldap
from ldap.filter import escape_filter_chars

# 检查点1：是否使用转义函数
safe_username = escape_filter_chars(username)
filter_str = f"(uid={safe_username})"

# 检查点2：DN转义（python-ldap没有内置DN转义，需自定义）
def escape_dn_chars(value):
    # 需检查此函数实现是否正确
    return value.replace(',', '\,').replace('=', '\=')

safe_uid = escape_dn_chars(uid)
dn = f"uid={safe_uid},ou=users,dc=example,dc=com"

# 检查点3：是否所有输入都转义
safe_uid = escape_filter_chars(username)
dept = department  # 未转义！
filter_str = f"(&(uid={safe_uid})(dept={dept}))"
```

关键检查点：
- 是否使用`escape_filter_chars()`
- DN转义是否正确实现
- 所有动态内容是否都被转义

## Classify

### 漏洞判定规则
- **明确漏洞**：`search_s()`或DN参数直接包含未转义的用户输入
- **高危信号**：
  - 认证函数中的过滤器拼接
  - DN字符串包含用户输入
  - modify/add/delete操作的DN未转义
- **误报排除**：
  - 使用`escape_filter_chars()`转义过滤器
  - 使用自定义函数正确转义DN
  - 输入经过严格验证

### 风险评估
- **高风险**：认证绕过、目录写入
- **中风险**：限定操作的注入
- **低风险**：仅只读，范围受限

## Low risk

### 低风险评级的情形

1. **输入白名单验证**
   - 使用`re.match(r'^[a-zA-Z0-9]+$', username)`
   - 仅允许字母数字，无法注入

2. **只读操作**
   - 仅使用`search_s()`，无`modify_s()`, `add_s()`等
   - 无法修改目录数据

3. **Base DN固定**
   - Base DN来自配置文件
   - 用户输入仅影响过滤器值

4. **连接权限受限**
   - LDAP连接使用只读账户
   - 绑定用户无写权限
