# C/C++ 不安全 TLS 配置

## Details

### 代码示例

**典型不安全配置模式：**

```cpp
// 1. 禁用证书验证
SSL_CTX_set_verify(ctx, SSL_VERIFY_NONE, NULL);

// 2. 接受任何证书（回调直接返回1）
SSL_CTX_set_verify(ctx, SSL_VERIFY_PEER, [](int, X509_STORE_CTX*){ return 1; });

// 3. 使用弱加密套件
SSL_CTX_set_cipher_list(ctx, "DES-CBC3-SHA:RC4");

// 4. 禁用主机名验证
SSL_set_hostflags(ssl, X509_CHECK_FLAG_NO_WILDCARDS);
X509_VERIFY_PARAM_set1_host(param, hostname, 0);  // 未调用或注释掉

// 5. 强制使用过时协议
SSL_CTX_set_min_proto_version(ctx, SSL_3_VERSION);
SSL_CTX_set_max_proto_version(ctx, TLS1_VERSION);

// 6. OpenSSL选项标志
SSL_CTX_set_options(ctx, SSL_OP_NO_TLSv1_3 | SSL_OP_NO_TLSv1_2);

// 7. CURL库配置
curl_easy_setopt(curl, CURLOPT_SSL_VERIFYPEER, 0L);
curl_easy_setopt(curl, CURLOPT_SSL_VERIFYHOST, 0L);

// 8. Boost.Asio配置
ssl_context.set_verify_mode(boost::asio::ssl::verify_none);

// 9. 自签名证书无验证加载
SSL_CTX_load_verify_locations(ctx, NULL, NULL);  // 未加载可信CA
```

### 快速定位核心操作技巧

**【L1：关键词扫描】** 全局搜索以下函数/宏：
- `SSL_CTX_set_verify`、`SSL_set_verify` + `SSL_VERIFY_NONE`
- `CURLOPT_SSL_VERIFYPEER`、`CURLOPT_SSL_VERIFYHOST`
- `set_verify_mode` + `verify_none`
- `SSL_CTX_set_cipher_list` + 弱套件（`DES`/`RC4`/`MD5`/`EXPORT`）
- `SSL_CTX_set_min_proto_version` + `SSL_3_VERSION`/`TLS1_VERSION`
- `X509_VERIFY_PARAM_set1_host`（关注是否缺失）

**【L2：跳读】** 重点扫描：
- 网络初始化函数：`init_ssl`、`setup_tls`、`create_context`
- 配置读取处理：`config.tls_verify`、`enable_ssl_check`
- 条件编译块：`#ifdef DEBUG`、`#ifndef PRODUCTION` 内的TLS设置
- 回调函数：verify_callback 实现是否直接 `return 1` 或 `return preverify_ok`

**【L3：逐行读】** 精细检查：
- `SSL_CTX_set_verify` 第二参数是否为回调函数指针，追踪回调实现
- `SSL_CTX_load_verify_locations` 是否传入有效CA证书路径
- `SSL_get_peer_certificate` 后是否进行 `X509_verify_cert` 调用
- 错误处理分支：证书验证失败后是否仍继续连接

### 快速定位保护机制技巧

**【L2：跳读】** 寻找防护代码：
- `SSL_CTX_set_verify` 第一参数为 `SSL_VERIFY_PEER | SSL_VERIFY_FAIL_IF_NO_PEER_CERT`
- `SSL_CTX_set_cipher_list` 配置现代套件（`ECDHE`/`AES_GCM`/`CHACHA20`）
- `SSL_CTX_set_min_proto_version(ctx, TLS1_2_VERSION)` 或更高
- `X509_VERIFY_PARAM_set1_host` 明确调用且传入正确主机名

**【L3：逐行读】** 验证保护完整性：
- verify_callback 函数体：是否检查 `X509_STORE_CTX_get_error` 返回值
- 主机名验证：是否匹配 SNI（`SSL_set_tlsext_host_name`）和证书CN/SAN
- 证书链验证：`SSL_get_verify_result` 是否等于 `X509_V_OK`
- CRL/OCSP检查：是否启用吊销列表验证

**【L4：跨模块追踪】** 全链路检查：
- 配置文件解析到 SSL_CTX 应用的完整路径
- 是否存在运行时动态关闭验证的开关（如命令行参数 `--insecure`）
- 多层封装库（如自定义 HttpClient）底层是否正确传递验证参数
- 不同环境配置（dev/prod）的差异化验证策略

## Classify

### 真实漏洞判定
- **生产环境**中完全禁用证书验证（`SSL_VERIFY_NONE` 且无条件编译保护）
- verify_callback 无条件返回成功，绕过所有证书检查
- 强制使用SSLv3/TLS1.0等已废弃协议，无降级保护
- 显式配置弱加密套件且为唯一选项（非兼容性后备）
- 处理敏感数据的连接缺少主机名验证

### 误报识别
- **测试/开发环境**专用代码（通过 `#ifdef TEST_MODE` 隔离且不可能编译到生产）
- 用于本地回环地址（`127.0.0.1`/`localhost`）的TLS配置
- 已有后续显式校验（手动调用 `X509_verify_cert` 且正确处理错误）
- 注释掉的历史代码或示例代码（未实际执行）
- 调用链中更上层已完成验证（需完整追踪确认）

### 代码异味
- 使用过时但尚未完全禁用的TLS1.1（存在兼容性考虑）
- 宽松加密套件列表但包含强加密项（如混合了AES256和3DES）
- 缺少明确的证书固定（Certificate Pinning），但基础验证完整
- 开发时临时关闭验证，但有明确 TODO/FIXME 注释
- 自签名证书场景，但通过其他机制（如证书白名单）补偿

## Low Risk

### 低风险场景评级标准

1. **隔离环境通信**
   - 内网专用系统间通信，物理/逻辑隔离，无外部网络访问
   - 容器内部服务网格通信，已有其他认证层（mTLS由服务网格统一管理）

2. **受限影响范围**
   - 仅用于非敏感数据传输（公开资源下载、静态内容获取）
   - 客户端主动发起且用户已明确同意跳过验证（如测试工具的 `--insecure` 参数）
   - 失败后有明确降级策略（如日志记录后拒绝连接，而非静默继续）

3. **补偿控制存在**
   - 虽禁用系统验证，但实现了自定义证书白名单机制
   - 通过应用层签名/加密提供额外保护（数据本身已加密且有完整性校验）
   - 短期临时配置，有自动过期机制或定期审计清理

4. **协议降级保护**
   - 允许TLS1.1但明确禁止SSLv2/SSLv3，且服务端强制TLS1.2+
   - 弱加密套件仅作为兜底选项，优先协商强加密

5. **上下文限定**
   - 仅在用户明确配置 "信任此证书" 后生效（证书例外管理）
   - 开发调试工具，不部署到生产环境，有清晰的构建隔离

**注意**：即使评为低风险，仍需在审计报告中记录，并建议在条件允许时改进配置。
