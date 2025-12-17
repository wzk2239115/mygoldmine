# Go 自定义 LDAP 查询构造

## Details

### 代码示例
自定义LDAP查询构造器如果实现不当会引入注入：

```go
package ldaputil

import (
    "fmt"
    "strings"
    "github.com/go-ldap/ldap/v3"
)

// 危险示例1：自定义查询构造器
type QueryBuilder struct {
    filters []string
}

func NewQueryBuilder() *QueryBuilder {
    return &QueryBuilder{filters: make([]string, 0)}
}

func (qb *QueryBuilder) AddCondition(attr, value string) *QueryBuilder {
    // 危险：未转义attr和value
    qb.filters = append(qb.filters, fmt.Sprintf("(%s=%s)", attr, value))
    return qb
}

func (qb *QueryBuilder) Build() string {
    if len(qb.filters) == 0 {
        return "(objectClass=*)"
    }
    return "(&" + strings.Join(qb.filters, "") + ")"
}

// 使用：
// query := NewQueryBuilder().
//     AddCondition("uid", userInput).  // 危险
//     AddCondition("dept", deptInput).
//     Build()

// 危险示例2：map转过滤器
func MapToFilter(criteria map[string]string) string {
    if len(criteria) == 0 {
        return "(objectClass=*)"
    }

    var parts []string
    for key, value := range criteria {
        // 危险：key和value都未验证
        parts = append(parts, fmt.Sprintf("(%s=%s)", key, value))
    }

    return "(&" + strings.Join(parts, "") + ")"
}

// 危险示例3：fluent接口
type LDAPQuery struct {
    baseDN string
    filter string
    attrs  []string
}

func (q *LDAPQuery) Where(attr, op, value string) *LDAPQuery {
    // 危险：value未转义
    q.filter = fmt.Sprintf("(%s%s%s)", attr, op, value)
    return q
}

func (q *LDAPQuery) And(attr, value string) *LDAPQuery {
    // 危险：拼接未转义内容
    newFilter := fmt.Sprintf("(%s=%s)", attr, value)
    q.filter = fmt.Sprintf("(&%s%s)", q.filter, newFilter)
    return q
}

// 危险示例4：条件构造器
type FilterBuilder struct {
    operator string
    children []string
}

func And() *FilterBuilder {
    return &FilterBuilder{operator: "&"}
}

func (fb *FilterBuilder) Equal(attr, value string) *FilterBuilder {
    // 危险：未转义
    fb.children = append(fb.children, fmt.Sprintf("(%s=%s)", attr, value))
    return fb
}

func (fb *FilterBuilder) String() string {
    return fmt.Sprintf("(%s%s)", fb.operator, strings.Join(fb.children, ""))
}
```

### 快速定位核心操作的技巧
**L1：关键词扫描** - 搜索以下特征：
- 自定义类型：`type *Builder struct`, `type *Query struct`
- 方法：`func (*Builder) Add*`, `func (*Query) Where()`
- 字符串拼接：`fmt.Sprintf()`, `strings.Join()`
- LDAP过滤器模式：`"(&"`, `"(|"`, `"(%s=%s)"`

重点检查文件：
```
pkg/ldap/query_builder.go
utils/ldap_filter.go
internal/ldap/builder.go
```

### 快速定位保护机制的技巧
**L2：跳读** - 检查防护迹象：
- `ldap.EscapeFilter(value)`在方法内部调用
- 属性名白名单验证
- 构造器方法返回错误（而非panic或忽略）

**L3：逐行读** - 验证防护完整性：
```go
import "github.com/go-ldap/ldap/v3"

// 检查点1：方法内部是否转义
func (qb *QueryBuilder) AddCondition(attr, value string) *QueryBuilder {
    safeValue := ldap.EscapeFilter(value)  // 转义
    // 但attr未验证！
    qb.filters = append(qb.filters, fmt.Sprintf("(%s=%s)", attr, safeValue))
    return qb
}

// 检查点2：属性名白名单
var allowedAttrs = map[string]bool{
    "uid": true, "cn": true, "mail": true,
}

func (qb *QueryBuilder) AddCondition(attr, value string) (*QueryBuilder, error) {
    if !allowedAttrs[attr] {
        return nil, fmt.Errorf("invalid attribute: %s", attr)
    }
    safeValue := ldap.EscapeFilter(value)
    qb.filters = append(qb.filters, fmt.Sprintf("(%s=%s)", attr, safeValue))
    return qb, nil
}

// 检查点3：是否一致处理
// 检查所有方法（Equal, Like, Greater等）是否都转义
```

关键检查点：
- 构造器的所有方法是否都转义值
- 属性名是否白名单验证
- 是否存在方法遗漏转义

## Classify

### 漏洞判定规则
- **明确漏洞**：查询构造器方法未转义值或未验证属性名
- **高危信号**：
  - 方法直接使用`fmt.Sprintf()`拼接输入
  - 属性名参数未白名单验证
  - map遍历构造过滤器
- **误报排除**：
  - 所有方法内部调用`ldap.EscapeFilter()`
  - 属性名严格白名单
  - 构造器仅接受常量属性

### 风险评估
- **高风险**：构造器被广泛使用，影响范围大
- **中风险**：部分方法有问题
- **低风险**：构造器正确实现转义

## Low risk

### 低风险评级的情形

1. **构造器内部转义**
   - 所有方法内部调用`ldap.EscapeFilter()`
   - 对调用者透明

2. **属性名类型安全**
   - 使用常量或枚举：
   ```go
   const (
       AttrUID  = "uid"
       AttrCN   = "cn"
       AttrMail = "mail"
   )

   func (qb *QueryBuilder) Equal(attr AttrType, value string) *QueryBuilder
   ```

3. **文档明确说明**
   - 构造器文档明确说明已处理转义
   - 调用者无需手动转义

4. **测试覆盖**
   - 构造器有单元测试覆盖注入场景
