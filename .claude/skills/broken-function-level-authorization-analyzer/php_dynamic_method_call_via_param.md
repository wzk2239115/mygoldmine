# PHP｜通过参数动态调用内部方法绕过权限

## Details

### 漏洞成因
一些 PHP 应用为了简化代码，会根据请求参数拼接方法名并通过 `call_user_func`, `call_user_func_array`, `invoke` 等方式调用控制器或服务方法。若调用前未校验权限，就可能被普通用户指定管理员方法，从而执行敏感操作。该模式常见于 AJAX “action” 端点、CMS 插件、RPC 控制器等。

### 代码示例

**易受攻击示例：**
```php
class AjaxController extends Controller
{
    protected $actions = [
        'updateProfile' => 'updateProfile',
        'resetUser' => 'resetUser', // 应仅管理员可用
    ];

    public function handle()
    {
        $action = $_POST['action'];
        if (!isset($this->actions[$action])) {
            abort(404);
        }
        return call_user_func([$this, $this->actions[$action]]);
    }
}
```

**安全示例：**
```php
public function handle()
{
    $action = $_POST['action'];
    if (!isset($this->actions[$action])) {
        abort(404);
    }
    $required = $this->getRequiredCapability($action);
    if (!Auth::user()->can($required)) {
        abort(403);
    }
    return call_user_func([$this, $this->actions[$action]]);
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `call_user_func`, `call_user_func_array`, `invoke`, `ActionMap`, `$_POST['action']`, `$_GET['method']`。

**定位步骤：**
1. 搜索动态方法调用或 `action` 参数；
2. 跳读（L2）确认调用前是否执行权限检查；
3. 检查映射表是否区分权限。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- 动作与权限映射；
- 白名单仅包含非敏感方法；
- 调用前使用 `Gate::authorize`、`$this->authorize`；
- 后端返回签名、token 校验。

**定位技巧：**
- 逐行读（L3）敏感方法实现（重置密码、修改角色）；
- 跨模块追踪（L4）其他接口是否共享该动态调用逻辑。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 动态动作调用前绑定权限 | **L0（快速跳过）** | 安全性好 |
| 少数动作缺少校验 | **L2（跳读）** | 需确认 |
| 完全根据参数执行方法 | **L3（逐行读）** | 高风险 |
| 动态调用可从多个入口触发 | **L4（跨模块追踪）** | 全链路审计 |

## Classify

### 研判标准

#### 确认漏洞
1. 参数控制方法执行；
2. 未做权限检查；
3. 普通用户可调用管理员方法。

#### 误报
1. 动作映射与权限绑定且调用时验证；
2. 方法仅执行无害操作；
3. 接口仅内部脚本使用并受其它控制。

#### 代码异味
1. 依赖客户端传入 `role`/`token` 但不验证；
2. 使用 `eval` 拼接方法；
3. 无审计日志记录动作执行。

## Low risk

### 低风险评级场景

#### 1. 动作仅影响非敏感配置
- **评估：** 可降级。

#### 2. 内部接口
- **评估：** 攻击面有限。

#### 3. 计划拆分并添加权限
- **评估：** 暂降级，跟踪执行。

#### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 非敏感 | 影响有限 | 低 |
| 内部 | 攻击面低 | 中 |
| 改造计划明确 | 可暂缓 | 低 |
