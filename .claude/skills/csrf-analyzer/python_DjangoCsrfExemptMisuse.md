# Python Django CSRF 豁免误用漏洞

## Details

### 漏洞成因
Django 默认通过中间件 `django.middleware.csrf.CsrfViewMiddleware` 防护表单提交。若开发者在视图函数或类视图上使用 `@csrf_exempt`、在 `urls.py` 中关闭中间件、或自定义 API 忽略 Token，任何依赖 Cookie 的敏感操作都将失去防护。常见场景包括为第三方集成快速豁免、调试时临时禁用、或 REST 端点误判无需 Cookie 而豁免。

### 代码示例

**易受攻击的代码：**
```python
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def update_profile(request):
    if request.method == "POST":
        request.user.email = request.POST["email"]
        request.user.save()
        return JsonResponse({"ok": True})
```

**另一个不安全示例（类视图豁免）：**
```python
from django.utils.decorators import method_decorator
from django.views import View

@method_decorator(csrf_exempt, name="dispatch")
class PaymentWebhookView(View):
    def post(self, request):
        # 处理信用卡扣款逻辑
        return HttpResponse("ok")
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- `@csrf_exempt`, `csrf_exempt(`, `method_decorator(csrf_exempt`
- 设置：`MIDDLEWARE`, `CSRF_TRUSTED_ORIGINS`
- REST 框架：`@permission_classes`, `csrf_exempt` with DRF

**定位步骤：**
1. 搜索代码中使用 `csrf_exempt` 的视图，确认是否用于敏感操作。
2. 检查全局 `MIDDLEWARE` 配置是否遗漏 `CsrfViewMiddleware`.
3. 跳读（L2）DRF、Graphene、Channels 等端点是否自定义处理 CSRF。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **替代防护**：如 HMAC 签名、Basic Auth、OAuth。
- **白名单域名**：`CSRF_TRUSTED_ORIGINS` 是否仅允许可信来源。
- **Token 注入**：模板使用 `{% csrf_token %}`。
- **Cookie 设置**：`CSRF_COOKIE_HTTPONLY`, `CSRF_COOKIE_SAMESITE`.

**定位技巧：**
- 分析为何豁免：第三方回调？如确需豁免，应验证签名。
- 检查中间件顺序，确保 CSRF 中间件在 Session 之后。
- 确认 REST API 是否仍依赖 Cookie 鉴权。

#### 审计等级标注

| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 无豁免 + 默认中间件 | **L0（快速跳过）** | 风险低 |
| 个别端点豁免但有签名校验 | **L2（跳读）** | 需确认安全性 |
| 大量敏感端点使用 `@csrf_exempt` | **L3（逐行读）** | 高风险 |
| 全局关闭中间件 | **L4（跨模块追踪）** | 防护失效 |

## Classify

### 研判标准

#### 确认漏洞
需满足：
1. 视图/端点使用 `csrf_exempt` 或关闭中间件。
2. 端点通过 Cookie/Session 认证。
3. 缺乏其它可靠防护。

#### 误报
以下情况为误报：
1. 端点完全无状态，使用 Token/Bearer Auth。
2. 第三方回调使用签名且不依赖 Cookie。
3. 豁免仅在 GET/HEAD 只读接口，且无敏感操作。

#### 代码异味
需记录：
1. 仅为了方便测试临时豁免，部署时忘记移除。
2. 通过中间件跳过 CSRF 但未记录审计。
3. GraphQL/DRF 端点自定义 schema 忽略 Token。
4. 使用 `CSRF_COOKIE_SECURE = False` 在生产环境。

## Low risk

### 低风险评级场景

#### 1. 内部系统 + 签名
- **场景：** @csrf_exempt 端点验证签名且仅内部调用。
- **风险评估：** 风险较低但需定期审查。

#### 2. REST API + Token Auth
- **场景：** 端点使用 JWT/Bearer Token，无 Cookie。
- **风险评估：** CSRF 风险小，确保无 Cookie 回退。

#### 3. SameSite=Strict Cookie
- **场景：** 认证 Cookie 设置 Strict。
- **风险评估：** 提供部分缓解，仍建议启用 CSRF。

#### 4. 审计告警
- **场景：** 记录所有豁免端点访问日志并监控异常。
- **风险评估：** 有助于发现滥用，非根治方案。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 内部调用 + 签名 | 攻击面有限 | 中 |
| Token Auth | 不使用 Cookie | 低 |
| SameSite=Strict | 浏览器缓解 | 低 |
| 审计与告警 | 提升检测能力 | 高（仍需评估豁免必要性）|

