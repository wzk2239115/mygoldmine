# C_PaymentData_MemoryLeakage

## Details

**核心漏洞特征**：C应用中支付数据（密钥、卡号等）分配到内存后未正确释放，导致内存泄露和数据泄露。

**代码示例定位**：查找内存管理代码，关键词包括 `malloc()`, `free()`, `memset()`, `card_data` 等。

**快速定位核心操作**（L1: 关键词扫描）：
- 搜索 `malloc()` 后是否有对应 `free()` - 检查内存释放
- 搜索 `memset(ptr, 0, size)` - 检查是否清零
- 搜索异常处理中的return - 检查是否有内存泄露
- 搜索缓冲区操作 `strcpy`, `memcpy` - 检查是否安全
- 搜索 `realloc()` - 检查是否正确处理返回值和原指针
- 搜索 `strdup()`, `strndup()` - 隐式分配需释放
- 搜索 `goto` 标签 - 检查错误处理路径的清理
- 搜索 `EVP_`, `RSA_`, `AES_` 等加密API - 检查密钥清理

**快速定位保护机制**（L2: 跳读）：
- 检查所有malloc都有对应free
- 检查异常路径的资源释放
- 检查是否在free前清零
- 检查是否使用内存池管理
- 检查是否使用 `explicit_bzero()` 或 `SecureZeroMemory()`
- 检查是否有自定义的 `secure_free()` 函数
- 检查是否使用 `-fstack-protector` 等编译选项
- 检查是否使用静态分析工具（Coverity/Valgrind）

## Classify

**漏洞判定标准**：
- malloc无对应free → **漏洞**
- free前未清零 → **漏洞**
- 异常路径有内存泄露 → **漏洞**
- 野指针操作 → **漏洞**
- 使用 `memset()` 但可能被编译器优化掉 → **漏洞**
- 在栈上处理敏感数据后未清零 → **漏洞**
- 密钥材料在内存中停留时间过长 → **漏洞**

**误报情况**：
- malloc和free成对出现 → 低风险
- free前调用memset清零 → 低风险
- 使用RAII模式 → 低风险
- 短期内存分配且立即处理 → 可能误报
- 使用内存池且池自身有清理机制 → 可能误报
- 测试代码或示例代码的简化处理 → 可能误报

**代码异味**：
- 虽有cleanup但不完整 → 审计
- 某些路径缺少清理 → 审计
- 清理逻辑散落在多处 → 审计
- 使用 `memset` 而非 `explicit_bzero` → 审计
- 在循环中重复分配但不在每次迭代释放 → 审计

## Audit Skills

### 1. 内存分配点识别技巧

**直接分配函数**：
```c
// 标准分配
void* ptr = malloc(size);
void* ptr = calloc(nmemb, size);
void* ptr = realloc(old_ptr, new_size);

// 字符串分配
char* str = strdup(source);
char* str = strndup(source, n);

// OpenSSL内存分配
unsigned char* buf = OPENSSL_malloc(size);
CRYPTO_malloc(size, __FILE__, __LINE__);
```

**隐式分配函数**（容易遗漏）：
```c
// 某些库函数会内部分配内存
BIO* bio = BIO_new(BIO_s_mem());
EVP_PKEY* pkey = EVP_PKEY_new();
X509* cert = X509_new();
RSA* rsa = RSA_generate_key(...);

// 需要查阅文档确认是否需要释放
```

### 2. 控制流分析技巧

**关键路径检查清单**：
1. **正常执行路径**：函数末尾的清理
2. **早期返回路径**：每个 `return` 前的清理
3. **错误处理路径**：每个 `goto error` 的清理
4. **循环提前退出**：`break`/`continue` 时的清理
5. **信号处理**：SIGINT/SIGTERM 处理中的清理

**审计模式**：
```c
// 模式1: 查找所有return语句
grep -n "return" payment_handler.c

// 模式2: 查找所有goto语句
grep -n "goto" payment_handler.c

// 模式3: 检查每个return前是否有free
for each return:
    check if free() called before
    check if error label has cleanup code
```

### 3. 真实漏洞 vs 误报区分

**真实漏洞案例1**：错误处理路径泄露
```c
// 漏洞代码
char* decrypt_card_number(const char* encrypted) {
    char* plaintext = malloc(256);
    if (!plaintext) return NULL;

    EVP_CIPHER_CTX* ctx = EVP_CIPHER_CTX_new();
    if (!ctx) return NULL;  // 泄露plaintext

    // 解密逻辑...
    if (decrypt_error) {
        EVP_CIPHER_CTX_free(ctx);
        return NULL;  // 泄露plaintext
    }

    EVP_CIPHER_CTX_free(ctx);
    return plaintext;
}

// 判定：真实漏洞，两个错误路径都泄露了plaintext
```

**真实漏洞案例2**：清零被编译器优化
```c
// 漏洞代码
void process_payment(const char* card_data) {
    char sensitive_buffer[256];
    strcpy(sensitive_buffer, card_data);

    // 处理支付...

    memset(sensitive_buffer, 0, 256);  // 可能被优化掉
    return;
}

// 判定：真实漏洞，编译器可能将memset优化掉（dead store elimination）
// 修复：使用 explicit_bzero() 或 volatile
```

