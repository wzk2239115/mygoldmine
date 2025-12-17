# C/C++ 结构体反序列化 Use After Free

## Details

### 典型代码示例

```c
// 场景1: 反序列化分配内存，但释放时机错误
struct Packet {
    uint32_t type;
    uint32_t data_len;
    char* data;  // 指针字段
};

void deserialize_packet(const char* buf, struct Packet* pkt) {
    pkt->type = *(uint32_t*)buf;
    pkt->data_len = *(uint32_t*)(buf + 4);
    pkt->data = malloc(pkt->data_len);  // 分配内存
    memcpy(pkt->data, buf + 8, pkt->data_len);
}

void process_and_cleanup(struct Packet* pkt) {
    // 处理数据
    process_data(pkt->data, pkt->data_len);
    free(pkt->data);  // 释放内存
    pkt->data = NULL;  // 但未在所有路径设置 NULL
}

void handle_packet(const char* buf) {
    struct Packet pkt;
    deserialize_packet(buf, &pkt);
    if (error_condition) {
        free(pkt.data);  // 错误路径释放
        return;  // 提前返回
    }
    process_and_cleanup(&pkt);
    // UAF: pkt.data 可能已被释放但结构体仍在使用
    log_packet(&pkt);  // 再次访问已释放的内存
}

// 场景2: 嵌套结构体指针生命周期管理错误
struct Node {
    int value;
    struct Node* next;
};

void deserialize_list(const char* buf, struct Node** head) {
    uint32_t count = *(uint32_t*)buf;
    struct Node* prev = NULL;
    for (uint32_t i = 0; i < count; i++) {
        struct Node* node = malloc(sizeof(struct Node));
        node->value = *(int*)(buf + 4 + i * sizeof(int));
        if (prev) {
            prev->next = node;
        } else {
            *head = node;
        }
        prev = node;
    }
    if (prev) prev->next = NULL;
}

void cleanup_list(struct Node* head) {
    while (head) {
        struct Node* next = head->next;
        free(head);  // 释放节点
        head = next;
    }
}

void handle_request(const char* buf) {
    struct Node* list = NULL;
    deserialize_list(buf, &list);
    process_list(list);
    cleanup_list(list);  // 释放所有节点
    // UAF: 如果 list 被其他结构体引用，后续访问会触发 UAF
    if (global_context) {
        global_context->cached_list = list;  // 保存已释放的指针
    }
}

// 场景3: 从文件反序列化，指针指向栈/静态内存
struct Config {
    char name[64];
    char* description;  // 可能指向已释放的栈内存
};

void load_config_file(const char* filename, struct Config* cfg) {
    FILE* fp = fopen(filename, "r");
    fread(cfg->name, 1, sizeof(cfg->name), fp);
    
    char temp[256];
    fgets(temp, sizeof(temp), fp);
    cfg->description = strdup(temp);  // 分配内存
    
    fclose(fp);
}

void reload_config(struct Config* cfg) {
    free(cfg->description);  // 释放旧描述
    // 但未重新加载，cfg->description 成为悬空指针
}

void use_config(struct Config* cfg) {
    printf("Desc: %s\n", cfg->description);  // UAF: 访问已释放内存
}

// 场景4: 共享内存或外部管理的指针
struct SharedData {
    uint32_t ref_count;
    void* payload;  // 指向外部管理的内存
};

void deserialize_shared(const char* buf, struct SharedData* sd) {
    sd->ref_count = *(uint32_t*)buf;
    sd->payload = (void*)*(uintptr_t*)(buf + 4);  // 直接反序列化指针值
    // 危险：指针指向的内存可能已被释放或重新分配
}

void process_shared(struct SharedData* sd) {
    if (sd->payload) {
        // UAF: payload 指向的内存可能已被外部释放
        memcpy(buffer, sd->payload, size);
    }
}
```

### 快速定位核心操作 (审计技巧)

**L1 (关键词扫描)**  
- 搜索：`malloc`/`calloc`/`realloc` 后接结构体指针字段赋值、`free()` 调用点、结构体包含指针成员的定义
- 反序列化入口：`deserialize_*`, `load_*`, `parse_*`, `from_bytes`, `unpack_*` 返回或填充包含指针的结构体
- 生命周期函数：`cleanup_*`, `destroy_*`, `free_*`, 析构函数 `~ClassName()`

**L2 (跳读)**  
- 指针字段识别：结构体定义中查找 `*`, `[]` (数组指针), 函数指针类型
- 内存分配模式：反序列化函数内是否有 `malloc` 并赋值给结构体成员
- 释放调用位置：搜索 `free(ptr->field)` 或 `free(struct_instance.field)` 的调用点
- 结构体使用点：反序列化后结构体被传递给其他函数的使用位置

**L3 (逐行读)**  
- 释放后清零检查：`free(ptr)` 后是否有 `ptr = NULL` 或 `ptr->field = NULL`
- 生命周期追踪：从分配到释放之间，指针是否被多次释放或访问
- 错误路径处理：函数提前返回、异常处理路径是否释放了内存但结构体仍在使用
- 引用计数检查：如果使用引用计数，释放时是否正确递减并检查计数

