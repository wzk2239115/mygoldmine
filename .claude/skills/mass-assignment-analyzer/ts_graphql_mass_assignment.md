# TypeScript GraphQL 批量赋值漏洞

## Details

### 漏洞成因
GraphQL Resolver 接收的 `args` 通常由自动生成的输入类型（InputType）映射。如果 InputType 包含敏感字段（如 `role`, `status`, `tenantId`, `credit`, `isAdmin`）且 Resolver 将 `args` 直接传入 ORM/Service 更新，攻击者即可构造 GraphQL mutation 覆盖敏感字段。使用 `@nestjs/graphql`, `type-graphql`, `graphql-tools` 等库时未区分输入类型与输出类型，会放大风险。

### 代码示例

**易受攻击的代码：**
```typescript
@InputType()
class UpdateUserInput {
  @Field()
  email!: string;

  @Field({ nullable: true })
  role?: string; // 未限制
}

@Resolver()
export class UserResolver {
  @Mutation(() => User)
  async updateUser(@Args('id') id: string, @Args('input') input: UpdateUserInput) {
    // input.role 可被设置为 "ADMIN"
    return this.userService.update(id, input);
  }
}
```

**另一个不安全示例（TypeGraphQL + TypeORM）：**
```typescript
@Mutation(() => Order)
async updateOrder(
  @Arg("id") id: number,
  @Arg("data") data: OrderUpdateInput
) {
  const order = await this.orderRepository.preload({ id, ...data });
  return this.orderRepository.save(order); // data 可包含 status="PAID", tenantId=2
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- `@InputType`, `@ArgsType`, `@Field`, `InputObjectType`
- Resolver 中的 `@Mutation`, `@Query`，查看 `args` 使用。
- Service 调用：`this.service.update(id, input)`, `repository.save(args)`
- `class-validator`/`class-transformer` 装饰器是否应用在输入类型上。

**定位步骤：**
1. 检查 GraphQL 输入类型定义，确认是否包括敏感字段。
2. 查看 Resolver 如何处理输入，是否直接传递给 ORM。
3. 跳读（L2）确认是否有权限/租户校验或字段过滤。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **输入类型白名单：** 将敏感字段排除在 InputType 之外。
- **字段装饰器：** 使用 `@HideField()`, `@Directive('@authentication')`.
- **权限守卫：** `@UseGuards`, `@Roles` 等验证调用者。
- **Service 过滤：** 手动 `pick` 允许字段。
- **Schema Stitching**： 确保远程 schema 不暴露敏感字段。

**定位技巧：**
- 检查 `graphql-codegen` 生成的类型是否包含敏感字段。
- 确认 `transformSchema`, `schemaDirectives` 是否允许动态添加字段。
- 对 Federation/子图，关注跨服务字段传递。

#### 审计等级标注

| 场景 | 审计等级 | 说明 |
|------|----------|------|
| InputType 不包含敏感字段 + Service 白名单 | **L0（快速跳过）** | 风险低 |
| 部分字段保护但依赖守卫 | **L2（跳读）** | 检查是否有旁路 |
| Resolver 直接将 `args` 传入 ORM | **L3（逐行读）** | 高风险 |
| 多服务 GraphQL Federation | **L4（跨模块追踪）** | 需分析所有子图 |

## Classify

### 研判标准

#### 确认漏洞
需满足以下条件：
1. **GraphQL InputType** 包含敏感字段或允许额外字段。
2. **Resolver/Service 直接使用输入** 更新数据库。
3. **可实际修改权限、状态或租户**。

#### 误报
可视为误报的情况：
1. InputType 明确排除敏感字段。
2. Resolver 在调用 Service 前剥离敏感字段。
3. 数据库层拒绝未授权修改。

#### 代码异味
需关注的风险：
1. 使用与输出类型相同的 InputType，包含多余字段。
2. `@HideField` 仅影响输出，未影响输入。
3. Schema 拼接/远程子图引入敏感字段。
4. 缺少审计日志，难以追踪变更。

## Low risk

### 低风险评级场景

#### 1. 内部服务 GraphQL
- **场景：** Endpoint 仅对受信服务开放。
- **风险评估：** 攻击面有限，但需防内部滥用。

#### 2. DTO 白名单
- **场景：** 使用专门 InputType，只包含可写字段。
- **风险评估：** 风险较低，需保持维护。

#### 3. 数据库触发器
- **场景：** 关键字段的修改被数据库拒绝。
- **风险评估：** 降低危害，但非根治。

#### 4. 审计告警
- **场景：** 对敏感字段的 GraphQL mutation 记录日志并告警。
- **风险评估：** 有助于检测异常，但仍需修复根因。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 内部调用 + 强鉴权 | 攻击面有限 | 中 |
| InputType 白名单 | 技术防护完善 | 低 |
| 数据库约束 | 阻断敏感修改 | 中 |
| 审计告警 | 及时发现异常 | 高（持续改进）|

