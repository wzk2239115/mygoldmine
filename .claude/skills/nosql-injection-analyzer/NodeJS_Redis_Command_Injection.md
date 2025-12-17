# NodeJS Redis Command Injection

## Details

**漏洞成因**：Node.js 的 Redis 客户端库（如 redis、ioredis）在处理 Redis 命令时，若使用动态命令执行（如 `redis.call()` 或 `redis.send_command()`）且参数由用户输入构造，攻击者可注入任意 Redis 命令。Lua 脚本执行（`eval()`）若脚本由用户输入提供，更加危险。

**代码审计焦点**：
- 是否使用 `redis.send_command()`、`redis.call()` 等动态命令方法
- Lua 脚本是否由用户输入构造
- `redis.set()`、`redis.get()` 等命令的参数是否来自用户输入
- 是否存在命令参数验证或白名单

**核心定位技巧**：
- **(L1: 关键词扫描)** 搜索 `redis.send_command(`、`redis.call(`、`redis.eval(`、`req.query` 等关键字
- **(L2: 跳读)** 检查参数是否来自 HTTP 请求或外部输入
- **(L3: 逐行读)** 追踪参数从接收到 Redis 执行的过程，确认是否进行了验证
- **(L4: 跨模块追踪)** 检查是否通过多个中间件或函数处理参数

**保护机制识别**：
- **(L1: 关键词扫描)** 检查是否使用了特定的 Redis 命令方法而非动态执行
- **(L2: 跳读)** 验证参数是否通过白名单验证
- **(L3: 逐行读)** 确认参数是否通过类型检查
- **(L4: 跨模块追踪)** 检查 Redis 连接是否启用了认证

## Classify

**漏洞研判**：
1. 若使用 `send_command()` 或 `call()` 执行用户输入构造的命令 → 漏洞
2. 若 Lua 脚本由用户输入构造 → 高危漏洞
3. 若允许执行任意 Redis 命令 → 漏洞

**误报风险**：
1. 使用特定的 Redis 命令方法且参数通过验证 → 低风险
2. 参数通过类型检查（parseInt、String 等）限制 → 低风险
3. Redis 连接只读且账户权限受限 → 低风险

## Low risk

- 仅使用特定的 Redis 命令方法而非动态执行
- 参数通过白名单验证或类型转换限制
- Redis 连接使用只读账户或密码认证
- 禁用 Lua 脚本执行（EVAL 命令）
- 连接使用 TLS/SSL 加密

