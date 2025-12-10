---
name: web-auth-analyzer
description: 专业认证分析技能：分析API端点认证要求、认证机制安全性、用户角色体系，并触发下游路由扫描任务。
---

## 概述与边界

- **聚焦**：分析API端点认证要求、认证机制安全性、用户角色体系
- **输出**：认证分析报告 + 下游任务列表
- **不做**：漏洞利用、深度安全分析

## 分析维度

### 1. 认证机制分析

#### 主流语言/框架认证识别方法

**通用思路**：
- 路由入口：定位路由表/装饰器/注册函数（router、app、server）及默认路由目录，识别分组/前缀
- 鉴权挂载点：收集中间件/filters/guards/interceptors/`RequireAuthorization`/角色声明，区分全局、分组、端点级
- 认证方式与参数：辨识 `token/basic/oauth/apikey/cookie/session` 等及携带位置（header/query/body/cookie）
- 重点缺口：优先记录缺少鉴权或可绕过的公开端点，明确公开 vs 需授权

#### 认证机制安全风险

| 风险类型 | 描述 | 检测要点 |
|---------|------|---------|
| JWT 密钥泄露 | 硬编码密钥、弱密钥、密钥存储不当 | 搜索 `secret`、`key`、`jwt` 相关配置 |
| JWT 算法混淆 | 允许 `none` 算法或 RS256/HS256 混用 | 检查 JWT 验证配置 |
| 会话固定 | 登录后未重新生成 Session ID | 检查登录逻辑 |
| 认证逻辑缺陷 | 条件判断可绕过、短路逻辑 | 审查认证中间件实现 |
| 默认凭证 | 硬编码用户名密码、默认管理员账户 | 搜索 `admin`、`password`、`default` |
| Token 验证缺失 | 部分端点跳过认证检查 | 对比中间件覆盖范围 |

#### 风险等级定义

- **可绕过**：存在明确的绕过路径，攻击者可直接获取未授权访问
- **存在风险**：存在潜在安全隐患，需特定条件才能利用
- **安全**：认证机制实现合理，未发现明显漏洞

### 2. 用户角色体系分析（新增）

**分析目标**：判断系统是否包含多角色用户体系，识别不同角色的权限边界。

#### 多角色体系识别特征

| 特征类型 | 识别模式 | 示例 |
|---------|---------|------|
| 角色枚举 | `enum Role`、`ROLE_*`、`UserRole` | `enum Role { ADMIN, USER, GUEST }` |
| 角色字段 | `role`、`roles`、`user_type`、`is_admin` | `user.role`, `user.is_staff` |
| 权限装饰器 | `@Roles`、`@RequireRole`、`@hasRole` | `@Roles('admin', 'user')` |
| 权限中间件 | `RoleGuard`、`PermissionGuard` | `UseGuards(RolesGuard)` |
| 权限配置 | `authorize`、`permissions`、`access_control` | `authorize: ['admin']` |

#### 常见角色类型

| 角色类型 | 典型命名 | 权限级别 |
|---------|---------|---------|
| 超级管理员 | `superadmin`, `root`, `super` | 最高权限 |
| 管理员 | `admin`, `administrator`, `staff` | 管理权限 |
| 普通用户 | `user`, `member`, `customer` | 普通权限 |
| 访客 | `guest`, `anonymous`, `visitor` | 最低/无权限 |

#### 角色体系分析步骤

1. **搜索角色定义**：
```bash
# 搜索角色枚举/常量
rg -i "role|permission|authority" -g'*.{js,ts,py,java,go,php}'
rg "enum.*Role|ROLE_|UserType|is_admin|is_staff"
```

2. **分析权限控制实现**：
- 全局权限中间件
- 路由级权限装饰器
- 控制器级权限注解

3. **识别角色边界**：
- 管理员专属路由（`/admin/*`、`/management/*`）
- 普通用户路由（需登录但非管理员）
- 公开路由（无需登录）

## 输出要求

### 产物文件

输出路径：`.workspace/tasks/{TASK_ID}/web-auth-analyzer.md`

```markdown
# Web 认证分析报告

## 认证机制安全评估

### 评估结论
- **认证可绕过**：是/否
- **风险等级**：可绕过 / 存在风险 / 安全
- **结论依据**：[具体说明]

### 发现的安全风险
| 风险类型 | 风险等级 | 位置 | 描述 |
|---------|---------|------|------|
| xxx | 高/中/低 | file:line | 详细描述 |

### 认证机制概述
- **主要认证方式**：[JWT/Session/OAuth/API Key/...]
- **认证覆盖范围**：[全局/部分端点]
- **高权限接口保护**：[描述 admin 等接口的保护方式]

---

## 用户角色体系分析

### 角色体系判定
- **多角色体系**：是/否
- **判定依据**：[具体说明]

### 识别的角色类型
| 角色名称 | 角色标识 | 权限级别 | 定义位置 |
|---------|---------|---------|---------|
| 管理员 | admin | 管理权限 | src/models/user.js:15 |
| 普通用户 | user | 普通权限 | src/models/user.js:16 |

### 角色权限边界
- **管理员专属路由前缀**：[/admin, /management, ...]
- **权限控制实现方式**：[中间件/装饰器/配置]
- **权限控制代码位置**：[file:line]

### 路由分类概览
| 分类 | 数量 | 示例路径 |
|------|------|---------|
| 无需认证 | N | /login, /register, /health |
| 普通用户 | N | /api/profile, /api/orders |
| 管理员专属 | N | /admin/users, /admin/config |
```

### 下游任务生成

根据分析结果生成下游任务：

#### 情况 1：存在多角色体系

触发两个下游任务：
- `unauth-route-scanner`：提取无需认证的路由
- `normal-route-scanner`：提取普通用户（非管理员）可访问的路由

```json
{
  "tasks": [
    {
      "artifact": ".workspace/tasks/{TASK_ID}/web-auth-analyzer.md",
      "skill": "unauth-route-scanner"
    },
    {
      "artifact": ".workspace/tasks/{TASK_ID}/web-auth-analyzer.md",
      "skill": "normal-route-scanner"
    }
  ]
}
```

#### 情况 2：无多角色体系（单一用户类型或无用户系统）

仅触发一个下游任务：
- `unauth-route-scanner`：提取无需认证的路由

```json
{
  "tasks": [
    {
      "artifact": ".workspace/tasks/{TASK_ID}/web-auth-analyzer.md",
      "skill": "unauth-route-scanner"
    }
  ]
}
```

#### 情况 3：认证机制可绕过

当认证机制存在绕过漏洞时，应分析所有路由（包括管理员路由），此时：
- 仍然触发 `unauth-route-scanner` 和 `normal-route-scanner`
- 在产物中标注 `认证可绕过: 是`，下游技能会据此调整分析范围

### 重要约束

- **必须输出用户角色体系分析**：即使判定为无多角色体系，也需要在产物中说明判定依据
- **下游任务必须生成**：根据分析结果生成对应的 tasks 列表
- **风险评估必须明确**：认证机制的风险等级必须给出明确结论
