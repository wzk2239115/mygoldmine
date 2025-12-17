# Django LDAP 认证注入

## Details

### 代码示例
Django应用中使用LDAP认证时未正确处理输入会导致注入：

```python
from django.contrib.auth.backends import BaseBackend
import ldap3

# 危险示例1：自定义认证后端
class LDAPAuthBackend(BaseBackend):
    def authenticate(self, request, username=None, password=None):
        # 危险：直接拼接用户名
        search_filter = f"(uid={username})"
        conn.search('dc=example,dc=com', search_filter)

        if conn.entries:
            user_dn = conn.entries[0].entry_dn
            # 尝试绑定
            if conn.rebind(user=user_dn, password=password):
                return self.get_or_create_user(username)
        return None

# 危险示例2：Django视图中的LDAP查询
from django.views import View
from django.http import JsonResponse

class UserSearchView(View):
    def get(self, request):
        query = request.GET.get('q', '')
        dept = request.GET.get('department', '')

        # 危险：GET参数未转义
        filter_str = f"(&(cn=*{query}*)(department={dept}))"
        conn.search(settings.LDAP_BASE_DN, filter_str)

        results = [entry.entry_to_json() for entry in conn.entries]
        return JsonResponse({'users': results})

# 危险示例3：Django REST Framework序列化器
from rest_framework import serializers, viewsets

class UserSerializer(serializers.Serializer):
    username = serializers.CharField()
    email = serializers.EmailField()

class LDAPUserViewSet(viewsets.ViewSet):
    def list(self, request):
        # 危险：查询参数未验证
        username = request.query_params.get('username', '')
        filter_str = f"(uid={username})"
        conn.search(settings.LDAP_BASE_DN, filter_str)

        users = [UserSerializer(entry.entry_attributes_as_dict).data
                 for entry in conn.entries]
        return Response(users)

# 危险示例4：中间件中的LDAP验证
from django.utils.deprecation import MiddlewareMixin

class LDAPGroupMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if request.user.is_authenticated:
            group = request.META.get('HTTP_X_REQUIRED_GROUP')
            # 危险：HTTP header未验证
            filter_str = f"(&(uid={request.user.username})(memberOf=cn={group},ou=groups,dc=example,dc=com))"
            conn.search(settings.LDAP_BASE_DN, filter_str)

            if not conn.entries:
                return HttpResponseForbidden()
```

### 快速定位核心操作的技巧
**L1：关键词扫描** - 搜索以下特征：
- `from django.contrib.auth.backends import`, `BaseBackend`
- `class *ViewSet`, `class *View(View)`
- `request.GET.get`, `request.POST.get`, `request.query_params.get`
- `conn.search()`, `ldap_conn.search()`
- f-string拼接：`f"..."`, `.format()`

重点检查文件：
```
backends.py
views.py
api/views.py
middleware.py
serializers.py
```

### 快速定位保护机制的技巧
**L2：跳读** - 检查防护迹象：
- `from ldap3.utils.conv import escape_filter_chars`
- Django表单验证：`form.is_valid()`, `clean_*`方法
- DRF序列化器验证：`validate_*`方法
- 自定义验证器：`from django.core.validators import RegexValidator`

**L3：逐行读** - 验证防护完整性：
```python
from ldap3.utils.conv import escape_filter_chars

# 检查点1：认证后端是否转义
def authenticate(self, request, username=None, password=None):
    safe_username = escape_filter_chars(username)
    search_filter = f"(uid={safe_username})"

# 检查点2：Django表单验证
from django import forms

class UserSearchForm(forms.Form):
    username = forms.CharField(validators=[
        RegexValidator(r'^[a-zA-Z0-9]+$', 'Only alphanumeric')
    ])

# 检查点3：DRF序列化器验证
class UserSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=32)

    def validate_username(self, value):
        if not re.match(r'^[a-zA-Z0-9]+$', value):
            raise serializers.ValidationError("Invalid format")
        return value
```

关键检查点：
- 认证后端是否转义用户名
- 视图是否使用Django表单验证
- DRF序列化器是否有validate方法

## Classify

### 漏洞判定规则
- **明确漏洞**：LDAP过滤器直接包含未转义的Django request数据
- **高危信号**：
  - 认证后端中的过滤器拼接
  - 中间件中的LDAP查询包含用户输入
  - DRF ViewSet未验证查询参数
- **误报排除**：
  - 使用`escape_filter_chars()`转义
  - Django表单验证覆盖所有输入
  - DRF序列化器有完整的validate方法

### 风险评估
- **高风险**：认证绕过、权限提升
- **中风险**：API层面的信息泄露
- **低风险**：仅只读，范围受限

## Low risk

### 低风险评级的情形

1. **Django表单验证**
   - 使用`forms.Form`定义所有输入
   - `form.is_valid()`验证通过才执行查询
   - 验证器包含正则和长度限制

2. **DRF序列化器验证**
   - 所有输入通过序列化器
   - `validate_*`方法检查格式
   - 验证失败返回400错误

3. **只读API**
   - 仅提供用户查询功能
   - 不影响认证或会话

4. **django-auth-ldap包**
   - 使用成熟的`django-auth-ldap`包
   - 包内部处理转义（需验证版本）
