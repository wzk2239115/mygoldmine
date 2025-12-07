# TypeScript TypeORM 原始 SQL 拼接注入

## Details

**漏洞成因**：在 TypeORM 中使用 `query()`、`manager.query()`、`createQueryBuilder().where()` 等方法时，通过模板字符串（template literals）或字符串拼接将用户输入直接嵌入 SQL 语句，而非使用 TypeORM 的参数化查询机制，导致恶意输入可破坏 SQL 语义。

**典型代码示例**：

```typescript
import { getRepository, getManager } from 'typeorm';

// 危险：使用模板字符串拼接
const username = req.body.username;
const query = `SELECT * FROM users WHERE username = '${username}'`;
await getManager().query(query);

// 危险：在 QueryBuilder 中拼接
const searchTerm = req.query.search;
await getRepository(User)
  .createQueryBuilder('user')
  .where(`user.name LIKE '%${searchTerm}%'`)
  .getMany();

// 危险：拼接表名或列名
const tableName = req.params.table;
await connection.query(`SELECT * FROM ${tableName} WHERE id = 1`);

// 危险：使用字符串拼接
const userId = req.query.id;
const sql = "DELETE FROM orders WHERE user_id = " + userId;
await dataSource.query(sql);

// 安全：使用参数化查询
await getManager().query(
  "SELECT * FROM users WHERE username = $1",
  [username]
);

// 安全：使用 QueryBuilder 参数化
await getRepository(User)
  .createQueryBuilder('user')
  .where('user.name LIKE :search', { search: `%${searchTerm}%` })
  .getMany();
```

**快速定位核心操作**（L2: 跳读）：
- 搜索 `.query(`、`manager.query(`、`connection.query(`、`dataSource.query(` 定位原始 SQL 执行点
- 搜索 `.where(`、`.andWhere(`、`.orWhere(`、`.having(` 定位 QueryBuilder 条件构造
- 识别字符串构造方式：模板字符串（`` `${var}` ``）、`+` 拼接、`.concat()`
- 回溯变量来源：检查是否来自 `req.body`、`req.query`、`req.params`、`req.headers`、`req.cookies`
- 检查跨函数传参链条，关注未经验证的函数参数直接嵌入 SQL

**快速定位保护机制**（L1: 关键词扫描）：
- 参数化查询特征：`query(sql, [param])` 或 `query(sql, params)` 第二参数为数组，SQL 中使用 `$1, $2` 或 `?` 占位符
- QueryBuilder 参数化：`.where('field = :param', { param: value })` 使用命名参数或位置参数
- 输入验证函数：`validator.isEmail()`、`validator.isInt()`、`/^[a-z]+$/.test()`、`typeof x === 'number'`
- 类型强制转换：`parseInt()`、`Number()`、`parseFloat()` + `isNaN()` 检查
- 白名单校验：`if (field in { id: true, name: true })`、`ALLOWED_FIELDS.includes(field)`、枚举类型映射
- ORM 方法使用：`.findOne()`、`.find()`、`.save()`、`.update()` 等自带参数化的方法（通常安全）

## Classify

**确认为漏洞**：
- 原始 SQL 通过模板字符串或 `+` 拼接直接嵌入用户可控变量
- 拼接变量直接或间接来源于 HTTP 请求（body/query/params/headers/cookies）
- `.query()` 方法仅传入单一拼接后的 SQL 字符串，未使用第二参数传递参数数组
- QueryBuilder 的 `.where()` 方法直接拼接字符串，未使用命名参数或位置参数语法
- 无有效的输入验证、类型转换或白名单校验

**判定为误报**：
- 拼接变量为常量、硬编码字符串、配置对象属性（如 `config.tableName`）非用户输入
- 拼接内容仅为表名/列名且已通过严格白名单校验（精确匹配预定义枚举或常量数组）
- 输入已完成强类型转换（如 `parseInt(id, 10)` 后 `if (isNaN(id)) throw Error`）
- SQL 仅用于日志记录、监控输出或注释，未实际执行
- 已使用参数化查询的占位符形式（`$1` 或 `:param`）传参

**代码异味**：
- 虽有输入验证但逻辑不严密（如仅检查 `length > 0`、`.trim()`、简单正则过滤）
- 使用 `.replace()` 转义特殊字符但规则不完整，存在绕过可能（如仅替换单引号）
- 混合使用参数化与拼接（部分字段使用占位符，部分字段直接拼接）
- 依赖 TypeScript 类型声明但运行时未校验（如接口定义 `id: number` 但实际传入字符串）
- 依赖前端校验、DTO 装饰器验证但未在 SQL 执行前二次验证
- 使用自定义转义函数但未覆盖所有数据库特定注入向量

## Low risk

**低风险场景**：
- 输入已通过强类型转换且异常处理完整（如 `const id = parseInt(req.query.id); if (isNaN(id)) return res.status(400)`）
- 变量限制在严格白名单内（如 `sortOrder in ['ASC', 'DESC']` 或 `column in ['id', 'name', 'email']`）
- 仅用于管理后台且需管理员权限，有严格的 RBAC 或 JWT 验证，普通用户无法访问
- 查询操作仅限 SELECT 且目标表不含敏感数据（如日志表、缓存表），数据库账户为只读权限
- 输入长度被严格限制（如前端 `maxLength={5}` 且后端 `if (input.length > 5) throw`）且仅允许字母数字
- 拼接位置为 LIMIT/OFFSET 且已强制转换为整数类型，影响范围仅限查询数量
- 注入点位于非关键业务流程（如搜索历史、统计报表）且应用为内网工具或开发环境
- 使用 TypeORM 实体和 Repository 模式构建查询，仅动态部分为排序字段且已枚举校验