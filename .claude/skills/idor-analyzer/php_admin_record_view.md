# PHP后台管理页面记录访问IDOR

## Details

**代码示例：**
```php
// admin/record_view.php
$record_id = $_POST['id'];
$sql = "SELECT * FROM records WHERE id = " . $record_id;
$result = mysqli_query($conn, $sql);

// admin/record_update.php  
$record_id = $_POST['record_id'];
$data = $_POST['data'];
mysqli_query($conn, "UPDATE sensitive_records SET data='$data' WHERE id=$record_id");

// admin/delete_user.php
$user_id = $_GET['uid'];
$db->query("DELETE FROM users WHERE id = $user_id");
```

**快速定位核心操作（L1：关键词扫描）**
- 搜索：`$_POST['id']`、`$_GET['id']`、`$_REQUEST['id']`、`$_POST['record_id']`、`$_POST['user_id']`
- 定位SQL操作：`SELECT`、`UPDATE`、`DELETE`后紧跟`WHERE id =`
- 关注：`admin/`、`manage/`、`backend/`目录下的操作类文件
- 文件名模式：`*_view.php`、`*_edit.php`、`*_delete.php`、`*_detail.php`

**快速定位保护机制（L2：跳读）**
- 检查ID接收前是否有：`checkPermission()`、`verifyOwnership()`、`isAuthorized()`
- 查找：`$_SESSION['admin_id']`、`$_SESSION['role']`与记录所有者的对比逻辑
- SQL中是否关联用户：`AND user_id = $current_user` 或 `AND created_by = $admin_id`
- 查看是否调用ACL类：`ACL::check()`、`Permission::verify()`
- 若无上述机制，则存在垂直越权风险

**进阶审计（L3：逐行读）**
- 确认权限检查是在ID使用前还是使用后（时序问题）
- 检查是否存在条件绕过：`if($role == 'admin' || $role == 'superadmin')`但未检查记录归属
- 审查是否有部门/组织隔离：同为管理员但不应跨部门访问
- 关注批量操作：`foreach($_POST['ids'] as $id)`是否逐一验证

## Classify

**漏洞判定：**
- 管理员可通过修改ID参数访问或操作其职责范围外的记录（跨部门、跨层级）
- 存在权限检查，但仅验证"是否为管理员"，未验证"是否有权操作该记录"
- 记录的敏感度与管理员权限不匹配（普通管理员可删除超级管理员记录）

**误报判定：**
- 权限检查在框架层统一处理（需跨模块追踪确认L4）
- 该功能仅超级管理员可访问且业务需求允许访问所有记录
- 记录本身不包含敏感信息且仅用于统计展示

**代码异味：**
- 权限检查存在但逻辑复杂，难以确认覆盖所有路径
- 依赖前端传递的role参数而非服务端session
- 权限代码与业务代码耦合，不易审计

## Low Risk

**以下情况评为低风险：**
- 仅查看类操作（SELECT），无法修改或删除，且记录不含高敏感数据（如内部日志、非个人隐私）
- 受影响记录为同级管理员范围内的数据，无跨层级越权
- 需要同时满足其他复杂条件（如需要有效token、CSRF保护、IP白名单等）
- 影响范围仅限测试环境或演示账户
- 业务逻辑上记录本身设计为管理员间共享（如公共配置、系统参数）