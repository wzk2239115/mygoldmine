# TypeScript NestJS DTO Bypass

## Details

**漏洞成因**：NestJS 中的 DTO 和验证装饰器（如 `@IsString()` 等）仅进行类型验证，并不能防止 MongoDB 操作符注入。当 DTO 验证通过后，用户输入被直接用于构造查询条件（特别是对象展开或 `Object.assign()` 合并时），攻击者可注入 MongoDB 操作符。此外，若 DTO 缺失对关键字段的白名单过滤，或在管道处理中有遗漏，输入会直接流入数据库层。

**代码审计焦点**：
- DTO 类是否仅进行类型验证而忽视操作符过滤
- 是否使用对象展开（`...dto`）或 `Object.assign()` 合并 DTO 到查询条件
- 验证管道（ValidationPipe）是否配置了 `forbidNonWhitelisted: true` 和 `forbidUnknownValues: true`
- 查询条件构造时是否缺失字段白名单或黑名单过滤
- 是否存在自定义装饰器或中间件绕过验证

**核心定位技巧**：
- **(L1: 关键词扫描)** 搜索 `@IsString()`、`@IsNumber()` 等验证装饰器；搜索 `...dto`、`Object.assign()`、`.find(`、`.findOne(` 等关键字；查找 `@Body()` 参数接收用户输入的地方
- **(L2: 跳读)** 检查 DTO 验证后是否直接用于构造查询对象；查看 `ValidationPipe` 的配置；确认查询方法是否接收了完整的 DTO 对象
- **(L3: 逐行读)** 追踪从 `@Body() dto` 到 `collection.find(query)` 的完整链路；确认是否进行了字段名验证或操作符过滤；检查是否遗漏了对嵌套属性的验证
- **(L4: 跨模块追踪)** 检查控制器、服务、数据访问层中 DTO 的传递和使用；验证是否有中间件或装饰器对参数进行了额外处理；确认 DTO 定义是否在多个服务间复用

**保护机制识别**：
- **(L1: 关键词扫描)** 检查是否使用了 `@Exclude()`、`@Transform()` 装饰器过滤字段；搜索 `pick()`、`omit()`、`.filter()` 等白名单过滤函数；查找是否使用了 `plainToClass()` 且配置了选项
- **(L2: 跳读)** 验证 `ValidationPipe` 配置中是否启用了 `forbidNonWhitelisted` 和 `forbidUnknownValues`；检查是否使用了自定义验证装饰器检查操作符；确认查询对象是否通过黑名单过滤操作符
- **(L3: 逐行读)** 确认字段白名单映射逻辑（如仅提取 `['username', 'email']` 字段）；验证是否使用了 `$` 字符黑名单过滤；检查 DTO 属性是否使用了枚举而非任意字符串
- **(L4: 跨模块追踪)** 检查是否使用了 ORM（Mongoose、MongoDB 原生驱动）的参数化查询；验证是否有全局防护中间件检查请求；确认数据库连接权限是否受限

## Classify

**漏洞研判**：
1. 若 DTO 仅进行类型验证但未过滤操作符，且直接用于构造查询条件 → 漏洞
2. 若使用对象展开或 `Object.assign()` 合并 DTO 到查询对象 → 漏洞
3. 若 DTO 允许控制查询操作符的键名（如 `{ [userKey]: userValue }`） → 漏洞
4. 若验证管道未启用 `forbidNonWhitelisted` 或 `forbidUnknownValues`，且接收额外属性 → 漏洞
5. 若使用 `plainToClass()` 转换但未配置黑名单或白名单 → 漏洞

**误报风险**：
1. DTO 仅包含预定义的字符串或数字属性，且在查询时进行了字段白名单映射 → 低风险
2. 使用了 `@Exclude()` 或 `@Transform()` 装饰器排除或转换敏感字段 → 低风险
3. 验证管道已正确配置 `forbidNonWhitelisted: true` 和 `forbidUnknownValues: true` → 低风险
4. 查询对象通过白名单字段映射（`pick(dto, ['name', 'email'])`） → 低风险

## Low risk

- DTO 属性通过 `@Exclude()` 或 `@Transform()` 装饰器过滤
- 使用了白名单字段映射（`pick()`、`lodash.pick()`）从 DTO 提取安全字段
- 验证管道配置 `forbidNonWhitelisted: true` 和 `forbidUnknownValues: true`
- 查询对象键名使用常量枚举而非用户输入
- DTO 使用自定义验证装饰器检查操作符前缀（`$`）
- 使用 Mongoose Schema 而非原生 MongoDB 驱动，且 DTO 字段与 Schema 一致
- 查询条件通过黑名单过滤操作符关键字（`$ne`、`$where` 等）
- 数据库连接权限受限（只读、特定表权限）
