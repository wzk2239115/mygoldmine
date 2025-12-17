# C_Pointer_Integer_Conversion

**漏洞类型**: 指针与整数转换，指针与整数类型之间的不安全转换

**漏洞成因**

指针与整数之间的不安全转换会导致严重的安全问题。常见于：
- 指针直接强制转换为整数（64位指针截断为32位整数）
- 整数直接强制转换为指针，无有效性检查
- 指针运算后转整数，失去内存布局信息导致地址预测
- 指针与整数混合运算，导致地址计算错误
- 在32/64位系统间移植时，指针大小假设错误
- 指针序列化/反序列化时，未考虑地址空间随机化 (ASLR)

---

## Details

### 代码示例

**危险模式1：指针截断为32位整数导致地址碰撞**
```c
void store_pointer_as_int(void *ptr) {
    int handle = (int)ptr;           // 64位指针截断为32位整数，信息丢失
    // 后续通过 handle 恢复指针时，高32位丢失
    void *restored = (void *)handle; // 地址错误，可能指向任意位置
}

struct node *obj = malloc(sizeof(struct node));
store_pointer_as_int(obj);  // 高位地址丢失，恢复时崩溃或指向错误内存
```

**危险模式2：整数直接转指针，无有效性检查**
```c
void *get_object_from_id(int id) {
    return (void *)id;  // 直接将用户输入转为指针，完全不受信任
}

void process_object(int user_id) {
    struct data *obj = (struct data *)get_object_from_id(user_id);
    obj->value = 100;  // 写入任意内存地址，导致任意写漏洞
}

int malicious_id = 0x40000000;  // 构造的地址
process_object(malicious_id);
```

**危险模式3：指针运算丢失后进行整数操作**
```c
void unsafe_pointer_math(void *base, int offset) {
    intptr_t addr = (intptr_t)base + offset;  // 指针转整数进行算术运算
    void *ptr = (void *)addr;                  // 转回指针
    *(int *)ptr = 0xdeadbeef;                 // 写入到计算的地址
}

char *buffer = malloc(1024);
unsafe_pointer_math(buffer, -1000);  // 负数偏移，越界写入
```

**危险模式4：ASLR环境下指针地址预测**
```c
void leak_pointer_value(void *ptr) {
    unsigned int leaked = (unsigned int)ptr;  // 泄露指针低位
    send_to_network(leaked);                  // 发送给攻击者
}

void *target = malloc(100);
leak_pointer_value(target);  // 攻击者可以计算出基地址，绕过ASLR
```

**危险模式5：指针序列化/反序列化无验证**
```c
typedef struct {
    unsigned int ptr_value;  // 存储指针的整数表示
    int size;
} SerializedObject;

void *deserialize_object(SerializedObject *data) {
    void *ptr = (void *)data->ptr_value;  // 直接恢复指针，无地址空间验证
    return ptr;
}

SerializedObject obj;
// obj 来自不信任的源（网络、文件）
void *ptr = deserialize_object(&obj);  // 指向任意地址
memcpy(ptr, user_data, obj.size);      // 任意写
```

**危险模式6：指针与整数类型混淆导致越界**
```c
void handle_array_element(int *array, int index) {
    void *ptr = (void *)&array[index];  // 指针计算
    int *elem = (int *)ptr;
    *elem = value;  // 越界写入
}

int arr[10];
handle_array_element(arr, 100);  // 转换为指针后索引失控，越界访问
```

### 快速定位核心操作 **[L1-L2]**

**关键词扫描:**
- `(int)` / `(unsigned int)` / `(long)` / `(size_t)` 直接作用于指针变量
- `(void *)` / `(char *)` 直接转换整数、特别是来自外部输入的整数
- `(intptr_t)` / `(uintptr_t)` 的使用，尤其涉及指针运算和地址计算
- 指针与整数的混合运算：`(void *)((int)ptr + offset)`
- `memcpy`、`strcpy` 等操作之前的指针-整数转换
- 指针值的网络传输或持久化存储（序列化）
- 跨平台代码中的 `sizeof(int) != sizeof(void *)`

**快速定位保护机制 [L2-L3]**
- 是否使用 `intptr_t`/`uintptr_t` 代替 `int`/`unsigned int` 转换指针
- 是否验证转换后的指针在有效的堆/栈地址范围内
- 是否检查指针来源的合法性（内部管理的对象池而非直接用户输入）
- 是否启用地址卫生工具 (ASan/MSan) 检测非法指针访问
- 是否使用指针白名单或对象池管理策略，避免直接整数转指针
- 编译器标志：`-faddress-sanitizer`、`-fsanitize=pointer-overflow` 是否启用

---

## Classify

**研判为真漏洞的特征：**
1. 整数直接转换为指针，无任何来源验证或范围检查，用于内存访问
2. 指针截断为较小的整数类型（如64位指针→32位int），导致信息丢失和地址碰撞
3. 指针值来自外部输入（用户、网络、文件），直接用于指针操作
4. 指针与整数混合运算计算地址，整数来源不受信任或无范围保证
5. 指针序列化/反序列化未考虑地址空间随机化 (ASLR) 或基地址重定位
6. 跨平台代码中假设 `sizeof(int) == sizeof(void *)`，移植时违反约定

**误报/代码异味的特征：**
- 使用 `intptr_t`/`uintptr_t` 进行指针转换，并在使用前验证地址合法性
- 指针值来源于内部可信的对象管理系统（内存池、句柄表）
- 转换结果用于非关键操作（调试输出、日志记录、统计）
- 指针运算在编译期已确定其范围和有效性（常量偏移）
- 启用了地址卫生工具或编译器指针安全检查
- 代码中明确使用了 `NULL` 检查和地址范围验证

---

## Low risk

**以下场景可评为低风险：**

1. **内部对象池管理**
   - 指针仅用于管理内部分配的对象，不接受外部输入的地址值
   - 如：内部句柄表 `handles[100] = {allocated_object_pointers}`，通过下标返回指针
   - 整数到指针的映射完全受程序控制，不涉及外部数据

2. **完整的指针验证**
   - 转换后显式验证指针的有效性：`if (ptr >= heap_start && ptr <= heap_end)`
   - 使用白名单检查：`if (is_valid_object(ptr))`，对象在预设的容器中
   - 检查指针对齐：`if ((uintptr_t)ptr % sizeof(struct_type) == 0)`

3. **平台无关的安全转换**
   - 使用 `intptr_t`/`uintptr_t` 进行系统相关的指针转换
   - 明确处理平台间的指针大小差异
   - 代码中注释说明假设条件，如 `// 假设64位系统，指针8字节`

4. **非安全敏感的操作**
   - 指针-整数转换仅用于调试、日志输出或统计，不影响实际内存访问
   - 如：`printf("Pointer value: %p", ptr)` 不存在安全风险

5. **受限制的转换范围**
   - 指针运算中的整数偏移已明确限制在安全范围内
   - 如：`offset` 范围在 `[-100, 100]`，而对象大小 1000+，不可能越界

