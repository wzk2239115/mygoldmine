# Rust - Reqwest/Hyper 用户可控 URL 请求 SSRF

## 漏洞定位

**高危函数模式：**
- `reqwest::get(url_str)` / `reqwest::Client::new().get(url_str).send()`
- `Client::post(url_str).send()` / `Client::request(Method, url_str).send()`
- `hyper::Client::request(uri)` - 特别是 Hyper v0.x 版本
- `ureq::get(url)` 等轻量级 HTTP 库

**高风险数据来源：**
- 路由参数：Actix-web `Path<String>`、Axum `Path<String>` 提取
- 查询参数：`Query<T>` 动态解析、URL fragment（#）
- 请求体：JSON 反序列化后的字段、FormData
- 外部输入：Redis 缓存、数据库查询结果、消息队列

**核心检查点：**
1. **解析后验证**：`Url::parse()` 必须验证 `.host()`、`.port()`、`.scheme()`
2. **IP 范围验证**：IPv4 loopback（127.0.0.0/8）+ private（10.0.0.0/8、172.16.0.0/12、192.168.0.0/16）
3. **元数据服务**：AWS 169.254.169.254、GCP metadata.google.internal、Azure 168.63.129.16
4. **IPv6 覆盖**：::1/128、::ffff:0:0/96（IPv4-mapped）、fe80::/10（link-local）、fc00::/7（ULA）

## 审计技巧速查

### 识别真漏洞的关键信号

**必现漏洞：**
```rust
// ❌ 最危险：直接使用用户输入
let client = reqwest::Client::new();
let resp = client.get(&user_url).send()?;  // user_url 来自 query/path

// ❌ 有 parse 但无验证
let url = Url::parse(&user_input)?;
let resp = client.get(url).send()?;  // 只检查语法，未检查 host

// ❌ 不完整的 IP 验证
if !url.host_str().unwrap_or("").contains("127") {
    client.get(url).send()?;  // 绕过：127.0.0.2、127.255.255.255
}
```

**高危改造（看似安全但有绕过）：**
- `is_loopback()` 仅检查 127.0.0.1，错漏 127.0.0.0/8
- `is_private()` 漏掉 169.254.0.0/16 和元数据服务 IP
- DNS 重绑定：缓存 DNS 查询结果不更新
- 只验证 HTTP/HTTPS 但允许 `https://169.254.169.254/`

### 绕过技巧速记

| 绕过方式 | 示例 | 绕过原因 |
|--------|------|--------|
| @ 符号混淆 | `http://attacker.com@127.0.0.1` | 验证逻辑用字符串搜索而非 `host()` |
| IPv6 映射 | `http://[::ffff:127.0.0.1]` | 未检查 IPv4-mapped IPv6 地址 |
| 十进制 IP | `http://2130706433` | 127.0.0.1 = 0x7f000001 = 2130706433 |
| 八进制 IP | `http://0177.0.0.1` | Url::parse() 会正规化但验证漏掉 |
| Localhost 别名 | `http://localhost/`、`http://0.0.0.0/` | 验证 IP 但不验证域名别名 |
| URL 编码 | `http://127%2e0%2e0%2e1` | 验证前未 decode（Url::parse() 自动 decode） |
| 短 URL 跳转 | 申请短链指向 127.0.0.1 | 未验证重定向目标 |

## 常见的假漏洞陷阱

✗ Host 来自代码常量：`client.get("https://api.example.com")` - 即使路径可控也安全
✗ 完整白名单验证：先 `Url::parse()` 再与允许列表逐一对比
✗ 使用 `http::Uri` + 强制 HTTPS scheme check
✗ 显式检查：`url.scheme() == "https" && ALLOWED_HOSTS.contains(url.host())`

## 实战审计清单

**第一步：数据流追踪**
- [ ] 在 handler 中搜 `Path<String>`、`Query<_>`、`web::Json<_>` 是否直接用于 URL
- [ ] 追踪是否经过 Redis/DB，看缓存有无失效机制
- [ ] 检查 async 任务中是否有延迟的 URL 请求（DNS rebinding 窗口）

**第二步：验证逻辑审查**
- [ ] `Url::parse()` 是否存在？如无，直接确认漏洞
- [ ] 验证对象：是否检查 `.host_str()`、`.host()` 而非整体 URL 字符串
- [ ] IPv4 检查：包含 127.0.0.0/8、10.0.0.0/8、172.16.0.0/12、192.168.0.0/16、169.254.0.0/16 + 0.0.0.0、255.255.255.255
- [ ] IPv6 检查：::1、::ffff:0:0/96、fe80::/10、fc00::/7、ff00::/8
- [ ] 云服务元数据：169.254.169.254、metadata.google.internal、169.254.169.250（Azure IMDS）

**第三步：场景风险评估**
- [ ] 请求响应是否返回给用户？（直接泄露 → 高危）
- [ ] 是否写入数据库/日志？（间接泄露 → 中危）
- [ ] 是否执行 RCE（如 curl/wget URL）？（超危）
- [ ] 网络隔离情况？（K8s NetworkPolicy 禁止则可降级）

## 风险降级要点

仅当**全部满足**以下任一条件时考虑降级：

- **绝对隔离**：K8s NetworkPolicy egress 明确禁止目标、VPC 无路由、iptables 规则锁死
- **硬编码 Host**：URL 构造为 `format!("https://api.example.com/webhook?url={}", user_id)`，host 无法改变
- **强制白名单**：代码级白名单（非配置文件）且枚举所有允许域名
- **被动操作**：非仅 GET、POST 查询操作，无 DELETE/PATCH，数据只读
- **完整审计日志**：所有 HTTP 请求记录且可追溯用户身份和源 IP

## 代码行为分析

当发现验证代码时，优先关注这些**常见的疏漏点**：
- 验证发生在 `.send()` 后（无用）
- 使用了 `contains("127")` 这类字符串匹配（绕过：127.255.255.255）
- IPv6 验证使用 string 而非 `IpAddr` 解析
- 没有处理 DNS 重绑定或 TOCTOU 竞态