**误报案例1**：内存池管理
```c
// 可能被误报的代码
struct memory_pool {
    char* data;
    size_t used;
};

void process_transaction(struct memory_pool* pool) {
    char* tmp = pool->data + pool->used;  // 从池中分配
    strcpy(tmp, "sensitive data");
    pool->used += strlen(tmp) + 1;

    // 没有显式free，但pool自身有清理机制
}

void cleanup_pool(struct memory_pool* pool) {
    explicit_bzero(pool->data, pool->used);
    free(pool->data);
}

// 判定：误报，pool有统一清理机制
```

**误报案例2**：静态缓冲区复用
```c
// 可能被误报的代码
static char key_buffer[32];  // 静态缓冲区

void init_crypto() {
    generate_key(key_buffer, 32);
    setup_encryption(key_buffer);
    explicit_bzero(key_buffer, 32);  // 用完立即清零
}

// 判定：误报，虽然是静态分配但有正确清理
```

### 4. 高级审计技巧

**技巧1：使用控制流图（CFG）分析**
```bash
# 生成函数调用图
cflow -l -b payment_processor.c > callgraph.txt

# 分析每个分配点的所有可能路径
for each malloc:
    trace all paths to function exit
    verify free() on every path
```

**技巧2：符号执行辅助**
```bash
# 使用静态分析工具
clang --analyze payment_processor.c
cppcheck --enable=all payment_processor.c

# 使用动态分析工具
valgrind --leak-check=full --show-leak-kinds=all ./payment_app
valgrind --tool=massif ./payment_app  # 内存使用分析
```

**技巧3：差异审计**
```bash
# 对比不同错误路径的清理逻辑
diff -u <(grep -A 10 "if.*error" file.c) \
        <(grep -A 10 "return NULL" file.c)

# 检查是否一致
```

**技巧4：敏感数据生命周期追踪**
```c
// 审计检查点：
1. 数据进入点（API参数、文件读取、网络接收）
2. 数据处理点（解密、验证、转换）
3. 数据存储点（内存、临时文件、日志）
4. 数据销毁点（清零、释放、覆盖）

// 确保每个数据流都有完整的生命周期管理
```

### 5. 专业审计检查清单

**内存管理检查**：
- [ ] 每个 `malloc/calloc/realloc` 都有对应的 `free`
- [ ] 每个 `strdup/strndup` 都有对应的 `free`
- [ ] 每个 `OPENSSL_malloc` 都有对应的 `OPENSSL_free`
- [ ] `realloc` 失败时原指针未泄露
- [ ] `free` 后指针设为 `NULL` 防止double-free
- [ ] 自定义分配器（如内存池）有正确的清理机制

**数据清理检查**：
- [ ] 使用 `explicit_bzero()` 而非 `memset()`
- [ ] Windows平台使用 `SecureZeroMemory()`
- [ ] 栈上敏感数据也进行清零
- [ ] 清零操作在所有退出路径上都执行
- [ ] 寄存器中的敏感数据也考虑清理（关键函数）
- [ ] 编译时未使用 `-O2` 优化掉清零操作

**错误处理检查**：
- [ ] 所有 `return` 语句前都有清理代码
- [ ] 所有 `goto` 标签指向的清理代码完整
- [ ] 异常信号处理（SIGTERM）中有清理
- [ ] 多层函数调用时每层都正确传播错误和清理
- [ ] 使用 `__attribute__((cleanup))` 或类似机制

**时间窗口检查**：
- [ ] 敏感数据在内存中停留时间最小化
- [ ] 不在全局变量中存储敏感数据
- [ ] 不在长生命周期对象中存储敏感数据
- [ ] 使用后立即清理，不等到函数末尾
- [ ] 避免将敏感数据传递给日志函数

## Low risk

**低风险评级条件**：
1. **配对管理**：所有malloc都有对应free
2. **清零处理**：释放前使用 `explicit_bzero(ptr, size)`
3. **异常安全**：异常处理中正确释放（goto cleanup模式）
4. **资源管理**：使用cleanup attribute或自定义secure_free
5. **工具检查**：使用valgrind验证无泄露
6. **编译保护**：使用 `-fstack-protector-strong` 和 `-D_FORTIFY_SOURCE=2`
7. **代码审查**：通过人工审计所有敏感数据路径
8. **静态分析**：通过Coverity/Clang Static Analyzer扫描

## Reference

**相关CVE**：
- CVE-2014-0160 (Heartbleed): OpenSSL内存泄露导致敏感数据暴露
- CVE-2019-1010305: 支付系统密钥材料未清零导致信息泄露

**参考标准**：
- PCI DSS 3.2.1 Requirement 6.5.6: 内存泄漏防护
- OWASP MASVS: MSTG-STORAGE-10 敏感数据内存处理
- CWE-401: Missing Release of Memory after Effective Lifetime
- CWE-226: Sensitive Information Uncleared Before Release

**推荐工具**：
- Valgrind: 内存泄漏检测
- AddressSanitizer: 编译时内存错误检测
- Coverity: 商业静态分析工具
- Dr. Memory: Windows/Linux内存调试工具