# JavaScript pg 驱动 SQL 拼接注入

## Details

**代码示例：**
```javascript
// 易受攻击的模式
const userId = req.query.id;
const query = `SELECT * FROM users WHERE id = ${userId}`;  // 模板字符串拼接
client.query(query);

const name = req.body.name;
const sql = "SELECT * FROM users WHERE name = '" + name + "'";  // + 运算符拼接
pool.query(sql);

// ORDER BY 拼接
const sortBy = req.query.sort;
client.query(`SELECT * FROM products ORDER BY ${sortBy}`);
```

**快速定位核心操作（L2: 跳读）：**
- 搜索 `client.query(`、`pool.query(`、`db.query(` 定位所有数据库查询点
- 关注第一参数：查看是否为字符串拼接而非参数化形式
- 识别拼接特征：模板字符串 `${}`、加号连接 `+`、字符串 concat 方法
- 回溯数据源：查看拼接变量是否来自 `req.query`、`req.params`、`req.body`、`req.headers`

**快速定位保护机制（L3: 逐行读）：**
- 检查是否使用参数化查询：`query('SELECT * FROM users WHERE id = $1', [userId])`
- 查找输入验证：正则校验、类型转换（`parseInt`、`parseFloat`）、白名单匹配
- 确认 ORM/查询构建器：是否使用 pg-promise、Sequelize、TypeORM 等安全封装
- 追踪中间件：Express validator、Joi、Yup 等验证框架的使用情况（L4: 跨模块追踪）

## Classify

**真实漏洞：**
- 用户可控输入直接拼接到 SQL 语句中，无任何验证或转义
- 拼接点用于敏感操作（WHERE、SET、INSERT VALUES），且输入未限制字符集
- 可注入特殊字符（单引号、分号、注释符）影响 SQL 语义

**误报：**
- 拼接内容为常量、配置项或硬编码值，非外部输入
- 输入已通过严格的白名单验证（如枚举值精确匹配）
- 数值型注入点已通过 `parseInt/Number` 强制转换且未包裹引号

**代码异味：**
- 输入经过部分清理但不彻底（如简单 replace 单引号）
- 拼接用于非关键字段（如 LIMIT、OFFSET 仅影响性能）
- 存在二次编码或特殊场景可绕过的验证逻辑

## Low risk

**低风险场景：**
- 拼接位置仅限于 ORDER BY、列名、表名，且已限制在预定义白名单内（字符串全等比较）
- 输入源为受信内部服务返回的结构化数据（非直接暴露的 HTTP 参数）
- 仅在管理后台且已通过强认证和角色权限校验的功能点
- 注入点位于 LIMIT/OFFSET，输入已强制转换为整数且数据库用户权限受限（只读权限）
- 查询结果仅用于日志记录或内部统计，不返回给前端且不影响业务逻辑