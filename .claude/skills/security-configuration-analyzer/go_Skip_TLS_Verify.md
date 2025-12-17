# Go - Skip TLS Verify

## Details

### 代码示例

**场景1：http.Client 跳过证书验证**
```go
tr := &http.Transport{
    TLSClientConfig: &tls.Config{
        InsecureSkipVerify: true,  // 危险：跳过所有证书验证
    },
}
client := &http.Client{Transport: tr}
resp, _ := client.Get("https://example.com")
```

**场景2：全局 http.DefaultTransport 污染**
```go
http.DefaultTransport.(*http.Transport).TLSClientConfig = &tls.Config{
    InsecureSkipVerify: true,  // 危险：影响所有后续 http 请求
}
```

**场景3：gRPC 连接跳过验证**
```go
creds := credentials.NewTLS(&tls.Config{
    InsecureSkipVerify: true,
})
conn, _ := grpc.Dial("server:443", grpc.WithTransportCredentials(creds))
```

**场景4：net/http.Server 禁用客户端证书验证（mTLS）**
```go
server := &http.Server{
    TLSConfig: &tls.Config{
        ClientAuth: tls.NoClientCert,  // 危险：不验证客户端证书
    },
}
```

**场景5：webhook/callback 场景**
```go
// 调用第三方 webhook 时跳过验证
func callWebhook(url string, data []byte) error {
    client := &http.Client{
        Transport: &http.Transport{
            TLSClientConfig: &tls.Config{InsecureSkipVerify: true},
        },
    }
    // ...
}
```

**场景6：条件判断伪装的跳过**
```go
skipVerify := os.Getenv("SKIP_TLS") == "true"
tlsConfig := &tls.Config{
    InsecureSkipVerify: skipVerify,  // 危险：可通过环境变量控制
}
```

### 快速定位核心操作的技巧

**（L1：关键词扫描）**
- 核心字段：`InsecureSkipVerify`、`ClientAuth`、`NoClientCert`
- 配置结构：`tls.Config{`、`TLSClientConfig:`、`TLSConfig:`
- 传输层：`http.Transport`、`http.DefaultTransport`、`grpc.Dial`
- 环境变量：`SKIP_TLS`、`INSECURE`、`NO_VERIFY`

**（L2：跳读）**
- HTTP 客户端初始化：`NewClient`、`makeHTTPClient`、`setupTransport` 函数
- 全局变量赋值：`var defaultClient`、`init()` 函数中的 Transport 配置
- 第三方库封装：查看 `resty`、`req`、`sling` 等库的配置调用
- 条件分支：`if debug`、`if dev`、`if !production` 内的 TLS 设置

**（L3：逐行读）**
- 结构体字面量：检查 `tls.Config{}` 完整初始化，确认 `InsecureSkipVerify` 是否显式设置为 `false`
- 函数参数传递：追踪 `tlsConfig *tls.Config` 参数从何处传入
- 默认值陷阱：Go 零值为 `false`，确认是否依赖默认行为还是显式配置
- 错误处理：证书验证失败后是否有重试逻辑或降级为跳过验证

**（L4：跨模块追踪）**
- 配置中心加载：检查从 Consul、etcd 读取的配置是否包含 `skip_tls_verify` 字段
- 依赖注入：框架（如 Wire、Dig）注入的 HTTP 客户端配置来源
- 中间层封装：自定义 HTTPClient 包装是否隐藏了底层 TLS 配置
- 动态代理：查看 HTTP 代理设置是否影响证书验证行为

### 快速定位保护机制的技巧

**（L1：关键词扫描）**
- 正向验证：`VerifyPeerCertificate`、`RootCAs`、`x509.SystemCertPool()`
- 主机名验证：`ServerName`、`VerifyConnection`
- 证书固定：`Certificates`、`GetCertificate`、`GetClientCertificate`
- 强制配置：`MinVersion: tls.VersionTLS12`、`CipherSuites`

**（L2：跳读）**
- 检查 `tls.Config` 是否配置 `RootCAs`（自定义可信 CA 列表）
- 确认 `ServerName` 字段是否设置（用于 SNI 和主机名验证）
- 查找 `VerifyPeerCertificate` 回调函数实现
- 验证 `MinVersion` 是否至少为 `tls.VersionTLS12`

**（L3：逐行读）**
- 回调函数体：`VerifyPeerCertificate` 内是否执行实际验证逻辑（如证书固定、自定义检查）
- 证书链解析：是否调用 `x509.Certificate.Verify()` 方法
- 错误处理：证书验证失败是否正确返回错误并终止连接
- 日志记录：是否记录证书信息用于审计

