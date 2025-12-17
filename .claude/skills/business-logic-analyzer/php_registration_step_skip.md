# PHP 注册/登录流程步骤跳过漏洞

## Details

### 漏洞成因
多步骤注册/登录/认证流程中缺乏步骤完成状态校验，用户可直接访问后续步骤URL绕过前置验证（邮箱验证、实名认证、安全问题等），直接完成注册或获取权限。

### 代码示例

```php
// 典型漏洞：步骤间无状态依赖校验
// step1.php - 填写基本信息
session_start();
$_SESSION['username'] = $_POST['username'];
header("Location: step2.php");  // 仅存储数据，未标记步骤完成

// step2.php - 邮箱验证（可直接访问）
session_start();
// 危险：未检查 step1 是否完成
$_SESSION['email_verified'] = true;
header("Location: step3.php");

// step3.php - 完成注册（可直接访问）
session_start();
// 危险：未验证前置步骤，直接创建账户
createAccount($_SESSION['username'], $_SESSION['email']);
```

```php
// 不安全的步骤控制：仅依赖前端跳转
class RegisterController {
    public function step2() {
        // 缺失：未检查 $_SESSION['step1_completed']
        if ($_POST['email']) {
            sendVerifyEmail($_POST['email']);
        }
    }
    
    public function step3() {
        // 危险：仅检查字段存在，不验证流程完整性
        if (isset($_SESSION['username'])) {
            $this->finalizeRegistration();
        }
    }
}
```

```php
// 弱校验：步骤标记可被篡改
// step1.php
$_SESSION['current_step'] = 2;  // 客户端可修改 session 值
// step2.php
if ($_SESSION['current_step'] >= 2) {  // 仅递增检查，无完成性校验
    // 允许访问
}
```

### 快速定位核心操作
- **关键词扫描**：`step`, `register`, `signup`, `wizard`, `verify`, `activate`, `complete`
- **URL模式**：`/register/step[1-9]`, `/signup?step=`, `/verify`, `/complete`
- **Session关键字**：`$_SESSION['step']`, `$_SESSION['*_verified']`, `$_SESSION['progress']`
- **高危结构**：
  - 多个独立的 `.php` 文件处理不同步骤
  - `header("Location: stepX.php")` 重定向链
  - 关键操作（创建账户、授权、发放权益）在最后步骤
- **数据流追踪**：从第一步到最后步骤，检查每步入口是否校验前序依赖

### 快速定位保护机制
- **Session状态标记**：
  - `$_SESSION['step1_completed'] = true`
  - `$_SESSION['completed_steps'] = [1, 2, 3]`
  - `$_SESSION['wizard_state'] = 'step2'`
- **防跳步校验**：
  - `if ($_SESSION['current_step'] < 2) { die('Invalid access'); }`
  - `if (!isset($_SESSION['email_verified'])) { redirect('step1.php'); }`
  - 白名单路由守卫：`RequireStep(['step1_done', 'step2_done'])`
- **Token/签名验证**：
  - `$_SESSION['step_token']` 哈希绑定已完成步骤
  - `verifyStepSequence($expectedSteps, $currentStep)`
- **数据库状态表**：
  - `user_registration_progress` 表记录步骤完成状态
  - 原子性 CAS 更新：`UPDATE ... WHERE step=1 AND completed=1`

### 审计等级判定

| 等级 | 场景 | 审计策略 |
|------|------|----------|
| **L0** | 单页面注册，无多步骤流程 | 跳过 |
| **L1** | 每步明确检查 `$_SESSION['stepX_completed']` 且有跳转拦截 | 关键词确认校验覆盖所有步骤入口 |
| **L2** | 有步骤检查但逻辑简单（如仅递增 `current_step`） | 跳读验证是否可通过修改 session 绕过 |
| **L3** | Session 校验与业务逻辑混合，或依赖前端参数 | 逐行追踪每步入口的完整性校验和异常处理 |
| **L4** | 跨服务/跨域步骤、前后端分离、涉及第三方验证 | 跨模块追踪 token 传递、API 鉴权、状态同步 |

---

## Classify

### 确认漏洞
1. **直接访问后续步骤成功**：
   - 未登录或仅完成第一步即可访问 `/step3.php` 等后续页面
   - 直接请求最终步骤可完成注册/激活账户
2. **无前置步骤校验**：
   - 后续步骤入口无 `$_SESSION` 状态检查
   - 缺少 `redirect()` 拦截或步骤完成标记
3. **Session 可伪造**：
   - 仅检查 `$_SESSION['current_step']` 数值，可手动修改
   - 步骤标记无签名/加密保护
4. **业务影响**：
   - 绕过邮箱/手机验证获取账户
   - 跳过实名认证获取特权
   - 绕过安全问题设置完成密码重置

**典型漏洞特征**：
- 每步独立 PHP 文件，无统一路由守卫
- 仅在前端 JS 控制步骤跳转，后端无校验
- 关键步骤（创建账户、授权）未检查 `email_verified` 等前置条件
- `header("Location: ...")` 前未调用 `exit()`，可继续执行后续代码
- Session 固定 ID 未在步骤间刷新

### 误报排除
- ✗ 每步入口明确检查前序步骤完成标记：`if (!$_SESSION['step1_done']) { exit; }`
- ✗ 使用流程引擎/状态机（如 Symfony Workflow）且配置严格转换规则
- ✗ 步骤 Token 基于已完成步骤哈希生成，篡改即失效
- ✗ 后续步骤需数据库记录 `progress_status` 且有唯一性约束
- ✗ 仅后台管理员可跨步操作（需确认鉴权严格）

### 代码异味（需进一步验证）
- △ 步骤检查存在但可通过清空/伪造 Cookie 绕过 Session
- △ 仅验证 `isset($_SESSION['username'])` 而非步骤完成标记
- △ 前端禁用按钮/隐藏链接但后端无强制拦截
- △ 步骤回退逻辑允许重置已完成标记
- △ Session 存储在客户端（JWT 无签名或可篡改）

---

## Low Risk

### 给予低风险评级的场景

1. **非敏感流程**
   - 仅影响用户体验优化流程（个性化推荐、皮肤选择）
   - 跳过的步骤不涉及认证、授权、资金、敏感信息

2. **有二次校验机制**
   - 最终步骤调用独立服务验证邮箱/手机真实性
   - 账户创建后需管理员审核才能激活
   - 关键操作（提现、修改权限）有额外验证码确认

3. **影响范围受限**
   - 测试/演示环境的注册流程
   - 内部员工注册系统（需确认无外网暴露）
   - 跳过步骤仅填充默认值，不授予额外权限

4. **攻击门槛高**
   - 需已持有有效邮箱/手机号才能最终激活（后台异步验证）
   - 步骤跳过后账户处于"待完善"状态，核心功能不可用
   - 需配合其他漏洞（Session 固定、CSRF）才能利用

5. **有补偿控制**
   - 后台监控异常注册行为（跳步、极短时间完成）
   - 定时任务清理未完成验证的账户
   - 风控系统阻断批量注册 IP

6. **业务逻辑天然防护**
   - 注册完成后需充值/绑定设备才能使用（自然门槛）
   - 每个步骤产生的数据有强依赖关系（如缺少邮箱无法接收激活链接）

**评级建议**：即便低风险，应在报告中注明缺陷并建议加固，防止批量注册、自动化攻击或配合其他漏洞利用。