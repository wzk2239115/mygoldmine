# Rust 自定义 LDAP 查询构造

## Details

### 代码示例
自定义LDAP查询构造器如果实现不当会引入注入：

```rust
// 危险示例1：简单的查询构造器
pub struct LdapFilter {
    conditions: Vec<String>,
}

impl LdapFilter {
    pub fn new() -> Self {
        Self { conditions: Vec::new() }
    }

    pub fn equal(&mut self, attr: &str, value: &str) -> &mut Self {
        // 危险：value未转义
        self.conditions.push(format!("({}={})", attr, value));
        self
    }

    pub fn like(&mut self, attr: &str, value: &str) -> &mut Self {
        // 危险：value未转义
        self.conditions.push(format!("({}=*{}*)", attr, value));
        self
    }

    pub fn build(&self) -> String {
        if self.conditions.is_empty() {
            "(objectClass=*)".to_string()
        } else {
            format!("(&{})", self.conditions.join(""))
        }
    }
}

// 使用：
// let filter = LdapFilter::new()
//     .equal("uid", user_input)  // 危险
//     .equal("dept", dept_input)
//     .build();

// 危险示例2：使用trait实现的Builder
pub trait FilterBuilder {
    fn to_filter(&self) -> String;
}

pub struct EqualCondition {
    attr: String,
    value: String,
}

impl FilterBuilder for EqualCondition {
    fn to_filter(&self) -> String {
        // 危险：未转义
        format!("({}={})", self.attr, self.value)
    }
}

// 危险示例3：类型安全的Builder但仍有问题
pub struct Filter<T> {
    attr: &'static str,
    value: T,
}

impl<T: std::fmt::Display> Filter<T> {
    pub fn new(attr: &'static str, value: T) -> Self {
        Self { attr, value }
    }

    pub fn to_string(&self) -> String {
        // 危险：虽然attr是'static，但value未转义
        format!("({}={})", self.attr, self.value)
    }
}

// 使用：
// let f = Filter::new("uid", username);  // username是String，未转义

// 危险示例4：流式API
pub struct QueryBuilder {
    filter: String,
}

impl QueryBuilder {
    pub fn where_attr(mut self, attr: &str, value: &str) -> Self {
        // 危险：未转义
        self.filter = format!("({}={})", attr, value);
        self
    }

    pub fn and(mut self, attr: &str, value: &str) -> Self {
        // 危险：拼接未转义内容
        let new_cond = format!("({}={})", attr, value);
        self.filter = format!("(&{}{})", self.filter, new_cond);
        self
    }

    pub fn build(self) -> String {
        self.filter
    }
}
```

### 快速定位核心操作的技巧
**L1：关键词扫描** - 搜索以下特征：
- `pub struct *Builder`, `pub struct *Filter`
- `impl *Builder`, `impl FilterBuilder for`
- `fn equal`, `fn like`, `fn where_`, `fn and`
- `format!()`, `to_string()`, `String::from()`
- `trait FilterBuilder`, `trait QueryBuilder`

重点检查文件：
```
src/ldap/filter.rs
src/ldap/query_builder.rs
src/utils/ldap.rs
```

### 快速定位保护机制的技巧
**L2：跳读** - 检查防护迹象：
- 方法内部调用`escape_*`函数
- 使用`PhantomData`确保类型安全
- 属性名使用枚举或const
- 文档说明已处理转义

**L3：逐行读** - 验证防护完整性：
```rust
// 检查点1：方法内部是否转义
impl LdapFilter {
    pub fn equal(&mut self, attr: &str, value: &str) -> &mut Self {
        let escaped = escape_ldap_filter(value);  // 转义
        // 但attr未验证！
        self.conditions.push(format!("({}={})", attr, escaped));
        self
    }
}

// 检查点2：属性名类型安全
pub enum Attr {
    Uid,
    Cn,
    Mail,
}

impl Attr {
    fn as_str(&self) -> &'static str {
        match self {
            Attr::Uid => "uid",
            Attr::Cn => "cn",
            Attr::Mail => "mail",
        }
    }
}

impl LdapFilter {
    pub fn equal(&mut self, attr: Attr, value: &str) -> &mut Self {
        let escaped = escape_ldap_filter(value);
        self.conditions.push(format!("({}={})", attr.as_str(), escaped));
        self
    }
}

// 检查点3：所有方法是否一致
// 检查equal, like, greater等所有方法是否都转义
```

关键检查点：
- Builder的所有方法是否都转义值
- 属性名是否类型安全（枚举/const）
- 转义函数实现是否正确

## Classify

### 漏洞判定规则
- **明确漏洞**：查询构造器方法未转义值或属性名不受限
- **高危信号**：
  - 方法直接使用`format!()`拼接输入
  - 属性名参数类型为`&str`且无验证
  - trait实现未包含转义逻辑
- **误报排除**：
  - 所有方法内部调用转义函数
  - 属性名使用枚举或const
  - 文档明确说明已处理安全性

### 风险评估
- **高风险**：构造器被广泛使用且未转义
- **中风险**：部分方法有问题
- **低风险**：构造器正确实现转义

## Low risk

### 低风险评级的情形

1. **方法内部转义**
   - 所有方法内部调用`escape_ldap_filter()`
   - 对调用者透明

2. **属性名类型安全**
   - 使用枚举：`enum Attr { Uid, Cn, Mail }`
   - 编译时保证属性名安全

3. **泛型约束**
   - 使用trait约束确保值可安全转换：
   ```rust
   pub trait LdapSafe {
       fn to_ldap_safe(&self) -> String;
   }

   impl LdapFilter {
       pub fn equal<T: LdapSafe>(&mut self, attr: Attr, value: T) -> &mut Self {
           // ...
       }
   }
   ```

4. **文档和测试**
   - 文档明确说明转义已处理
   - 单元测试覆盖注入案例
