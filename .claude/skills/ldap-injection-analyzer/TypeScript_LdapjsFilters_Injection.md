# TypeScript LdapjsFilters 注入

## Details

### 代码示例
在 TypeScript 中使用 `ldap-filters` 库时，类型系统同样无法防止注入，需要运行时验证：

```typescript
import { Filter, EqualityFilter, parseFilter } from 'ldap-filters';

// 危险示例1：类型化的接口不保证安全
interface FilterCriteria {
  attribute: string;  // 类型为 string，但可能包含恶意值
  value: string;
}

function buildFilter(criteria: FilterCriteria): string {
  // 危险：虽然有类型，但未验证内容
  return `(${criteria.attribute}=${criteria.value})`;
}

// 危险示例2：泛型参数的误用
class LdapFilterBuilder<T extends Record<string, any>> {
  build(input: T): string {
    const parts = Object.entries(input).map(([key, val]) => {
      // 危险：key 和 val 都不安全
      return `(${key}=${val})`;
    });
    return `(&${parts.join('')})`;
  }
}

// 使用：new LdapFilterBuilder().build(req.body)  // req.body 是 any

// 危险示例3：类型化的 parseFilter 仍不安全
interface SearchRequest {
  username: string;
  department: string;
}

function searchUsers(req: SearchRequest): Filter {
  // 危险：parseFilter 不会转义，仅解析语法
  const filterStr = `(&(uid=${req.username})(dept=${req.department}))`;
  return parseFilter(filterStr);  // 类型正确但仍危险
}

// 危险示例4：类型收窄不等于内容验证
type LdapAttribute = 'uid' | 'cn' | 'mail' | string;  // string 使得联合类型失效

function createFilter(attr: LdapAttribute, value: string) {
  // 危险：attr 可以是任意 string
  const filter = new EqualityFilter({ attribute: attr, value });
  return filter.toString();
}
```

### 快速定位核心操作的技巧
**L1：关键词扫描** - 搜索以下特征：
- `import { Filter, parseFilter } from 'ldap-filters'`
- `EqualityFilter`, `SubstringFilter`, `AndFilter`, `OrFilter`
- `parseFilter()`, `.toString()` 方法
- 接口定义中的 `string` 类型字段
- `Record<string, any>`, `[key: string]: string` 索引签名

重点检查文件：
```
src/utils/ldapFilters.ts
src/services/filterBuilder.ts
src/types/ldap.d.ts
src/controllers/searchController.ts
```

### 快速定位保护机制的技巧
**L2：跳读** - 检查防护迹象：
- 字面量类型：`type Attr = 'uid' | 'cn' | 'mail'`（无 `string` 后缀）
- 运行时验证：`zod`, `io-ts`, `class-validator`
- 转义函数调用：`ldap-escape`
- 自定义验证函数与类型守卫的结合

**L3：逐行读** - 验证防护完整性：
```typescript
// 检查点1：字面量类型是否严格
type ValidAttr = 'uid' | 'cn' | 'mail';  // 严格，无 string
// vs
type InvalidAttr = 'uid' | 'cn' | string;  // 不严格，任意字符串都可以

// 检查点2：是否结合运行时验证
import { z } from 'zod';

const AttrSchema = z.enum(['uid', 'cn', 'mail']);
const attr = AttrSchema.parse(req.body.attr);  // 运行时验证

// 检查点3：EqualityFilter 的值是否转义
const filter = new EqualityFilter({
  attribute: 'uid',
  value: ldapEscape.filter(username)  // 是否转义？
});

// 检查点4：是否使用品牌类型
type SafeAttr = 'uid' | 'cn' | 'mail' & { readonly __safe: unique symbol };
```

关键检查点：
- 联合类型是否包含 `string` 兜底
- 是否结合 zod 等运行时验证
- EqualityFilter 的 value 是否被转义

## Classify

### 漏洞判定规则
- **明确漏洞**：使用 `parseFilter()` 处理包含用户输入的字符串，无运行时验证
- **高危信号**：
  - 接口定义为 `string` 类型但无验证
  - 联合类型包含 `string`，使得类型限制失效
  - `Object.entries()` 遍历 `req.body` 等不可信对象
- **误报排除**：
  - 严格的字面量联合类型（无 `string` 后缀）
  - 结合运行时验证库（zod, io-ts）
  - 所有值经过 `ldap-escape` 转义

### 风险评估
- **高风险**：仅依赖 TypeScript 类型，无运行时防护
- **中风险**：有类型限制但不严格（如包含 `string`）
- **低风险**：严格类型 + 运行时验证 + 转义

## Low risk

### 低风险评级的情形

1. **严格的字面量类型**
   - `type Attr = 'uid' | 'cn' | 'mail'`（不包含 `string`）
   - 编译时拒绝任意字符串
   - 配合 `as const` 断言使用

2. **运行时 Schema 验证**
   - 使用 zod 定义严格的输入 Schema
   - Schema 包含 `.regex()`, `.enum()` 等约束
   - 验证失败时抛出异常，阻止继续执行

3. **品牌类型强制流程**
   - 定义 `type EscapedString = string & { __escaped: true }`
   - 过滤器函数仅接受 `EscapedString`
   - 编译时强制调用转义函数

4. **纯 API 使用**
   - 完全使用 `new EqualityFilter({ attribute, value })` 形式
   - 不使用 `parseFilter()` 或字符串拼接
   - 依赖库的内部转义（需确认库版本安全）
