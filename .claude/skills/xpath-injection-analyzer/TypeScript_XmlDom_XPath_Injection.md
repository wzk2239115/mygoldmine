# TypeScript - @xmldom/xmldom + xpath 组合注入

## Details

### 漏洞成因
`@xmldom/xmldom` 是 TypeScript/JavaScript 中常用的 DOM 解析库，通常与 `xpath` 库组合使用进行 XML 节点查询。当用户输入通过模板字符串或字符串拼接方式嵌入 XPath 表达式时，TypeScript 的类型系统无法在运行时防止注入攻击。开发者可能误认为 TypeScript 的类型注解能提供安全保障，但类型擦除后仍是不安全的 JavaScript 代码。常见于 XML 配置解析和 SOAP 客户端。

代码示例：
```typescript
import { DOMParser } from '@xmldom/xmldom';
import * as xpath from 'xpath';

interface SearchParams {
    username: string;
    password: string;
}

function authenticate(params: SearchParams): boolean {
    const doc = new DOMParser().parseFromString(userXML, 'text/xml');

    const query = `//user[username='${params.username}' and password='${params.password}']`;
    const result = xpath.select(query, doc) as Node[];

    return result.length > 0;
}
```

### 快速定位核心操作 (L1: 关键词扫描)
- `import { DOMParser } from '@xmldom/xmldom'`, `import * as xpath`
- `new DOMParser()`, `.parseFromString()`, `.parse()`
- `xpath.select()`, `xpath.select1()`, `xpath.evaluate()`
- 模板字符串：`` `//path[${var}]` ``, 字符串拼接：`+`, `.concat()`
- 类型断言：`as Node[]`, `as string`
- XPath 特征：`//`, `@`, `[`, `]`, `'`, `"`, `and`, `or`

### 快速定位保护机制 (L2-L4)
- **接口验证** (L2 跳读) - 检查接口定义是否配合运行时验证库（`zod`, `class-validator`）
- **DTO 类** (L2 跳读) - 查找 DTO 类与 `class-validator` 装饰器的组合
- **验证管道** (L3 逐行读) - 检查 NestJS 的 `ValidationPipe` 或 Express 中间件
- **转义函数** (L3 逐行读) - 检查自定义 `sanitizeXPath()` 或 `escapeInput()` 实现
- **跨层追踪** (L4) - 从 Controller/Route Handler 到 Service 层的数据流分析

## Classify

### 漏洞判定标准

**确认为漏洞**：
1. 用户输入（即使有 TypeScript 接口约束）通过字符串拼接嵌入 XPath 表达式
2. 仅有接口或类型注解，缺乏运行时验证
3. 无有效的转义或参数化机制
4. 查询的 XML 数据包含敏感信息

**误报情况**：
- 接口配合运行时验证库（如 `zod.object({ field: z.string().regex(...) })`）
- 使用 DTO 类且有 `class-validator` 装饰器（`@IsAlphanumeric()`, `@Matches()`）
- 输入通过类型守卫且包含白名单验证
- XML 数据为公开的静态资源

**代码异味**：
- 接口定义严格但无运行时验证
- 使用类型断言（`as string`）绕过类型检查
- 自定义转义函数但未处理所有 XPath 特殊字符
- 仅在某些路由使用验证，其他路由缺失

## Low risk

### 低风险评级场景

1. **Zod 验证** - 使用 `zod` 进行运行时模式验证
   - 例：`const UserSchema = z.object({ username: z.string().regex(/^[a-zA-Z0-9]+$/) }); UserSchema.parse(input);`

2. **class-validator** - 使用 DTO 类配合装饰器验证
   - 例：`class SearchDto { @IsAlphanumeric() @MaxLength(20) username: string; }`

3. **类型守卫 + 白名单** - 自定义类型守卫函数结合枚举验证
   - 例：`function isSafeField(s: string): s is 'name' | 'email' { return ['name', 'email'].includes(s); }`

4. **品牌类型** - 使用品牌类型结合验证函数
   - 例：`type ValidatedString = string & { __validated: true }; function validate(s: string): ValidatedString { ... }`

5. **非敏感数据** - XML 数据为公开的产品目录或配置

6. **NestJS 管道** - 使用 NestJS 的 `ValidationPipe` 全局验证

7. **中间件保护** - Express 的验证中间件对所有 XPath 相关输入进行检查

8. **完整转义库** - 使用经过测试的第三方 XPath 转义库
