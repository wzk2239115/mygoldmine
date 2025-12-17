# PHP｜管理员 AJAX 接口缺少角色复核

## Details

### 漏洞成因
后台界面常通过 AJAX 调用执行敏感操作，如果服务器端仅凭登录态或一次性验证后便允许执行所有 AJAX 请求，未在每个请求上复核用户角色，就会被普通用户伪造请求越权操作。典型场景：CMS 后台公共入口 `admin-ajax.php`、Drupal/WordPress 等插件接口未验证 `current_user_can()`。

### 代码示例

**易受攻击示例：**
```php
// admin_ajax.php
require_login();
$action = $_POST['action'];
if ($action === 'export_users') {
    export_users(); // 未验证当前用户是否为管理员
}
```

**安全示例：**
```php
require_login();
$action = $_POST['action'];
if ($action === 'export_users') {
    if (!Auth::user()->can('user:export')) {
        http_response_code(403);
        exit('forbidden');
    }
    export_users();
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `admin-ajax`, `ajax_action`, `action=`, `do_action`, `wp_ajax`, `ajax.php`。

**定位步骤：**
1. 搜索 AJAX 入口文件或控制器；
2. 跳读（L2）检查是否调用权限函数（`current_user_can`, `Gate::authorize`）；
3. 确认每个 action 都执行校验，而非仅初始化时验证一次。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- 每个 action 调用能力函数；
- CSRF token 搭配权限检查；
- 动作白名单按角色区分；
- 服务器端 session 中缓存权限但仍在请求时校验。

**定位技巧：**
- 逐行读（L3）高风险 action（导出、删除、变更权限）；
- 跨模块追踪（L4）前端 JS 是否可被普通用户访问并调用这些接口。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 每个 AJAX action 复核权限 | **L0（快速跳过）** | 安全性高 |
| 少数 action 遗漏 | **L2（跳读）** | 需确认 |
| 完全无权限复核 | **L3（逐行读）** | 高风险 |
| AJAX 接口对外暴露 | **L4（跨模块追踪）** | 全链路审计 |

## Classify

### 研判标准

#### 确认漏洞
1. AJAX action 未检查角色；
2. 普通用户可伪造请求执行管理员操作；
3. 行为影响敏感数据或配置。

#### 误报
1. action 仅返回公共数据；
2. action 仅在 Admin session 内部可调用且服务器端再次校验；
3. action 已被废弃，不再部署。

#### 代码异味
1. 只在前端 JS 判断角色；
2. 使用 nonce 但不校验能力；
3. 动作列表生硬拼接字符串，无安全封装。

## Low risk

### 低风险评级场景

#### 1. 功能仅影响显示或缓存
- **评估：** 可标低风险。

#### 2. 内部管理后台
- **评估：** 攻击面有限，但需记录。

#### 3. 计划迁移至 REST API 权限框架
- **评估：** 暂降级，跟踪执行。

#### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 非敏感操作 | 影响有限 | 低 |
| 内部后台 | 攻击面低 | 中 |
| 改造计划明确 | 可暂缓 | 低 |
