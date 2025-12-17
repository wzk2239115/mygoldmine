# C/C++ - 未检查的资源消耗

## Details

**漏洞描述**：资源消耗操作（内存分配、文件句柄、线程创建、网络连接等）未绑定用户权限、会话上下文或配额限制，攻击者可通过重复调用触发资源耗尽。

**代码示例**：
```c
// 易受攻击 - 用户控制分配大小
void handle_upload(int user_size) {
    char* buffer = malloc(user_size);  // 无上限检查
}

// 易受攻击 - 无限制资源创建
while(accept_connection()) {
    pthread_create(&tid, NULL, handler, NULL);  // 无线程数限制
}

// 易受攻击 - 递归深度不受控
void process(Node* node) {
    if(node->next) process(node->next);  // 栈消耗无限制
}
```

**快速定位核心操作**：
- 内存分配：`malloc`, `calloc`, `realloc`, `new`, `new[]`, `alloca`, `mmap`
- 资源创建：`pthread_create`, `fork`, `socket`, `open`, `fopen`, `accept`, `connect`
- 容器扩展：`vector::resize`, `push_back`, `insert`（STL容器）
- 重点关注：循环/递归中的资源分配，用户参数直接作为分配大小

**快速定位保护机制**：
- 上限检查：`if (size > MAX_*)`、`MIN(size, limit)`
- 配额验证：`check_quota()`, `rate_limit()`, `user->remaining_quota`
- 资源池模式：线程池、连接池、内存池的`max_size`配置
- 计数器：`active_count`, `resource_counter`
- 前置鉴权：`authenticate()`, `check_permission()`在资源操作前

**审计等级**：**L3-L4**（逐行读-跨模块追踪）
- L3：单函数内审查资源分配参数来源、边界检查、异常处理
- L4：跨模块追踪用户身份传递链、配额管理系统、资源清理机制

## Classify

**确认为漏洞**：
- ✓ 资源分配大小/次数由用户输入直接控制，无硬编码上限
- ✓ 未认证/低权限接口触发昂贵资源操作（fork、大内存、复杂计算）
- ✓ 循环/递归分配资源，退出条件受外部输入控制
- ✓ 资源仅分配不释放，或释放逻辑在错误路径缺失
- ✓ 时间复杂度受用户控制（如O(n²)操作，n由用户指定）

**误报**：
- ✗ 资源操作前有可靠的业务限制（如"仅限购买用户"且购买有上限）
- ✗ 代码路径需管理员权限（root、内部维护接口）
- ✗ 外层已有防护（Web网关速率限制、系统最大连接数配置）
- ✗ 使用资源池且有硬上限（如固定大小的线程池）

**代码异味**（需进一步评估）：
- △ 有上限但阈值可疑（如`MAX_SIZE = INT_MAX - 1`）
- △ 仅客户端校验，服务端无验证
- △ 错误处理路径中资源泄漏
- △ 依赖外部配置项但配置可被篡改

## Low risk

**低风险评级场景**：
- 资源操作在管理后台且有多层认证（如本地Unix socket + root用户）
- 已有可靠外部防护（硬件防火墙连接数限制、云平台配额管理）
- 受系统级限制保护且难以达到（如`ulimit -n 1024`且正常业务仅用<100）
- 资源开销微小（如每次分配<1KB）且有快速自动回收
- 触发条件极其苛刻（需完成复杂业务流程且有其他瓶颈限制）
- 仅影响攻击者自己的资源配额，无法影响其他用户