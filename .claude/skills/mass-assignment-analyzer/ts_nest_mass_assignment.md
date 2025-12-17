# TypeScript NestJS 批量赋值漏洞

## Details

### 漏洞成因
NestJS 通过管道（class-transformer/class-validator）、DTO、`ValidationPipe` 将请求体转换为类实例。如果 DTO 未使用 `@Expose`, `@Exclude`, `@IsOptional`、`@IsBoolean` 等装饰器限制可写字段，或 `transform: true`, `whitelist: true` 未启用，攻击者可提交额外字段（如 `role`, `isAdmin`, `tenantId`, `status`）并通过 `Object.assign(entity, dto)` 或 `repository.save(dto)` 覆盖敏感字段。自动映射工具（如 `plainToClass`, `classToPlain`）也会引入风险。

### 代码示例

**易受攻击的代码：**
```typescript
export class UpdateUserDto {
  email!: string;
  name!: string;
  isAdmin?: boolean; // 未排除敏感字段
}

@Put(':id')
async update(@Param('id') id: string, @Body() dto: UpdateUserDto) {
  const user = await this.usersService.findOne(id);
  Object.assign(user, dto); // dto 可设置 isAdmin=true
  return this.usersService.save(user);
}
```

**另一个不安全示例（未启用 whitelist）：**
```typescript
async function bootstrap() {
  const app = await NestFactory.create(AppModule);
  app.useGlobalPipes(new ValidationPipe({ transform: true })); // 未启用 whitelist
  await app.listen(3000);
}

// DTO 未显式声明字段，payload 可带任何属性
@Patch(':id')
update(@Param('id') id: string, @Body() payload: any) {
  return this.service.update(id, payload); // payload 直接传入
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- `@Body() dto:`, `plainToClass`, `Object.assign`, `classToPlain`
- `ValidationPipe({ whitelist: ... })`, `transformOptions`
- DTO 中的敏感字段：`role`, `tenantId`, `status`, `amount`
- Service 方法：`repository.save(dto)`, `this.model.assign(dto)`

**定位步骤：**
1. 检查 `main.ts` 中 `ValidationPipe` 配置是否启用 `whitelist: true`, `forbidNonWhitelisted: true`.
2. 查看 DTO 是否使用 `@Expose`/`@Exclude` 控制字段。
3. 跳读（L2）确认 Service 层如何处理 DTO。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **白名单管道：** `whitelist: true`, `forbidNonWhitelisted: true`.
- **DTO 装饰器：** `@Expose()`, `@Exclude()`, `@IsEnum`, `@IsOptional`.
- **敏感字段只读：** 使用 `@Exclude()` 或不在 DTO 中声明。
- **权限校验：** Guard/Interceptor 检查当前用户权限。
- **Service 层过滤：** `const allowed = pick(dto, ['email', 'name']);`

**定位技巧：**
- 检查 `@Type` 装饰器和嵌套对象，防止深层字段可写。
- 确认 `ValidationPipe` 是否在特定路由覆盖默认配置。
- 对 `PartialType`, `PickType`, `IntersectionType` 生成的 DTO，确认未引入敏感字段。

#### 审计等级标注

| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 全局 ValidationPipe 开启 whitelist + DTO 装饰器完备 | **L0（快速跳过）** | 风险低 |
| 部分控制器启用白名单 | **L2（跳读）** | 检查遗漏路由 |
| 直接将 DTO 合并到实体 | **L3（逐行读）** | 高风险 |
| 多模块共享 DTO/GraphQL 输入 | **L4（跨模块追踪）** | 需全局检查 |

## Classify

### 研判标准

#### 确认漏洞
需满足以下条件：
1. **DTO/管道接受未经过滤的输入**。
2. **Service/Repository 将 DTO 直接保存或合并**。
3. **敏感字段可被覆盖**，造成越权或关键数据篡改。

#### 误报
可视为误报的情况：
1. DTO 未声明敏感字段且启用 whitelist 阻止额外字段。
2. Service 在保存前手动剥离敏感字段。
3. 接口仅供内部服务调用并有额外鉴权。

#### 代码异味
需关注的风险：
1. `@Body() payload: any` 绕过 DTO 验证。
2. DTO 引入 `PartialType` 后意外包含敏感字段。
3. 使用 `plainToClass` 时未设置 `excludeExtraneousValues`.
4. 依赖黑名单 `delete dto.role` 过滤字段。

## Low risk

### 低风险评级场景

#### 1. 内部管理员接口
- **场景：** API 仅供管理员使用。
- **风险评估：** 攻击面有限，但需防账号泄露。

#### 2. DTO 白名单 + 手动赋值
- **场景：** Service 层手动选择可更新字段。
- **风险评估：** 风险较低，需保持维护。

#### 3. 数据库/业务层约束
- **场景：** 敏感字段由数据库或业务逻辑重写。
- **风险评估：** 降低危害，但非根治。

#### 4. 审计告警
- **场景：** 对关键字段更新有日志与告警。
- **风险评估：** 有助于发现问题，但仍需修复。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 管理员专用接口 | 攻击面有限 | 中 |
| DTO 白名单 + whitelist | 技术防护完善 | 低 |
| 数据库/业务重写 | 阻断敏感修改 | 中 |
| 审计告警 | 及时发现异常 | 高（持续改进）|

