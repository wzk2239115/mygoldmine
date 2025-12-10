---
name: normal-route-scanner
description: 普通用户路由扫描技能：从项目中提取普通用户（非管理员）可访问的API端点，为后续安全分析提供攻击面清单。
---

## 概述与边界

- **聚焦**：提取项目中普通用户（非管理员）可访问的API端点
- **输入依赖**：`web-auth-analyzer` 产物（认证分析和角色体系分析）
- **不做**：漏洞利用、深度安全分析（由下游技能完成）

## 执行流程

### 1. 读取上游产物

**必需输入**：
- 认证分析结果：`.workspace/tasks/{AUTH_TASK_ID}/web-auth-analyzer.md`

从上游产物中获取：
- 认证机制是否可绕过
- 角色体系定义
- 管理员专属路由前缀
- 权限控制实现方式

### 2. 普通用户路由识别标准

#### 2.1 定义：普通用户可访问的路由

普通用户路由 = 需要登录认证 + 非管理员专属

**包含**：
- 需要登录但无角色限制的路由
- 限制为普通用户角色的路由（如 `@Roles('user')`）
- 登录用户都可访问的通用功能路由

**排除**：
- 无需认证的公开路由（由 `unauth-route-scanner` 处理）
- 管理员/超级管理员专属路由
- 内部/调试路由

#### 2.2 识别方法

**识别需要认证的路由**：

```python
# Python Flask - 有 @login_required 但无 @admin_required
@login_required
@app.route('/api/profile')
def get_profile():
    return profile

# Python FastAPI - 有 Depends(get_current_user) 但无管理员检查
@router.get('/api/orders')
async def list_orders(user: User = Depends(get_current_user)):
    return orders
```

```javascript
// Express - 有 auth 中间件但无 admin 中间件
app.get('/api/profile', authMiddleware, (req, res) => {
    res.json(profile);
});

// NestJS - 有 @UseGuards(AuthGuard) 但无 @Roles('admin')
@UseGuards(AuthGuard)
@Get('orders')
findOrders() {
    return this.ordersService.findAll();
}
```

```java
// Spring - 需要认证但无管理员角色要求
@GetMapping("/api/profile")
@PreAuthorize("isAuthenticated()")
public Profile getProfile() {
    return profileService.get();
}
```

```go
// Gin - 在 auth 中间件组内但不在 admin 组内
authGroup := r.Group("/api", authMiddleware)
{
    authGroup.GET("/profile", getProfile)
    authGroup.GET("/orders", listOrders)
}
```

**排除管理员路由的特征**：

| 排除特征 | 示例 |
|---------|------|
| 路径前缀 | `/admin/*`, `/management/*`, `/internal/*`, `/superuser/*` |
| 角色装饰器 | `@Roles('admin')`, `@RequireRole('admin')`, `@admin_required` |
| 权限注解 | `@PreAuthorize("hasRole('ADMIN')")`, `roles=['admin']` |
| 中间件 | `AdminGuard`, `adminMiddleware`, `IsAdminMiddleware` |
| 权限配置 | `permission: 'admin'`, `is_staff=True`, `is_superuser=True` |

#### 2.3 认证可绕过时的处理

当 `web-auth-analyzer` 判定认证机制可绕过时：
- **包含管理员路由**：因为攻击者可能绕过认证访问这些路由
- 在产物中标注：`认证绕过风险: 是`
- 将管理员路由单独分组标记

### 3. 风险分级

| 风险等级 | 描述 | 路由特征 |
|---------|------|----------|
| **高危** | 敏感操作 | 支付、密码修改、权限变更、数据删除 |
| **中危** | 数据修改 | 个人信息修改、订单操作、文件上传 |
| **低危** | 数据读取 | 查看个人资料、订单列表、消息记录 |

### 4. 输出格式

#### 4.1 产物文件

输出路径：`.workspace/tasks/{TASK_ID}/normal-route-scanner.md`

```markdown
# 普通用户路由清单

## 概述

- **扫描时间**：{timestamp}
- **总路由数**：{total_routes}
- **普通用户路由数**：{normal_user_count}
- **认证可绕过**：{auth_bypassable: 是/否}

## 风险统计

| 风险等级 | 数量 | 占比 |
|---------|------|------|
| 高危 | {high_count} | {high_percent}% |
| 中危 | {medium_count} | {medium_percent}% |
| 低危 | {low_count} | {low_percent}% |

## 高危普通用户路由

| # | 方法 | 路径 | 文件位置 | 功能说明 | 风险说明 |
|---|------|------|---------|---------|----------|
| 1 | POST | /api/payment | src/routes/payment.js:25 | 支付接口 | 支付操作无二次验证 |
| 2 | PUT | /api/password | src/routes/user.js:80 | 修改密码 | 密码修改敏感操作 |

## 中危普通用户路由

| # | 方法 | 路径 | 文件位置 | 功能说明 | 风险说明 |
|---|------|------|---------|---------|----------|
| 1 | PUT | /api/profile | src/routes/user.js:45 | 修改个人资料 | 可能存在越权修改 |
| 2 | POST | /api/upload | src/routes/file.js:30 | 文件上传 | 需检查文件类型限制 |

## 低危普通用户路由

| # | 方法 | 路径 | 文件位置 | 功能说明 |
|---|------|------|---------|---------|
| 1 | GET | /api/profile | src/routes/user.js:20 | 查看个人资料 |
| 2 | GET | /api/orders | src/routes/order.js:15 | 订单列表 |

## 因认证绕过而包含的管理员路由

> 以下路由因认证机制可绕过而被纳入分析范围

| # | 方法 | 路径 | 文件位置 | 原始权限要求 |
|---|------|------|---------|-------------|
| 1 | GET | /admin/users | src/routes/admin.js:30 | admin |
| 2 | DELETE | /admin/data | src/routes/admin.js:55 | admin |
```

## 与其他技能的协作

### 上游依赖

| 技能 | 产物 | 用途 |
|------|------|------|
| `web-auth-analyzer` | web-auth-analyzer.md | 获取认证机制和角色体系分析 |

### 下游消费

此技能产物供以下技能使用：

| 技能 | 用途 |
|------|------|
| `route-deep-analyzer` | 对普通用户路由进行深度分析 |

## 输出要求

### 产物输出

**Markdown 报告**：`.workspace/tasks/{TASK_ID}/normal-route-scanner.md`

### 下游任务生成

每个普通用户路由清单对应一个 `route-deep-analyzer` 任务：

```json
{
  "tasks": [
    {
      "artifact": ".workspace/tasks/{TASK_ID}/normal-route-scanner.md",
      "skill": "route-deep-analyzer",
      "dependencies": [
        ".workspace/tasks/{AUTH_TASK_ID}/web-auth-analyzer.md"
      ]
    }
  ]
}
```

### 重要约束

- **必须读取上游产物**：不可独立运行，需依赖 web-auth-analyzer 的输出
- **必须排除公开路由**：公开路由由 `unauth-route-scanner` 处理，避免重复
- **风险分级必须明确**：每个路由必须标注风险等级和原因
- **JSON 输出必须有效**：确保 JSON 格式正确，便于下游程序化处理
- **认证绕过时包含管理员路由**：当认证可绕过时，需要将管理员路由也纳入分析
