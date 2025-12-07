# Python | SQLAlchemy会话数据用于SQL拼接漏洞

## 基本信息
- **难度等级：** ★★★☆☆ (中级)
- **审计时间：** 20-25分钟

## 🚀 30秒快速清单
- [ ] 是否使用了text()或execute()执行原生SQL？
- [ ] 是否拼接ORM查询结果到SQL中？
- [ ] 是否在会话中缓存用户数据后用于SQL构造？
- [ ] 是否使用了参数化的text()查询？

## Details

### 漏洞成因
SQLAlchemy提供了text()方法来执行原生SQL，但如果在text()中拼接会话中的数据（来自之前的ORM查询），可能导致SQL注入。二阶SQL注入可发生在从数据库读取的数据被用于后续SQL构造时。此外，SQLAlchemy的ORM查询虽然大多是安全的，但当使用literal_column()或直接字符串拼接时仍存在风险。

### 代码示例

```python
# 漏洞1：在text()中拼接ORM查询结果
from sqlalchemy import text
from sqlalchemy.orm import Session

def search_by_category(db: Session, category_id: int):
    # 从数据库查询类别名称
    category = db.query(Category).filter(Category.id == category_id).first()

    if not category:
        return []

    # 问题：直接拼接category.name到SQL
    sql = text(f"SELECT * FROM products WHERE category_name = '{category.name}'")

    products = db.execute(sql).fetchall()
    return products

# 攻击场景：
# 如果category.name包含 "'; DROP TABLE products; --"
# 后续查询时会执行恶意SQL
```

```python
# 漏洞2：缓存用户数据后用于SQL构造
from sqlalchemy import text

def get_user_orders(db: Session, user_id: int):
    # 从会话获取用户（如果已被缓存）
    user = db.query(User).get(user_id)

    if not user:
        return []

    # 问题：user.status可能是用户之前输入的
    # 虽然来自ORM，但在text()中拼接时未参数化
    sql = text(f"SELECT * FROM orders WHERE user_status = '{user.status}'")

    orders = db.execute(sql).fetchall()
    return orders
```

```python
# 漏洞3：使用literal_column()with字符串拼接
from sqlalchemy import literal_column, select

def dynamic_select(db: Session, column_name: str):
    # 问题：column_name来自用户输入
    # literal_column()直接使用，无参数化
    stmt = select(literal_column(column_name)).select_from(User)

    users = db.execute(stmt).fetchall()
    return users
```

```python
# 漏洞4：在filter()中使用字符串拼接
from sqlalchemy import and_

def complex_filter(db: Session, filter_dict: dict):
    query = db.query(Product)

    for key, value in filter_dict.items():
        # 问题：key来自用户输入，未验证
        # 虽然没有明显的注入，但仍需谨慎
        filter_clause = f"{key} = '{value}'"

        # 尝试直接拼接会导致错误或注入
        # query = query.filter(text(filter_clause))
```

### 快速定位核心操作
- **关键词扫描**：`text()`, `execute()`, `literal_column()`, `f"SELECT"`, `.filter(text())`
- **原生SQL**：`db.execute(sql)`, `text(f"...")`, `session.execute()`
- **数据来源**：`db.query(...).first()`, `.get()`, ORM结果
- **缺少参数**：无 `:parameter` 绑定变量

### 快速定位保护机制
- **参数化text()**：`text("SELECT * FROM ... WHERE id = :id").bindparams(id=user_id)`
- **避免literal_column()**：使用ORM列引用
- **使用filter()**：`query.filter(Product.name == value)` 而非 `filter(text(...))`
- **参数绑定**：使用 `bindparams()` 或 ORM参数

---

## Classify

### 确认漏洞（需满足以下任一条）
1. **text()中拼接ORM结果**：`text(f"... {orm_data} ...")`
2. **text()中拼接用户输入**：无参数化
3. **literal_column()with用户输入**：`literal_column(user_column_name)`
4. **未使用filter()而使用text()**：`filter(text(f"...={value}..."))`

**典型漏洞特征**：
- `db.execute(text(f"SELECT * FROM ... WHERE ... = '{value}'"))`
- `db.query(...).filter(text(f"... = '{value}'"))`
- `literal_column(user_input)`
- 缺少 `bindparams()` 或 `:parameter` 绑定

### 误报排除
- ✗ 使用参数化的text()：`text("... = :id").bindparams(id=value)`
- ✗ 仅使用ORM filter()方法
- ✗ 不拼接ORM查询结果
- ✗ 验证列名和值（白名单）

### 代码异味（需进一步验证）
- △ 有参数化但仍有字符串拼接其他部分
- △ 从ORM提取值且有某种验证

---

## Low Risk

给予低风险评级的场景：
1. 使用参数化的text()：`text("... WHERE id = :id").bindparams(id=value)`
2. 仅使用ORM filter()方法
3. 白名单验证列名和表名

---

## 安全实现

```python
from sqlalchemy import text, and_, func
from sqlalchemy.orm import Session
from sqlalchemy.sql import bindparam

class SecureSQLAlchemyQuery:
    """安全的SQLAlchemy查询处理"""

    # 方法1：完全使用ORM（最安全）
    @staticmethod
    def search_products_safe(db: Session, category_id: int, search_term: str):
        return db.query(Product).filter(
            and_(
                Product.category_id == category_id,
                Product.name.ilike(f"%{search_term}%")
            )
        ).all()

    # 方法2：参数化的text()
    @staticmethod
    def search_with_text_safe(db: Session, user_id: int, status: str):
        valid_statuses = ['active', 'inactive', 'pending']
        if status not in valid_statuses:
            raise ValueError("Invalid status")

        sql = text(
            "SELECT * FROM orders WHERE user_id = :user_id AND status = :status"
        ).bindparams(
            bindparam("user_id", value=user_id, type_=int),
            bindparam("status", value=status, type_=str)
        )
        return db.execute(sql).fetchall()

    # 方法3：动态过滤with白名单
    @staticmethod
    def complex_filter_safe(db: Session, filter_dict: dict):
        ALLOWED = {'status': Product.status, 'category_id': Product.category_id}
        query = db.query(Product)
        for key, value in filter_dict.items():
            if key in ALLOWED:
                query = query.filter(ALLOWED[key] == value)
        return query.all()

    # 方法4：从ORM获取ID后使用
    @staticmethod
    def fetch_and_use_id(db: Session, category_name: str):
        if not category_name or len(category_name) > 100:
            return []
        category = db.query(Category).filter(
            Category.name == category_name
        ).first()
        if not category:
            return []
        return db.query(Product).filter(
            Product.category_id == category.id
        ).all()
```

## 修复优先级

1. **立即修复（当天）**：停止在text()中拼接ORM查询结果
2. **快速修复（3天内）**：使用参数化的text()或完全改为ORM方法
3. **短期改善（1周内）**：审计所有text()和literal_column()的使用
4. **长期改进（1个月）**：尽量使用ORM的filter()和select()安全方法
