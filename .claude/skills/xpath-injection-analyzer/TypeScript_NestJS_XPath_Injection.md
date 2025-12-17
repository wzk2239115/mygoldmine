# TypeScript - NestJS 框架 XPath 注入

## Details

### 漏洞成因
NestJS 是基于 TypeScript 的企业级 Node.js 框架，提供强大的依赖注入和装饰器系统。当 NestJS 应用使用 XPath 库（如 `xpath` 或 `@xmldom/xmldom`）进行 XML 数据查询时，从 DTO 或请求对象获取的用户输入若仅依赖 TypeScript 类型而未进行运行时验证，通过字符串拼接嵌入 XPath 表达式将导致注入。NestJS 的 `ValidationPipe` 如果未正确配置，无法自动防御此类注入。常见于 XML API 集成、配置管理和 SOAP 服务。

代码示例：
```typescript
import { Controller, Get, Query } from '@nestjs/common';
import * as xpath from 'xpath';
import { DOMParser } from '@xmldom/xmldom';

class SearchDto {
    username: string; // 仅有类型注解，无运行时验证
}

@Controller('users')
export class UserController {
    @Get('search')
    searchUser(@Query() query: SearchDto) {
        const doc = new DOMParser().parseFromString(userXML, 'text/xml');

        const xpathQuery = `//user[username='${query.username}']`;
        const result = xpath.select(xpathQuery, doc);

        return result;
    }
}
```

### 快速定位核心操作 (L1: 关键词扫描)
- `import { Controller, Get, Post, Query, Body, Param } from '@nestjs/common'`
- `@Controller()`, `@Get()`, `@Post()`, `@Query()`, `@Body()`
- `xpath.select()`, `DOMParser`, `.parseFromString()`
- DTO 类定义：`class SearchDto`, `class QueryDto`
- 模板字符串拼接：`` `//path[${var}]` ``, `+`, `.concat()`
- XPath 特征：`//`, `@`, `[`, `]`, `'`, `"`, `and`, `or`

### 快速定位保护机制 (L2-L4)
- **ValidationPipe** (L2 跳读) - 检查 `app.useGlobalPipes(new ValidationPipe())` 配置
- **class-validator 装饰器** (L2 跳读) - 查找 `@IsString()`, `@IsAlphanumeric()`, `@Matches()`, `@IsIn()`
- **class-transformer** (L3 逐行读) - 检查 `@Transform()` 装饰器的转换逻辑
- **自定义验证器** (L3 逐行读) - 查找自定义 `@Validate()` 装饰器或验证类
- **服务层追踪** (L4) - 从 Controller 到 Service 的数据流，检查业务逻辑层的验证

## Classify

### 漏洞判定标准

**确认为漏洞**：
1. NestJS DTO 或请求对象的字段仅有类型注解，缺乏 `class-validator` 装饰器
2. 未启用全局 `ValidationPipe` 或验证配置不严格
3. 用户输入通过字符串拼接嵌入 XPath 表达式
4. 查询的 XML 数据包含敏感信息

**误报情况**：
- DTO 使用 `class-validator` 装饰器且验证严格（如 `@IsAlphanumeric()`, `@Matches(/^[a-zA-Z0-9]+$/)`）
- 启用全局 `ValidationPipe` 且配置 `whitelist: true`, `forbidNonWhitelisted: true`
- 输入通过自定义验证器或管道进行白名单检查
- XML 数据为公开的静态资源

**代码异味**：
- DTO 有装饰器但验证不严格（如仅 `@IsString()`）
- 未启用全局 `ValidationPipe`，验证逻辑分散在各个 Controller
- 使用 `@Query()` 或 `@Body()` 但未指定 DTO 类型
- 自定义转义函数但未覆盖所有 XPath 特殊字符

## Low risk

### 低风险评级场景

1. **严格 DTO 验证** - 使用 `class-validator` 装饰器进行白名单验证
   - 例：`@IsAlphanumeric() @MaxLength(20) username: string;`

2. **全局 ValidationPipe** - 启用全局验证管道且配置严格
   - 例：`app.useGlobalPipes(new ValidationPipe({ whitelist: true, forbidNonWhitelisted: true }));`

3. **自定义验证器** - 使用 `@Validate()` 装饰器配合自定义验证类
   - 例：`@Validate(XPathSafeValidator) field: string;`

4. **枚举验证** - 使用 `@IsIn()` 限制输入为枚举值
   - 例：`@IsIn(['name', 'email', 'phone']) field: string;`

5. **正则验证** - 使用 `@Matches()` 进行严格正则验证
   - 例：`@Matches(/^[a-zA-Z0-9]+$/) username: string;`

6. **非敏感数据** - XPath 查询的 XML 数据为公开的配置或产品列表

7. **Guard 保护** - 使用自定义 Guard 对输入进行额外验证

8. **Interceptor 清理** - 使用 Interceptor 对输入进行清理或转义

9. **服务层封装** - XPath 查询封装在 Service 层，且输入经过严格验证

10. **异常过滤器** - 配置异常过滤器捕获验证失败，防止意外绕过
