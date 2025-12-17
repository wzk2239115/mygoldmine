# PHP 原生模型批量赋值漏洞

## Details

### 漏洞成因
在未使用框架的原生 PHP 项目中，开发者常将 `$_POST`、`$_REQUEST`、`json_decode` 的结果直接赋值给对象或使用 `foreach` 遍历赋值。如果缺乏字段白名单，攻击者可提交额外字段覆盖敏感属性（如 `role`, `status`, `is_admin`, `price`, `tenant_id`）。自定义 ORM、ActiveRecord 实现、或简单的 `hydrate` 函数若遍历键值对赋值，也会导致批量赋值漏洞。

### 代码示例

**易受攻击的代码：**
```php
class User {
    public $id;
    public $email;
    public $role;
    public $active;
}

function hydrateUser(User $user, array $data) {
    foreach ($data as $key => $value) {
        if (property_exists($user, $key)) {
            $user->$key = $value; // 未过滤 role
        }
    }
}

// Controller
$user = find_user($_POST['id']);
hydrateUser($user, $_POST); // POST 可包含 role=admin
save_user($user);
```

**另一个不安全示例（自定义 ORM）：**
```php
class BaseModel {
    protected $attributes = [];

    public function fill(array $data) {
        foreach ($data as $key => $value) {
            $this->attributes[$key] = $value; // 无白名单
        }
        return $this;
    }
}

// 使用
$order = (new Order())->fill($_POST); // 可修改 price、status
$order->save();
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- `foreach ($_POST as $key => $value)`、`foreach ($data as $key => $value)`
- 自定义函数 `hydrate`, `fill`, `assign`, `loadFromArray`
- `property_exists`, `isset($this->attributes[$key])`
- `$_POST`, `$_REQUEST`, `json_decode(file_get_contents('php://input'), true)`

**定位步骤：**
1. 搜索赋值函数并查看调用信息。
2. 检查对象属性是否包含敏感字段。
3. 跳读（L2）确认是否有字段白名单或权限检查。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **白名单数组：** `if (!in_array($key, self::$fillable)) continue;`
- **敏感字段过滤：** 手动 `unset($data['role'])` 等。
- **权限校验：** 更新前确认当前用户是否允许。
- **数据验证层：** 使用独立验证器仅返回合法字段。
- **DTO/映射类：** 输入 DTO 与模型分离。

**定位技巧：**
- 检查是否对嵌套数组执行递归赋值（可能覆盖关联对象）。
- 确认白名单/黑名单配置是否从外部文件加载，防止配置错误。
- 对 `json_decode` 返回值进行类型检查，防止覆盖为 `null`。

#### 审计等级标注

| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 手动指定白名单字段 | **L0（快速跳过）** | 风险低 |
| 部分字段过滤但黑名单维护 | **L2（跳读）** | 检查是否完整 |
| 遍历 `$_POST`/`json` 直接赋值 | **L3（逐行读）** | 高风险 |
| 自定义 ORM/ActiveRecord 广泛使用 | **L4（跨模块追踪）** | 需分析整个框架 |

## Classify

### 研判标准

#### 确认漏洞
需满足以下条件：
1. **批量赋值函数** 直接使用外部输入。
2. **缺乏字段白名单或敏感字段过滤**。
3. **导致敏感字段被覆盖**，产生越权或关键数据篡改。

#### 误报
可视为误报的情况：
1. 数据在进入赋值函数前已验证并剥离敏感字段。
2. 执行赋值前通过权限/业务规则重写敏感字段。
3. 接口仅在受信环境运行且有外部保障（签名、VPN）。

#### 代码异味
需关注的风险：
1. 使用黑名单过滤敏感字段，易遗漏新增属性。
2. `property_exists` + 动态属性写入，易影响继承层次。
3. 缺乏输入验证，导致类型转换问题。
4. 同一函数既处理用户输入又处理内部数据，逻辑混乱。

## Low risk

### 低风险评级场景

#### 1. 内部管理接口
- **场景：** 仅在受控后台使用。
- **风险评估：** 攻击面小，但需防凭证泄露。

#### 2. DTO 过滤后赋值
- **场景：** 先使用验证器返回 `filtered_data`，再赋值。
- **风险评估：** 风险较低，需确保验证器无绕过。

#### 3. 数据库/业务层约束
- **场景：** 更新后会强制校正敏感字段。
- **风险评估：** 降低危害，但仍需修复根因。

#### 4. 审计日志
- **场景：** 对敏感字段修改记录日志与告警。
- **风险评估：** 有助于监控，但不替代修复。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 管理后台专用 | 攻击面有限 | 中 |
| DTO 白名单验证 | 技术防护完善 | 低 |
| 业务层重写敏感字段 | 降低影响 | 中 |
| 审计告警 | 快速发现问题 | 高（持续改进）|

