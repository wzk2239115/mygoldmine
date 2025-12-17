# TypeScript｜多角色调用共享 Service 缺少权限分流

## Details

### 漏洞成因
在 NestJS、Express(TypeScript)、GraphQL 服务中，经常将业务逻辑封装在 service 层，供不同角色的控制器（Admin/API/Client）调用。如果 service 内部未根据调用者角色或权限进行分流，就可能让普通用户通过 GraphQL/REST 请求触发管理员逻辑，导致越权。

### 代码示例

**易受攻击示例：**
```ts
@Injectable()
export class UserService {
  async updateRole(userId: string, role: Role) {
    await this.usersRepository.update({ id: userId }, { role });
  }
}

// 管理端
@Mutation(() => Boolean)
@UseGuards(AdminGuard)
async adminUpdateRole(@Args('userId') id: string, @Args('role') role: Role) {
  await this.userService.updateRole(id, role);
  return true;
}

// 普通用户 API 误用
@Mutation(() => Boolean)
@UseGuards(AuthGuard)
async updateSelf(@CurrentUser() user: User, @Args('role') role: Role) {
  await this.userService.updateRole(user.id, role); // 未限制 role 范围
  return true;
}
```

**安全示例：**
```ts
async updateRole(userId: string, role: Role, actor: User) {
  if (!actor.permissions.includes('user:role:update')) {
    throw new ForbiddenException();
  }
  await this.usersRepository.update({ id: userId }, { role });
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `@Injectable`, `service`, `updateRole`, `reset`, `promote`, `guard`, `permissions`。

**定位步骤：**
1. 找出被多个控制器/Resolver 调用的 service 方法；
2. 跳读（L2）确认方法是否接收 `actor`/`currentUser`；
3. 检查方法内部是否调用权限工具（Casbin、policy service）。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- Service 方法接收 `actor` 并校验；
- 自定义装饰器 `@Permission('…')`；
- GraphQL `@ResolveField` 级权限；
- Casbin/OPA/自建策略服务。

**定位技巧：**
- 逐行读（L3）敏感 service，确认未忽略权限；
- 跨模块追踪（L4）微服务间调用、API Gateway 是否绕过权限。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| Service 内部统一校验 | **L0（快速跳过）** | 风险低 |
| 部分方法缺少校验 | **L2（跳读）** | 需确认 |
| 完全信任调用者 | **L3（逐行读）** | 高风险 |
| Service 被多个系统共享 | **L4（跨模块追踪）** | 全链路审计 |

## Classify

### 研判标准

#### 确认漏洞
1. Service 未校验调用者权限；
2. 普通用户通过共享 service 越权执行管理员操作；
3. 造成实际权限提升或敏感数据修改。

#### 误报
1. Service 仅被管理员控制器调用，外部无法访问；
2. 方法内部调用 `authorizationService.check`；
3. 操作仅调整非敏感参数。

#### 代码异味
1. 方法签名未包含 actor，依赖调用者传入 `isAdmin`；
2. 仅靠 DTO 验证而无权限逻辑；
3. 注释说明“仅管理员调用”，缺乏机制约束。

## Low risk

### 低风险评级场景

#### 1. 操作只影响非敏感配置
- **评估：** 可标低风险。

#### 2. 服务部署在内网且有网关控制
- **评估：** 攻击面有限。

#### 3. 将引入策略服务
- **评估：** 暂降级，跟踪实施。

#### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 非敏感操作 | 影响有限 | 低 |
| 内网网关 | 攻击面低 | 中 |
| 改造计划明确 | 可暂缓 | 低 |
