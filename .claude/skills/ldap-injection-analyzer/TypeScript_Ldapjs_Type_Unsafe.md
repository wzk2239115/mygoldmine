# TypeScript ldapjs 类型不安全

## Details

### 代码示例
TypeScript 的类型系统无法防止运行时的 LDAP 注入，未转义的字符串拼接仍然危险：

```typescript
import * as ldap from 'ldapjs';
import { Request, Response } from 'express';

// 危险示例1：类型标注不等于安全
interface SearchParams {
  username: string;  // 类型仅为 string，不保证内容安全
  department: string;
}

function searchUser(params: SearchParams): Promise<any[]> {
  const filter = `(&(uid=${params.username})(dept=${params.department}))`;  // 危险
  return new Promise((resolve, reject) => {
    client.search(baseDN, { filter }, (err, res) => {
      // ...
    });
  });
}

// 危险示例2：泛型类型不保证安全
class LdapService<T> {
  search(query: T): Promise<any> {
    // 危险：即使 T 有类型，运行时值仍可能被注入
    const filter = `(uid=${(query as any).uid})`;
    return this.client.search(this.baseDN, { filter });
  }
}

// 危险示例3：类型守卫不足
function isValidUsername(input: string): input is string {
  return typeof input === 'string';  // 仅检查类型，不验证内容
}

app.post('/search', (req: Request, res: Response) => {
  const username = req.body.username;
  if (isValidUsername(username)) {  // 类型守卫通过
    const filter = `(uid=${username})`;  // 但仍然危险
    client.search(baseDN, { filter }, handleResult);
  }
});

// 危险示例4：联合类型的误用
type FilterValue = string | number;

function buildFilter(attr: string, value: FilterValue) {
  // 危险：number 类型也可能包含恶意内容（如从字符串转换而来）
  const filter = `(${attr}=${value})`;
  return filter;
}

// 调用时：buildFilter(req.body.attr, req.body.value)  // 两个参数都不安全
```

### 快速定位核心操作的技巧
**L1：关键词扫描** - 搜索以下特征：
- `import * as ldap from 'ldapjs'`, `import { Client } from 'ldapjs'`
- `.search()`, `.bind()` 方法调用
- `req.body`, `req.params`, `req.query` 类型为 `any` 或 `string`
- 模板字符串 `` `${var}` ``，类型断言 `as string`
- 接口定义中的 `string` 类型字段

重点检查文件：
```
src/services/ldapService.ts
src/controllers/authController.ts
src/middleware/ldapAuth.ts
src/types/ldap.d.ts
src/utils/filterBuilder.ts
```

### 快速定位保护机制的技巧
**L2：跳读** - 检查防护迹象：
- 运行时验证库：`zod`, `yup`, `io-ts`, `class-validator`
- 自定义验证函数：带有正则或白名单检查的类型守卫
- `ldap-escape` 包的使用
- 品牌类型（Branded Types）或 Opaque Types

**L3：逐行读** - 验证防护完整性：
```typescript
// 检查点1：是否有运行时验证
import { z } from 'zod';

const UsernameSchema = z.string().regex(/^[a-zA-Z0-9]+$/);
const username = UsernameSchema.parse(req.body.username);  // 运行时验证

// 检查点2：类型守卫是否包含内容验证
function isValidLdapInput(input: string): input is string {
  return typeof input === 'string' && /^[a-zA-Z0-9]+$/.test(input);  // 包含验证
}

// 检查点3：是否使用了品牌类型
type SafeLdapString = string & { readonly __brand: unique symbol };

function escapeLdap(input: string): SafeLdapString {
  return ldapEscape.filter(input) as SafeLdapString;
}

// 使用时强制转义
function search(filter: SafeLdapString) { /* ... */ }
search(escapeLdap(username));  // 必须先转义
```

关键检查点：
- 类型定义是否结合运行时验证
- 是否仅依赖 TypeScript 类型而无运行时检查
- 是否使用了品牌类型强制转义

## Classify

### 漏洞判定规则
- **明确漏洞**：用户输入仅有 TypeScript 类型标注，无运行时验证或转义
- **高危信号**：
  - 接口定义为 `username: string`，但无验证逻辑
  - 类型守卫仅检查 `typeof` 而不验证内容
  - 类型断言 `as string` 用于绕过类型检查
- **误报排除**：
  - 结合运行时验证库（zod, yup 等）
  - 使用品牌类型强制转义流程
  - 所有输入在使用前都经过 `ldap-escape`

### 风险评估
- **高风险**：仅依赖 TypeScript 类型，无任何运行时防护
- **中风险**：有部分运行时验证，但未覆盖所有输入
- **低风险**：类型系统结合严格的运行时验证

## Low risk

### 低风险评级的情形

1. **结合运行时验证库**
   - 使用 zod 或 yup 定义严格的 Schema
   - Schema 包含正则验证：`z.string().regex(/^[a-zA-Z0-9]+$/)`
   - 所有输入在解析时自动验证

2. **品牌类型强制转义**
   - 定义 `SafeLdapString` 品牌类型
   - 过滤器函数仅接受 `SafeLdapString` 参数
   - 编译时强制开发者调用转义函数

3. **严格的类型守卫**
   - 类型守卫包含完整的内容验证
   - 如 `isValidUsername` 检查正则、长度、字符集
   - 通过守卫后的值可安全使用

4. **装饰器验证（class-validator）**
   - DTO 类使用 `@IsAlphanumeric()`, `@Length()` 等装饰器
   - 验证管道在控制器层自动执行
   - 无效输入在到达业务逻辑前被拒绝
