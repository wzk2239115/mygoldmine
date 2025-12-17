# Go｜HTTP Handler 缺失操作级权限检查

## Details

### 漏洞成因
在 Go 中，常用中间件验证 token 或 session，随后将请求交给具体 handler。如果 handler 内未进一步检查当前用户是否有权限执行该操作（例如删除、导出、审批），就会导致普通用户越权调用。问题常见于使用 `net/http`、Gin、Echo 等框架时只实现身份验证中间件，未细化到操作级权限。

### 代码示例

**易受攻击示例：**
```go
func deleteUserHandler(w http.ResponseWriter, r *http.Request) {
    // authMiddleware 已验证用户登录，但未检查角色
    id := mux.Vars(r)["id"]
    if err := userService.Delete(r.Context(), id); err != nil {
        http.Error(w, err.Error(), http.StatusInternalServerError)
        return
    }
    w.WriteHeader(http.StatusNoContent)
}
```

**安全示例：**
```go
func deleteUserHandler(w http.ResponseWriter, r *http.Request) {
    principal := auth.GetPrincipal(r.Context())
    if !principal.HasPermission("user:delete") {
        http.Error(w, "forbidden", http.StatusForbidden)
        return
    }
    id := mux.Vars(r)["id"]
    if err := userService.Delete(r.Context(), id, principal); err != nil {
        http.Error(w, err.Error(), http.StatusInternalServerError)
        return
    }
    w.WriteHeader(http.StatusNoContent)
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `Delete`, `Approve`, `Export`, `POST`, `PUT`, `Admin`, `HasPermission`, `RequireRole`。

**定位步骤：**
1. 搜索敏感 handler（用户管理、配置、付款等）；
2. 跳读（L2）确认是否调用权限检查函数；
3. 检查 `context.Context` 是否包含 principal 但未使用。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- 中间件设置权限上下文 (`context.WithValue` + `principal`)， handler 使用；
- RBAC/ABAC 库（casbin、ladon、ory keto）；
- Service 层二次校验；
- API Gateway 执行细粒度授权。

**定位技巧：**
- 逐行读（L3）敏感 handler，确认 `principal` 是否被忽略；
- 跨模块追踪（L4）微服务间调用是否绕过授权。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| handler 调用权限模块 | **L0（快速跳过）** | 风险低 |
| 部分 handler 校验 | **L2（跳读）** | 确认遗漏 |
| 完全无权限检查 | **L3（逐行读）** | 高风险 |
| 多入口调用同一 handler | **L4（跨模块追踪）** | 全链路审计 |

## Classify

### 研判标准

#### 确认漏洞
1. handler 未验证操作权限；
2. 普通用户越权执行敏感操作；
3.影响核心业务或安全。

#### 误报
1. handler 被上层中间件统一做权限判断并且不可绕过；
2. handler 仅执行非敏感操作；
3. handler 不对外暴露，仅供内部管理服务。

#### 代码异味
1. handler 依赖 query/body 中的 `isAdmin` 字段判断；
2. 权限检查以注释形式写明但未实现；
3. 跨服务调用没有重复验证。

## Low risk

### 低风险评级场景

#### 1. 操作仅修改个人偏好
- **评估：** 可标低风险。

#### 2. 内网管理接口
- **评估：** 攻击面较小，但需加固。

#### 3. 已计划集成权限库
- **评估：** 暂降级，跟踪实施。

#### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 非敏感操作 | 影响有限 | 低 |
| 内部接口 | 攻击面低 | 中 |
| 改造计划明确 | 可暂缓 | 低 |
