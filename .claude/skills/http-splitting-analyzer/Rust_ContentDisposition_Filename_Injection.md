# Rust Content-Disposition 文件名注入

## Details

**审计等级：L1（关键词扫描）/ L2（跳读）**

**危险函数特征：**
- `response.insert_header(("Content-Disposition", value))` 直接设置
- 文件名直接拼接进头值
- 从文件系统或用户输入读取文件名

**快速定位核心操作：**
1. 搜索关键字：`Content-Disposition`、`filename=`、`insert_header`
2. 追踪文件名来源：`web::Query`、`web::Form`、文件系统
3. 检查是否使用双引号
4. 查看是否过滤特殊字符

**快速定位保护机制：**
- 特殊字符过滤：`value.contains(|c: char| c == ';' || c == ',')`
- 双引号转义：`value.replace('"', "\"")`
- 白名单验证：正则表达式检查
- RFC 5987 编码：使用标准编码

**代码示例：**
```rust
// 危险：用户文件名直接用于下载
async fn download(Query(params): Query<HashMap<String, String>>) -> impl Responder {
    let filename = params.get("file").unwrap_or(&"file".to_string());
    let header_value = format!("attachment; filename={}", filename);
    HttpResponse::Ok()
        .insert_header(("Content-Disposition", header_value.as_str()))  // 危险
        .finish()
}

// 危险：Form 参数
async fn export(Form(data): Form<ExportData>) -> impl Responder {
    let header = format!("attachment; filename={}", data.name);
    HttpResponse::Ok()
        .insert_header(("Content-Disposition", header.as_str()))  // 危险
        .finish()
}

// 危险：路径参数
async fn file(web::Path(name): web::Path<String>) -> impl Responder {
    let header = format!("attachment; filename={}", name);
    HttpResponse::Ok()
        .insert_header(("Content-Disposition", header.as_str()))  // 危险
        .finish()
}
```

## Classify

**漏洞（High）：**
- 用户文件名未验证
- 文件名包含特殊字符导致头分割
- 允许目录遍历

**误报：**
- 文件名硬编码
- 经过白名单验证
- 使用安全方法

**代码异味（Medium）：**
- 仅过滤部分字符
- 黑名单不完整
- 间接来源

## Low risk

**以下情况评为低风险：**
- 文件名硬编码
- 严格白名单验证
- RFC 合规编码
- 内部来源且已验证

## 审计专业技巧

### 1. 真实漏洞的三层识别

**第一层：直接拼接识别**
```rust
// 真实漏洞：格式字符串直接拼接，无任何验证
let filename = params.get("filename").unwrap();
let value = format!("attachment; filename={}", filename);  // 危险信号：format!直接使用
```
审计要点：寻找 `format!()` 或字符串拼接后直接用于 `insert_header`

**第二层：绕过识别**
```rust
// 真实漏洞：只过滤分号，攻击者可用其他字符
if !filename.contains(';') {  // 不完整的黑名单
    let value = format!("attachment; filename={}", filename);
    // 逗号、换行符、制表符仍可用于注入
}
```
审计要点：识别不完整的黑名单（只过滤单一字符）

**第三层：间接拼接识别**
```rust
// 真实漏洞：在保存前未验证，取出时才拼接
let filename = db.get_user_filename(id);  // 假设用户曾注入数据
let value = format!("attachment; filename={}", filename);
```
审计要点：追踪数据源，即使代码看似安全，污染源也要追溯

### 2. 常见误报情况与区分

**误报Case1：白名单验证（不是漏洞）**
```rust
// 这不是漏洞
let allowed_files = vec!["report.pdf", "data.xlsx", "archive.zip"];
if allowed_files.contains(&filename.as_str()) {
    let value = format!("attachment; filename={}", filename);
    // 白名单验证确保只有预定义文件名
}
```
判断标准：
- 使用明确的白名单数组或集合
- 文件名必须完全匹配（contains/equals检查）
- 在拼接前完成验证

**误报Case2：强制转义（RFC 5987）**
```rust
// 这不是漏洞
fn sanitize_filename(name: &str) -> String {
    if name.contains(|c| c == ';' || c == ',' || c == '\n' || c == '\r' || c == '"') {
        format!("attachment; filename*=UTF-8''{}",
                urlencoding::encode(name))
    } else {
        format!("attachment; filename=\"{}\"", name)
    }
}
```
判断标准：
- 过滤包含常见HTTP头分割字符：`;`, `,`, `\n`, `\r`
- 对特殊字符进行URL编码或转义
- 使用 RFC 5987 编码标准

**误报Case3：硬编码文件名**
```rust
// 这不是漏洞
async fn download_report(id: i32) -> impl Responder {
    let filename = "annual_report.pdf";  // 硬编码
    let value = format!("attachment; filename={}", filename);
}
```
判断标准：文件名来自常量或硬编码字符串，不从用户输入获取

### 3. 审计工作流程

**第一步：污染源识别**
```
用户输入源识别 → Query/Form/Path/Json参数 → 跨越函数调用追踪
```

**第二步：转移路径检查**
- 是否经过验证函数？（regex、白名单、split验证）
- 是否在数据库中往返？（往往导致审计遗漏）
- 是否有间接引用？（通过另一个参数间接获取）

**第三步：输出验证**
在 `insert_header` 调用前检查：
- 是否进行了多层验证？
- 验证逻辑是否正确？
- 是否有编码/转义？

### 4. 易被遗漏的变体

**变体1：动态文件名但来自内部列表**
```rust
// 看似危险，实际安全（需确认userfiles真实来源）
let userfiles = vec!["user_profile.json", "preferences.txt"];
let filename = userfiles.get(index)?;
let value = format!("attachment; filename={}", filename);
// ✓ 安全：内部列表维护，用户只控制index
```

**变体2：部分路径可控**
```rust
// 真实漏洞：允许目录遍历拼接
let dir = "downloads/";
let filename = params.get("file")?;
let path = format!("{}{}", dir, filename);  // "../../../etc/passwd"
let value = format!("attachment; filename={}", filename);
// ✗ 危险：虽然头值来自用户输入，但目录遍历也是问题
```

**变体3：多步骤验证但漏了一步**
```rust
// 真实漏洞：数据库验证后，再次动态拼接
let filename = sanitize(user_input);  // 第一次验证
let db_filename = db.save_file(&filename)?;
let retrieved = db.get_filename(id)?;  // 从DB取出
let value = format!("attachment; filename={}", retrieved);
// ✗ 危险：DB中的数据可能被其他流程污染
```

### 5. 快速判定表

| 代码模式 | 信号 | 判定 |
|---------|------|------|
| `format!(..., user_param)` + `insert_header` | 直接拼接 | 真实漏洞 |
| `contains(';')` 检查 | 不完整黑名单 | 代码异味 |
| 白名单数组 + 完全匹配 | 列表验证 | 误报 |
| 硬编码字符串 | 无用户输入 | 误报 |
| RFC 5987 编码 | 标准编码 | 误报 |
| 正则表达式验证 + 编码 | 双重防护 | 误报 |
| 来自DB但源头不可控 | 间接污染 | 真实漏洞 |

### 6. 审计建议

1. **优先级排序**：直接 Query/Form 参数 > 路径参数 > DB查询 > 文件系统
2. **全链路追踪**：不要只看拼接点，要追踪数据来源
3. **验证完整性**：黑名单必须包含 `;`, `,`, `\n`, `\r`, `"`
4. **编码检查**：如有编码，确认是URL编码还是转义编码
5. **多文件关联**：参数在多个地方使用，都要检查
