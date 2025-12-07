**Java - MyBatis 字符串拼接与 ${} 参数占位符**  
常出现在使用 MyBatis 映射器时错误地使用 `${}` 占位符或在 Mapper 接口中通过字符串拼接构造动态 SQL，而非使用 `#{}` 参数化绑定机制，常见于动态条件查询、排序字段、表名/列名动态拼接、批量操作等模块。

## Details

**代码示例：**
```java
// 典型漏洞模式 - XML Mapper 中使用 ${}
<!-- UserMapper.xml -->
<select id="findByUsername" resultType="User">
    SELECT * FROM users WHERE username = '${username}'  <!-- 直接替换，未转义 -->
</select>

<!-- 动态排序字段拼接 -->
<select id="getUserList" resultType="User">
    SELECT * FROM users ORDER BY ${sortField} ${sortOrder}  <!-- 列名和方向拼接 -->
</select>

<!-- 动态表名/列名 -->
<select id="queryTable" resultType="Map">
    SELECT ${columns} FROM ${tableName} WHERE id = #{id}  <!-- 混用 ${} 和 #{} -->
</select>

<!-- LIKE 模糊查询错误用法 -->
<select id="searchUser" resultType="User">
    SELECT * FROM users WHERE name LIKE '%${keyword}%'  <!-- 未使用 CONCAT 参数化 -->
</select>

// Java 代码字符串拼接 Mapper SQL
@Select("SELECT * FROM orders WHERE status = '" + status + "'")  // 注解中拼接
List<Order> findByStatus(@Param("status") String status);

// Provider 类中字符串拼接
public String buildQuery(Map<String, Object> params) {
    String condition = (String) params.get("condition");
    return "SELECT * FROM logs WHERE " + condition;  // 整条件拼接
}

// XML 中动态 SQL 拼接
<select id="dynamicQuery" resultType="Map">
    SELECT * FROM products WHERE 1=1
    <if test="category != null">
        AND category = '${category}'  <!-- 条件中使用 ${} -->
    </if>
</select>
```

**快速定位核心操作技巧（L1-L2）：**
- **L1 关键词扫描：** `${` 占位符（XML Mapper）、`@Select`/`@Update`/`@Delete`/`@Insert` 注解中的字符串拼接 `+`
- 搜索模式：`\$\{.*\}` 或 `@Select.*\+.*\)` 或 `@SelectProvider`/`@UpdateProvider`
- XML 中重点关注：`ORDER BY ${`、`LIKE '%${`、`FROM ${`、`WHERE ${` 等动态部分
- 注解 Mapper 中检查：`".*" + .* + ".*"` 字符串拼接模式
- Provider 类中审查：`SqlBuilder`、`SQL()` 方法中的字符串拼接、`StringBuilder.append()` 拼接变量
- 关注 HTTP 输入源头：`@RequestParam`、`@PathVariable`、`request.getParameter()` 流入 Mapper 参数
- 优先审查：动态排序、分页、多条件筛选、批量 IN 查询、报表统计等复杂查询模块

**快速定位保护机制技巧（L2-L3）：**
- **L2 跳读识别：** `#{}` 参数化占位符（预编译）、`<foreach>` 标签处理集合参数
- LIKE 安全写法：`CONCAT('%', #{keyword}, '%')` 或 `'%' || #{keyword} || '%'`（PostgreSQL）
- 动态列名/表名白名单：Service 层中的 `Map<String, String>` 映射、`switch-case` 穷举
- 类型安全校验：`@NotNull`、`@Pattern` 注解校验、枚举类型传参
- MyBatis 动态 SQL 安全标签：`<choose>`、`<when>`、`<otherwise>` 配合参数化
- SQL 注入防护拦截器：自定义 `Interceptor` 拦截 `${}` 使用、日志审计敏感操作
- 批量参数处理：`<foreach collection="ids" item="id" separator=","> #{id} </foreach>`
- **审计等级 L2-L3**：跳读确认所有用户输入走 `#{}`，逐行验证 `${}` 仅用于白名单值

## Classify

**漏洞判定：**
- XML Mapper 或注解 Mapper 中使用 `${}` 接收外部输入（HTTP 参数、JSON 字段、Cookie）
- 动态列名、表名、排序字段使用 `${}` 拼接且无白名单校验
- Provider 类中通过字符串拼接 `+` 或 `StringBuilder` 构造 SQL 且包含用户可控变量
- LIKE 查询、IN 子句、WHERE 条件使用 `${}` 而非 `#{}`
- 混合使用 `#{}` 和 `${}`，但关键部分（如条件值）仍用 `${}`

**误报判定：**
- `${}` 拼接内容完全来自枚举值、`static final` 常量、配置文件硬编码
- 列名/表名通过 Service 层严格白名单映射后传入 Mapper（需确认白名单覆盖所有可能值）
- 仅在单元测试 `@Test` 方法或数据库迁移脚本中使用
- 查询值已通过 `#{}` 参数化，仅排序方向（`ASC`/`DESC`）经过 `toUpperCase()` + 白名单校验后用 `${}`
- MyBatis Generator 自动生成的 Example 类动态查询（需确认前端未直接传递构造条件）

**代码异味：**
- 注释标注"临时处理 SQL 拼接"或"待优化"但长期未修复
- 混合参数化与拼接（部分字段用 `#{}`，部分用 `${}`）且无明确注释说明原因
- 动态列名来自枚举但未在 Mapper 层二次校验白名单
- 依赖前端固定传值（如排序字段限定为 `"name|age|createTime"`）但后端未强制验证
- 使用正则校验输入但允许范围过宽（如 `^[a-zA-Z0-9_]+$` 允许任意字段名）
- SQL 拼接逻辑分散在多个 Provider 类中，数据流追踪困难

## Low risk

**低风险场景：**
- 排序字段/方向从实体类 `@TableName`、`@Column` 注解反射获取且映射不可外部修改
- 数值型 ID 参数经 `Long.parseLong()` 或 `Integer.valueOf()` 强制转换（抛异常则中断执行）
- 表名拼接来自系统配置表且配置修改需要管理员数据库权限（需确认权限隔离）
- 内部管理后台且已通过 Shiro/Spring Security + 角色二次鉴权（需评估业务敏感度）
- 查询用于非关键业务的操作日志/审计日志且不包含敏感字段（密码、token、手机号）
- 数据源为只读从库或数据仓库副本，注入仅导致信息泄露无数据篡改风险
- 批量 IN 查询中动态生成占位符数量（如 `?, ?, ?`）但值本身走 `#{}`
- 列名拼接用于 GROUP BY、ORDER BY 但所有可能值已通过枚举类 `@EnumValue` 限定
