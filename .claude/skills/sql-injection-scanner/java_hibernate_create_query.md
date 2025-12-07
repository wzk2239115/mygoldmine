**Java - Hibernate 原生 SQL 查询字符串拼接**  
常出现在使用 Hibernate Session 的 createSQLQuery、createQuery 或 createNativeQuery 方法时错误地使用字符串拼接或 String.format 构造查询，而非使用命名参数或位置参数绑定机制，常见于动态条件查询、报表统计、批量操作等模块。

## Details

**代码示例：**
```java
// 典型漏洞模式 - createSQLQuery 字符串拼接
String username = request.getParameter("username");
String sql = "SELECT * FROM users WHERE username = '" + username + "'";
Query query = session.createSQLQuery(sql);
List results = query.list();

// String.format 拼接
String keyword = req.getParameter("keyword");
String hql = String.format("FROM Product WHERE name LIKE '%%%s%%'", keyword);
Query query = session.createQuery(hql);

// 动态列名/表名拼接
String sortField = request.getParameter("sort");
String sql = "SELECT * FROM orders ORDER BY " + sortField;
session.createNativeQuery(sql).getResultList();

// createQuery HQL 拼接（同样危险）
String status = params.get("status");
Query query = session.createQuery("FROM Order o WHERE o.status = " + status);

// StringBuilder 拼接
StringBuilder sql = new StringBuilder("SELECT * FROM logs WHERE 1=1");
if (userId != null) {
    sql.append(" AND user_id = ").append(userId);  // 数值型注入
}
session.createSQLQuery(sql.toString()).list();
```

**快速定位核心操作技巧（L1-L2）：**
- 关键 API：`.createSQLQuery(`、`.createQuery(`、`.createNativeQuery(`、`.getNamedQuery(`
- 拼接模式：字符串 `+` 连接、`String.format()`、`StringBuilder.append()` 后接 Hibernate 查询方法
- 搜索正则：`createSQLQuery\(.*\+\s*|String\.format.*SELECT|INSERT|UPDATE|DELETE`
- 关注 HTTP 参数源头：`request.getParameter`、`@RequestParam`、`@PathVariable` 直接流入查询构造
- 优先审查：动态条件筛选、分页排序、多表联查、批量更新等复杂查询模块
- 注意 HQL 查询同样存在注入风险（非原生 SQL 也不安全）

**快速定位保护机制技巧（L2-L3）：**
- 参数化查询：`setParameter("name", value)` 或 `setParameter(0, value)` 位置参数
- 命名参数：HQL/SQL 中使用 `:paramName` 占位符配合 `setParameter()`
- Criteria API：`session.createCriteria(User.class).add(Restrictions.eq("name", name))` 结构化查询
- JPA CriteriaBuilder：`cb.equal(root.get("status"), status)` 类型安全方式
- 输入校验：`Integer.parseInt()`、正则匹配、枚举类型转换、白名单映射
- ORM 对象绑定：`Query.setEntity()`、`setProperties()` 整体对象绑定
- 检查自定义工具类：可能封装了参数化逻辑的 `QueryBuilder`、`SqlHelper` 等
- **审计等级 L2-L3**：跳读白名单覆盖范围，逐行确认所有动态部分均已参数化

## Classify

**漏洞判定：**
- 外部输入（HTTP 参数、JSON 字段、Cookie、Header）未经校验直接拼接到 SQL/HQL
- 动态列名、表名、ORDER BY 字段、JOIN 条件无白名单限制直接拼接
- 使用 `String.format`、`+`、`StringBuilder` 拼接用户可控内容到查询语句
- HQL 查询中拼接动态实体属性名或条件表达式
- Native SQL 中拼接 LIKE 模糊查询、IN 子句、LIMIT/OFFSET 分页参数

**误报判定：**
- 拼接内容完全来自常量、枚举、配置文件硬编码值（`static final` 常量）
- 列名/表名通过严格 `switch-case`、`Map` 白名单映射后拼接
- 查询值已通过 `.setParameter()` 参数化，仅表名/列名需要动态拼接且有校验
- 仅在单元测试 `@Test` 方法或数据库初始化脚本中使用
- 使用 Hibernate Validator 或 Spring Validation 完成类型/格式强校验后拼接

**代码异味：**
- 混合参数化与拼接（部分条件用 `setParameter`，部分条件拼接）
- 依赖前端传递固定值但后端未二次校验白名单
- 动态查询构造逻辑分散在多个 Service/DAO 方法，数据流追踪困难
- 使用正则校验列名但允许范围过宽（如 `^[a-zA-Z0-9_]+$` 允许任意字段名）
- 注释标注"临时方案"或"待重构"但长期未修复

## Low risk

**低风险场景：**
- 列名从实体类 `@Column` 注解反射获取且映射关系不可外部修改
- 排序方向限定为 `"ASC"`/`"DESC"` 且通过 `toUpperCase()` 标准化后白名单匹配
- 数值型 ID 经 `Long.parseLong()` 或 `Integer.valueOf()` 强制类型转换后用于条件（抛异常中断执行）
- 内部管理后台且已通过 Shiro/Spring Security 角色权限二次鉴权（需评估业务敏感度）
- 查询用于非关键业务的操作日志/审计日志且结果不包含敏感字段（密码、token）
- 数据源为只读从库或数据仓库副本，注入仅可能导致信息泄露而无数据篡改风险
- 表名拼接来自系统配置表且配置修改需要数据库管理员权限（需确认权限隔离）