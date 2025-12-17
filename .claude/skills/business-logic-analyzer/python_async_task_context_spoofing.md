# Python 异步任务上下文伪造

## 漏洞成因
异步任务（Celery/RQ/APScheduler）或定时任务未校验触发上下文，仅依赖任务参数执行敏感操作，允许攻击者伪造任务调用或提升权限。

---

## Details

**审计等级**: L3（逐行读） → L4（跨模块追踪）

### 代码特征
```python
# 典型漏洞：Celery 任务直接信任参数
@celery.task
def transfer_funds(from_user_id, to_user_id, amount):
    # 无权限校验，直接执行转账
    from_account = Account.objects.get(id=from_user_id)
    to_account = Account.objects.get(id=to_user_id)
    from_account.balance -= amount
    to_account.balance += amount
    from_account.save()
    to_account.save()

# 典型漏洞：APScheduler 定时任务无来源校验
@scheduler.scheduled_job('cron', hour=0)
def grant_admin_role(user_id):
    User.objects.filter(id=user_id).update(role='admin')

# 可疑：RQ 任务暴露对外接口
@app.route('/api/task/execute')
def trigger_task():
    task_name = request.json['task']
    user_id = request.json['user_id']
    # 直接排队任务，无校验
    queue.enqueue(task_name, user_id)
```

### 快速定位核心操作
1. **关键装饰器**: `@celery.task` / `@shared_task` / `@task` / `@app.task` / `@scheduled_job` / `@cron`
2. **队列操作**: `apply_async()` / `delay()` / `enqueue()` / `add_job()` / `send_task()`
3. **敏感动作**: 资金变动、权限修改、数据删除、订单状态变更、积分操作
4. **搜索模式**: `grep -r "@task\|@celery\|apply_async\|enqueue" --include="*.py"`

### 快速定位保护机制
1. **校验上下文**: 任务内是否检查 `current_user` / `request.user` / 权限令牌
2. **签名验证**: 参数是否包含 `signature` / `token` / `hmac` 并进行校验
3. **白名单限制**: 是否限制可调用的任务名称或仅内部触发
4. **审计日志**: 任务执行前是否记录 `caller_id` / `trigger_source`

### 审计关注点（按优先级）
| 优先级 | 检查项 | 检查方法 |
|--------|--------|----------|
| P0 | 任务函数是否执行敏感操作 | 搜索 `update()` / `delete()` / `save()` / `balance` |
| P1 | 参数是否来自用户可控输入 | 回溯 `apply_async()`/`delay()` 调用处的参数来源 |
| P2 | 任务内是否存在权限校验 | 查找 `check_permission()` / `has_perm()` / `require_role()` |
| P3 | 任务触发点是否暴露给外部 | 检查 API 路由是否直接调用 `apply_async()` |

---

## Classify

### ✅ 确认为漏洞
- 任务执行敏感操作（转账/授权/删除）且参数直接来自用户输入，无二次校验
- 定时任务接受外部参数控制执行目标，无白名单限制
- 任务触发接口无认证或可被越权调用
- 任务内部使用全局管理员权限执行用户请求的操作

### ⚠️ 代码异味
- 任务参数包含 `user_id` 但仅用于日志记录，不影响业务逻辑
- 异步任务有权限校验但逻辑不完整（如仅检查是否登录，未检查资源归属）
- 任务可被触发但操作结果不敏感（如发送通知、统计计数）

### ❌ 误报
- 任务内部重新查询用户权限并校验（如 `if not user.has_perm('admin'): return`）
- 任务参数使用加密签名，且在任务内解密验证
- 任务仅能被内部服务调用（检查消息队列 ACL 或网络隔离）
- 定时任务不接受任何外部参数，执行固定逻辑

---

## Low risk

### 低风险场景（酌情降级）
1. **操作幂等且可逆**: 任务执行的操作可通过管理后台撤销，且有完整审计日志
2. **影响范围有限**: 任务仅能操作低敏感数据（如修改昵称、头像），不涉及资金/权限
3. **外部约束充足**: 
   - 消息队列仅内网可访问且有认证
   - 任务调用处已做充分校验，即使任务本身无校验
   - 云环境下使用 IAM 角色限制任务执行权限
4. **攻击成本高**: 需要同时满足多个前置条件（如已获取有效 session + 知道内部任务名称）

### 降级示例
```python
# 场景：异步发送邮件，无权限校验但影响有限
@celery.task
def send_notification(user_id, message):
    user = User.objects.get(id=user_id)
    send_email(user.email, message)  # 仅发送邮件，不修改数据
# 评级：Low（可被滥用发送垃圾邮件，但不影响数据完整性）
```

### 不可降级情况（必须 High/Critical）
- 涉及资金流转（转账/退款/充值）
- 权限提升（授予管理员/修改角色）
- 数据删除（订单/用户/核心业务数据）
- 状态篡改（订单状态/审核结果/KYC状态）