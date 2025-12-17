# CPP_Session_Logout_Memory_Leak

**漏洞类型**: C++ 自定义会话管理中，用户登出后会话对象和敏感数据未从内存中清除，导致敏感信息泄露

---

## Details

### 代码示例

**易受攻击的代码模式**:
```cpp
// 示例1: 登出后未清理会话对象
class Session {
    char sessionID[256];
    char userData[1024];
    bool authenticated;
    
    void logout() {
        authenticated = false;
        // 缺少 memset() 清零敏感数据
        // 内存仍包含旧的用户数据
    }
};

// 示例2: 会话对象被复制但未清理
Session* createSession(const char* userID) {
    Session* session = new Session();
    strcpy(session->userData, userID); // 不安全的 strcpy
    return session;
}

void endSession(Session* session) {
    delete session; // 仅删除指针，内存可能未初始化
}

// 示例3: 静态会话对象未清理
static Session globalSession;
void logout() {
    globalSession.authenticated = false;
    // globalSession 的成员变量仍在内存中
}

// 示例4: 密码存储在栈上，未清理
bool authenticateUser(const char* password) {
    char inputPassword[128];
    strcpy(inputPassword, password);
    bool result = verify(inputPassword);
    return result; // inputPassword 在栈上，函数返回后仍可能被读取
}

// 示例5: 会话缓存未清理
std::map<std::string, Session*> sessionCache;
void removeSession(const std::string& sessionID) {
    sessionCache.erase(sessionID);
    // 仅从 map 中移除，但 Session* 对象可能未释放或未清理
}

// 示例6: 字符串处理未清理
std::string getUserData(const std::string& sessionID) {
    std::string data = sessionCache[sessionID]->userData;
    return data; // std::string 复制数据但原始位置未清理
}
```

### 快速定位核心操作 **[L1-L2]**

**L1 关键词扫描**:
- 登出函数: `logout()`, `endSession()`, `disconnect()`, `closeConnection()`
- 内存操作: `delete`, `free()`, `malloc()`, `new`, 缺少的 `memset()`
- 敏感数据: `password`, `token`, `sessionID`, `userData`, 字符数组或字符串
- 清理缺失: 未见 `memset()`, `bzero()`, `secure_zero_memory()` 等
- 指针操作: 删除后未设为 nullptr, 内存重用

**L2 跳读定位**:
- 登出路由/处理函数: 搜索 logout, disconnect 等端点的实现
- 会话对象定义: Session 类的声明和析构函数
- 内存分配: 所有 new/malloc 的对应 delete/free
- 敏感数据的生命周期: 从创建到销毁
- 检查是否有不安全的字符串操作

### 快速定位保护机制 **[L2-L4]**

**L2 跳读检测**:
- 清零函数: `memset()`, `bzero()`, `SecureZeroMemory()`, `OPENSSL_cleanse()`
- 智能指针: `std::unique_ptr`, `std::shared_ptr` 自动管理
- 析构函数: Session 类的 `~Session()` 是否清理敏感数据

**L3 逐行分析**:
- 登出逻辑:
  - 登出时是否调用了 `memset(ptr, 0, size)` 清零敏感数据
  - 清零范围是否涵盖所有敏感字段
  - 是否在删除前清零，还是删除后清零 (删除前更安全)
- 内存管理:
  - 是否使用了智能指针 (std::unique_ptr, shared_ptr) 自动清理
  - 析构函数中是否清零了敏感数据
  - 是否使用了 RAII 原则确保资源清理
- 字符串处理:
  - 是否使用 std::string (不安全) 还是 secure_string (安全)
  - std::string 的数据是否在使用后清零
  - 是否使用了字符数组且用 memset 清零
- 缓存管理:
  - map/set 中移除元素时是否也清理了数据
  - 缓存过期时是否清理旧数据
  - 是否有内存泄漏导致旧数据长期存在
- 栈内存:
  - 本地变量是否被适当清零
  - 函数返回前是否清零栈上的敏感数据
  - 是否存在缓冲区溢出风险

**L4 跨模块追踪**:
- 追踪所有会话对象的生命周期
- 检查析构函数和资源清理的完整性
- 验证全局或静态会话对象的清理
- 检查是否有第三方库负责会话管理
- 审查内存分配器和释放函数的配置

---

## Classify

### 漏洞判定标准

**确认为漏洞**:
- 登出时未清零敏感数据，内存可被读取
- 删除会话对象但未调用 memset() 清零
- 使用不安全的 strcpy 等函数，缓冲区可能溢出
- 栈上敏感数据未清理，可被缓存或侧信道攻击读取
- 静态或全局会话对象未在登出时清理
- 缓存的会话在移除后内存未清理

**误报判定**:
- 使用智能指针 (unique_ptr, shared_ptr) 自动管理
- 析构函数中明确清零了所有敏感数据
- 使用了 secure_string 或类似的安全字符串类
- 所有敏感操作后调用了 memset() 清零
- 应用有内存保护 (ASLR, canary 等)

**代码异味**:
- 存在 memset() 调用但编译器可能优化掉
- 登出函数只修改状态标志，未清理数据
- 缓存清理与内存释放不同步
- 有多个登出入口，部分清理敏感数据，部分不清理
- 注释中提到"需要清理敏感数据"但未实现

---

## Low risk

### 低风险场景

**隔离保护**:
- 应用运行在沙箱或虚拟机中，无法直接访问内存
- 操作系统级别有内存保护机制

**监控与检测**:
- 有实时内存审计，检测敏感数据的非预期访问
- 使用地址空间随机化 (ASLR) 和栈保护
