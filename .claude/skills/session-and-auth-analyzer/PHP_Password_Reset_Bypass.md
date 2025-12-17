# PHP_Password_Reset_Bypass

**漏洞类型**: PHP 密码重置功能中，重置流程可被绕过，无需验证用户身份或完整流程，攻击者可重置任意用户密码

---

## Details

### 代码示例

**易受攻击的代码模式**:
```php
// 示例1: 未验证用户身份直接重置
function resetPassword() {
    $userId = $_POST['user_id'];
    $newPassword = $_POST['new_password'];
    // 未验证此用户是否是当前用户或有权重置
    $user = User::find($userId);
    $user->password = Hash::make($newPassword);
    $user->save();
}

// 示例2: Token 验证可被跳过
function processReset() {
    if (isset($_POST['token'])) {
        validateToken($_POST['token']);
    }
    // token 可选，可不提供直接重置
    resetUserPassword($_POST['user_id']);
}

// 示例3: Email 作为唯一验证，可被伪造
function resetByEmail() {
    $email = $_POST['email'];
    // 仅检查 email 存在，未验证用户身份
    User::whereEmail($email)->update(['password' => $_POST['new_password']]);
}

// 示例4: 重置流程步骤可跳过
function step2_resetPassword() {
    // 应该是第二步，但可直接访问
    if (!isset($_SESSION['step1_completed'])) {
        $_SESSION['step1_completed'] = true; // 自己设置
    }
    // 重置密码...
}

// 示例5: Token 验证逻辑缺陷
function verifyResetToken($token) {
    $reset = PasswordReset::where('token', $token)->first();
    return $reset != null; // 仅检查存在，不验证有效性
}

// 示例6: 登录状态下可重置他人密码
@auth
public function resetPassword(Request $request) {
    // 仅检查是否登录，未检查是否是本人或有权限
    User::find($request->user_id)->update(['password' => ...]);
}

// 示例7: POST/GET 参数注入
function getResetForm() {
    $userId = $_GET['user_id'] ?? $_POST['user_id'];
    return renderResetForm($userId);
}
```

### 快速定位核心操作 **[L1-L2]**

**L1 关键词扫描**:
- 重置函数: `resetPassword()`, `updatePassword()`, `changePassword()`, `forgot_password()`
- 身份验证缺失: 无 `Auth::check()`, 无 `user_id` 验证
- Token 验证: `validateToken()`, `verifyToken()`, 但验证逻辑不完整
- 参数来源: `$_POST['user_id']`, `$_GET['user_id']`, 直接来自用户
- 缺失检查: 无权限验证, 无 CSRF 防护

**L2 跳读定位**:
- 重置路由: `/forgot-password`, `/reset-password`, `/password-reset/:token`
- 完整流程: 请求 -> token 生成 -> 邮件发送 -> 验证 -> 重置
- 检查是否所有步骤都必须按顺序执行
- 验证权限: 用户只能重置自己的密码

### 快速定位保护机制 **[L2-L4]**

**L2 跳读检测**:
- 权限检查: `$request->user()->id == $userId`, `Auth::user()->id`
- Token 验证: `verify()`, `check()`, 验证令牌有效性
- CSRF 保护: `csrf_token()`, `VerifyCsrfToken` 中间件
- Session 检查: 步骤状态验证

**L3 逐行分析**:
- 身份验证:
  - 是否检查当前用户是否登录
  - 是否验证用户只能重置自己的密码
  - 重置他人密码时是否需要额外权限 (admin)
  - 是否检查 `Auth::user()->id == $userId`
- Token 验证:
  - Token 是否有效期检查
  - Token 是否与用户关联
  - Token 是否已使用过
  - 验证失败时是否返回通用错误信息
- 流程完整性:
  - 是否验证了邮件验证步骤
  - 是否记录了重置状态，防止步骤跳过
  - 是否有确认邮件发送之前的步骤
- 密码验证:
  - 新密码是否强度检查
  - 新密码是否与旧密码不同
  - 是否要求再次输入新密码

**L4 跨模块追踪**:
- 追踪整个重置流程的实现
- 检查中间件中的权限检查
- 验证邮件模块的 token 生成
- 检查是否有 API 端点与 web 端点的一致性
- 审查日志和审计记录

---

## Classify

### 漏洞判定标准

**确认为漏洞**:
- 重置密码时未验证用户身份，可重置任意用户
- Token 验证可被跳过或逻辑不完整
- 仅通过邮箱地址验证，无 token
- 步骤可被跳过，不必完成整个流程
- 登录状态下可重置他人密码无需额外验证

**误报判定**:
- 必须是该用户本人或有特殊权限才能重置
- Token 验证严格且无法绕过
- 验证失败返回通用错误，不泄露用户存在信息
- 重置后自动登出并要求重新登录
- 有完整的审计日志

**代码异味**:
- 有权限检查但在某些代码路径被跳过
- Token 验证在条件语句中 (可被绕过)
- 有注释提到"应该验证用户"但代码未实现
- 参数来自用户输入未验证

---

## Low risk

### 低风险场景

**多因素验证**:
- 重置密码需要额外验证 (OTP, 安全问题等)
- 邮件发送后还需要用户确认

**用户通知**:
- 密码重置时立即通知用户
- 用户可在通知中快速撤销重置

**监控**:
- 实时检测异常密码重置
- 检测到多用户重置时告警
- 记录所有重置操作
