# Rust ldap3 过滤器拼接

## Details

### 代码示例
Rust `ldap3` crate虽然有所有权系统，但字符串拼接仍可能引入注入：

```rust
use ldap3::{LdapConn, Scope, SearchEntry};

// 危险示例1：format!宏拼接
fn authenticate(username: &str, password: &str) -> Result<bool, Box<dyn std::error::Error>> {
    let mut ldap = LdapConn::new("ldap://localhost:389")?;

    // 危险：format!直接拼接
    let filter = format!("(&(uid={})(userPassword={}))", username, password);

    let (rs, _res) = ldap.search(
        "dc=example,dc=com",
        Scope::Subtree,
        &filter,
        vec!["dn"]
    )?.success()?;

    Ok(!rs.is_empty())
}

// 危险示例2：使用String拼接
fn search_users(name: &str, dept: &str) -> Result<Vec<SearchEntry>, Box<dyn std::error::Error>> {
    let mut ldap = LdapConn::new("ldap://localhost:389")?;

    // 危险：String拼接
    let filter = "(&(cn=*".to_string() + name + "*)(department=" + dept + "))";

    let (rs, _res) = ldap.search(
        "dc=example,dc=com",
        Scope::Subtree,
        &filter,
        vec!["dn", "cn", "mail"]
    )?.success()?;

    Ok(rs.into_iter().map(SearchEntry::construct).collect())
}

// 危险示例3：Actix-web handler中的注入
use actix_web::{web, HttpResponse};

async fn search_handler(query: web::Query<HashMap<String, String>>) -> HttpResponse {
    let username = query.get("username").unwrap_or(&"".to_string());

    // 危险：直接使用用户输入
    let filter = format!("(uid={})", username);

    let mut ldap = LdapConn::new("ldap://localhost:389").unwrap();
    let (rs, _res) = ldap.search("dc=example,dc=com", Scope::Subtree, &filter, vec!["*"])
        .unwrap().success().unwrap();

    HttpResponse::Ok().json(rs)
}

// 危险示例4：动态构造过滤器
fn build_filter(criteria: &HashMap<String, String>) -> String {
    let mut parts = Vec::new();

    for (key, value) in criteria {
        // 危险：key和value都未转义
        parts.push(format!("({}={})", key, value));
    }

    format!("(&{})", parts.join(""))
}
```

### 快速定位核心操作的技巧
**L1：关键词扫描** - 搜索以下特征：
- `use ldap3::*`, `LdapConn::new()`
- `.search()`, `.bind()` 方法
- `format!()`, `to_string()`, `+` 字符串拼接
- `web::Query`, `web::Json` Actix-web提取器
- `axum::extract::Query` Axum提取器

重点检查文件：
```
src/ldap/client.rs
src/handlers/auth.rs
src/services/directory.rs
src/utils/ldap_filter.rs
```

### 快速定位保护机制的技巧
**L2：跳读** - 检查防护迹象：
- `ldap3::ldap_escape()` 函数（如果存在）
- 自定义`escape_filter()`函数
- 使用`regex::Regex`验证输入
- 使用`validator` crate验证

**L3：逐行读** - 验证防护完整性：
```rust
// 检查点1：是否有自定义转义函数
fn escape_ldap_filter(input: &str) -> String {
    input.replace('*', "\\*")
         .replace('(', "\\(")
         .replace(')', "\\)")
         .replace('\\', "\\\\")
         .replace('\0', "\\00")
}

// 检查点2：是否所有输入都转义
let safe_username = escape_ldap_filter(username);
let dept = department;  // 未转义！
let filter = format!("(&(uid={})(dept={}))", safe_username, dept);

// 检查点3：属性名是否白名单验证
const ALLOWED_ATTRS: &[&str] = &["uid", "cn", "mail"];

if !ALLOWED_ATTRS.contains(&attr.as_str()) {
    return Err("Invalid attribute");
}
```

关键检查点：
- 过滤器字符串中的所有动态部分
- 是否存在转义函数及其实现
- 属性名是否来自用户输入

## Classify

### 漏洞判定规则
- **明确漏洞**：`.search()`的filter参数使用`format!()`直接拼接用户输入
- **高危信号**：
  - web handler中直接使用查询参数
  - `format!()`或`+`拼接用户输入
  - HashMap遍历构造过滤器
- **误报排除**：
  - 使用转义函数处理所有输入
  - 输入经过`validator` crate验证
  - 属性名使用`const`或白名单

### 风险评估
- **高风险**：认证handler中的注入
- **中风险**：搜索API的注入
- **低风险**：仅只读，返回字段受限

## Low risk

### 低风险评级的情形

1. **使用validator验证**
   - 使用`validator` crate的`#[validate]`属性
   - 输入验证规则：`#[validate(regex = "^[a-zA-Z0-9]+$")]`

2. **属性名类型安全**
   - 使用枚举而非String：
   ```rust
   enum LdapAttr {
       Uid,
       Cn,
       Mail,
   }
   impl LdapAttr {
       fn as_str(&self) -> &str {
           match self {
               Self::Uid => "uid",
               Self::Cn => "cn",
               Self::Mail => "mail",
           }
       }
   }
   ```

3. **转义函数正确实现**
   - 所有值经过`escape_ldap_filter()`
   - 函数正确转义所有元字符

4. **只读操作**
   - 仅search，无bind/add/modify
