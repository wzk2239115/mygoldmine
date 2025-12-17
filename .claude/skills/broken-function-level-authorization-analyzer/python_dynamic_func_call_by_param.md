# Python｜基于参数的动态函数调用绕过权限

## Details

### 漏洞成因
某些后端为了实现“动作驱动”或通用调度，会通过请求参数指定要执行的函数或方法。如果在调用前未校验该动作是否允许当前用户执行，就可能被普通用户构造请求调用管理员函数。此类实现常见于 Flask `getattr` 调用、Django `import_string` 动态加载、FastAPI 使用映射表执行不同操作。

### 代码示例

**易受攻击示例：**
```python
ADMIN_ACTIONS = {
    'reset': reset_password,
    'promote': promote_user,
}

@app.post('/action')
@login_required
def do_action():
    action = request.json['action']
    func = ADMIN_ACTIONS.get(action)
    if not func:
        abort(404)
    return func(request.json)   # 未校验角色
```

**安全示例：**
```python
@app.post('/action')
@login_required
def do_action():
    action = request.json['action']
    func = ADMIN_ACTIONS.get(action)
    if not func:
        abort(404)
    if not current_user.has_permission(action):
        abort(403)
    return func(request.json, current_user)
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `getattr`, `globals()`, `locals()`, `import_string`, `ACTION_MAP`, `dispatch`, `func =`, `callable`。

**定位步骤：**
1. 搜索动态函数调用或映射表；
2. 跳读（L2）查看是否根据用户角色过滤动作；
3. 确认函数调用前是否有白名单与权限校验。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- 动作与权限映射表；
- `current_user.has_permission`、`policy.enforce` 等调用；
- 仅允许管理员访问该路由；
-使用签名令牌或 CSRF 保护。

**定位技巧：**
- 逐行读（L3）每个动作的实现，确认是否检查调用者身份；
- 跨模块追踪（L4）动态路由是否被外部接口或脚本使用。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 动作执行前强制权限校验 | **L0（快速跳过）** | 安全性高 |
| 仅部分动作校验 | **L2（跳读）** | 快速确认遗漏 |
| 动作完全根据参数调用 | **L3（逐行读）** | 高风险 |
| 动作可通过多个入口触发 | **L4（跨模块追踪）** | 全链路排查 |

## Classify

### 研判标准

#### 确认漏洞
1. 请求参数控制动作或函数；
2. 未校验用户是否具备该动作权限；
3. 可绕过限制执行管理员操作。

#### 误报
1. 动作映射表与权限绑定且调用前验证；
2. 路由仅对管理员开放；
3. 动作只是查看公共信息。

#### 代码异味
1. 动作列表混合管理员和普通操作；
2. 使用 `eval` 或 `exec` 动态执行；
3. 缺乏日志记录，难以追踪滥用。

## Low risk

### 低风险评级场景

#### 1. 动作仅影响个人偏好
- **场景：** 即使被滥用，影响有限；
- **评估：** 可标低风险。

#### 2. 内部自动化端点
- **场景：** 仅供后端服务调用，部署在受控网络；
- **评估：** 攻击面小，但仍需注意。

#### 3. 计划拆分动作到独立 API
- **场景：** 即将改造为显式接口并加权限；
- **评估：** 暂记低风险并跟踪。

#### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 非敏感动作 | 影响有限 | 低 |
| 内部网络 | 攻击面低 | 中 |
| 改造计划明确 | 可暂缓 | 低 |