**L4 (跨模块追踪)**  
- 数据流追踪：反序列化分配 → 传递到业务逻辑 → 清理函数 → 后续访问
- 全局状态影响：结构体指针是否被保存到全局变量、静态变量、其他结构体中
- 并发访问检查：多线程环境下，释放和使用之间是否存在竞态条件
- 回调函数链：释放后结构体指针是否在回调函数中被访问

### 快速定位保护机制 (审计技巧)

**L0 (快速跳过)**  
- 智能指针使用：C++ 中结构体使用 `std::unique_ptr`, `std::shared_ptr` 自动管理生命周期
- 无指针字段：结构体仅包含标量类型、固定数组，不涉及动态内存
- RAII 模式：C++ 析构函数自动释放，且无手动 `free` 调用

**L1 (关键词扫描)**  
- 释放后清零：`free(ptr); ptr = NULL;` 或 `free(ptr->field); ptr->field = NULL;`
- 生命周期标记：`is_valid`, `is_freed`, `ref_count` 等状态标记字段
- 空指针检查：`if (ptr == NULL)` 在使用前检查

**L2 (跳读)**  
- 所有权明确：结构体明确标注所有权（`owns_data`, `borrowed_ptr`）并在文档说明
- 清理函数完整性：清理函数中释放所有动态分配的资源并清零指针
- 错误处理一致性：所有错误路径都正确释放已分配的内存

**L3 (逐行读)**  
- 引用计数实现：`atomic_ref_count`, 释放前检查 `if (--ref_count == 0)`
- 延迟释放机制：使用标记删除，延迟到安全时机再实际释放
- 内存池管理：使用内存池而非直接 `malloc`/`free`，减少 UAF 风险

**L4 (跨模块追踪)**  
- 静态分析工具：代码中是否启用了 AddressSanitizer (ASan) 检测 UAF
- 代码审查标记：注释中明确说明指针生命周期和所有权
- 单元测试覆盖：测试用例覆盖各种生命周期场景，包括错误路径

## Classify

### 确认为漏洞的条件

1. **释放后访问**：结构体指针字段指向的内存已被 `free()` 释放，但后续代码仍通过该指针访问内存（无空指针检查或检查被绕过）
2. **双重释放路径**：同一指针在多个代码路径中被释放，或清理函数被多次调用
3. **生命周期混乱**：反序列化分配的内存，但其生命周期与结构体实例不匹配，结构体被复制/传递后原指针被释放，副本仍持有悬空指针
4. **外部管理指针**：反序列化直接解析指针值（而非分配新内存），该指针指向的内存由外部管理，可能在结构体使用期间被释放

### 判定为误报的情况

1. **智能指针保护**：C++ 中使用 `std::unique_ptr`/`std::shared_ptr` 等自动管理生命周期，编译器保证释放后访问会在编译期/运行期被检测
2. **释放后立即清零**：`free(ptr); ptr = NULL;` 且所有访问点都有空指针检查 `if (ptr == NULL) return;`
3. **内存池管理**：使用内存池技术，指针指向的内存不会被真正释放，仅标记为可复用，且访问时有有效性检查
4. **只读访问且内存持久**：指针指向静态内存、只读段、或生命周期明显长于结构体的内存区域（如字符串常量、全局变量）

### 代码异味（需进一步确认）

1. **部分清零**：结构体有多个指针字段，释放时只清零了部分字段，其他字段可能成为悬空指针
2. **错误路径不一致**：正常路径和错误路径的内存管理逻辑不一致，某些错误路径可能遗漏释放或错误释放
3. **所有权不明确**：无法从代码明确判断结构体是否拥有指针指向的内存，导致释放时机不确定
4. **全局引用**：结构体指针被保存到全局变量或其他长生命周期对象中，但原始内存可能已被释放

## Low risk

### 低风险评级场景

1. **立即检测机制**  
   - 释放后访问立即触发段错误（SIGSEGV），无法持续利用
   - 启用 AddressSanitizer 或其他内存检测工具，会在访问时立即崩溃并报告
   - 指针指向的页面已被标记为不可访问（mprotect）

2. **受限影响范围**  
   - 仅读取操作（无写入），且读取的值不影响控制流或关键决策
   - 结构体指针仅在调试日志中使用，生产环境已禁用
   - UAF 发生在进程退出前的清理阶段，无法影响业务逻辑

3. **保护性机制存在**  
   - 使用内存分配器在释放后填充特殊模式（如 0xdeadbeef），访问时会立即被检测到异常值
   - 指针访问前有魔数校验，即使 UAF 也会因魔数不匹配而失败
   - 启用了控制流完整性（CFI）等缓解措施，限制了利用可能性

4. **难以触发条件**  
   - 需要特定的时序条件（如多线程竞态），在实际环境中难以稳定复现
   - 错误路径需要特定的输入组合才能触发，正常业务流程不会经过
   - 指针仅在异常处理中使用，而异常处理本身就有额外的保护机制

5. **业务逻辑限制**  
   - 结构体在使用后立即被销毁，无法长期持有悬空指针
   - 反序列化结果仅用于一次性验证，验证后立即释放且不再访问
   - 内存分配大小受限，即使 UAF 也只能访问有限的内存区域