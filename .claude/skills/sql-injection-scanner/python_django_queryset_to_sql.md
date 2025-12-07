# Python | Django ORM查询结果用于SQL拼接漏洞

## 基本信息
- **难度等级：** ★★★☆☆ (中级)
- **审计时间：** 20-25分钟

## 🚀 30秒快速清单
- [ ] 是否使用了Django ORM的raw()方法？
- [ ] 是否在raw()中拼接QuerySet的查询结果？
- [ ] 是否使用了extra()方法with用户输入？
- [ ] 是否在模型的__str__()中包含用户输入？
- [ ] 是否使用了参数化的raw()查询？

## Details

### 漏洞成因
Django ORM虽然在大多数情况下是安全的（使用了参数化查询），但raw()、extra()等方法允许直接SQL查询。如果在raw()中拼接QuerySet的结果（特别是来自用户输入的模型字段值），可能导致SQL注入。此问题常见于需要复杂查询或动态SQL构造的场景。

### 代码示例

```python
# 漏洞1：在raw()中拼接ORM查询结果
from django.db import connection
from django.db.models import Q

def search_products(category_id, search_term):
    # 获取QuerySet结果
    categories = Category.objects.filter(id=category_id).values_list('name', flat=True)

    if not categories.exists():
        return []

    # 问题：直接拼接QuerySet结果
    category_name = categories[0]  # 来自数据库，但仍需验证
    sql = f"SELECT * FROM products WHERE category = '{category_name}' AND name LIKE '%{search_term}%'"

    # 使用raw()执行自定义SQL
    products = Product.objects.raw(sql)
    return list(products)

# 攻击场景：
# 如果category表中被插入恶意数据 "'; DROP TABLE products; --"
# 后续查询时会执行恶意SQL
```

```python
# 漏洞2：使用extra()方法with字符串拼接
from django.db.models import Q

def get_user_by_filter(user_id, filter_name):
    # user的某个字段可能来自用户之前输入
    user = User.objects.get(id=user_id)

    # 问题：filter_name来自用户输入
    # 虽然使用了ORM，但extra()允许SQL片段
    queryset = Order.objects.extra(
        where=[f"status = '{user.status}' AND filter = '{filter_name}'"]
    )

    return list(queryset)
```

```python
# 漏洞3：在raw()中使用without参数化
def advanced_search(user_input):
    # 问题：虽然指定了参数，但拼接了其他SQL片段
    users = User.objects.filter(username__startswith='test')

    # 获取用户名列表
    usernames = list(users.values_list('username', flat=True))

    # 问题：拼接用户名到SQL
    username_list = "', '".join(usernames)  # "user1', 'user2', 'user3'"

    sql = f"SELECT * FROM orders WHERE username IN ('{username_list}')"

    orders = Order.objects.raw(sql)
    return list(orders)
```

```python
# 漏洞4：利用Model __str__方法包含用户数据
class UserProfile(models.Model):
    name = models.CharField(max_length=100)  # 用户输入

    def __str__(self):
        return self.name

def generate_report(profile_id):
    profile = UserProfile.objects.get(id=profile_id)

    # 问题：__str__() 返回用户输入的数据
    # 虽然这里用于字符串拼接，但如果在raw()中使用会导致注入
    sql = f"SELECT * FROM reports WHERE owner = '{profile}'"  # 调用__str__()

    reports = Report.objects.raw(sql)
    return list(reports)
```

### 快速定位核心操作
- **关键词扫描**：`raw()`, `extra()`, `values_list()`, `.objects`, `f"SELECT"` SQL拼接
- **QuerySet操作**：`User.objects.filter()`, `.values()`, `.values_list()`, `[0]`
- **raw()使用**：`Model.objects.raw(sql)` 或 `connection.cursor()`
- **缺少参数**：无 `%s` 占位符，无参数列表传递

### 快速定位保护机制
- **参数化raw()**：`Model.objects.raw("SELECT * FROM table WHERE id = %s", [user_id])`
- **避免extra()**：使用Q对象和filter()代替
- **不拼接QuerySet结果**：避免在SQL字符串中包含ORM查询结果
- **使用ORM方法**：尽量使用filter()、exclude()等安全ORM方法

