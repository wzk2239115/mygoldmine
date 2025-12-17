# JavaScript sqlite3 驱动 SQL 拼接注入

## Details

**代码示例：**
```javascript
// 易受攻击的模式
const username = req.body.username;
const query = `SELECT * FROM users WHERE name = '${username}'`;  // 模板字符串拼接
db.get(query, (err, row) => { ... });

const userId = req.query.id;
const sql = "DELETE FROM sessions WHERE user_id = " + userId;  // + 运算符拼接
db.run(sql);

// 动态列名拼接
const sortBy = req.query.sort;
db.all(`SELECT * FROM products ORDER BY ${sortBy}`, callback);

// WHERE 子句动态拼接
const keyword = req.params.keyword;
db.each("SELECT * FROM posts WHERE title LIKE '%" + keyword + "%'", callback);
```

**快速定位核心操作（L1-L2）：**
- 关键词扫描：`db.run(`、`db.get(`、`db.all(`、`db.each(`、`db.exec(` 定位所有执行点
- 搜索正则：`\.(run|get|all|each)\(.*[\$\{|'.*\+]` 识别拼接模式
- 特征识别：模板字符串 `${}` 插值、加号连接 `+`、字符串 `.concat()` 方法
- 数据流回溯：查看拼接变量是否来自 `req.query`、`req.params`、`req.body`、`req.cookies`

**快速定位保护机制（L2-L3）：**
- 参数化查询特征：`db.run('SELECT * FROM users WHERE id = ?', [userId])` 或命名占位符 `$id`
- 输入校验函数：`validator.isAlphanumeric()`、`Number.isInteger()`、白名单数组 `.includes()`
- 类型强制转换：`parseInt()`、`parseFloat()`、`String.match(/^[0-9]+$/)`
- ORM/查询构建器：检查是否使用 better-sqlite3、Sequelize、TypeORM 等封装（L3）
- 中间件验证：Express-validator、Joi、Zod 等验证框架的使用（L4：跨模块追踪）

## Classify

**真实漏洞：**
- 用户可控输入直接通过字符串拼接嵌入 SQL 语句，无转义或验证
- 拼接点位于关键子句（WHERE、SET、INSERT VALUES、ORDER BY），输入未限制特殊字符
- 可注入单引号、双引号、分号、注释符（`--`、`/**/`）破坏 SQL 语义
- 输入验证不严格（仅检查长度、非空等弱规则）

**误报：**
- 拼接内容为常量、环境变量或硬编码配置值，非外部输入
- 输入已通过严格白名单验证（精确匹配枚举值、正则 `^[a-zA-Z0-9_]+$`）
- 数值型字段已通过 `Number()` + `isFinite()` 强制转换且未包裹引号
- 使用参数化查询数组/对象形式传递变量

**代码异味：**
- 输入经过简单清理但不彻底（如仅 `.replace(/'/g, "''")` 转义单引号）
- 部分参数使用占位符，部分仍用拼接（混合模式）
- 拼接用于非敏感操作（LIMIT、OFFSET）但未校验数据类型
- 依赖客户端验证或前端过滤

## Low risk

**低风险场景：**
- 拼接位置仅限于 ORDER BY、列名、表名，且已限制在白名单数组内（全等比较 `===`）
- 输入源为内部服务或数据库查询结果（非直接暴露的 HTTP 接口），但需警惕二次注入
- 仅在管理后台且已通过强身份认证和 RBAC 权限校验的功能
- 查询操作为只读且目标表不含敏感信息（如公开商品列表、日志统计表）
- SQLite 数据库文件权限受限（只读挂载、容器隔离），攻击者无法写入恶意文件
- 注入点位于 LIMIT/OFFSET，输入已强制转为整数且未在引号内包裹