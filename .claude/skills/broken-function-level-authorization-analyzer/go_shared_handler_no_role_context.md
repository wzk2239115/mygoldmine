# Go｜共享 Handler 未区分角色上下文

## Details

### 漏洞成因
Go 项目中经常复用 handler 或 service 逻辑处理多种角色请求，例如同一 `HandlerFunc` 同时支持普通用户与管理员。当代码未根据角色区分执行路径或校验权限时，普通用户可能通过特定参数触发管理员分支，实现越权。常见于多租户接口、GraphQL resolver、gRPC 服务共享实现。

### 代码示例

**易受攻击示例：**
```go
func profileHandler(w http.ResponseWriter, r *http.Request) {
    principal := auth.PrincipalFromContext(r.Context())
    action := r.URL.Query().Get("action")
    switch action {
    case "view":
        renderProfile(principal.ID)
    case "adminView":
        // 管理员才允许查看任意用户
        id := r.URL.Query().Get("id")
        renderProfile(id) // 未检查角色
    }
}
```

**安全示例：**
```go
func profileHandler(w http.ResponseWriter, r *http.Request) {
    principal := auth.PrincipalFromContext(r.Context())
    action := r.URL.Query().Get("action")
    switch action {
    case "view":
        renderProfile(principal.ID)
    case "adminView":
        if !principal.HasRole("admin") {
            http.Error(w, "forbidden", http.StatusForbidden)
            return
        }
        id := r.URL.Query().Get("id")
        renderProfile(id)
    }
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `switch action`, `role`, `tenant`, `admin`, `mode`, `Context()`。

**定位步骤：**
1. 找出处理多种角色或操作的 handler/service；
2. 跳读（L2）检查分支逻辑是否校验 `principal` 权限；
3. 确认是否存在“隐藏”参数控制管理员分支。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- 基于角色的分支提前返回；
- `principal.HasRole`、`policy.Enforce` 调用；
- 将管理员功能拆分为独立 handler；
- GraphQL/REST 层统一授权中间件。

**定位技巧：**
- 逐行读（L3）不同分支，确认高风险操作是否有校验；
- 跨模块追踪（L4）其他入口是否复用该 handler。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 分支前即校验角色 | **L0（快速跳过）** | 安全性好 |
| 少数分支缺少校验 | **L2（跳读）** | 需确认 |
| 完全依赖参数选择敏感分支 | **L3（逐行读）** | 高风险 |
| 多服务共享同一逻辑 | **L4（跨模块追踪）** | 全链路审计 |

## Classify

### 研判标准

#### 确认漏洞
1. 共享 handler/service 未区分角色；
2. 普通用户可通过参数访问管理员路径；
3. 操作影响敏感数据或权限。

#### 误报
1. 分支实际仅返回公共信息；
2. 外层路由将管理员路径隔离；
3. handler 仅内部调用，不对外暴露。

#### 代码异味
1. 使用查询参数/字段 `action` 控制敏感操作；
2. 将角色判断交由客户端；
3. 缺乏日志记录无法监控滥用。

## Low risk

### 低风险评级场景

#### 1. 敏感分支不会修改状态
- **评估：** 可标低风险。

#### 2. 内部工具接口
- **评估：** 攻击面小，但需说明约束。

#### 3. 正在拆分 handler
- **评估：** 暂降级，跟踪实施。

#### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 只读操作 | 影响有限 | 低 |
| 内部使用 | 攻击面低 | 中 |
| 改造计划明确 | 可暂缓 | 低 |
