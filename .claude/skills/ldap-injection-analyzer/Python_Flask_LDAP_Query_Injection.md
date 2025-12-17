# Flask LDAP 查询注入

## Details

### 代码示例
Flask应用中使用LDAP查询时未验证输入会导致注入：

```python
from flask import Flask, request, jsonify
from ldap3 import Server, Connection

app = Flask(__name__)

# 危险示例1：登录认证注入
@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']

    # 危险：直接拼接用户输入
    search_filter = f"(&(uid={username})(userPassword={password}))"
    conn.search('dc=example,dc=com', search_filter)

    if conn.entries:
        return jsonify({'success': True})
    return jsonify({'success': False}), 401

# 危险示例2：用户搜索注入
@app.route('/api/users/search')
def search_users():
    query = request.args.get('q', '')
    department = request.args.get('dept', '')

    # 危险：多个参数未转义
    filter_str = f"(&(cn=*{query}*)(department={department}))"
    conn.search(base_dn, filter_str, attributes=['dn', 'cn', 'mail'])

    results = [entry.entry_to_json() for entry in conn.entries]
    return jsonify(results)

# 危险示例3：从JSON接收参数
@app.route('/api/directory/query', methods=['POST'])
def directory_query():
    data = request.get_json()
    criteria = data.get('criteria', {})

    # 危险：动态构造过滤器
    filter_parts = []
    for key, value in criteria.items():
        # key和value都未验证
        filter_parts.append(f"({key}={value})")

    search_filter = "(&" + "".join(filter_parts) + ")"
    conn.search(base_dn, search_filter)

    return jsonify({'results': [e.entry_to_json() for e in conn.entries]})

# 危险示例4：使用请求头
@app.route('/api/check_membership')
def check_membership():
    username = request.headers.get('X-Username')
    group = request.headers.get('X-Group')

    # 危险：header值未验证
    filter_str = f"(&(uid={username})(memberOf=cn={group},ou=groups,dc=example,dc=com))"
    conn.search(base_dn, filter_str)

    return jsonify({'is_member': len(conn.entries) > 0})
```

### 快速定位核心操作的技巧
**L1：关键词扫描** - 搜索以下特征：
- `@app.route`, `@app.post`, `@app.get` Flask路由装饰器
- `request.form`, `request.args`, `request.json`, `request.headers`
- `conn.search()`, `ldap_conn.search()`
- f-string拼接：`f"..."`, `.format()`, `+` 拼接

重点检查文件：
```
app.py
views/*.py
api/*.py
blueprints/*.py
```

### 快速定位保护机制的技巧
**L2：跳读** - 检查防护迹象：
- `from ldap3.utils.conv import escape_filter_chars`
- Flask-WTF表单验证：`form.validate_on_submit()`
- 自定义验证装饰器：`@validate_input`
- 输入验证逻辑：`if not re.match(...)`

**L3：逐行读** - 验证防护完整性：
```python
from ldap3.utils.conv import escape_filter_chars

# 检查点1：是否转义所有输入
username = escape_filter_chars(request.form['username'])
password = escape_filter_chars(request.form['password'])
filter_str = f"(&(uid={username})(userPassword={password}))"

# 检查点2：Flask-WTF表单验证
from flask_wtf import FlaskForm
from wtforms import StringField
from wtforms.validators import Regexp

class SearchForm(FlaskForm):
    username = StringField('Username', validators=[
        Regexp(r'^[a-zA-Z0-9]+$')  # 验证规则
    ])

# 检查点3：是否所有输入源都被处理
form_input = escape_filter_chars(request.form.get('username'))
query_input = request.args.get('username')  # 未转义！
```

关键检查点：
- 所有用户输入源（form, args, json, headers）
- 是否使用Flask-WTF或自定义验证
- 转义是否覆盖所有动态内容

## Classify

### 漏洞判定规则
- **明确漏洞**：LDAP过滤器直接包含未转义的request数据
- **高危信号**：
  - 认证路由中的注入
  - 多个输入源未全部转义
  - 动态遍历字典构造过滤器
- **误报排除**：
  - 使用`escape_filter_chars()`转义所有输入
  - Flask-WTF验证规则严格
  - 输入白名单验证

### 风险评估
- **高风险**：认证绕过、完整目录泄露
- **中风险**：限定API的注入
- **低风险**：仅只读，返回属性受限

## Low risk

### 低风险评级的情形

1. **Flask-WTF严格验证**
   - 表单使用`Regexp(r'^[a-zA-Z0-9]+$')`
   - `Length(max=32)`长度限制
   - 验证失败时请求被拒绝

2. **装饰器验证**
   - 自定义`@validate_ldap_input`装饰器
   - 在视图函数执行前验证所有参数

3. **只读API**
   - 仅提供搜索功能，无写操作
   - 不影响认证或授权决策

4. **属性白名单**
   - `search()`明确指定`attributes=['cn', 'displayName']`
   - 不返回敏感信息
