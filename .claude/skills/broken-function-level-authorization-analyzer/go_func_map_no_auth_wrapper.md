# Go｜函数映射缺少授权封装

## Details

### 漏洞成因
Go 中常见使用 `map[string]func` 或 `map[string]HandlerFunc` 动态注册操作。如果在注册时未对函数进行授权包装，而是直接根据请求参数调用，就会允许普通用户执行管理员函数。此模式常用于任务调度、Webhook action、后台脚本执行等场景。

### 代码示例

**易受攻击示例：**
```go
var actions = map[string]func(context.Context, *Request) error{
    "user.reset": resetUser,
    "system.restart": restartSystem, // 应仅管理员可用
}

func actionHandler(w http.ResponseWriter, r *http.Request) {
    action := r.URL.Query().Get("action")
    handler := actions[action]
    if handler == nil {
        http.NotFound(w, r)
        return
    }
    if err := handler(r.Context(), parseRequest(r)); err != nil {
        http.Error(w, err.Error(), http.StatusInternalServerError)
    }
}
```

**安全示例：**
```go
func wrapWithAuth(required Permission, handler ActionFunc) ActionFunc {
    return func(ctx context.Context, req *Request) error {
        principal := auth.PrincipalFromContext(ctx)
        if !principal.HasPermission(required) {
            return errors.New("forbidden")
        }
        return handler(ctx, req)
    }
}

func init() {
    actions["user.reset"] = wrapWithAuth(PermissionUserReset, resetUser)
    actions["system.restart"] = wrapWithAuth(PermissionSystemRestart, restartSystem)
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `map[string]func`, `actions`, `handlers`, `register`, `invoke`, `ActionFunc`。

**定位步骤：**
1. 搜索动作映射表及调用逻辑；
2. 跳读（L2）确认是否对 handler 进行权限包装；
3. 检查是否存在公共注册函数（`RegisterAction`）缺少授权参数。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- 注册函数要求传入 `required Permission`；
- handler 内部校验 `principal.HasRole`；
- 动作表分为公开和管理员两套；
- 调用链前置权限检查。

**定位技巧：**
- 逐行读（L3）敏感动作实现，确认是否直接执行；
- 跨模块追踪（L4）动作是否可由外部 API/消息触发。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 动作注册即绑定权限 | **L0（快速跳过）** | 安全性高 |
| 部分动作校验 | **L2（跳读）** | 快速确认遗漏 |
| 根据参数直接调用函数 | **L3（逐行读）** | 高风险 |
| 动作可由外部系统触发 | **L4（跨模块追踪）** | 必须全链路验证 |

## Classify

### 研判标准

#### 确认漏洞
1. 动作表直接指向函数，缺少权限包装；
2. 普通用户可执行管理员动作；
3. 操作危害大（重启系统、删除资源等）。

#### 误报
1. 注册函数已在内部强制权限；
2. 动作仅用于只读操作；
3. 动作调度入口仅开放给内部可信服务。

#### 代码异味
1. 依赖前端传入 `token` 或 `role` 字段判断；
2. 未记录动作执行日志；
3. 映射表与权限列表脱节。

## Low risk

### 低风险评级场景

#### 1. 动作仅触发非敏感任务
- **评估：** 可标低风险。

#### 2. 受控环境
- **评估：** 动作仅内部脚本调用，攻击面小。

#### 3. 计划统一动作注册流程
- **评估：** 暂降级，跟踪执行。

#### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 非敏感任务 | 影响有限 | 低 |
| 内部调用 | 攻击面低 | 中 |
| 改造计划明确 | 可暂缓 | 低 |
