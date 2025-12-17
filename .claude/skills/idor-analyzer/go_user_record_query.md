# Go - 用户记录查询未授权访问

## Details

**代码示例：**
```go
// 典型漏洞模式
func GetUserProfile(w http.ResponseWriter, r *http.Request) {
    userID := r.URL.Query().Get("user_id")  // 或 r.Header.Get("X-User-ID")
    var user User
    db.Where("id = ?", userID).First(&user)  // 直接查询，无权限校验
    json.NewEncoder(w).Encode(user)
}

// 更隐蔽的变体
func GetUserData(c *gin.Context) {
    uid := c.Param("id")  // 路径参数
    result := db.Model(&User{}).Where("user_id = ?", uid).Find(&data)
    c.JSON(200, data)
}
```

**快速定位核心操作（L2-L3 跳读/逐行）：**
- 识别HTTP处理器：`http.HandlerFunc`、`gin.Context`、`echo.Context`、`fiber.Ctx`
- 追踪参数来源：`Query().Get()`、`Param()`、`Header.Get()`、`FormValue()`、`PostForm()`
- 定位数据库操作：`db.Where()...First/Find/Scan()`、`db.Query/QueryRow()`、`Collection.FindOne()`
- 关注敏感资源：User、Profile、Order、Document、File、Record等模型查询

**快速定位保护机制（L3-L4 逐行/跨模块）：**
- **同层检查（L3）**：在查询前后寻找：
  - 会话校验：`GetSession()`、`c.Get("user")`、`middleware.Auth`
  - 所有权判断：`if user.ID != currentUserID`、`user.OwnerID == session.UserID`
  - 错误处理：查询后是否检查`user.ID`与请求者身份匹配
- **中间件层（L3）**：函数注册处是否挂载：
  - `router.Use(AuthMiddleware)`
  - `router.Group("/api", authCheck)`
  - `.Before(validateOwnership)`
- **跨模块追踪（L4）**：
  - 追踪`GetUserByID()`等封装函数实现，检查内部是否校验
  - 检查ORM模型的Scope/Hook：`func (u *User) BeforeFind()`是否注入权限逻辑
  - 查找Context传递：`ctx.Value("user_id")`是否在数据层自动过滤

## Classify

**漏洞判定标准：**
- 可横向访问：请求参数中的ID可被任意修改且能获取他人数据
- 敏感数据泄露：返回包含姓名、手机、地址、财务等隐私字段
- 无任何校验：既无中间件拦截，也无业务层权限判断

**误报常见场景：**
- 公开资源：查询的是公开文章、商品详情等非敏感数据
- 前置拦截：虽然handler未检查，但全局中间件已校验token并过滤ID范围
- 只读投影：查询后仅返回公开字段（需检查ORM的Select/Omit是否排除敏感列）

**代码异味识别：**
- 防御不完整：有校验但可绕过（如仅校验ID格式、仅对部分路由生效）
- 依赖前端：后端未校验，期望前端不传他人ID
- 条件保护：仅在特定分支校验（如只在is_admin=false时检查）

## Low risk

**可降级为低风险的场景：**
- **数据脱敏充分**：返回已完全脱敏的用户数据（如昵称hash、头像URL）
- **影响范围受限**：
  - 仅泄露非敏感枚举值（如用户等级、公开标签）
  - 查询结果通过白名单字段过滤（确认未泄露敏感列）
- **外部依赖控制**：
  - 数据库层强制RLS策略（需确认Postgres Row-Level Security已启用）
  - API Gateway已实施统一鉴权（需审查网关配置覆盖完整性）
- **间接访问**：需配合其他高权限操作才能利用（如需先通过管理员API获取有效ID列表）
- **只读且无枚举**：ID为UUID且无遍历价值，泄露信息极少