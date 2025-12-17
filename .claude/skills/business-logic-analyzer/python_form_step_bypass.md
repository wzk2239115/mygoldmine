# Python - 多步骤表单流程跳步漏洞

## Details

**漏洞成因**：多步骤表单/流程中，后续步骤未验证前置步骤是否完成，仅依赖前端参数或可预测字段，导致可直接访问终点绕过中间验证。

**代码特征**：
```python
# 典型漏洞模式
@route('/step2', methods=['POST'])
def step2():
    # 危险：直接接收参数，未验证 step1 是否完成
    user_id = request.form.get('user_id')
    process_step2(user_id)

@route('/step3', methods=['POST']) 
def step3():
    # 危险：仅检查参数存在，未校验流程状态
    if request.form.get('agreement_id'):
        finalize_order(request.form.get('order_id'))
```

**快速定位核心操作**：
- 搜索关键词：`/step`, `@route.*step`, `wizard`, `process_step`, `current_step`, `next_step`
- 关注：多个连续路由处理器、参数名包含 `step/phase/stage` 的视图函数
- 追踪：订单创建、注册流程、审批流、支付流等多阶段业务

**快速定位保护机制**：
- 检查是否存在：`session['step']`、`session['flow_state']`、`redis.get(f'step:{user_id}')`
- 验证逻辑：`if current_step != expected_step`、`if not session.get('step1_completed')`
- 状态机实现：`FlowStateMachine`、`@require_step(1)`、装饰器校验

**审计等级**：**L3（逐行读）**  
需逐行确认每个 step 函数入口是否校验前置状态，重点看 session/数据库状态读取和对比逻辑。

---

## Classify

**确认为漏洞**：
- 后续步骤完全不检查前置步骤状态，直接接收参数执行敏感操作
- 仅校验参数格式，未绑定会话或数据库状态标记
- 可通过直接 POST `/stepN` 跳过 `/step1` 到 `/step(N-1)` 的必要验证（如协议同意、资质审核、支付验证）

**误报**：
- 每个 step 都通过 `session['completed_steps']` 或数据库字段严格校验前置完成情况
- 使用 token/nonce 机制，后续步骤需要前置步骤生成的不可预测令牌
- 前端分页纯展示，实际提交在最后一步统一校验所有字段

**代码异味**：
- 有状态校验但逻辑可绕过（如 `step > 0` 的弱判断）
- 部分关键步骤有保护，部分无保护
- 依赖可预测的自增 ID 或时间戳做流程控制

---

## Low risk

**以下情况降级为低风险**：

1. **内部管理流程**：仅管理员可访问的多步骤配置向导，已有角色权限保护
2. **无敏感操作**：跳过的步骤仅为信息收集或帮助引导，不涉及权限变更、资金操作、数据审批
3. **前置验证已充分**：虽可跳步，但最终提交时会完整校验所有必填字段和业务规则
4. **只读查询流程**：多步骤查询表单，跳步仅影响用户体验不影响数据安全
5. **已有补偿控制**：虽无步骤校验，但有事后审计日志、人工复核、异常检测等机制