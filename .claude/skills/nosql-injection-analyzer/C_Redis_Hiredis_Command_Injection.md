# C Redis Hiredis Command Injection

## Details

**漏洞成因**：Hiredis 是 C 语言的 Redis 客户端库。当使用 `redisCommand()` 或 `redisCommandArgv()` 执行命令时，若命令参数由用户输入构造且未进行验证，攻击者可注入任意 Redis 命令。特别是使用字符串拼接或 `sprintf()` 构造命令。

**代码审计焦点**：
- 是否使用 `redisCommand()`、`redisCommandArgv()` 等函数
- 命令字符串是否通过 `sprintf()`、`strcpy()` 等不安全函数构造
- 是否对命令参数进行了验证或白名单检查
- Redis 连接是否启用了认证

**核心定位技巧**：
- **(L1: 关键词扫描)** 搜索 `redisCommand`、`redisCommandArgv`、`sprintf` 等关键字
- **(L2: 跳读)** 检查命令字符串的构造是否使用了不安全函数
- **(L3: 逐行读)** 追踪参数从接收到 Redis 执行的过程，确认是否进行了验证
- **(L4: 跨模块追踪)** 检查是否通过多个函数组合构造命令

**保护机制识别**：
- **(L1: 关键词扫描)** 检查是否使用了 `snprintf()` 等带长度限制的函数
- **(L2: 跳读)** 验证参数是否通过白名单验证
- **(L3: 逐行读)** 确认是否使用了参数化命令构造
- **(L4: 跨模块追踪)** 检查 Redis 连接是否启用了认证和 SSL/TLS

## Classify

**漏洞研判**：
1. 若使用 `sprintf()` 拼接用户输入的命令 → 漏洞
2. 若 `redisCommand()` 的参数直接来自用户输入 → 漏洞
3. 若允许执行任意 Redis 命令 → 漏洞

**误报风险**：
1. 使用 `snprintf()` 且指定长度限制 → 低风险
2. 参数通过白名单验证 → 低风险
3. Redis 连接启用了认证 → 低风险

## Low risk

- 使用 `snprintf()` 而非 `sprintf()`
- 参数通过白名单验证
- Redis 连接启用密码认证
- 使用只读账户或 ACL
- 连接使用 SSL/TLS 加密

