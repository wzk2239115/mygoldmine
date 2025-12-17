**Go HTTP处理器IDOR - 从URL参数直接查询数据库**

## Details

**典型代码示例：**
```go
func GetUserProfile(w http.ResponseWriter, r *http.Request) {
    userID := mux.Vars(r)["id"]  // 或 r.URL.Query().Get("id")
    var user User
    db.Where("id = ?", userID).First(&user)  // 直接查询
    json.NewEncoder(w).Encode(user)
}
```

**快速定位核心操作（L2:跳读）：**
- 路由定义处扫描路径变量：`/{id}`、`/{user_id}`、`/{order_id}`等
- 参数提取函数：`mux.Vars()`、`chi.URLParam()`、`r.URL.Query().Get()`、`r.FormValue()`
- 数据库查询入口：`db.Where()`、`db.First()`、`db.Find()`、`db.Raw()`、`Query()`、`QueryRow()`
- ORM链式调用：`gorm.DB.Where("id = ?", id)`、`xorm.ID(id).Get()`
- SQL拼接：`fmt.Sprintf("SELECT * FROM users WHERE id = %s", id)`

**快速定位保护机制（L3:逐行读/L4:跨模块追踪）：**
- **L3层面** - 查询前检查：
  - 会话验证：`session.Get("user_id")`、`claims["user_id"]`、`ctx.Value("user")`
  - 所有权比对：`if record.OwnerID != currentUserID`、`WHERE id = ? AND user_id = ?`
  - 中间件拦截：函数签名前的装饰器、`chi.Use(AuthMiddleware)`
- **L4层面** - 跨模块：
  - 权限服务调用：`authService.CanAccess(userID, resourceID)`、`policy.Allow()`
  - 数据层过滤：追踪到repository层是否内置租户/用户过滤
  - Context传递：检查`context.Context`是否携带权限上下文并被使用

## Classify

**漏洞确认：**
- 参数到查询间无任何过滤/验证逻辑
- 仅验证资源存在性，未校验访问者与资源关系
- 权限检查在查询后，且仅影响返回格式（如仍返回敏感字段）

**误报排除：**
- 查询条件包含隐式用户过滤（如`WHERE id = ? AND owner = ?`，owner来自可信会话）
- 资源本身为公开资源（需结合业务判断）
- 中间件已在路由层统一鉴权（需追踪确认有效性）

**代码异味：**
- 有权限检查但逻辑薄弱（如仅验证角色不验证所有权）
- 部分路由有保护部分路由缺失
- 权限逻辑分散，未统一至middleware或service层

## Low risk

**以下情况降级为低风险：**
- 泄露资源为非敏感公开数据（如商品详情、公开文章）
- ID遍历有业务价值但不涉及隐私（如订单号仅泄露存在性）
- 数据已脱敏处理（如手机号打码、金额隐藏）
- 受业务场景限制（如仅内网访问、测试环境、已废弃端点）
- 操作为只读且数据时效性已过期
- 有频率限制机制防止批量爬取（需实测验证有效性）