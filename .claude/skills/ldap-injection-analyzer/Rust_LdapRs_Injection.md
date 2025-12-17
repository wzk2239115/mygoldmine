# Rust ldap-rs 注入

## Details

### 代码示例
使用`ldap-rs` crate时的注入风险：

```rust
// 注意：ldap-rs是假设的crate名，实际可能不同
use ldap_rs::{Ldap, SearchScope};

// 危险示例1：基本过滤器拼接
async fn search_user(username: &str) -> Result<Vec<Entry>, Error> {
    let ldap = Ldap::connect("ldap://localhost").await?;

    // 危险：format!拼接
    let filter = format!("(uid={})", username);

    let results = ldap.search("dc=example,dc=com", SearchScope::Sub, &filter).await?;
    Ok(results)
}

// 危险示例2：Axum handler中的注入
use axum::{extract::Query, Json};
use serde::Deserialize;

#[derive(Deserialize)]
struct SearchParams {
    username: String,
    department: String,
}

async fn search_handler(Query(params): Query<SearchParams>) -> Json<Vec<String>> {
    // 危险：直接使用用户输入
    let filter = format!("(&(uid={})(department={}))",
                         params.username, params.department);

    let ldap = Ldap::connect("ldap://localhost").await.unwrap();
    let results = ldap.search("dc=example,dc=com", SearchScope::Sub, &filter)
        .await.unwrap();

    Json(results.into_iter().map(|e| e.dn).collect())
}

// 危险示例3：Builder模式但未转义
struct LdapQueryBuilder {
    filters: Vec<String>,
}

impl LdapQueryBuilder {
    fn new() -> Self {
        Self { filters: Vec::new() }
    }

    fn add_condition(&mut self, attr: &str, value: &str) -> &mut Self {
        // 危险：value未转义
        self.filters.push(format!("({}={})", attr, value));
        self
    }

    fn build(&self) -> String {
        format!("(&{})", self.filters.join(""))
    }
}

// 危险示例4：使用宏简化但仍不安全
macro_rules! ldap_filter {
    ($attr:expr, $value:expr) => {
        format!("({}={})", $attr, $value)  // 危险：宏不会转义
    };
}

fn search_with_macro(uid: &str) -> String {
    ldap_filter!("uid", uid)  // 危险
}
```

### 快速定位核心操作的技巧
**L1：关键词扫描** - 搜索以下特征：
- `use ldap_rs::*` 或类似ldap crate
- `.search()`, `.connect()`, `.bind()` 方法
- `format!()`, `to_string()`, `String::from()`
- `Query`, `Json` 提取器（Axum/Actix）
- `struct *Builder`, `impl *Builder`

重点检查文件：
```
src/ldap/*.rs
src/api/handlers.rs
src/services/auth.rs
src/utils/filter_builder.rs
```

### 快速定位保护机制的技巧
**L2：跳读** - 检查防护迹象：
- 自定义`escape_*`函数
- `validator` crate使用
- `lazy_static!`定义的正则或白名单
- Builder的方法是否有验证逻辑

**L3：逐行读** - 验证防护完整性：
```rust
// 检查点1：转义函数实现
fn escape_ldap_filter(input: &str) -> String {
    input.chars()
         .flat_map(|c| match c {
             '*' => vec!['\\', '2', 'a'],
             '(' => vec!['\\', '2', '8'],
             ')' => vec!['\\', '2', '9'],
             '\\' => vec!['\\', '5', 'c'],
             '\0' => vec!['\\', '0', '0'],
             _ => vec![c],
         })
         .collect()
}

// 检查点2：Builder是否转义
impl LdapQueryBuilder {
    fn add_condition(&mut self, attr: &str, value: &str) -> &mut Self {
        let escaped = escape_ldap_filter(value);  // 转义
        // 但attr未验证！
        self.filters.push(format!("({}={})", attr, escaped));
        self
    }
}

// 检查点3：宏是否安全
macro_rules! safe_ldap_filter {
    ($attr:expr, $value:expr) => {
        format!("({}={})", $attr, escape_ldap_filter($value))
    };
}
```

关键检查点：
- 转义函数是否正确实现（十六进制转义）
- Builder方法是否调用转义
- 宏定义是否包含转义逻辑

## Classify

### 漏洞判定规则
- **明确漏洞**：LDAP过滤器使用`format!()`直接拼接用户输入
- **高危信号**：
  - web提取器（Query/Json）直接用于过滤器
  - Builder模式未转义值
  - 宏不包含转义逻辑
- **误报排除**：
  - 所有值经过转义函数
  - 使用`validator` crate验证
  - 属性名使用枚举或const

### 风险评估
- **高风险**：认证相关的注入
- **中风险**：搜索API注入
- **低风险**：仅只读，范围受限

## Low risk

### 低风险评级的情形

1. **Validator验证**
   - 使用`#[validate(regex = "^[a-zA-Z0-9]+$")]`
   - 输入验证失败返回400错误

2. **类型安全的属性名**
   - 使用枚举而非&str：
   ```rust
   enum Attr {
       Uid,
       Cn,
   }
   ```

3. **Builder内部转义**
   - Builder的所有方法内部调用转义
   - 对外API透明处理

4. **只读操作**
   - 仅search，无modify/add
