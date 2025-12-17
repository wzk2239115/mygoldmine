# 通用安全配置漏洞审计小抄

拿到任何涉及安全功能的应用项目，以下通用安全配置漏洞模式都必须进行审计，与具体编程语言实现无关。

## 敏感信息硬编码或明文存储
- 密码、API 密钥、数据库凭证、加密密钥硬编码在源代码中
- 环境变量文件（.env）或配置文件提交到版本控制系统
- 配置文件中敏感信息明文存储，未加密
- 配置文件权限过于宽松（如 644、666），任何用户可读取

## TLS/SSL 配置不安全
- HTTPS 客户端跳过证书验证（InsecureSkipVerify、verify=false 等）
- 自签名证书未正确验证
- 证书主机名验证被禁用
- 允许使用 SSLv3、TLS 1.0/1.1 等过时协议
- 使用弱加密套件（DES、RC4、MD5 等）
- 未强制使用 HTTPS，允许 HTTP 明文传输
- 未设置 HSTS 响应头或 max-age 设置过短（< 31536000）

## 跨域资源共享（CORS）配置不当
- CORS Access-Control-Allow-Origin 使用通配符 * 且允许携带凭证
- CORS 允许的源列表包含不可信的通配符模式（如 *.example.com）
- CORS 预检请求（OPTIONS）未正确验证来源
- 预检响应缓存时间过长（max-age > 86400）

## 调试和错误信息泄露
- 生产环境启用调试模式（debug=true、DEBUG=true 等）
- 详细的错误堆栈跟踪直接暴露给用户（应仅在日志中记录）
- 开发工具、管理面板或调试端点在生产环境可访问（如 /admin、/debug、/actuator 等）
- 日志中记录密码、Token、API 密钥等敏感信息

## HTTP 安全响应头缺失
- 缺少 X-Frame-Options（可被 Clickjacking 攻击）
- 缺少 X-Content-Type-Options（可被 MIME 嗅探）
- 缺少 X-XSS-Protection（XSS 防护未启用）
- 缺少 Referrer-Policy（泄露引用信息）
- 缺少 Content-Security-Policy 或 CSP 配置过于宽松（unsafe-inline、unsafe-eval）

## 会话管理配置不安全
- Session Cookie 未设置 HttpOnly（可被 JavaScript 读取）
- Session Cookie 未设置 Secure（可在 HTTP 下传输）
- Session Cookie 未设置 SameSite（CSRF 风险）
- 会话超时时间过长或无限期
- 会话过期后未强制重新认证

## 身份认证和授权配置缺陷
- JWT 签名算法未验证，允许 none 算法
- JWT 签名密钥弱或硬编码
- JWT 过期时间过长或未验证过期状态
- OAuth 重定向 URI 未严格验证（允许开放重定向）
- OAuth state 参数未使用或未验证（CSRF 风险）
- 密码强度要求过低
- 密码使用弱哈希算法（MD5、SHA1）而非 bcrypt/scrypt/Argon2
- 密码哈希未使用盐值或盐值固定

## 默认配置和凭证使用
- 数据库、缓存、管理后台使用默认凭证（如 admin/admin、root/root）
- Web 服务器保留默认配置，未禁用危险功能
- 数据库未修改默认端口
- 框架默认开启的调试或测试功能未关闭

## 访问控制和权限配置不当
- 配置文件、密钥文件权限过于宽松（777、666、644）
- 应用目录权限过于宽松，允许任意用户写入或执行
- 角色权限定义过于宽泛，违反最小权限原则
- 默认角色拥有过多权限

## 数据库和缓存配置不安全
- 数据库连接未使用 SSL/TLS 加密
- 数据库账户权限过高（使用 root 或超级用户）
- Redis、Memcached 等缓存服务未配置认证或使用弱密码
- 缓存服务绑定到公网 IP

## 第三方服务集成配置不当
- 第三方 API 密钥硬编码或提交到代码仓库
- API 密钥权限范围过大（应使用最小权限原则）
- Webhook 回调未验证签名，可被伪造
- Webhook URL 未使用 HTTPS

## 环境配置混用或泄露
- 生产环境使用开发环境配置
- 测试数据或测试账户在生产环境存在
- 配置文件在 Web 根目录下可直接访问（如 /config.php、/config.json）
- .git、.env、.config、.bak 等敏感文件未排除在部署外