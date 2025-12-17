# PHP Laravel 批量赋值漏洞

## Details

### 漏洞成因
Laravel 提供 `Model::create`, `update`, `fill`, `updateOrCreate` 等 API，可将数组映射为模型属性。如果模型未正确设置 `$fillable` 或 `$guarded`，攻击者可在表单中附加敏感字段（如 `role`, `is_admin`, `status`, `balance`, `tenant_id`）覆盖数据库值。结合 `Request::all()`、`$request->input()` 直接传入模型的情况尤为常见。

### 代码示例

**易受攻击的代码：**
```php
class User extends Model {
    protected $fillable = ['name', 'email', 'password', 'role']; // role 不应在 fillable 中
}

Route::post('/users', function (Request $request) {
    // POST 数据可包含 role=admin
    return User::create($request->all());
});
```

**另一个不安全示例（$guarded = []）：**
```php
class Order extends Model {
    protected $guarded = []; // 允许所有字段批量赋值
}

Route::patch('/orders/{order}', function (Order $order, Request $request) {
    $order->update($request->all()); // 可修改 status、tenant_id
    return $order;
});
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- `protected $fillable`, `protected $guarded`, `$guarded = []`
- 控制器代码中的 `Model::create`, `$model->update`, `$model->fill`
- `Request::all()`, `input()`, `only()`, `validated()`
- FormRequest/Resource Controller 更新逻辑

**定位步骤：**
1. 检查模型定义的 `$fillable`/`$guarded`。
2. 搜索 `create/update/fill` 调用，确认传入数据来源。
3. 跳读（L2）确认是否使用 `$request->only()` 或 FormRequest 白名单。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **白名单：** 使用 `$fillable` 仅列出安全字段。
- **黑名单（谨慎）：** `$guarded` 排除敏感字段。
- **FormRequest 验证：** `rules()` 限制提交字段。
- **资源转换：** DTO/Resource 过滤字段。
- **权限策略：** `Policy`/`Gate` 检查调用者权限。

**定位技巧：**
- 确认 FormRequest `validated()` 是否返回安全字段。
- 检查模型是否使用 `hidden` 属性隐藏敏感字段（仅影响序列化，不影响写入）。
- 对 `updateOrCreate`, `firstOrCreate` 等复合方法同样审计。

#### 审计等级标注

| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 使用 FormRequest + `$fillable` 白名单 | **L0（快速跳过）** | 风险低 |
| `$guarded` 设置但确保敏感字段排除 | **L2（跳读）** | 检查覆盖范围 |
| `$guarded = []` 或 `$request->all()` 直接更新 | **L3（逐行读）** | 高风险 |
| 多租户/批量导入操作 | **L4（跨模块追踪）** | 需确认租户隔离 |

## Classify

### 研判标准

#### 确认漏洞
需满足以下条件：
1. **模型允许批量赋值** 所有字段或包含敏感字段。
2. **用户可提交 JSON/表单** 添加敏感字段。
3. **导致敏感字段被覆盖**（权限提升、状态篡改等）。

#### 误报
可视为误报的情形：
1. **使用 `$fillable` 严格限制字段**。
2. **控制器 `only()` 选取字段** 或 `validated()` 返回值已过滤。
3. **接口仅供内部受信调用** 且有额外校验。

#### 代码异味
需关注的风险：
1. **`$guarded = []`** 在多人协作中易被忽视。
2. **FormRequest 未覆盖所有路由**，存在旁路。
3. **使用 `merge()`/`replace()` 合并请求数据**。
4. **绕过策略：** 通过 API Resource/Job 更新时未复用验证逻辑。

## Low risk

### 低风险评级场景

#### 1. 受控后台接口
- **场景：** 仅管理员可调用且有 MFA。
- **风险评估：** 攻击面有限，但需防账号泄露。

#### 2. DTO 层过滤
- **场景：** 使用 Service/DTO 手动赋值字段。
- **风险评估：** 风险较低，需保持维护。

#### 3. 数据库层限制
- **场景：** 设置数据库触发器阻止敏感列更新。
- **风险评估：** 降低危害，但不替代修复。

#### 4. 完整审计日志
- **场景：** 对敏感字段修改记录审计与告警。
- **风险评估：** 有助于发现异常，仍应修复根因。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 管理员专用接口 | 攻击面小 | 中 |
| `$fillable` 白名单 + 验证 | 技术防护完善 | 低 |
| 数据库触发器/约束 | 阻断敏感修改 | 中 |
| 审计告警 | 及时发现异常 | 高（持续改进）|

