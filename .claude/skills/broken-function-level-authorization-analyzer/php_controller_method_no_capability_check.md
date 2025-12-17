# PHP｜控制器方法缺少能力校验

## Details

### 漏洞成因
在 Laravel、Symfony、ThinkPHP 等框架中，常通过中间件或控制器基类进行登录检测。但若控制器方法内部未进一步校验能力（capability）或角色，普通用户即可调用本应仅管理员可访问的功能。问题常见于在路由层忘记添加 `can`/`authorize`，或控制器方法复用服务逻辑而未传入调用者信息。

### 代码示例

**易受攻击示例：**
```php
class AdminUserController extends Controller
{
    public function __construct()
    {
        $this->middleware('auth'); // 仅登录
    }

    public function forceDelete($id)
    {
        User::findOrFail($id)->forceDelete(); // 未检查权限
        return response()->noContent();
    }
}
```

**安全示例：**
```php
public function forceDelete($id)
{
    $this->authorize('forceDelete', User::class);
    User::findOrFail($id)->forceDelete();
    return response()->noContent();
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `middleware('auth')`, `authorize`, `Gate::allows`, `can`, `policy`, `@can`。

**定位步骤：**
1. 搜索敏感控制器（`Admin`, `Manage`, `Settings`）；
2. 跳读方法实现，确认是否调用授权 API；
3. 检查路由定义是否使用 `->middleware('can:...')`。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- Laravel Policy/Gate；
- Symfony `@IsGranted`、`$this->denyAccessUnlessGranted`；
- ThinkPHP RBAC 插件；
- Service 层再次校验能力。

**定位技巧：**
- 逐行读（L3）敏感操作（删除、导出、设置）；
- 跨模块追踪（L4）API、AJAX、CLI 是否复用同方法。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 控制器统一使用授权 API | **L0（快速跳过）** | 风险低 |
| 部分方法缺权 | **L2（跳读）** | 快速确认 |
| 全无能力校验 | **L3（逐行读）** | 高风险 |
| 多入口调用控制器 | **L4（跨模块追踪）** | 全链路排查 |

## Classify

### 研判标准

#### 确认漏洞
1. 方法缺少能力校验；
2. 普通用户可调用管理员功能；
3. 操作影响敏感资源。

#### 误报
1. 上层中间件阻止非授权访问；
2. 方法只读或提供公共信息；
3. 路由仅在测试环境启用。

#### 代码异味
1. 注释指出需添加政策但未实现；
2. 依赖请求参数 `role` 判断；
3. 将授权逻辑留给前端。

## Low risk

### 低风险评级场景

#### 1. 功能影响有限
- **评估：** 可标低风险。

#### 2. 内部运维接口
- **评估：** 攻击面小。

#### 3. 即将接入 Policy/Gate
- **评估：** 暂降级并跟踪。

#### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 影响有限 | 风险低 | 低 |
| 内网访问 | 攻击面低 | 中 |
| 改造计划明确 | 可暂缓 | 低 |
