**JavaScript (Node.js) - mysql 驱动模板字符串拼接 SQL**

## Details

**代码示例：**
```javascript
// 典型漏洞场景
const query = `SELECT * FROM users WHERE username = '${req.body.username}' AND password = '${req.body.password}'`;
connection.query(query, (err, results) => { ... });

// 动态条件拼接
const sql = `SELECT * FROM products WHERE 1=1 ${category ? `AND category='${category}'` : ''}`;

// ORDER BY 动态排序
const orderSql = `SELECT * FROM items ORDER BY ${sortField}`;
```

**快速定位核心操作（L1-L2）：**
- 关键词：`connection.query(`、`pool.query(`、`db.query(`、`execute(`
- 特征模式：\`SELECT|INSERT|UPDATE|DELETE\` 开头的模板字符串
- 搜索正则：`\.query\(.*\$\{` 定位字符串插值点
- 注意 Express/Koa 路由中的 `req.params`、`req.query`、`req.body` 流向数据库操作

**快速定位保护机制（L2-L3）：**
- 参数化查询标志：`query('SELECT * FROM users WHERE id = ?', [userId])`（占位符 `?` + 数组参数）
- 转义函数：`connection.escape()`、`mysql.escapeId()` 包裹用户输入
- ORM 框架：检查是否使用 Sequelize、TypeORM 等（通常安全，但需确认未使用 `.query()` raw SQL）
- 输入验证：查找 `validator.isInt()`、`parseInt()`、白名单映射（如 `allowedFields.includes(sortField)`）

## Classify

**漏洞（True Positive）：**
- 用户可控数据（HTTP 参数、Cookie、Header）直接插值到 SQL 模板字符串，且未经转义或验证
- 动态表名/字段名拼接且无白名单限制
- WHERE 条件、ORDER BY、LIMIT 等子句使用字符串拼接且输入源不可信

**误报（False Positive）：**
- 插值内容为硬编码常量或配置文件静态值
- 在拼接前已通过 `connection.escape()` 转义或使用严格类型转换（如 `parseInt(id, 10)`）
- 使用参数化查询数组形式（`query(sql, [param1, param2])`）

**代码异味（Code Smell）：**
- 虽有基础验证（如 `isNaN()` 检查），但未覆盖所有 SQL 注入场景（如 UNION、注释符）
- 部分参数使用占位符，部分仍用字符串拼接（混合模式）
- 依赖前端验证或简单长度限制

## Low risk

**评级为低风险的情况：**
- 仅在内部管理系统或需强认证（硬编码 token、IP 白名单）的接口中使用
- 拼接字段为数值类型且已强制 `Number()` 转换 + `isFinite()` 校验
- 动态内容来自数据库已有数据（非直接用户输入），但需警惕二次注入场景
- 存在 WAF 或中间件进行全局 SQL 关键词过滤（不可靠，但可降级风险）
- 影响范围限于只读操作且数据非敏感（如公开商品列表）