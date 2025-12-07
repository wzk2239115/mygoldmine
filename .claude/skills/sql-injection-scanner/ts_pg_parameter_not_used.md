# TypeScript node-postgres(pg) 未使用参数化查询 SQL 注入

## Details

**漏洞成因**：在 TypeScript/Node.js 后端使用 node-postgres(pg) 驱动连接 PostgreSQL 时，通过模板字符串、字符串拼接或 `.format()` 直接嵌入用户输入到 SQL 语句，而非使用 pg 的参数化查询机制（`$1`, `$2` 占位符），导致 SQL 注入漏洞。

**典型代码示例**：

```typescript
import { Pool, Client } from 'pg';

const pool = new Pool();

// 危险：使用模板字符串拼接
const userId = req.query.id as string;
await pool.query(`SELECT * FROM users WHERE id = ${userId}`);

// 危险：使用字符串拼接
const username = req.body.username;
const sql = "SELECT * FROM users WHERE username = '" + username + "'";
await client.query(sql);

// 危险：动态拼接 WHERE 条件
const email = req.params.email;
await pool.query(`SELECT * FROM accounts WHERE email = '${email}'`);

// 危险：拼接 ORDER BY 字段
const sortField = req.query.sort;
await client.query(`SELECT * FROM products ORDER BY ${sortField}`);

// 危险：动态表名拼接
const tableName = req.body.table;
await pool.query(`SELECT * FROM ${tableName} WHERE status = 1`);

// 安全：使用参数化查询
await pool.query('SELECT * FROM users WHERE id = $1', [userId]);

// 安全：使用命名参数（通过库扩展）
await pool.query('SELECT * FROM users WHERE username = $1 AND status = $2', [username, 'active']);
```

**快速定位核心操作**（L1-L2: 关键词扫描 → 跳读）：
- **L1**: 搜索 `pool.query(`、`client.query(`、`.query(` 定位所有 SQL 执行点
- **L1**: 搜索字符串拼接特征：模板字符串 `` `...${...}` ``、`+` 操作符、`.concat()`
- **L2**: 跳读检查 query() 第一参数是否为动态字符串，是否存在第二参数（参数数组）
- **L2**: 识别输入源：`req.query`、`req.params`、`req.body`、`request.input()`、`ctx.request.body`
- **L2**: 检查是否存在跨函数传参链条，关注函数参数未验证直接传入 query()
- **L3**: 逐行追踪变量在传入 query() 前的所有变换操作，确认是否存在验证逻辑
- **L4**: 跨文件追踪：检查导入的工具函数、中间件是否对输入进行了有效验证

**快速定位保护机制**（L1-L3: 关键词扫描 → 跳读 → 逐行读）：
- **L1**: 参数化查询特征：`query('....$1....$2....', [param1, param2])` 使用 `$n` 占位符且传入参数数组
- **L1**: 查询构造器库：TypeORM 的 `.where()`、Prisma 的 `.findMany()`、Sequelize 等（通常安全）
- **L2**: 输入验证函数：`Number.isInteger()`、`parseInt()` + `isNaN()` 检查、`typeof === 'number'`
- **L2**: 白名单校验：`const allowedFields = ['id', 'name']; if (!allowedFields.includes(field))`、枚举映射
- **L2**: TypeScript 类型守卫：`as number` + 运行时验证、Zod/Joi/Yup schema 验证、class-validator
- **L2**: pg-format 库：`format('SELECT * FROM %I WHERE id = %L', table, id)` 正确使用标识符/字面量转义
- **L3**: 追踪验证逻辑完整性，检查是否覆盖所有分支、边界情况和异常处理
- **L3**: 检查中间件：express-validator、Koa 参数校验中间件是否正确应用到路由

## Classify

**确认为漏洞**：
- query() 方法使用模板字符串或字符串拼接操作构造 SQL，且拼接变量直接或间接来自外部输入
- 拼接变量来源于 HTTP 请求参数、表单数据、WebSocket 消息、GraphQL 变量、文件上传内容、外部 API 响应等不可信源
- query() 调用仅传入单一拼接后的字符串，未使用 `$1`、`$2` 等占位符和第二参数数组
- 无有效的输入验证、类型转换、白名单校验或转义处理
- 动态表名/列名/函数名来自用户输入且未经严格白名单验证（`pg-format` 的 `%I` 未使用或误用）

**判定为误报**：
- 拼接变量为常量、硬编码字符串、环境变量（如 `DB_SCHEMA`）、配置文件值、编译时常量，非用户输入
- 拼接内容仅为表名/列名且已通过严格白名单校验（精确匹配预定义列表、枚举类型、常量映射）
- 输入已完成强类型转换（如 `parseInt()` + `isNaN()` 校验、`Number.isInteger()`）且处理了边界情况和异常
- 使用了参数化形式：`query('SELECT * FROM users WHERE id = $1', [userId])` 正确传参
- 使用 pg-format 库正确转义：`format('SELECT * FROM %I WHERE id = %L', tableName, userId)`（`%I` 标识符，`%L` 字面量）
- 使用 ORM/查询构造器（TypeORM、Prisma、Sequelize）的安全 API 而非原始 SQL
- SQL 仅用于日志记录、调试输出、测试代码、注释示例，未实际执行或影响生产数据库

**代码异味**：
- 虽有输入验证但逻辑不严密（如仅检查长度、正则过滤但规则不完整、遗漏分支情况）
- 使用自定义转义函数（如 `.replace(/'/g, "''")` ）但未覆盖所有注入向量（如双引号、分号、`--`、`/**/`、换行符）
- 混合使用参数化与拼接（部分字段使用 `$n` 占位符，表名/ORDER BY 字段仍拼接）
- 依赖前端校验、客户端传入的 `type`/`format` 字段、JWT payload 中未验证的声明
- pg-format 误用：使用 `%s` 进行字符串拼接而非 `%L` 字面量转义，或未对标识符使用 `%I`
- TypeScript 类型标注为 `string` 或 `number` 但缺乏运行时验证，存在类型欺骗风险（如传入对象、数组）
- 验证逻辑位于条件分支中，存在绕过路径（如 `if (mode === 'safe')` 但有其他 mode 未验证）

## Low risk

**低风险场景**：
- 输入已通过强类型转换且异常处理完整（如 `const id = parseInt(req.query.id); if (isNaN(id) || id <= 0) throw new Error()`）
- 变量限制在严格白名单内（如 `const direction = req.query.dir; if (!['ASC', 'DESC'].includes(direction)) return error`）
- 使用枚举类型映射且无默认分支：`const columnMap: Record<string, string> = {...}; const col = columnMap[input]; if (!col) throw`
- 仅用于内部管理工具、CLI 脚本、单租户 SaaS 管理后台，且有完善的权限验证机制（如多因素认证、IP 白名单）
- 查询操作仅限 SELECT 且目标表不含敏感数据（如统计表、缓存表、日志表），数据库用户权限为只读
- 输入长度被严格限制（如 `maxLength: 3`）且仅允许字母数字字符（正则 `/^[a-zA-Z0-9]+$/` 且无其他分支）
- 拼接位置为 LIMIT/OFFSET 且已强制转换为整数类型（`parseInt()` + 范围校验），影响范围仅限查询结果数量
- 注入点位于非关键业务流程（如搜索历史、浏览记录、统计报表）且应用运行在隔离的开发/测试环境
- 数据库配置禁用了危险特性（如 `lo_import`、`COPY FROM PROGRAM`），且连接用户权限受严格限制（无 DROP/ALTER/CREATE 权限）
- 应用使用行级安全策略（RLS）且正确配置，限制了 SQL 注入的影响范围