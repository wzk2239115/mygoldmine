# Rust Actix-web 资源获取 IDOR

## Details

**代码特征示例**

```rust
// 路径参数直接查询
async fn get_document(path: web::Path<i32>) -> Result<HttpResponse> {
    let doc_id = path.into_inner();
    let doc = Document::find_by_id(doc_id).await?;
    Ok(HttpResponse::Ok().json(doc))
}

// 查询参数直接使用
async fn download_file(Query(params): Query<HashMap<String, String>>) -> Result<HttpResponse> {
    let file_id = params.get("file_id").unwrap();
    let content = storage::read(file_id).await?;
    Ok(HttpResponse::Ok().body(content))
}
```

**快速定位核心操作** (L2:跳读)
- 关注路由处理器签名：`web::Path<T>`、`web::Query<T>`、`web::Json<T>` 提取ID参数
- 追踪ID流向：`path.into_inner()`、`query.id`、解构赋值后直接传入查询函数
- 数据库查询模式：`find_by_id()`、`get()`、`SELECT ... WHERE id = $1` 等直接根据ID查询操作
- 文件系统访问：`std::fs::read()`、`tokio::fs::File::open()`、S3 `get_object()` 使用用户输入路径

**快速定位保护机制** (L3:逐行读 + L4:跨模块追踪)
- 会话校验：处理器内是否提取 `session`、`Identity`、`jwt_claims` 等认证信息
- 所有权比对：是否存在 `doc.owner_id == current_user_id`、`belongs_to(user)` 等判断逻辑
- 中间件拦截：检查 `.wrap(Auth)` 等中间件，追踪其实现是否包含资源级授权（非仅身份认证）
- 数据库层面：查询条件是否同时包含 `id` 和 `user_id`，如 `WHERE id = $1 AND owner_id = $2`
- 权限框架：寻找 `casbin`、自定义 `authorize()` 函数调用，需跨模块确认是否对该资源类型生效

## Classify

**漏洞判定**：ID参数可控 + 数据查询成功即返回 + 无任何用户关联校验 = 确认IDOR

**误报排除**：
- 资源本身为公开性质（如公开文章、系统配置项），但需确认业务逻辑是否真的允许任意访问
- 认证中间件已限制登录用户，但仍需判断是否不同登录用户间可越权（水平越权）
- ID为不可枚举的随机令牌（UUID/哈希），降低利用难度但不消除漏洞本质

**代码异味**：
- 存在所有权检查但逻辑可绕过（如仅检查非空、类型匹配）
- 检查代码在错误处理分支，正常流程未覆盖
- 依赖前端传递的"权限标识"而非后端查库验证

## Low risk

- **已废弃接口**：路由在 `#[cfg(test)]` 或标注为 deprecated，生产环境未启用
- **读取受限敏感度低的数据**：如公开元数据、缓存统计信息等，业务影响有限
- **需配合其他高权限操作**：前置条件为管理员 session，普通用户无法触发漏洞路径
- **ID取值空间受业务严格限制**：如只能访问当天创建的记录，且结合日志监控能快速发现异常
- **响应已脱敏**：返回数据经过字段过滤（如用户手机号打码），实际泄露信息价值低
- **环境隔离**：仅内网访问接口，且网络层有严格访问控制（需结合部署架构评估）