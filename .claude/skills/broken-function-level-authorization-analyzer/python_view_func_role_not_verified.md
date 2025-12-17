# Python｜视图函数缺少角色校验

## Details

### 漏洞成因
在 Django、Flask、FastAPI 等框架中，开发者常使用登录装饰器或会话检测保证用户已认证，但若视图函数未进一步检查当前用户是否具备执行操作的角色或权限，就会导致普通用户执行管理员功能，如删除账户、导出数据、修改配置等。

### 代码示例

**易受攻击示例：**
```python
@app.route('/admin/delete_user', methods=['POST'])
@login_required
def delete_user():
    user_id = request.form['id']
    User.query.filter_by(id=user_id).delete()
    db.session.commit()
    return 'OK'
```

**安全示例：**
```python
@app.route('/admin/delete_user', methods=['POST'])
@login_required
@role_required('admin')
def delete_user():
    user_id = request.form['id']
    UserService.delete_user(user_id, current_user)
    return 'OK'
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `@app.route`, `@login_required`, `@permission_required`, `current_user`, `request.user`, `@router.post`。

**定位步骤：**
1. 搜索敏感路径（`/admin`, `/manage`, `/api/v1/users` 等）；
2. 跳读（L2）查看是否仅有登录检测，缺少角色判断；
3. 确认是否使用 `current_user.is_admin`, `permissions.has()` 等逻辑。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- 角色装饰器（`@role_required`, `@permission_required`）；
- 基于 `flask-principal`、`django-guardian`、`fastapi_permissions` 的授权；
- Service 层二次校验；
- API Gateway/JWT 内包含权限声明并后端验证。

**定位技巧：**
- 逐行读（L3）视图函数，确认是否依赖前端参数判断角色；
- 跨模块追踪（L4）REST、GraphQL、Admin 端是否共用相同视图。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 视图或装饰器统一校验权限 | **L0（快速跳过）** | 安全性高 |
| 某些视图缺少装饰器 | **L2（跳读）** | 快速确认遗漏 |
| 完全无角色校验 | **L3（逐行读）** | 高风险 |
| API 跨端共享但权限不统一 | **L4（跨模块追踪）** | 全链路审计 |

## Classify

### 研判标准

#### 确认漏洞
1. 视图仅校验登录；
2. 普通用户可调用接口执行管理员操作；
3. 操作影响敏感数据或安全策略。

#### 误报
1. 上层网关或 Service 内部执行了权限校验；
2. 视图仅用于公开或非敏感功能；
3. 部署环境限制访问（且有证据）。

#### 代码异味
1. 注释提示“TODO 权限”但未实现；
2. 依赖客户端传入角色字段；
3. 多模块共享 `@login_required` 装饰器却无权限分支。

## Low risk

### 低风险评级场景

#### 1. 仅修改非关键偏好
- **场景：** 功能只影响个人展示设置；
- **评估：** 可标低风险。

#### 2. 部署在受控网络
- **场景：** 内部管理平台仅内网访问；
- **评估：** 攻击面小。

#### 3. 即将引入权限框架
- **场景：** 已确定使用 `casbin`, `opa` 等；
- **评估：** 暂降级但需跟踪。

#### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 非敏感功能 | 影响有限 | 低 |
| 内网访问 | 攻击面低 | 中 |
| 改造计划明确 | 可暂缓 | 低 |
