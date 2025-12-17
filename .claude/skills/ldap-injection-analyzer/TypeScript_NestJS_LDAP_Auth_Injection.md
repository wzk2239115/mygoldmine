# TypeScript NestJS LDAP 身份认证注入

## Details

### 代码示例
NestJS 框架中常通过自定义服务或策略实现 LDAP 认证。以下是常见易受攻击模式：

```typescript
import { Injectable } from '@nestjs/common';
import { Client } from 'ldapjs';

@Injectable()
export class LdapAuthService {
  private client: Client;

  authenticate(username: string, password: string): Promise<boolean> {
    // 危险：直接拼接用户输入到过滤器
    const filter = `(&(uid=${username})(userPassword=${password}))`;

    return new Promise((resolve) => {
      this.client.search('ou=users,dc=example,dc=com', { filter }, (err, res) => {
        res.on('searchEntry', (entry) => {
          resolve(true);  // 用户存在则认证成功
        });
      });
    });
  }
}
```

### 快速定位核心操作的技巧
**L1：关键词扫描** - 检查以下特征：
- 服务类（`*.service.ts`）中的 LDAP 相关方法
- 参数来自控制器的输入（`@Body()`, `@Param()`, `@Query()`）
- 模板字符串或字符串拼接构造过滤器
- `ldapjs` 或 `ldap3` 包的使用

重点检查文件：
```
src/auth/*.service.ts       - LDAP 认证服务
src/auth/*.strategy.ts      - Passport 策略实现
src/*/ldap/*                - LDAP 相关模块
```

### 快速定位保护机制的技巧
**L2：跳读** - 检查防护迹象：
- `escapeFilter()` 或 `escapeLdapString()` 的调用
- 使用装饰器进行输入验证（`@IsAlphanumeric()`, `@Matches()`）
- 手动实现的转义逻辑

**L3：逐行读** - 验证防护完整性：
```typescript
// 安全的防护方式
import { escapeFilter } from 'ldapjs';
const filter = `(&(uid=${escapeFilter(username)})...)`;

// 或使用输入验证 DTO
@IsAlphanumeric()
@MaxLength(32)
username: string;
```

关键检查点：
- 转义函数是否在模板字符串构造前应用
- DTO 验证是否涵盖所有用户输入字段
- 是否遗漏了某个输入来源（路径参数、查询参数、请求体）

## Classify

### 漏洞判定规则
- **明确漏洞**：服务方法接收来自 HTTP 请求的参数，直接用于过滤器构造
- **高危信号**：NestJS 控制器中的 `@Body()` 或 `@Param()` 参数传递到 LDAP 查询
- **误报排除**：
  - 服务层应用了完整的 LDAP 转义
  - 控制器使用 DTO 和验证装饰器进行输入限制
  - 使用了 Passport.js 的官方 LDAP 策略

### 风险评估
- **高风险**：类型安全的 TypeScript 无法弥补运行时的注入风险，仍可改变 LDAP 查询逻辑
- **中风险**：仅某个参数未转义，其他参数有保护
- **低风险**：所有输入都经过数值类型或严格正则验证，注入空间有限

## Low risk

### 低风险评级的情形

1. **强类型+装饰器验证**
   - DTO 使用了 `@IsEmail()`, `@IsUUID()` 等严格的验证装饰器
   - TypeScript 编译时检查无法突破运行时验证

2. **特定字段的预检查**
   - 用户名字段仅用于日志或审计，不直接参与 LDAP 过滤器
   - 实际认证使用了后端生成的 DN 或受保护的 ID

3. **框架层级的防护**
   - 使用官方的 Passport LDAP 策略（已实现转义）
   - 或使用了 NestJS 官方 LDAP 模块的参数化接口