---

## Classify

### 确认漏洞（需满足以下任一条）
1. **raw()中拼接QuerySet结果**：`raw(f"...{queryset_value}...")`
2. **raw()中拼接用户输入**：无参数化，如 `f"SELECT * FROM {table}"`
3. **使用extra()with字符串拼接**：`extra(where=[f"...{value}..."])`
4. **从ORM结果中提取值后拼接SQL**：`value = User.objects.get(...); raw(f"...{value}...")`

**典型漏洞特征**：
- `Product.objects.raw(f"SELECT * FROM ... WHERE ... = '{value}'")`
- `.values_list(...)[0]` 后跟 SQL拼接
- `extra(where=[f"... = '{user_input}'"])`
- 缺少 raw()的第二参数（参数列表）

### 误报排除
- ✗ 使用参数化的raw()：`raw("SELECT * FROM ... WHERE id = %s", [user_id])`
- ✗ 仅使用filter()、exclude()等ORM方法
- ✗ 不在SQL中拼接ORM查询结果
- ✗ 验证从ORM获取的值（白名单）

### 代码异味（需进一步验证）
- △ 有参数化raw()但仍有字符串拼接其他部分
- △ 从QuerySet提取值且有某种验证

---

## Low Risk

给予低风险评级的场景：
1. 使用参数化的raw()：`raw("... WHERE column = %s", [value])`
2. 不拼接ORM查询结果，仅使用ORM方法
3. 来自ORM的值经过白名单验证（如枚举值）

---

## 安全实现

```python
from django.db.models import Q
from django.db import connection
from django.core.exceptions import ValidationError

class SecureDjangoQuery:
    """安全的Django ORM查询处理"""

    # 方法1：完全使用ORM（最安全）
    @staticmethod
    def search_products_safe(category_id, search_term):
        if not category_id or not search_term:
            return []
        return list(Product.objects.filter(
            category_id=category_id,
            name__icontains=search_term
        ))

    # 方法2：参数化的raw()
    @staticmethod
    def search_with_raw_safe(user_id, status):
        valid_statuses = ['active', 'inactive', 'pending']
        if status not in valid_statuses:
            raise ValidationError("Invalid status")
        sql = "SELECT * FROM orders WHERE user_id = %s AND status = %s"
        return list(Order.objects.raw(sql, [user_id, status]))

    # 方法3：使用Q对象动态构造查询
    @staticmethod
    def complex_query_safe(user_id, filter_options):
        query = Q(user_id=user_id)
        for key, value in filter_options.items():
            if key not in ['status', 'category', 'priority']:
                continue
            if SecureDjangoQuery._validate_filter(key, value):
                query &= Q(**{key: value})
        return list(Order.objects.filter(query))

    @staticmethod
    def _validate_filter(key, value):
        if len(str(value)) > 100:
            return False
        validations = {
            'status': lambda v: v in ['active', 'inactive', 'pending'],
            'category': lambda v: str(v).isdigit(),
            'priority': lambda v: v in ['high', 'medium', 'low']
        }
        return validations.get(key, lambda v: False)(value)

    # 必须使用raw()时的安全实现
    @staticmethod
    def raw_with_params(user_id, search_pattern):
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError("Invalid user_id")
        if not search_pattern or len(search_pattern) > 100:
            raise ValueError("Invalid search pattern")

        sql = "SELECT * FROM products WHERE user_id = %s AND name LIKE %s"
        params = [user_id, f"%{search_pattern}%"]
        return list(Product.objects.raw(sql, params))

    # 使用cursor时的安全实现
    @staticmethod
    def cursor_safe(user_id):
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM orders WHERE user_id = %s", [user_id])
            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
```

## 修复优先级

1. **立即修复（当天）**：停止在raw()中拼接ORM查询结果
2. **快速修复（3天内）**：使用参数化的raw()或完全改为ORM方法
3. **短期改善（1周内）**：审计所有raw()和extra()的使用
4. **长期改进（1个月）**：尽量使用ORM的filter()、Q对象等安全方法
