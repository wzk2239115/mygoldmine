# Python_Password_Reset_No_Expiry

**漏洞类型**: Django/Flask 密码重置功能中，重置链接或令牌未设置过期时间，导致重置链接长期有效，攻击者可无限期利用

---

## Details

### 代码示例

**易受攻击的代码模式**:
```python
# 示例1: Django 密码重置链接未设置过期时间
from django.contrib.auth.views import PasswordResetView
class CustomPasswordResetView(PasswordResetView):
    template_name = 'password_reset.html'
    # 未设置 email_template_name 或 token_generator
    # 使用 Django 默认的 30 分钟过期时间，但代码中可能被覆盖为永不过期

# 示例2: 自定义重置令牌，无过期检查
from django.db import models
class PasswordResetToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    token = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # 缺少 expires_at 或 expiry_time 字段

def reset_password(request, token):
    try:
        reset_token = PasswordResetToken.objects.get(token=token)
        # 直接使用 token，无过期时间验证
        user = reset_token.user
        user.set_password(request.POST['password'])
        user.save()
    except PasswordResetToken.DoesNotExist:
        return HttpResponse('Invalid token')

# 示例3: Flask 密码重置无超时设置
from itsdangerous import URLSafeTimedSerializer
def generate_reset_token(email):
    serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])
    return serializer.dumps(email, salt='password-reset-salt')
    # 缺少 salt 或 max_age 参数

def verify_reset_token(token, max_age=None):
    serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])
    try:
        email = serializer.loads(token)  # 未传递 max_age
        return email
    except SignatureExpired:
        return None

# 示例4: 忘记设置重置链接有效期
reset_link = f"http://example.com/reset/{reset_token}"
# 发送 reset_link，但无过期时间检查

# 示例5: 检查过期时间但条件错误
def is_token_expired(created_at, expiry_hours=24):
    return (datetime.now() - created_at).seconds < expiry_hours * 3600  # 逻辑反向
```

### 快速定位核心操作 **[L1-L2]**

**L1 关键词扫描**:
- 密码重置功能: `PasswordResetView`, `PasswordResetTokenGenerator`, `reset_password()`, `verify_reset_token()`, `forgot_password()`
- 令牌生成: `secrets.token_urlsafe()`, `uuid.uuid4()`, `serializer.dumps()`, `URLSafeTimedSerializer`
- 令牌存储: `PasswordResetToken`, `reset_token`, `password_reset_token` 数据库表
- 令牌验证: `reset_token = PasswordResetToken.objects.get()`, `serializer.loads()`, `verify()`, `check_token()`
- 缺失的过期检查: 无 `expires_at`, `expiry_time`, `max_age`, `timeout`, `TTL` 字段或参数

**L2 跳读定位**:
- 密码重置路由: 搜索 `/forgot-password`, `/reset-password`, `/password-reset` 等端点
- 追踪令牌从生成到验证的全过程
- 关键检查点: 是否存在 `expires_at` 或过期时间字段
- 查看令牌验证时是否检查时间戳
- 检查密码重置邮件模板中链接是否包含过期提示

### 快速定位保护机制 **[L2-L4]**

**L2 跳读检测**:
- 过期字段存在: 模型中是否定义 `expires_at`, `expiry_time`, `created_at` 等时间字段
- 过期验证调用: `is_expired()`, `check_expiry()`, `token.expired`, `token.is_valid()` 等验证方法
- Django TokenGenerator 使用: `PasswordResetTokenGenerator.check_token()` 内置过期检查

**L3 逐行分析**:
- 过期时间字段设置:
  - 检查 `expires_at = models.DateTimeField()` 是否定义且有默认值
  - 查看过期时间计算方式: `expires_at = created_at + timedelta(hours/minutes)` 等
  - 确认过期时间长度是否合理 (建议不超过 24 小时)
- 过期检查逻辑:
  - `now() > expires_at` 或 `now() < expires_at` 判断是否正确
  - 是否同时检查了 `not reset_token.used` 防止重复使用
  - 时区处理是否正确 (UTC vs 本地时间)
- URLSafeTimedSerializer 的 `max_age` 参数:
  - `serializer.loads(token, max_age=3600)` 的秒数是否设置
  - 如果使用 `salt` 参数，是否与生成时保持一致
- 令牌使用标志:
  - 是否有 `used` 或 `used_at` 字段，防止令牌重复使用
  - 验证成功后是否设置 `used = True` 或删除令牌

**L4 跨模块追踪**:
- 追踪 Django 密码重置视图的完整流程，确认是否重写了 `token_generator`
- 检查是否有中间件或装饰器修改了令牌验证逻辑
- 验证密码重置邮件发送时是否传递了过期时间
- 检查前端 JavaScript 是否有额外的过期检查或倒计时逻辑
- 审查配置文件中关于令牌过期的设置 (如 `PASSWORD_RESET_TIMEOUT`)

---

## Classify

### 漏洞判定标准

**确认为漏洞**:
- 密码重置数据模型中完全缺少过期时间字段 (`expires_at`, `expiry_time` 等)
- 令牌验证时未检查时间戳或过期标志
- 重置链接在生成后可无限期使用，无时间限制
- 即使有过期字段，验证逻辑也错误或被禁用
- URLSafeTimedSerializer 使用时未设置 `max_age` 参数
- 密码重置后未标记令牌为已使用，可重复利用
- 没有机制清理过期的重置令牌，导致数据库积累

**误报判定**:
- Django 内置 `PasswordResetTokenGenerator` 使用，框架自动处理过期检查 (默认 12 小时，可配置)
- 密码重置令牌有明确的过期时间字段，且验证逻辑正确
- 使用 URLSafeTimedSerializer 且正确设置了 `max_age` 参数
- 令牌验证后被删除或标记为已使用，无法重复利用
- 应用有定期清理过期令牌的任务
- 密码重置过程中有额外的身份验证 (如邮箱确认码、安全问题验证)

**代码异味**:
- 存在 `expires_at` 字段但验证时未使用
- 过期时间过长 (超过 72 小时) 或无明确定义
- 使用 `secrets.token_urlsafe()` 生成令牌但缺少时间戳机制
- 令牌验证代码中存在 try-catch 但捕获异常时未正确处理过期情况
- 缺少令牌使用日志或审计记录

---

## Low risk

### 低风险场景

**访问限制**:
- 密码重置功能仅供已认证的用户使用，通过邮件链接访问时需额外验证
- 重置链接中包含用户身份验证信息 (如数字签名、HMAC)，无法被无权限用户使用
- 需要在重置密码前进行电话或二次邮件确认

**补偿控制**:
- 密码重置后自动登出所有现有会话，强制用户重新登录
- 应用中敏感操作 (如修改邮箱、添加支付方式) 需进行额外身份验证
- 有详细的账户登录历史，用户可及时发现异常登录
- 重置密码后在 IP 或地理位置异常时发送通知

**检测与监控**:
- 实时监控密码重置请求频率，异常时进行限流或额外验证
- 记录所有密码重置操作的时间、IP 和邮箱，可供用户查询
- 检测到多个账户同时重置密码时，可能为批量攻击，进行告警
- 有机制防止用户枚举 (如邮箱是否存在不显示区别提示)

**用户提示**:
- 发送密码重置邮件时明确提示用户有效期 (如 "此链接 24 小时内有效")
- 在密码重置页面显示过期倒计时
- 链接过期后显示清晰的错误提示，并允许用户重新请求重置
