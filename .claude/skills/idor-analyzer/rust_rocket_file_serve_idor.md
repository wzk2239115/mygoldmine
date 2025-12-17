# Rust Rocket 文件服务 IDOR 漏洞审计

## Details

**代码特征示例**

```rust
// 路径参数直接提供文件服务
#[get("/download/<filename>")]
fn download_file(filename: String) -> Option<NamedFile> {
    NamedFile::open(Path::new("uploads/").join(filename)).ok()
}

// 多段路径参数拼接
#[get("/files/<path..>")]
fn serve_file(path: PathBuf) -> Option<NamedFile> {
    NamedFile::open(Path::new("storage/").join(&path)).ok()
}

// 查询参数获取文件
#[get("/resource?<file_id>")]
fn get_resource(file_id: i32, conn: DbConn) -> Option<File> {
    files::table.find(file_id).first::<File>(&*conn).ok()
}

// 数据库查询后提供文件
#[get("/doc/<doc_id>")]
fn serve_document(doc_id: i32, conn: DbConn) -> Option<NamedFile> {
    let doc = documents::table.find(doc_id).first::<Document>(&*conn).ok()?;
    NamedFile::open(&doc.file_path).ok()
}

// JSON响应返回文件信息
#[get("/api/attachment/<id>")]
fn get_attachment(id: i32, conn: DbConn) -> Json<Attachment> {
    let attachment = attachments::table.find(id).first(&*conn).unwrap();
    Json(attachment)
}
```

**快速定位核心操作** (L2:跳读)
- **路由宏参数**：`#[get("/<param>")]`、`#[post("/<id>")]` 等路由宏中的动态段提取ID/文件名
- **参数类型提取**：`String`、`PathBuf`、`i32`、`i64` 等直接接收路径段或查询参数
- **查询参数**：函数签名中的 `file_id: Type` 自动解析query string
- **文件操作函数**：
  - `NamedFile::open()`、`File::open()`、`std::fs::read()`
  - `Path::new().join()` 路径拼接操作
  - `PathBuf` 类型的路径变量直接使用
- **数据库查询**：
  - Diesel ORM：`.find(id)`、`.filter(files::id.eq(id))`
  - 原生SQL：`query!("SELECT * FROM files WHERE id = $1", id)`
  - 未包含用户过滤条件的查询
- **响应类型**：`NamedFile`、`File`、`Vec<u8>`、`Stream` 等文件内容返回

**快速定位保护机制** (L3:逐行读 + L4:跨模块追踪)
- **请求守卫（Request Guard）**：
  - 函数参数中是否有自定义守卫：`user: AuthUser`、`_auth: AdminGuard`
  - 守卫实现是否仅验证身份而非资源所有权
- **所有权验证逻辑**：
  - 文件记录查询后是否比对：`file.owner_id == user.id`、`doc.user_id != current_user`
  - 返回前的条件判断：`if`/`match` 分支进行权限检查
- **Diesel关联查询**：
  - 查询条件是否同时包含：`.filter(files::id.eq(id).and(files::user_id.eq(uid)))`
  - 是否通过 `inner_join` 关联用户表限制可见性
- **Fairings（全局中间件）**：
  - `.attach()` 附加的中间件，追踪其 `on_request()` 实现是否包含资源级ACL
  - 检查是否仅做认证而无授权
- **响应错误处理**：
  - `Option<T>` 返回 `None` 时是否先验证权限（避免信息泄露）
  - `Result<T, E>` 错误类型是否区分"不存在"与"无权限"
- **路径规范化**：
  - `canonicalize()` 使用但仅防路径遍历，未验证用户权限
  - `starts_with()` 检查路径前缀但无所有权检查

## Classify

**漏洞判定**：路由参数/查询参数直接用于文件访问或数据库查询 + 无任何用户身份关联校验 + 返回文件内容/敏感数据 = 确认IDOR

**误报排除**：
- 文件存储路径为公共静态资源目录（如 `static/`、`public/`），业务逻辑允许匿名访问
- 存在有效的Request Guard提取当前用户，且数据库查询强制包含 `user_id` 过滤条件
- 文件名/ID为不可预测的加密token或UUID（需超过128位且无枚举接口），并在后端验证token与用户绑定关系
- Fairing中间件已实现细粒度资源授权，且通过单元测试确认对该路由生效

**代码异味**：
- 存在Request Guard但仅提取用户信息，后续未使用该信息进行权限比对
- 所有权检查位于错误分支或可选逻辑路径（如 `if let Some(user) = maybe_user`），主流程可绕过
- 使用 `unwrap()` 或 `expect()` 直接解包查询结果，错误时panic而非返回403
- 权限判断依赖客户端传递的header参数（如 `X-User-ID`）而非服务端session/JWT验证
- 路径安全检查仅调用 `canonicalize()` 防路径遍历，但未限制用户只能访问自己的文件
- 返回 `Option::None` 时不区分资源不存在与无权限，可能泄露资源存在性信息

## Low Risk

- **测试/调试路由**：被 `#[cfg(debug_assertions)]` 或 `#[cfg(test)]` 条件编译限制，生产环境未编译
- **公开资源端点**：业务明确设计为公开文件分享，如临时下载链接、公共文档库
- **高熵ID设计**：文件ID为256位随机哈希且无关联接口可枚举，利用成本极高
- **脱敏响应数据**：返回的文件经过水印、压缩或仅返回元数据（文件名、大小），敏感内容未泄露
- **补偿控制机制**：
  - 文件访问记录完整审计日志，异常行为可实时告警
  - 下载需消耗业务凭证（积分、验证码），有效限制批量利用
  - 存储层（S3/OSS）已配置细粒度ACL，后端仅签发短效临时URL
- **内网隔离环境**：服务仅监听内网地址，网络层有严格访问控制（需结合部署架构评估）
- **低敏感度数据**：文件内容为系统模板、示例数据、已公开的文档副本，泄露无业务影响
- **访问速率限制**：Fairing实现严格的IP/用户级别限流，且配合WAF规则防止暴力枚举