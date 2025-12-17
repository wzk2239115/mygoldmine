# C/C++ Custom Socket SSRF

**漏洞描述**：自实现 socket 连接使用用户控制的主机和端口参数，缺少安全验证

---

## Details

**代码示例**：
```c
// 典型漏洞场景
int sock = socket(AF_INET, SOCK_STREAM, 0);
struct sockaddr_in server;
server.sin_family = AF_INET;
server.sin_port = htons(atoi(user_port));        // 用户可控端口
server.sin_addr.s_addr = inet_addr(user_host);   // 用户可控主机
connect(sock, (struct sockaddr*)&server, sizeof(server));
```

**快速定位核心操作**（L2: 跳读）：
- 搜索关键函数：`socket()` → `connect()` / `bind()`
- 关注 `sockaddr_in` 结构体的赋值点，特别是 `sin_addr` 和 `sin_port` 字段
- 追踪数据流：从参数输入（`argv`、环境变量、网络输入）到 socket 地址结构
- C++场景下留意 `boost::asio`、`libuv` 等库的异步连接接口

**快速定位保护机制**（L3: 逐行读）：
- 检查地址白名单验证：`strcmp()`、正则匹配、IP 范围检查
- 检查端口限制：端口号范围判断（如禁止 <1024 或内网常用端口）
- 检查 DNS 解析控制：是否使用 `getaddrinfo()` 并验证解析结果
- 检查私有地址过滤：`inet_pton()` 后检查 10.0.0.0/8、172.16.0.0/12、192.168.0.0/16、127.0.0.0/8
- 检查 socket 选项限制：`SO_BINDTODEVICE`、超时设置等防护措施

---

## Classify

**确认为漏洞**：
- 主机/端口参数直接来源于外部输入且无任何验证
- 存在 IP 白名单但可通过 DNS rebinding 绕过
- 仅验证格式不验证地址范围（如只检查是否为有效 IP 格式）
- 端口限制不完整（如只禁止 22、80，但未禁止 6379、3306 等内网服务端口）

**误报场景**：
- 连接地址硬编码为外部可信服务
- 用户输入仅影响 URL 路径部分，主机名来自配置文件
- 存在完整的白名单验证且无法绕过
- 仅用于本地进程间通信（Unix Domain Socket）

**代码异味**：
- 有地址验证但逻辑较弱（如仅字符串前缀匹配）
- 验证与连接之间存在 TOCTOU 时间窗口
- 依赖客户端验证而服务端未二次检查
- 错误处理不当可能泄露内网拓扑信息

---

## Bypass Techniques

**常见绕过方法**（审计重点）：

### IP 验证绕过
- **DNS Rebinding**：验证后 IP 解析变化
  ```c
  // 验证通过后，后续 connect() 解析同域名获得不同 IP
  struct hostent *h = gethostbyname(hostname);  // 第一次可能返回合法 IP
  // ... 验证逻辑 ...
  connect(sock, (struct sockaddr*)&(h->h_addr), ...);  // 实际连接可能是内网 IP
  ```

- **IPv6 映射**：`::ffff:127.0.0.1` 绕过 IPv4 检查
  ```c
  // 应用只检查 IPv4 黑名单，未考虑 IPv6 映射地址
  inet_pton(AF_INET6, "::ffff:127.0.0.1", &addr);
  ```

- **整数溢出**：端口号转换时的整数溢出
  ```c
  uint16_t port = atoi(user_port);  // "65536" → 0 or "65535" → -1
  server.sin_port = htons(port);
  ```

- **CIDR 绕过**：验证 IP 范围时的逻辑漏洞
  - 验证是否在 10.0.0.0/8 时未正确使用位运算
  - 未考虑网络字节序转换

### 格式混淆
- **八进制/十六进制 IP**：`0127.0.0.1`、`0x7f.0.0.1`
- **整数型 IP**：`2130706433` 等于 127.0.0.1
- **冗余 0**：`192.168.001.001`、`192.168.0.1.` 尾部点号

---

## Audit Methodology

**三层递进审计流程**：

### Layer 1 - 快速筛查
1. 全局搜索 `socket()` 和 `connect()` 调用
2. 检查参数来源：是否涉及用户输入
3. 统计发现数量，判断代码量是否需要深入分析

### Layer 2 - 数据流追踪
1. **输入点识别**
   - 命令行参数：`argv[i]`
   - 环境变量：`getenv()`
   - 网络输入：socket 读取、HTTP 参数
   - 配置文件：无硬编码路径

2. **传播路径**
   - 追踪变量赋值链：`user_input → var → inet_addr() → sin_addr`
   - 关注数据转换：字符串→整数、字符串→IP、URL 解析

3. **验证点检查**
   ```c
   // 标准的安全模式
   if (!is_whitelisted_host(hostname)) {
       return ERROR;  // 拒绝连接
   }

   // 警戒的模式
   inet_pton(AF_INET, input, &addr);
   if (is_private_ip(addr)) {
       return ERROR;
   }
   ```

### Layer 3 - 代码细节验证
- **验证逻辑缺陷**：前缀匹配 vs 完整匹配
- **时间窗口**：验证后到连接前是否有变化机会
- **错误处理**：连接失败信息是否泄露内网拓扑
- **库函数行为**：`inet_addr()` 返回值、`inet_pton()` 边界情况

---

## Low risk

**降低风险评级的情况**：
- 功能仅对高权限管理员开放且有完整审计日志
- 连接超时设置极短（<1秒）且无重试，利用难度高
- 目标应用部署在隔离网络环境，无法访问敏感内网资源
- 连接前有多因素认证且单次会话仅允许 1-2 次连接尝试
- 应用已部署网络层防护（如出站流量白名单、网络分段）
- 仅允许连接到特定协议端口（如仅允许 HTTP/HTTPS 的 80/443）且目标服务无敏感信息
