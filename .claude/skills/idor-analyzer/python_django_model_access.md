# Python Django - 模型对象直接访问未授权漏洞

## Details

**代码示例：**
```python
# 典型漏洞模式 1 - 直接查询单个对象
from django.shortcuts import render
from django.http import JsonResponse
from .models import UserProfile

def get_user_profile(request):
    user_id = request.GET.get('user_id')  # 从URL参数提取ID
    profile = UserProfile.objects.get(id=user_id)  # 直接查询无权限检查
    return JsonResponse(profile.to_dict())

# 典型漏洞模式 2 - REST风格URL路径参数
from django.views import View
from rest_framework.decorators import api_view
from rest_framework.response import Response

class UserDetailView(View):
    def get(self, request, user_id):
        user = User.objects.get(id=user_id)  # 未验证当前用户是否有权访问
        return JsonResponse({'user': user.username, 'email': user.email})

# 典型漏洞模式 3 - APIView/ViewSet
from rest_framework.views import APIView

class OrderDetailAPI(APIView):
    def get(self, request):
        order_id = request.data.get('order_id')  # 从请求体提取
        order = Order.objects.filter(id=order_id).first()  # 无owner校验
        return Response(OrderSerializer(order).data)

# 典型漏洞模式 4 - 关联对象访问
def get_user_documents(request):
    user_id = request.GET['uid']
    user = User.objects.get(id=user_id)
    documents = user.documents.all()  # 通过关系访问，但未检查当前用户权限
    return JsonResponse([d.to_dict() for d in documents])

# 典型漏洞模式 5 - 批量查询
def list_orders(request):
    user_id = request.GET.get('user_id')
    orders = Order.objects.filter(user_id=user_id)  # 未验证当前用户是否为此user_id
    return JsonResponse([o.to_dict() for o in orders])

# 典型漏洞模式 6 - 动态字段查询
from rest_framework.generics import RetrieveAPIView

class DynamicProfileView(RetrieveAPIView):
    queryset = UserProfile.objects.all()
    serializer_class = ProfileSerializer
    # 默认使用pk或id参数，未配置permission_classes
    # GET /api/profile/123/ 可访问任意用户资料
```

**快速定位核心操作（L1-L2 关键词扫描/跳读）：**
- **参数提取识别**：
  - 请求参数：`request.GET.get()`、`request.POST.get()`、`request.data.get()`、`request.query_params.get()`
  - URL路径参数：视图函数签名中的参数如`def view(request, user_id):`或`def view(request, pk):`
  - 请求体：`request.body`、`request.data`、JSON反序列化后的dict
  - Cookie/Header：`request.COOKIES.get()`、`request.META.get('HTTP_')`
  - 参数名特征：`id`、`user_id`、`uid`、`order_id`、`pk`、`product_id`、`doc_id`等资源ID
- **ORM查询入口（L1 关键词扫描）**：
  - 单对象查询：`.get()`、`.first()`、`.last()`、`.retrieve()`
  - 多对象查询：`.filter()`、`.all()`、`.exclude()`、`.select_related()`、`.prefetch_related()`
  - 原始SQL：`.raw()`、`Model.objects.raw()`、`.extra()`、`connection.cursor().execute()`
  - 聚合操作：`.aggregate()`、`.annotate()`、`.values()`
  - 关注敏感模型：User、UserProfile、Account、Order、Document、Payment、Invoice
- **定位技巧**：
  - 搜索`request.GET[`或`request.POST[` → 提取参数名 → 全局搜索该变量 → 追踪至`.get()`或`.filter()` → 验证中间无权限过滤

**快速定位保护机制（L3-L4 逐行读/跨模块追踪）：**
- **L3-同文件同函数检查**：
  - **会话校验（L3）**：
    - `request.user.is_authenticated`是否存在检查（仅表示登录，不代表有权限）
    - `current_user = request.user`、`request.user.id`获取当前用户身份
    - 自定义用户上下文：`user_from_token = verify_token(request.headers['Authorization'])`
  - **所有权判断（L3）**：
    - 查询前校验：`if profile.user_id != request.user.id: raise PermissionDenied`
    - 查询后校验：`if order.user != request.user: return forbidden()`
    - 关系验证：`if not request.user.has_perm('view_profile', profile) else forbidden()`
    - SQL过滤条件：`.filter(user_id=request.user.id)`（检查filter条件是否包含当前用户）
  - **异常处理**：
    - `UserProfile.objects.get(id=user_id)`抛`DoesNotExist`异常
    - 若异常被吞没导致逻辑继续执行，可能跳过后续权限校验
