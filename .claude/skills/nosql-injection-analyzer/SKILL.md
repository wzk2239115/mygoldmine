---
name: nosql-injection-analyzer
description: 专业的审计工作流程，通过静态代码分析识别和验证 NoSQL 注入漏洞；重点关注检测不安全的 NoSQL 查询构造，即用户可控输入未经适当验证或过滤直接用于构造 NoSQL 查询对象、操作符或查询条件；利用按编程语言组织的参考资料目录中的参考指南。
---

## 通用 NoSQL 注入漏洞模式（所有项目必审）

查看详细说明：[general.md](general.md)

快速概览：操作符注入（$ne/$gt/$lt/$regex/$where 等操作符可控）、JavaScript 代码注入（$where 子句执行用户输入、eval 函数调用）、数组操作符注入（$in/$nin/$all 等数组操作符可控）、正则表达式注入（$regex 操作符中用户输入未转义）、类型混淆攻击（字符串与数字类型混淆、布尔值注入）、逻辑操作符注入（$or/$and/$nor 等逻辑操作符可控）、查询对象直接构造（用户输入直接作为查询对象、JSON 解析后直接使用）、ORM/ODM 框架不安全使用（未使用参数化、直接拼接查询条件）、NoSQL 盲注场景（布尔盲注、时间盲注、错误信息泄露）

**NoSQL 注入漏洞**

**Attention**  
当项目中使用了 NoSQL 数据库（如 MongoDB、CouchDB、Redis、Cassandra 等）并将用户可控输入未经安全处理直接用于构造查询对象、操作符或查询条件时，极易引发 NoSQL 注入漏洞。此类问题通常出现在用户登录认证、数据查询（搜索、列表展示、条件过滤）、数据更新、删除等涉及 NoSQL 数据库交互的业务模块中，需重点审计动态构造 NoSQL 查询的代码路径。

**Early exit**  
若项目完全未使用 NoSQL 数据库（如仅使用关系型数据库且无 NoSQL 接口）、或所有 NoSQL 数据库操作均通过完全参数化查询/ORM 框架（且确保无查询对象直接构造）、或前端为纯静态页面无后端逻辑，则可快速退出对该漏洞类型的审计。

**Cases**