**（L4：跨模块追踪）**
- 证书管理模块：检查证书更新、轮换机制是否与 TLS 配置同步
- 环境隔离：开发/测试/生产环境的证书配置是否独立管理
- 配置优先级：多处 TLS 配置存在时，最终生效的配置来源
- 运行时切换：是否存在热更新配置导致安全配置被覆盖

**（L0：快速跳过）**
- 测试文件：`*_test.go` 中的 Mock HTTP Server 配置
- 示例代码：`examples/`、`docs/` 目录中的演示代码
- 供应商代码：`vendor/` 目录中第三方库的内部实现

## Classify

### 确认为漏洞的判定标准
- **生产环境**代码中硬编码 `InsecureSkipVerify: true`，无条件分支保护
- 调用外部 HTTPS API 时跳过验证，可能遭受中间人攻击
- 修改全局 `http.DefaultTransport`，影响整个应用所有 HTTP 请求
- mTLS 场景中使用 `NoClientCert`，但业务逻辑依赖客户端身份认证
- 环境变量控制跳过验证且默认值为 `true` 或缺少访问控制

### 误报的常见场景
- **单元测试**中使用 `httptest.NewTLSServer()` 的自签名证书，仅限测试范围
- 内网服务间通信使用自签名证书，但通过其他机制（如 IP 白名单、证书固定）保护
- 示例代码或文档中的演示配置，明确标注"仅供参考"
- 已通过 build tag（如 `//go:build !production`）隔离到非生产构建
- 代码注释掉或位于 `if false` 等永不执行的分支

### 代码异味的判定
- 使用环境变量控制但缺少默认安全配置（应默认 `false`）
- 通过配置文件读取 `skip_verify` 但无强制校验或告警机制
- 仅在开发环境跳过验证，但环境判断逻辑不严密（如仅依赖主机名判断）
- 存在 TODO/FIXME 注释说明"临时跳过"，但已存在超过合理期限
- 跳过验证的同时未实现 `VerifyPeerCertificate` 等补偿措施

### 研判流程
1. **确认作用域**：该 TLS 配置影响的连接范围（单次请求/全局客户端/所有连接）
2. **评估敏感度**：传输数据类型（认证凭据/敏感业务数据/公开信息）
3. **检查网络环境**：是否为内网隔离环境，外部是否可达
4. **追溯配置来源**：硬编码/环境变量/配置文件/配置中心，默认值是什么
5. **验证运行环境**：通过部署配置、容器镜像、CI/CD 流程确认实际部署状态
6. **代码历史分析**：`git log -S InsecureSkipVerify` 追溯引入时间和修改记录

## Low Risk

### 低风险场景评级标准

**场景1：完全隔离的测试环境**
- 仅在 `*_test.go` 文件中使用，配合 `httptest.NewTLSServer()`
- 测试代码明确标注 `// Testing only`，不可能编译到生产二进制
- 使用 build constraint（`//go:build test`）限制编译范围
- CI/CD 流水线中一次性容器环境，每次运行后销毁

**场景2：私有网络内部通信**
- 物理隔离内网（无互联网访问），服务间通信使用自签名证书
- 容器编排平台（K8s/Service Mesh）统一管理证书，应用层仅处理加密传输
- 存在网络策略（NetworkPolicy）限制 Pod 间通信，且有 mTLS 补偿
- VPN/专线环境，通信双方身份已通过其他机制（如 IP 白名单 + API Key）验证

**场景3：公开非敏感资源访问**
- 仅用于下载公开内容（CDN 静态资源、公共 API 数据）
- 数据本身已有应用层签名验证（如 GPG 签名、SHA256 校验）
- 失败后不影响核心业务，且有降级策略或重试机制
- 用户主动配置 `--insecure` 参数（如开发工具、CLI 客户端）

**场景4：补偿控制存在**
- 虽跳过系统验证，但实现了 `VerifyPeerCertificate` 自定义证书固定
- 通过证书指纹白名单限制可信证书范围
- 数据传输层加密外，应用层再次加密敏感字段
- 所有连接记录完整审计日志（源/目标 IP、证书指纹、时间戳）

**场景5：动态生成的临时配置**
- 开发环境容器启动时生成自签名证书并在本地配置信任
- 短生命周期场景（如临时调试工具，运行后立即退出）
- 配置有自动过期机制（如 24 小时后强制启用验证）
- 明确的功能开关管理，变更需要管理员审批

**评级升级条件（需提升风险等级）**
- 即使内网环境，但处理高敏感数据（PII、支付信息、密钥）
- 跳过验证的代码路径可被外部输入触发（如 URL 参数控制）
- 配置文件或环境变量可被非管理员用户修改
- 缺少监控告警，无法检测异常 TLS 连接行为
- 代码注释表明"临时方案"但已存在超过 6 个月且无改进计划
