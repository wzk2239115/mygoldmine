---
name: unauth-route-scanner
description: 未授权路由扫描技能：从路由扫描结果中提取无需认证即可访问的API端点，为后续安全分析提供攻击面清单。
---

## 概述与边界

- **聚焦**：提取项目中无需认证即可访问的API端点，生成未授权访问路由清单
- **输入依赖**：`web-auth-analyzer` 产物（认证机制分析和角色体系分析）
- **不做**：漏洞利用、深度安全分析（由下游技能完成）

## 执行流程

### 1. 读取上游产物

**必需输入**：
- 认证分析结果：`.workspace/tasks/{AUTH_TASK_ID}/web-auth-analyzer.md`

从上游产物中获取：
- 认证机制是否可绕过
- 路由分类概览
- 无需认证的路由列表

### 2. 未授权路由识别标准

#### 2.1 明确无需认证的路由

以下路由类型通常无需认证即可访问：

| 路由类型 | 示例路径 | 识别特征 |
|---------|---------|----------|
| 公开资源 | `/public/*`, `/static/*`, `/assets/*` | 路径前缀包含 public/static/assets |
| 健康检查 | `/health`, `/healthz`, `/ping`, `/status` | 运维监控端点 |
| API文档 | `/swagger*`, `/api-docs`, `/openapi*` | Swagger/OpenAPI 端点 |
| 登录注册 | `/login`, `/register`, `/signup`, `/auth/*` | 认证流程入口 |
| 密码重置 | `/forgot-password`, `/reset-password` | 密码恢复流程 |
| OAuth回调 | `/oauth/callback`, `/auth/callback` | OAuth 认证回调 |
| Webhook | `/webhook/*`, `/hooks/*` | 外部服务回调 |
| 验证码 | `/captcha`, `/verify-code` | 人机验证端点 |

#### 2.2 代码级认证缺失识别

根据 `web-auth-analyzer` 产物中的分析结果，识别以下情况：

**无认证中间件/装饰器的路由**：
```python
# Python Flask - 无 @login_required
@app.route('/api/data')
def get_data():
    return data

# Python FastAPI - 无 Depends(get_current_user)
@router.get('/api/items')
async def list_items():
    return items
```

```javascript
// Express - 无 auth 中间件
app.get('/api/users', (req, res) => {
    res.json(users);
});

// NestJS - 无 @UseGuards(AuthGuard)
@Get('items')
findAll() {
    return this.itemsService.findAll();
}
```

```java
// Spring - 无 @PreAuthorize 或 SecurityConfig 排除
@GetMapping("/api/products")
public List<Product> getProducts() {
    return productService.findAll();
}
```

```go
// Gin - 无 auth 中间件组
r.GET("/api/info", func(c *gin.Context) {
    c.JSON(200, info)
})
```

**认证配置排除的路由**：
```yaml
# Spring Security 配置排除
security:
  ignored:
    - /api/public/**
    - /actuator/health
```

```javascript
// Express 中间件排除
app.use('/api', authMiddleware.unless({
    path: ['/api/login', '/api/register', '/api/public']
}));
```

#### 2.3 认证可绕过的路由

当 `web-auth-analyzer` 判定认证机制可绕过时，以下路由视为潜在未授权访问：

- **JWT 签名未验证**：所有使用该 JWT 保护的路由
- **认证逻辑缺陷**：存在短路逻辑或条件绕过的路由
- **默认凭证存在**：使用默认认证的管理端点
- **Token 验证可选**：允许匿名访问的敏感端点

### 3. 风险分级

| 风险等级 | 描述 | 路由特征 |
|---------|------|----------|
| **高危** | 敏感数据暴露 | 用户数据、配置信息、内部接口 |
| **中危** | 功能滥用风险 | 批量操作、资源消耗型接口 |
| **低危** | 信息泄露风险 | 版本信息、调试端点、公开数据 |
| **安全** | 设计为公开 | 静态资源、登录注册、健康检查 |

### 4. 输出格式

#### 4.1 产物文件

输出路径：`.workspace/tasks/{TASK_ID}/unauth-route-scanner.md`

```markdown
# 未授权访问路由清单

## 概述

- **扫描时间**：{timestamp}
- **总路由数**：{total_routes}
- **未授权路由数**：{unauthenticated_count}
- **认证可绕过**：{auth_bypassable: 是/否}

## 风险统计

| 风险等级 | 数量 | 占比 |
|---------|------|------|
| 高危 | {high_count} | {high_percent}% |
| 中危 | {medium_count} | {medium_percent}% |
| 低危 | {low_count} | {low_percent}% |
| 安全 | {safe_count} | {safe_percent}% |

## 高危未授权路由

| # | 方法 | 路径 | 文件位置 | 风险说明 |
|---|------|------|---------|----------|
| 1 | GET | /api/users | src/routes/user.js:15 | 用户列表未授权访问 |
| 2 | POST | /api/config | src/routes/admin.js:42 | 配置修改无认证 |

## 中危未授权路由

| # | 方法 | 路径 | 文件位置 | 风险说明 |
|---|------|------|---------|----------|
| 1 | POST | /api/export | src/routes/data.js:88 | 数据导出无限制 |

## 低危未授权路由

| # | 方法 | 路径 | 文件位置 | 风险说明 |
|---|------|------|---------|----------|
| 1 | GET | /api/version | src/routes/info.js:5 | 版本信息泄露 |

## 设计为公开的路由（安全）

| # | 方法 | 路径 | 文件位置 | 说明 |
|---|------|------|---------|------|
| 1 | GET | /health | src/app.js:10 | 健康检查端点 |
| 2 | POST | /api/login | src/routes/auth.js:20 | 登录入口 |

## 认证绕过相关路由

> 以下路由因认证机制存在绕过风险而被标记

| # | 方法 | 路径 | 文件位置 | 绕过原因 |
|---|------|------|---------|----------|
| 1 | GET | /api/admin/users | src/routes/admin.js:30 | JWT 算法可切换为 none |
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
| `route-deep-analyzer` | 对未授权路由进行深度功能分析 |

## 输出要求

### 产物输出

**Markdown 报告**：`.workspace/tasks/{TASK_ID}/unauth-route-scanner.md`

### 下游任务生成

根据未授权路由数量和风险等级，推荐下游分析任务：

**输出格式（JSON）**：

```json
{
  "tasks": [
    {
      "artifact": ".workspace/tasks/{TASK_ID}/unauth-route-scanner.md",
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
- **风险分级必须明确**：每个未授权路由必须标注风险等级和原因
- **不遗漏高危路由**：即使数量较多，高危路由必须全部列出
- **JSON 输出必须有效**：确保 JSON 格式正确，便于下游程序化处理
