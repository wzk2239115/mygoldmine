# TypeScript Knex.js raw() 字符串拼接 SQL 注入

## Details

**漏洞成因**：在 TypeScript/Node.js 后端使用 Knex.js 查询构造器时，通过 `knex.raw()` 方法结合模板字符串、字符串拼接或 `.format()` 直接嵌入用户输入，绕过了 Knex 的参数化查询机制，导致 SQL 注入。

**典型代码示例**：

```typescript
import knex from 'knex';

// 危险：使用模板字符串拼接
const userId = req.query.id;
await knex.raw(`SELECT * FROM users WHERE id = ${userId}`);

// 危险：使用字符串拼接
const tableName = req.params.table;
await knex.raw("SELECT * FROM " + tableName + " WHERE status = 1");

// 危险：动态拼接 WHERE 条件
const keyword = req.body.search;
await knex.raw(`SELECT * FROM posts WHERE title LIKE '%${keyword}%'`);

// 危险：拼接 ORDER BY 字段
const sortField = req.query.sort;
await knex.raw(`SELECT * FROM products ORDER BY ${sortField}`);

// 安全：使用 knex.raw() 的参数绑定
await knex.raw('SELECT * FROM users WHERE id = ?', [userId]);

// 安全：使用 Knex 查询构造器
await knex('users').where('id', userId).select('*');
```

**快速定位核心操作**（L1-L2: 关键词扫描 → 跳读）：
- **L1**: 搜索 `knex.raw(`、`.raw(`、`db.raw(` 定位所有原始 SQL 执行点
- **L1**: 搜索模板字符串特征：`` `...${...}` ``、字符串拼接 `+`、`.concat()`
- **L2**: 跳读检查 raw() 参数是否为动态字符串，回溯变量来源
- **L2**: 识别输入源：`req.query`、`req.params`、`req.body`、`request.input()`、`ctx.request`
- **L2**: 检查是否存在跨函数传参链条，关注函数参数未验证直接传入 raw()
- **L3**: 逐行追踪变量在传入 raw() 前的所有变换操作，确认是否存在验证逻辑

**快速定位保护机制**（L1-L2: 关键词扫描 → 跳读）：
- **L1**: 参数化查询特征：`knex.raw('...?...', [param])` 或 `knex.raw('...??...', [ident])` 使用占位符且传入参数数组
- **L1**: Knex 查询构造器：`.where()`、`.whereIn()`、`.select()` 方法（通常安全）
- **L2**: 输入验证函数：`Number.isInteger()`、`parseInt()` + `isNaN()` 检查、`typeof === 'number'`
- **L2**: 白名单校验：`if (field in allowedFields)`、`switch-case` 枚举、常量映射对象
- **L2**: TypeScript 类型守卫：`as number`、类型断言 + 运行时验证、Zod/Joi 等 schema 验证
- **L3**: 追踪验证逻辑完整性，检查是否覆盖所有分支和异常情况

## Classify

**确认为漏洞**：
- raw() 方法使用模板字符串或字符串拼接操作构造 SQL，且拼接变量直接或间接来自外部输入
- 拼接变量来源于 HTTP 请求参数、表单数据、WebSocket 消息、GraphQL 变量、文件上传内容等不可信源
- raw() 调用仅传入单一拼接后的字符串，未使用 `?` 或 `??` 占位符和第二参数数组
- 无有效的输入验证、类型转换、白名单校验或转义处理
- 动态表名/列名/函数名来自用户输入且未经严格白名单验证

**判定为误报**：
- 拼接变量为常量、硬编码字符串、环境变量（如 `TABLE_PREFIX`）、配置文件值，非用户输入
- 拼接内容仅为表名/列名且已通过严格白名单校验（精确匹配预定义列表或枚举类型）
- 输入已完成强类型转换（如 `parseInt()` + `isNaN()` 校验）且处理了边界情况
- 使用了 raw() 的参数化形式：`knex.raw('...?...', [param])` 正确传参
- 使用 Knex 查询构造器 API（`.where()`、`.insert()` 等）而非 raw() 拼接
- SQL 仅用于日志记录、调试输出、测试代码，未实际执行或影响生产数据库

**代码异味**：
- 虽有输入验证但逻辑不严密（如仅检查长度、使用正则过滤但规则不完整）
- 使用自定义转义函数（如 `.replace(/'/g, "''")` ）但未覆盖所有注入向量（如反引号、注释符）
- 混合使用参数化与拼接（部分字段使用 `?` 占位符，表名/ORDER BY 字段仍拼接）
- 依赖前端校验或客户端传入的 `type`/`format` 字段判断处理逻辑
- 使用 `knex.raw()` 包装 SQL 片段后再拼接到查询构造器中，增加审计复杂度
- TypeScript 类型标注为 `string` 但缺乏运行时验证，存在类型欺骗风险

## Low risk

**低风险场景**：
- 输入已通过强类型转换且异常处理完整（如 `const id = parseInt(req.query.id); if (isNaN(id)) throw error`）
- 变量限制在严格白名单内（如 `direction in ['ASC', 'DESC']` 或枚举类型映射）
- 仅用于内部管理工具、CLI 脚本或单租户 SaaS 管理后台，且有完善的权限验证机制
- 查询操作仅限 SELECT 且目标表不含敏感数据（如统计表、缓存表），数据库用户权限为只读
- 输入长度被严格限制（如 `maxLength: 3`）且仅允许字母数字字符（正则 `/^[a-zA-Z0-9]+$/`）
- 拼接位置为 LIMIT/OFFSET 且已强制转换为整数类型，影响范围仅限查询结果数量
- 注入点位于非关键业务流程（如日志查询、统计报表）且应用运行在隔离的开发/测试环境
- 数据库配置禁用了堆叠查询、注释语法，且连接用户权限受严格限制（无 DROP/ALTER 权限）