**Go - MongoDB BSON 查询对象注入**

使用官方 MongoDB Go Driver（mongo-go-driver）时，用户输入直接作为 `bson.M` 查询映射的键或值，或通过 `bson.D` 文档拼接用户可控字段名/操作符，导致 MongoDB 操作符注入。常见于灵活的动态查询构造、前端条件透传、JSON 反序列化后直接用于数据库查询等场景。

## Details

**代码示例：**
```go
// 典型漏洞1：用户输入作为查询字段键
username := r.FormValue("username")
password := r.FormValue("password")
filter := bson.M{username: password}  // {$ne: null} 绕过认证
collection.FindOne(ctx, filter)

// 典型漏洞2：用户输入作为操作符值
age := r.FormValue("age")
filter := bson.M{"age": age}  // {$gt: 18} 逻辑绕过
collection.Find(ctx, filter)

// 典型漏洞3：JSON 反序列化直接用于查询
var query bson.M
json.Unmarshal(body, &query)  // 攻击者可构造 {"$where": "..."}
collection.Find(ctx, query)

// 典型漏洞4：bson.D 文档拼接字段名
fieldName := r.FormValue("field")
filter := bson.D{{fieldName, value}}  // $ne、$regex 等被注入
collection.UpdateOne(ctx, filter, update)

// 典型漏洞5：查询结果用于构造后续查询
var result bson.M
collection.FindOne(ctx, bson.M{"_id": id}).Decode(&result)
// result 中可能包含 $where，后续再次用于查询
filter := bson.M{"data": result["data"]}
collection.Find(ctx, filter)
```

**快速定位核心操作技巧（L1-L2）：**
- 关键词扫描：`bson.M{`、`bson.D{`、`bson.E{` 后接用户输入变量或直接反序列化的 map/slice
- 搜索模式：查找 `json.Unmarshal`、`json.NewDecoder` 直接解析到 `bson.M`、`bson.D` 或 `map[string]interface{}`
- 关注 HTTP 参数（`r.FormValue`、`r.URL.Query()`、`c.Query`）、JSON 请求体直接流入 `bson.M` 构造
- 追踪 `bson.M{}` 初始化时是否存在动态键名（非常量字符串）
- 优先审查搜索、过滤、聚合管道构造、动态条件查询功能
- 检查是否使用了 `filter` 变量，尤其是跨函数传递的 filter 参数
- **审计等级 L1-L2**：关键词定位后快速检查输入源与 `bson.M` 构造的关联性

**快速定位保护机制技巧（L2-L3）：**
- 检查是否使用 `bson.M` 的参数化构造：显式用常量键名，值通过 `bson.D` 带有类型标签
- 查找白名单映射：`allowedFields := map[string]bool{"name": true, "age": true}` 校验字段名
- 检查对用户输入的预处理：字段名的枚举验证、操作符黑名单、JSON Schema 验证
- 追踪 `reflection` 包是否用于动态字段提取（潜在的类型混乱）
- 检查是否使用结构体序列化而非 `bson.M`：`json.Unmarshal(body, &StructType{})`
- 查找对 `$` 开头操作符的过滤：正则模式 `^$` 或显式的操作符黑名单判断
- **审计等级 L2-L3**：跳读白名单逻辑的完整性，逐行确认 `bson.M` 键名的来源是否完全可控

## Classify

**漏洞判定：**
- 外部输入（HTTP 参数、请求体 JSON、URL 参数）经 `json.Unmarshal` 直接解析到 `bson.M`、`bson.D` 或 `map[string]interface{}`，无后续验证
- 用户输入作为 `bson.M` 查询对象的键名（字段名），允许注入 `$where`、`$ne`、`$regex` 等操作符
- 用户输入作为 `bson.M` 值且无类型检查，允许嵌套对象包含操作符（如 `{"age": {"$gt": 18}}`）
- 从数据库查询结果或缓存中获取的 `bson.M` 对象再次用于查询条件，且中间过程未校验
- 聚合管道 `bson.A` 数组中使用用户输入构造阶段（`$match`、`$group` 等），无操作符白名单

**误报判定：**
- 使用结构体反序列化（`json.Unmarshal(body, &UserFilter{})`），JSON 字段对应结构体成员，字段名由编译时固定的结构标签确定
- 用户输入仅用于填充结构体的标量字段（字符串、整数），结构体本身被转换为 `bson.M` 时已由 `bson` 包标签控制键名
- 字段名通过严格的 `switch-case` 或 `map` 白名单映射后才用于 `bson.M` 构造
- 操作符完全来自常量或枚举值，不受外部输入影响
- 查询条件用于权限受限的只读操作或内部管理后台

**代码异味：**
- 混合结构体与 `bson.M` 反序列化，逻辑难以追踪
- 多层嵌套的 `bson.M` 构造，内层与外层字段来源不明确
- 依赖前端的数据类型转换但后端无二次校验
- `bson.M` 作为函数参数跨模块传递，修改点和使用点分散
- 使用 `reflection` 反射动态访问结构体字段后填充到 `bson.M`

## Low risk

**低风险场景：**
- 查询条件完全由编译时固定的结构体定义，用户输入仅填充结构体字段值，字段名由 `bson` 标签确定
- 字段名从预定义的常量映射表（如配置文件或常量 map）查询后使用，映射表不可外部修改
- 操作符黑名单检查明确排除 `$where`、`$function`、`$regex`、`$ne` 等危险操作符，检查在 JSON 反序列化后立即进行
- 查询条件仅包含数值、布尔、ISO8601 日期等原始类型，无嵌套对象或数组
- 使用官方推荐的 `bson` 包的 `filter` 帮助函数（如 `bson.A{}`、`primitive.ObjectID()` 等）构造类型安全的查询
- 数据库连接使用读只账户，即使注入也仅影响可见性而无法修改数据
- 查询用于非关键业务的日志审计或统计，且结果不包含敏感字段
