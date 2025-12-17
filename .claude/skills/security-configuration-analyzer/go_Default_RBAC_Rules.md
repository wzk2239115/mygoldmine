# Go - Default RBAC Rules

## Details

### 代码示例

**场景1：Casbin 默认允许策略**
```go
enforcer, _ := casbin.NewEnforcer("model.conf", "policy.csv")
// 未配置默认拒绝，直接使用空策略或过于宽松的通配符
enforcer.AddPolicy("*", "*", "*")  // 任意用户访问任意资源
```

**场景2：Kubernetes RBAC 过度授权**
```go
rules := []rbacv1.PolicyRule{
    {
        Verbs:     []string{"*"},           // 全部动作
        APIGroups: []string{"*"},           // 全部API组
        Resources: []string{"*"},           // 全部资源
    },
}
```

**场景3：HTTP 中间件默认放行**
```go
func AuthMiddleware() gin.HandlerFunc {
    return func(c *gin.Context) {
        role := c.GetHeader("X-Role")
        // 缺少默认拒绝逻辑，空角色时放行
        if role == "admin" {
            c.Next()
            return
        }
        c.Next()  // 危险：默认继续执行
    }
}
```

**场景4：自定义 RBAC 缺少默认拒绝**
```go
type Authorizer struct {
    rules map[string][]string
}

func (a *Authorizer) Check(user, resource string) bool {
    if perms, ok := a.rules[user]; ok {
        return contains(perms, resource)
    }
    return true  // 危险：找不到规则时默认允许
}
```

### 快速定位核心操作的技巧

**（L1：关键词扫描）**
- 搜索策略关键词：`AddPolicy`、`PolicyRule`、`Allow`、`Deny`、`ACL`、`Permission`、`Role`
- Casbin 相关：`NewEnforcer`、`AddRoleForUser`、`AddPermissionForUser`
- K8s RBAC：`ClusterRole`、`RoleBinding`、`PolicyRule`、`rbacv1`

**（L2：跳读）**
- 重点关注初始化代码块：`init()`、`NewXxx()`、`Setup()`函数
- 扫描通配符使用：`*`、`**`、空字符串作为角色/资源
- 检查默认行为：`default:`、`else`分支、函数返回值（true/false）

**（L3：逐行读）**
- 验证策略加载顺序：先加载允许规则还是拒绝规则
- 检查角色继承链：`AddRoleForUser` 是否创建超级权限
- 确认空值处理：未认证用户、匿名访问、缺失角色的处理逻辑

### 快速定位保护机制的技巧

**（L1：关键词扫描）**
- 搜索保护关键词：`Enforce`、`Authorize`、`CheckPermission`、`ValidateRole`、`Forbidden`、`Unauthorized`
- 默认拒绝相关：`DefaultDeny`、`Whitelist`、`return false`

**（L2：跳读）**
- 查找显式拒绝逻辑：`return false`、`c.AbortWithStatus(403)`、`errors.New("forbidden")`
- 检查中间件链顺序：认证中间件是否在业务逻辑之前
- 确认错误处理：权限检查失败后是否终止请求

**（L3：逐行读）**
- 验证策略文件加载：`policy.csv`、`rbac_model.conf` 内容是否被校验
- 检查匹配函数：自定义 matcher 函数是否存在绕过风险
- 确认否定逻辑正确性：`!ok`、`!allowed` 的返回分支

**（L4：跨模块追踪）**
- 追踪策略定义源头：静态配置文件 vs 数据库动态加载
- 检查策略更新机制：是否存在竞态条件导致临时放行
- 验证角色分配过程：用户注册时是否被赋予默认高权限角色

## Classify

### 漏洞判定标准
- **真实漏洞**：默认策略允许未授权用户访问敏感资源；使用通配符 `*` 授予所有权限给普通角色；缺少显式拒绝逻辑导致空角色/未定义角色可访问；生产环境中 ClusterRole 使用 `verbs:["*"]`
  
### 误报场景
- 开发/测试环境的临时宽松配置（有环境变量或注释说明）
- 公开资源的故意放行（如健康检查端点、静态资源）
- 内部服务间通信的互信设计（已有网络隔离保护）

### 代码异味识别
- 策略定义与业务逻辑混杂在同一文件
- 硬编码角色名称而非使用常量/枚举
- 缺少策略变更审计日志
- RBAC 逻辑分散在多处无统一鉴权点

## Low Risk

### 低风险场景判定

**场景条件组合降级**
- 默认宽松 RBAC **且**已有上层网络隔离（VPC、防火墙仅允许内网访问）
- 使用通配符权限**但**仅限于只读操作（如 `verbs:["get", "list"]`）
- 开放匿名访问**且**资源本身为公开设计（文档、公告）

**防御深度存在**
- 存在二次鉴权：在业务逻辑层有额外的资源所有权校验
- 数据层面隔离：即使权限放行，数据查询强制 WHERE 租户ID过滤
- 操作审计完备：所有访问均记录到不可篡改日志系统

**影响范围受限**
- 仅影响非生产环境（明确配置隔离）
- 受影响服务为内部工具（无对外暴露）
- 默认角色仅能访问非敏感测试数据

**时间窗口因素**
- 宽松配置仅在初始化短暂生效，后续自动收紧
- 临时提权有过期机制且日志可追溯