**JavaScript (Node.js)**
使用 MongoDB 原生驱动时，用户输入直接用于构造查询对象或操作符，详见：[NodeJS_MongoDB_QueryObject_Injection.md](NodeJS_MongoDB_QueryObject_Injection.md) | 遇到操作符注入或类型混淆保护机制，详见：[bypassTricks.md#1-mongodb-操作符注入绕过](bypassTricks.md#1-mongodb-操作符注入绕过) 或 [bypassTricks.md#4-类型混淆攻击](bypassTricks.md#4-类型混淆攻击)
MongoDB $where 子句中直接执行用户输入的 JavaScript 代码，详见：[NodeJS_MongoDB_Where_Code_Injection.md](NodeJS_MongoDB_Where_Code_Injection.md) | 遇到 JavaScript 代码注入保护机制，详见：[bypassTricks.md#2-javascript-代码注入where-绕过](bypassTricks.md#2-javascript-代码注入where-绕过)
Mongoose ODM 框架中未使用参数化而直接拼接查询条件，详见：[NodeJS_Mongoose_Query_Concat.md](NodeJS_Mongoose_Query_Concat.md) | 遇到 ORM/ODM 框架保护机制，详见：[bypassTricks.md#6-ormodm-框架绕过](bypassTricks.md#6-ormodm-框架绕过)
Redis 命令构造时用户输入未转义直接拼接，详见：[NodeJS_Redis_Command_Injection.md](NodeJS_Redis_Command_Injection.md) | 遇到 Redis 命令注入保护机制，详见：[bypassTricks.md#7-redis-命令注入绕过](bypassTricks.md#7-redis-命令注入绕过)
CouchDB 查询中用户输入直接用于构造查询对象，详见：[NodeJS_CouchDB_Query_Injection.md](NodeJS_CouchDB_Query_Injection.md) | 遇到 JSON 解析或查询对象注入保护机制，详见：[bypassTricks.md#5-json-和对象解析注入](bypassTricks.md#5-json-和对象解析注入)

**TypeScript**
TypeScript 中使用 MongoDB 驱动时，类型不安全的查询对象构造，详见：[TypeScript_MongoDB_Type_Unsafe_Query.md](TypeScript_MongoDB_Type_Unsafe_Query.md) | 遇到类型混淆或操作符注入保护机制，详见：[bypassTricks.md#4-类型混淆攻击](bypassTricks.md#4-类型混淆攻击) 或 [bypassTricks.md#1-mongodb-操作符注入绕过](bypassTricks.md#1-mongodb-操作符注入绕过)
TypeORM MongoDB 驱动中原始查询的不安全使用，详见：[TypeScript_TypeORM_MongoDB_Raw_Query.md](TypeScript_TypeORM_MongoDB_Raw_Query.md) | 遇到 ORM/ODM 框架保护机制，详见：[bypassTricks.md#6-ormodm-框架绕过](bypassTricks.md#6-ormodm-框架绕过)
NestJS 中 DTO 验证绕过导致的查询注入，详见：[TypeScript_NestJS_DTO_Bypass.md](TypeScript_NestJS_DTO_Bypass.md) | 遇到类型验证或 JSON 解析保护机制，详见：[bypassTricks.md#4-类型混淆攻击](bypassTricks.md#4-类型混淆攻击) 或 [bypassTricks.md#5-json-和对象解析注入](bypassTricks.md#5-json-和对象解析注入)

**Python**
使用 PyMongo 时，用户输入直接用于构造查询字典或操作符，详见：[Python_PyMongo_Query_Dict_Injection.md](Python_PyMongo_Query_Dict_Injection.md) | 遇到操作符注入或类型混淆保护机制，详见：[bypassTricks.md#1-mongodb-操作符注入绕过](bypassTricks.md#1-mongodb-操作符注入绕过) 或 [bypassTricks.md#4-类型混淆攻击](bypassTricks.md#4-类型混淆攻击)
MongoEngine ODM 框架中未使用参数化而直接拼接查询条件，详见：[Python_MongoEngine_Query_Concat.md](Python_MongoEngine_Query_Concat.md) | 遇到 ORM/ODM 框架保护机制，详见：[bypassTricks.md#6-ormodm-框架绕过](bypassTricks.md#6-ormodm-框架绕过)
Redis-py 客户端中命令构造时用户输入未转义，详见：[Python_Redis_Command_Injection.md](Python_Redis_Command_Injection.md) | 遇到 Redis 命令注入保护机制，详见：[bypassTricks.md#7-redis-命令注入绕过](bypassTricks.md#7-redis-命令注入绕过)
Cassandra 驱动中 CQL 查询构造时用户输入直接拼接，详见：[Python_Cassandra_CQL_Injection.md](Python_Cassandra_CQL_Injection.md) | 遇到 CQL 注入保护机制，详见：[bypassTricks.md#8-cqlcassandra-注入绕过](bypassTricks.md#8-cqlcassandra-注入绕过)
Django 中使用 MongoDB 时查询对象直接构造，详见：[Python_Django_MongoDB_Query_Injection.md](Python_Django_MongoDB_Query_Injection.md) | 遇到 ORM 框架或 JSON 解析保护机制，详见：[bypassTricks.md#6-ormodm-框架绕过](bypassTricks.md#6-ormodm-框架绕过) 或 [bypassTricks.md#5-json-和对象解析注入](bypassTricks.md#5-json-和对象解析注入)

**Java**
使用 MongoDB Java 驱动时，用户输入直接用于构造 BasicDBObject 或查询操作符，详见：[Java_MongoDB_BasicDBObject_Injection.md](Java_MongoDB_BasicDBObject_Injection.md) | 遇到操作符注入或类型混淆保护机制，详见：[bypassTricks.md#1-mongodb-操作符注入绕过](bypassTricks.md#1-mongodb-操作符注入绕过) 或 [bypassTricks.md#4-类型混淆攻击](bypassTricks.md#4-类型混淆攻击)
Spring Data MongoDB 中查询方法参数未验证直接使用，详见：[Java_SpringData_MongoDB_Query_Injection.md](Java_SpringData_MongoDB_Query_Injection.md) | 遇到 ORM/ODM 框架保护机制，详见：[bypassTricks.md#6-ormodm-框架绕过](bypassTricks.md#6-ormodm-框架绕过)
Morphia ODM 框架中查询条件直接构造，详见：[Java_Morphia_Query_Injection.md](Java_Morphia_Query_Injection.md) | 遇到 ORM/ODM 框架保护机制，详见：[bypassTricks.md#6-ormodm-框架绕过](bypassTricks.md#6-ormodm-框架绕过)
Redis Jedis 客户端中命令构造时用户输入未转义，详见：[Java_Redis_Jedis_Command_Injection.md](Java_Redis_Jedis_Command_Injection.md) | 遇到 Redis 命令注入保护机制，详见：[bypassTricks.md#7-redis-命令注入绕过](bypassTricks.md#7-redis-命令注入绕过)
Cassandra 驱动中 CQL 查询构造时用户输入直接拼接，详见：[Java_Cassandra_CQL_Injection.md](Java_Cassandra_CQL_Injection.md) | 遇到 CQL 注入保护机制，详见：[bypassTricks.md#8-cqlcassandra-注入绕过](bypassTricks.md#8-cqlcassandra-注入绕过)

**Go**
使用 mongo-driver 时，用户输入直接用于构造 bson.M 查询对象，详见：[Go_MongoDB_BSON_Injection.md](Go_MongoDB_BSON_Injection.md) | 遇到操作符注入或类型混淆保护机制，详见：[bypassTricks.md#1-mongodb-操作符注入绕过](bypassTricks.md#1-mongodb-操作符注入绕过) 或 [bypassTricks.md#4-类型混淆攻击](bypassTricks.md#4-类型混淆攻击)
GORM MongoDB 插件中查询条件直接构造，详见：[Go_GORM_MongoDB_Query_Injection.md](Go_GORM_MongoDB_Query_Injection.md) | 遇到 ORM/ODM 框架保护机制，详见：[bypassTricks.md#6-ormodm-框架绕过](bypassTricks.md#6-ormodm-框架绕过)
Redis go-redis 客户端中命令构造时用户输入未转义，详见：[Go_Redis_Command_Injection.md](Go_Redis_Command_Injection.md) | 遇到 Redis 命令注入保护机制，详见：[bypassTricks.md#7-redis-命令注入绕过](bypassTricks.md#7-redis-命令注入绕过)
Cassandra gocql 驱动中 CQL 查询构造时用户输入直接拼接，详见：[Go_Cassandra_CQL_Injection.md](Go_Cassandra_CQL_Injection.md) | 遇到 CQL 注入保护机制，详见：[bypassTricks.md#8-cqlcassandra-注入绕过](bypassTricks.md#8-cqlcassandra-注入绕过)

**PHP**
使用 MongoDB PHP 库时，用户输入直接用于构造查询数组或操作符，详见：[PHP_MongoDB_Query_Array_Injection.md](PHP_MongoDB_Query_Array_Injection.md) | 遇到操作符注入或类型混淆保护机制，详见：[bypassTricks.md#1-mongodb-操作符注入绕过](bypassTricks.md#1-mongodb-操作符注入绕过) 或 [bypassTricks.md#4-类型混淆攻击](bypassTricks.md#4-类型混淆攻击)
Doctrine MongoDB ODM 中查询条件直接构造，详见：[PHP_Doctrine_MongoDB_Query_Injection.md](PHP_Doctrine_MongoDB_Query_Injection.md) | 遇到 ORM/ODM 框架保护机制，详见：[bypassTricks.md#6-ormodm-框架绕过](bypassTricks.md#6-ormodm-框架绕过)
Redis phpredis 扩展中命令构造时用户输入未转义，详见：[PHP_Redis_Command_Injection.md](PHP_Redis_Command_Injection.md) | 遇到 Redis 命令注入保护机制，详见：[bypassTricks.md#7-redis-命令注入绕过](bypassTricks.md#7-redis-命令注入绕过)
Laravel 中使用 MongoDB 时查询对象直接构造，详见：[PHP_Laravel_MongoDB_Query_Injection.md](PHP_Laravel_MongoDB_Query_Injection.md) | 遇到 ORM 框架或 JSON 解析保护机制，详见：[bypassTricks.md#6-ormodm-框架绕过](bypassTricks.md#6-ormodm-框架绕过) 或 [bypassTricks.md#5-json-和对象解析注入](bypassTricks.md#5-json-和对象解析注入)

**C/C++**
使用 MongoDB C 驱动时，用户输入直接用于构造 BSON 查询对象，详见：[C_MongoDB_BSON_Injection.md](C_MongoDB_BSON_Injection.md) | 遇到操作符注入或类型混淆保护机制，详见：[bypassTricks.md#1-mongodb-操作符注入绕过](bypassTricks.md#1-mongodb-操作符注入绕过) 或 [bypassTricks.md#4-类型混淆攻击](bypassTricks.md#4-类型混淆攻击)
Redis hiredis 客户端中命令构造时用户输入未转义，详见：[C_Redis_Hiredis_Command_Injection.md](C_Redis_Hiredis_Command_Injection.md) | 遇到 Redis 命令注入保护机制，详见：[bypassTricks.md#7-redis-命令注入绕过](bypassTricks.md#7-redis-命令注入绕过)
自定义 NoSQL 查询解析器中的注入风险，详见：[C_Custom_NoSQL_Parser_Injection.md](C_Custom_NoSQL_Parser_Injection.md) | 遇到 JSON 解析或自定义查询解析保护机制，详见：[bypassTricks.md#5-json-和对象解析注入](bypassTricks.md#5-json-和对象解析注入)

**Rust**
使用 mongodb crate 时，用户输入直接用于构造 Document 查询对象，详见：[Rust_MongoDB_Document_Injection.md](Rust_MongoDB_Document_Injection.md) | 遇到操作符注入或类型混淆保护机制，详见：[bypassTricks.md#1-mongodb-操作符注入绕过](bypassTricks.md#1-mongodb-操作符注入绕过) 或 [bypassTricks.md#4-类型混淆攻击](bypassTricks.md#4-类型混淆攻击)
Redis rustis 客户端中命令构造时用户输入未转义，详见：[Rust_Redis_Command_Injection.md](Rust_Redis_Command_Injection.md) | 遇到 Redis 命令注入保护机制，详见：[bypassTricks.md#7-redis-命令注入绕过](bypassTricks.md#7-redis-命令注入绕过)
自定义 NoSQL 查询构建器的不安全实现，详见：[Rust_Custom_NoSQL_Query_Builder.md](Rust_Custom_NoSQL_Query_Builder.md) | 遇到 JSON 解析或自定义查询构建器保护机制，详见：[bypassTricks.md#5-json-和对象解析注入](bypassTricks.md#5-json-和对象解析注入)

# 输出要求

确认漏洞后，加载 `bug-report` 技能获取标准化报告格式，生成漏洞报告文件。

**加载技能**：`bug-report`

**输出路径**：`.workspace/findings/BUG-nosql-injection-{file}-L{line}-{source}-{sink}.md`

**约束**：
- 每个漏洞必须生成独立的 BUG 文件，禁止合并或省略
- 漏洞报告格式严格遵循 `bug-report` 技能定义的模板

