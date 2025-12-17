# Django 登录视图缺乏速率限制

## Details

### 核心代码示例

Django 登录视图在缺乏速率限制中间件时的典型漏洞形式：

```python
# views.py - 不安全的登录视图
from django.contrib.auth import authenticate, login
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse

@require_http_methods(["POST"])
def login_view(request):
    username = request.POST.get('username')
    password = request.POST.get('password')

    user = authenticate(request, username=username, password=password)
    if user is not None:
        login(request, user)
        return JsonResponse({'status': 'success'})
    else:
        return JsonResponse({'status': 'failed'}, status=401)
```

### 核心操作定位技巧（L1: 关键词扫描）

- 搜索关键函数：`authenticate()`、`login()`、`LoginView`、`AuthenticationForm`
- 关键路由模式：`/login`、`/auth`、`/api/login`、`/api/auth`
- 搜索视图装饰器：`@require_http_methods(["POST"])`、`@csrf_exempt`
- 查看 URLconf 中的认证相关路由配置

### 保护机制定位技巧（L2: 跳读）

关键位置检查以下保护机制是否存在：

1. **中间件层面**（L2: 跳读）
   - `django-ratelimit` 中间件或装饰器使用
   - 自定义速率限制中间件（继承 `MiddlewareMixin`）
   - 检查 `MIDDLEWARE` 配置中是否有速率限制组件

2. **视图层面**（L2: 跳读）
   - 装饰器保护：`@ratelimit(key='ip', rate='5/m')`
   - 类视图中的 `dispatch()` 方法是否有速率检查
   - 检查 `request.META['REMOTE_ADDR']` 或 `request.META['HTTP_X_FORWARDED_FOR']` 的使用

3. **缓存层面**（L3: 逐行读）
   - `cache.get()`/`cache.set()` 的使用（Redis、Memcached）
   - 登录失败计数器的实现逻辑
   - IP/用户名维度的失败次数追踪

4. **数据库层面**（L3: 逐行读）
   - `LoginAttempt` 或 `AuditLog` 模型是否存在
   - 账户锁定机制：`is_active`、`locked_until` 字段
   - 登录失败历史的记录与查询逻辑

## Classify

### 漏洞识别标准

**判定为漏洞的条件：**
1. 登录视图/接口未配置任何形式的速率限制
2. 无IP级别或用户名级别的失败尝试计数
3. 无账户暂时锁定或冷却机制
4. 中间件配置中完全缺少速率限制组件
5. 登录接口可被公开访问，无访问控制

**判定为误报的条件：**
1. 存在有效的速率限制装饰器或中间件（如 `django-ratelimit`）
2. 实现了自定义的失败计数与账户锁定机制
3. 前置认证网关或WAF已配置速率限制规则
4. 登录接口配置了CAPTCHA或二次验证机制

**判定为代码异味的条件：**
1. 速率限制配置存在但阈值过高（如 100 次/分钟）
2. 锁定时间过短（< 15分钟）
3. 错误消息过于详细泄露用户存在信息
4. 登录尝试日志不完整或未持久化

## Low risk

### 低风险评级情形

1. **完整的防护体系**
   - 全面实现 IP 级和用户名级速率限制
   - 账户锁定机制与合理的冷却时间（>= 15分钟）
   - 清晰的审计日志与监控告警

2. **额外安全措施**
   - 启用了CAPTCHA或二次认证（邮件码、OTP）
   - 实现了异常登录检测（地理位置、设备指纹）
   - 配置了登录失败告警通知用户

3. **部署级防护**
   - 前置WAF/负载均衡器实现速率限制
   - API Gateway 层面的请求频率控制
   - DDoS 防护与IP白名单机制
