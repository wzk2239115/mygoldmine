# C/C++ 自定义二进制反序列化溢出

## Details

### 典型代码示例

```c
// 场景1: 直接 memcpy 填充结构体
struct Config {
    char name[32];
    int value;
};
void load_config(const char* data, size_t len) {
    struct Config cfg;
    memcpy(&cfg, data, len);  // 未验证 len <= sizeof(cfg)
}

// 场景2: fread 直接读取
void load_save(FILE* fp) {
    struct Player player;
    fread(&player, sizeof(player), 1, fp);  // 未验证文件内容有效性
}

// 场景3: 读取长度后分配内存
void parse_packet(const char* buf) {
    uint32_t len = *(uint32_t*)buf;
    char* data = malloc(len);  // 未检查 len 上限，可能整数溢出
    memcpy(data, buf+4, len);
}

// 场景4: 嵌套结构体动态长度
struct Message {
    uint16_t type;
    uint16_t payload_len;
    char payload[1];  // 柔性数组
};
void handle_msg(char* raw) {
    struct Message* msg = (struct Message*)raw;
    process(msg->payload, msg->payload_len);  // payload_len 未验证
}
```

### 快速定位核心操作 (审计技巧)

**L1 (关键词扫描)**  
- 搜索：`memcpy`, `fread`, `read`, `recv`, `Boost::archive`, `istream::read`, `strncpy` 后接结构体指针
- 反序列化入口：`load_*`, `parse_*`, `deserialize_*`, `from_bytes`, `unpack`

**L2 (跳读)**  
- 定位数据源：函数参数是否为外部输入 (socket, file, shared memory)
- 检查尺寸计算：查找 `sizeof()`, `strlen()`, 读取的长度参数
- 关注类型转换：`(struct *)buf`, `reinterpret_cast<>`

**L3 (逐行读)**  
- 验证边界检查：`if (len > MAX_SIZE)`, `if (len <= sizeof(target))`
- 检查长度来源：长度是从数据包头部读取还是硬编码常量
- 结构体布局：是否包含指针、动态数组、柔性数组成员

**L4 (跨模块追踪)**  
- 追踪数据流：从网络/文件读取 → 中间缓冲区 → 最终结构体
- 检查回调链：插件加载、配置热更新、协议扩展点
- 分析状态机：多阶段解析中长度字段的累积效应

### 快速定位保护机制 (审计技巧)

**L0 (快速跳过)**  
- 硬编码常量：`fread(&obj, sizeof(obj), 1, fp)` 且无后续动态操作
- 已有库保护：使用 protobuf/flatbuffers/Cap'n Proto 等成熟库

**L1 (关键词扫描)**  
- 边界检查关键词：`assert`, `CHECK`, `VERIFY`, `min()`, `max()`, `clamp`
- 异常处理：`throw`, `return -1`, `goto error`

**L2 (跳读)**  
- 检查顺序：先验证长度再分配内存
- 魔数校验：`if (header->magic != EXPECTED_MAGIC) return;`
- 版本检查：`if (version > SUPPORTED_VERSION) reject;`

**L3 (逐行读)**  
- 整数溢出防护：`if (len > SIZE_MAX - offset)` 或使用 `__builtin_add_overflow`
- 对齐检查：`if ((uintptr_t)buf % alignof(struct X) != 0)`
- 白名单校验：类型字段是否在枚举范围内

**L4 (跨模块追踪)**  
- 沙箱机制：反序列化发生在独立进程/容器
- ASLR/CFI：内存布局随机化、控制流完整性检查
- Sanitizers：是否在编译时启用 ASan/UBSan

## Classify

### 确认为漏洞的条件
1. **可控长度未验证**：外部输入的长度字段直接用于 memcpy/malloc，无上限检查
2. **结构体尺寸假设错误**：代码假设接收的数据大小匹配结构体定义，但协议演进导致不匹配
3. **整数溢出导致小分配**：`malloc(len1 + len2)` 在 len1+len2 溢出时分配极小内存后写入大量数据
4. **类型混淆**：通过修改类型字段触发错误的分支，按错误的结构体布局解析

### 判定为误报的情况
1. **数据源可信**：反序列化来自只读内存区、签名验证后的配置文件、内部IPC通道且调用方已校验
2. **长度已验证**：在调用栈上游已确认 `len <= sizeof(target)` 且中间无修改
3. **自动生成代码**：由 IDL 编译器生成且运行时有额外校验层（如 RPC 框架自带的反序列化器）
4. **仅读取安全字段**：只读取固定偏移的标量字段，不涉及指针解引用或动态内存分配

### 代码异味（需进一步确认）
1. **隐式尺寸依赖**：使用 `sizeof(struct)` 但结构体包含指针，实际数据尺寸不确定
2. **部分校验**：只检查了总长度，未校验嵌套字段的单独长度
3. **校验后修改**：TOCTOU - 检查后到使用前，长度字段可能被并发修改
4. **依赖编译器行为**：假设结构体无 padding、字节序一致、指针尺寸固定

## Low risk

### 低风险评级场景

1. **受限输入源**  
   - 数据来自同用户权限的本地文件（非共享目录）
   - 仅在测试/调试模式下启用的反序列化路径
   - 需要管理员权限才能触发的配置加载

2. **纵深防御到位**  
   - 进程运行在严格沙箱中（seccomp-bpf, pledge, Capsicum）
   - 启用所有内存安全编译选项（Stack Canary, PIE, RELRO, FORTIFY_SOURCE）
   - 反序列化后的对象仅用于只读查询，不影响控制流

3. **溢出影响受限**  
   - 溢出目标是栈上局部变量，但无函数指针/返回地址可覆盖
   - 堆溢出但对象后紧跟的是 padding/未使用内存
   - 长度限制虽不严格，但最大可能溢出量 < 16 字节

4. **快速失效机制**  
   - 后续操作立即触发段错误或断言，无法持续利用
   - 关键指针在使用前有魔数校验
   - 进程崩溃不影响系统稳定性（守护进程自动重启，无持久化状态）

5. **已有补偿控制**  
   - 业务逻辑层对反序列化结果再次验证
   - 数据库/文件系统的完整性检查会拦截异常值
   - 监控告警能快速检测到异常反序列化行为