- **L4-跨模块追踪**：
  - **中间件层拦截（L4）**：
    - 搜索`django.http.middleware`、自定义`MiddleWare`类
    - 检查是否有中间件在`process_request()`或`process_view()`中进行全局权限校验
    - 确认中间件是否能覆盖所有敏感路由
  - **装饰器保护（L4）**：
    - `@login_required`仅检查登录，不校验资源所有权
    - `@permission_required('view_profile')`是否使用且配置正确
    - 自定义装饰器：`@check_owner`实现中是否正确提取`pk`参数并校验所有权
    - DRF装饰器：`@api_view(['GET'])`、`@authentication_classes()`、`@permission_classes()`
  - **权限类配置（L4）**：
    - DRF权限体系：`permission_classes = [IsAuthenticated, IsOwner]`
    - 检查`permission_classes`是否为空（默认允许所有）或仅包含`IsAuthenticated`
    - 自定义权限类：`class IsOwner(permissions.BasePermission):`的`has_object_permission()`实现
    - 模型级权限：`django-guardian`、`django-rules`的`has_perm()`调用
  - **Service层封装（L4）**：
    - 追踪`UserService.get_profile(user_id, current_user)`实现
    - 确认方法是否内置所有权校验或需外部验证
    - 关注方法签名：是否强制接收`current_user`参数
  - **QuerySet定制化（L4）**：
    - Django ORM Manager自定义：`class OwnedQuerySet(QuerySet):`中`.for_user(user)`方法
    - 全局过滤：`BaseQuerySet.filter(user=request.user)`是否被正确使用
    - 模型管理器：`objects = OwnedManager()`是否替代默认Manager
  - **安全框架集成（L4）**：
    - `django-rest-framework`权限框架配置
    - `django-guardian`对象级权限：`user.has_perm('view', obj)`
    - `django-rules`规则引擎：`@predicate`装饰的权限判断逻辑

## Classify

**漏洞确认标准：**
- **可横向越权**：修改请求中的`user_id`或`pk`参数可访问任意用户/订单/文档，无需额外权限或凭证
- **敏感数据泄露**：响应包含密码hash、手机号、邮箱、身份证、地址、余额、支付信息等隐私字段
- **零防护特征**：既无权限装饰器、也无`has_perm()`调用、更无`.filter(user=request.user)`条件约束
- **批量利用可行**：无限流限制，可通过简单循环遍历大量ID获取数据

**误报排除依据：**
- **公开资源设计**：
  - 查询的是公开文章、商品详情、分类数据等业务逻辑本身无需权限的资源
  - 社交平台用户公开资料（昵称、头像、认证勋章），设计上允许互查
- **前置拦截有效**：
  - 全局中间件已绑定用户身份，后续视图直接使用`request.user`参数（需审查中间件逻辑完整性）
  - API网关层统一鉴权，后端仅处理预授权请求
- **字段投影安全**：
  - 序列化时仅映射公开字段：`class PublicProfileSerializer(serializers.ModelSerializer): fields = ['id', 'username', 'avatar']`
  - 查询时显式排除敏感字段：`.values('id', 'username')`不含密码或邮箱
  - DTO转换白名单：`profile_dict = {k: v for k, v in profile.to_dict().items() if k in allowed_fields}`
- **数据库级保护**：
  - PostgreSQL RLS策略已启用：`ALTER TABLE user_profile ENABLE ROW LEVEL SECURITY`
  - 数据库视图已过滤：SELECT查询的是受保护的view而非直接表

**代码异味识别：**
- **防御不完整**：
  - 仅校验参数类型（`int(user_id)`）或格式，未校验所有权
  - 仅使用`@login_required`验证登录态，未校验资源归属
  - `if request.user.is_staff:`跳过权限检查，管理员路径存在漏洞
- **条件性保护**：
  - 仅在特定条件下校验权限：`if user_id > 1000: check_permission()`
  - 权限校验依赖客户端参数：`if request.GET.get('check_auth') == '1':`
- **客户端依赖**：
  - 前端过滤不显示他人ID，后端无二次验证
  - 通过`request.data.get('is_owner')`或表单隐藏字段判断权限
- **异常处理缺陷**：
  - `.get()`异常被吞没导致返回None，跳过权限校验逻辑
  - `.filter().first()`对空结果无特殊处理，继续返回数据
- **关系遍历漏洞**：
  - `user.documents.all()`通过关系访问但未验证当前用户是否为此user
  - 序列化器递归序列化关联对象，暴露敏感嵌套数据

## Low risk

**可降级为低风险的场景：**
- **数据脱敏充分**：
  - 手机号脱敏为`137****0123`、邮箱为`us****@example.com`、身份证隐藏中间11位
  - 敏感字段返回`null`或固定值`[HIDDEN]`而非真实数据
  - 金额/余额字段不返回或返回范围段（如`1000-5000`）
- **影响范围受限**：
  - 仅泄露用户等级、注册时间、头像URL、公开标签等低敏感度信息
  - 返回字段通过`serializer_class.Meta.fields = ['id', 'username']`严格白名单控制
  - API文档确认仅返回非敏感字段
- **外部控制层**：
  - 数据库RLS策略已启用：查询自动按当前会话过滤（需查看`policy_name`和条件）
  - API网关统一鉴权：Kong/NGINX OIDC模块已校验，后端信任`X-User-Id` header
  - WAF规则有效：拦截ID枚举模式（如`/api/user/1, /api/user/2`连续请求）
- **间接利用门槛高**：
  - ID为UUID/hash且不可预测，需先通过其他漏洞获取有效ID列表
  - 查询接口存在严格限流：1秒内仅允许1次，批量枚举成本高
  - 需验证码或OTP验证才能查看完整数据
- **业务场景限制**：
  - 内部ERP/CRM系统，员工间本可互查（需与业务方确认设计意图）
  - 测试/开发/预发布环境，不含真实生产数据
  - 已下线API，近6个月无生产流量（需查看日志确认）
  - 历史兼容接口，新版本已改为正确实现（需确认旧版本流量比例）