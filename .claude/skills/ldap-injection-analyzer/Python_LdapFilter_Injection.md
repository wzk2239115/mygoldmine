# Python LdapFilter 注入

## Details

### 代码示例
Python中使用LDAP过滤器构造库时，不当使用仍可能引入注入：

```python
# 危险示例1：手工构造过滤器字符串
def build_filter(criteria):
    filter_parts = []
    for key, value in criteria.items():
        # 危险：key和value都未验证
        filter_parts.append(f"({key}={value})")
    return "(&" + "".join(filter_parts) + ")"

# 使用：build_filter(request.json)  # request.json不可信

# 危险示例2：部分转义
from ldap3.utils.conv import escape_filter_chars

def search_user(username, department):
    safe_username = escape_filter_chars(username)
    # 危险：department未转义
    filter_str = f"(&(uid={safe_username})(dept={department}))"
    return ldap_search(filter_str)

# 危险示例3：属性名未验证
def dynamic_search(attr_name, attr_value):
    # 危险：attr_name来自用户输入，未白名单验证
    safe_value = escape_filter_chars(attr_value)
    filter_str = f"({attr_name}={safe_value})"
    return ldap_search(filter_str)

# 调用：dynamic_search(request.args['attr'], request.args['value'])

# 危险示例4：复杂逻辑的拼接
def advanced_search(name=None, email=None, dept=None):
    filters = []
    if name:
        # 危险：部分参数转义，部分未转义
        filters.append(f"(cn=*{escape_filter_chars(name)}*)")
    if email:
        filters.append(f"(mail={email})")  # 未转义！
    if dept:
        filters.append(f"(department={dept})")  # 未转义！

    if len(filters) > 1:
        return "(&" + "".join(filters) + ")"
    elif filters:
        return filters[0]
    return "(objectClass=*)"
```

### 快速定位核心操作的技巧
**L1：关键词扫描** - 搜索以下特征：
- 过滤器构造函数：`def build_filter`, `def create_filter`
- 字符串拼接：f-string, `.format()`, `+`, `.join()`
- `for...in` 遍历用户输入的字典
- LDAP过滤器模式：`"(&"`, `"(|"`, `"(uid="`

重点检查文件：
```
utils/ldap_utils.py
services/ldap_service.py
filters/ldap_filters.py
helpers/directory.py
```

### 快速定位保护机制的技巧
**L2：跳读** - 检查防护迹象：
- `from ldap3.utils.conv import escape_filter_chars`
- 属性名白名单：`ALLOWED_ATTRS = ['uid', 'cn', 'mail']`
- 输入验证：`if attr not in ALLOWED_ATTRS`
- 类型检查：`isinstance(criteria, dict)`

**L3：逐行读** - 验证防护完整性：
```python
from ldap3.utils.conv import escape_filter_chars

# 检查点1：是否所有值都转义
def build_filter(criteria):
    filters = []
    for key, value in criteria.items():
        safe_value = escape_filter_chars(value)  # 值转义
        # 但key未验证！
        filters.append(f"({key}={safe_value})")

# 检查点2：属性名白名单
ALLOWED_ATTRS = {'uid', 'cn', 'mail', 'department'}

def safe_build_filter(criteria):
    filters = []
    for key, value in criteria.items():
        if key not in ALLOWED_ATTRS:  // 白名单验证
            raise ValueError(f"Invalid attribute: {key}")
        safe_value = escape_filter_chars(value)
        filters.append(f"({key}={safe_value})")
    return "(&" + "".join(filters) + ")"

# 检查点3：是否存在部分转义的情况
```

关键检查点：
- 动态构造过滤器时是否验证属性名
- 所有值是否都经过转义
- 是否存在条件分支导致部分未转义

## Classify

### 漏洞判定规则
- **明确漏洞**：动态构造LDAP过滤器，未转义或部分转义用户输入
- **高危信号**：
  - 遍历用户输入的字典构造过滤器
  - 属性名来自用户输入且无白名单
  - 条件分支中部分路径未转义
- **误报排除**：
  - 所有值使用`escape_filter_chars()`转义
  - 属性名使用白名单验证
  - 输入来自配置文件或常量

### 风险评估
- **高风险**：完整的LDAP注入，可操纵查询逻辑
- **中风险**：部分参数可注入
- **低风险**：仅值可控，属性名受白名单限制

## Low risk

### 低风险评级的情形

1. **属性名白名单**
   - 所有属性名从预定义集合选择
   - `if key not in ALLOWED_ATTRS: raise ValueError()`
   - 用户无法控制属性名

2. **完整的值转义**
   - 所有值都使用`escape_filter_chars()`
   - 无条件分支导致的遗漏

3. **输入类型验证**
   - 检查`isinstance(criteria, dict)`
   - 检查值的类型：`isinstance(value, str)`

4. **构造器模式**
   - 使用类封装过滤器构造
   - 类方法强制转义流程
