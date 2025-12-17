# TypeScript - XPath 类型不安全构造

## Details

### 漏洞成因
TypeScript 的类型系统虽然提供编译时类型检查，但在运行时仍是 JavaScript。当使用 `xpath` 库进行 XPath 查询时，如果将用户输入声明为 `string` 或 `any` 类型并通过字符串拼接嵌入表达式，TypeScript 的类型系统无法防止注入攻击。开发者可能误认为类型注解能提供安全保障，实际上类型擦除后的运行时代码仍存在漏洞。常见于强类型项目中的安全误判。

代码示例：
```typescript
import * as xpath from 'xpath';
import { DOMParser } from 'xmldom';

function searchUser(username: string): any {
    const doc = new DOMParser().parseFromString(xmlData, 'text/xml');
    const query: string = `//user[username='${username}']`;
    const nodes = xpath.select(query, doc);
    return nodes;
}

// 类型注解无法防止注入
const userInput: string = getUserInput(); // 即使声明为 string 类型
searchUser(userInput);
```

### 快速定位核心操作 (L1: 关键词扫描)
- `import xpath from 'xpath'`, `import * as xpath`
- `xpath.select()`, `xpath.select1()`, `xpath.evaluate()`
- 类型注解：`: string`, `: any`, `: unknown` 与 XPath 相关变量
- 模板字符串拼接：`` `${var}` ``, `+`, `.concat()`
- XPath 特征：`//`, `@`, `[`, `]`, `'`, `"`, `and`, `or`
- 数据源：`req.query`, `req.body`, `req.params`（Express/Fastify）

### 快速定位保护机制 (L2-L4)
- **运行时验证** (L2 跳读) - 查找 `zod`, `yup`, `class-validator`, `io-ts` 等验证库
- **类型守卫** (L2 跳读) - 检查自定义类型守卫函数（`is` 关键字）
- **泛型约束** (L3 逐行读) - 查找泛型参数约束（`T extends number`）但注意仅编译时有效
- **转义函数** (L3 逐行读) - 检查自定义 `escapeXPath()` 函数的实现
- **跨模块追踪** (L4) - 从控制器到服务层的数据流，检查中间验证逻辑

## Classify

### 漏洞判定标准

**确认为漏洞**：
1. 用户输入即使有 TypeScript 类型注解，仍通过字符串拼接嵌入 XPath 表达式
2. 未使用运行时验证库（仅依赖编译时类型检查）
3. 无有效的转义或参数化机制
4. 查询的 XML 数据包含敏感信息

**误报情况**：
- 使用运行时验证库（如 `zod.string().regex(/^[a-zA-Z0-9]+$/)`）严格验证
- 输入通过类型守卫函数验证且包含白名单检查
- 使用品牌类型（Branded Types）结合运行时验证
- XML 数据为公开的静态资源

**代码异味**：
- 使用 `any` 或 `unknown` 类型却未进行运行时验证
- 类型断言（`as string`）绕过类型检查
- 仅依赖接口或类型别名，缺乏运行时保护
- 自定义转义函数但未覆盖所有特殊字符

## Low risk

### 低风险评级场景

1. **运行时验证** - 使用 `zod`, `yup`, `class-validator` 等库进行严格验证
   - 例：`const schema = z.string().regex(/^[a-zA-Z0-9]+$/); const validated = schema.parse(input);`

2. **品牌类型 + 验证** - 结合品牌类型和运行时验证函数
   - 例：`type SafeString = string & { __brand: 'SafeString' }; function validate(s: string): SafeString { ... }`

3. **数值型泛型** - 泛型约束为 `number` 且有运行时类型检查
   - 例：`function query<T extends number>(id: T) { if (typeof id !== 'number') throw ... }`

4. **枚举类型** - 使用 TypeScript 枚举或字面量类型限制输入
   - 例：`type Field = 'name' | 'email'; function search(field: Field) { ... }`

5. **非敏感数据** - XPath 查询的 XML 数据为公开的配置或产品列表

6. **中间件验证** - Express/NestJS 的验证中间件或管道进行运行时检查

7. **DTO 验证** - 使用 DTO 类配合 `class-validator` 装饰器

8. **完整转义** - 实现并测试过的 XPath 转义函数，处理所有特殊字符
