# CPP_Session_Weak_Random

**漏洞类型**: C++ 会话管理中使用不安全的随机数生成器，导致会话令牌可被预测

---

## Details

### 代码示例

```cpp
#include <cstdlib>
#include <ctime>
std::string generateToken() {
    srand(time(nullptr));  // 弱种子
    return std::to_string(rand());  // 弱 RNG
}

// 修复: 使用安全 RNG
#include <random>
std::string generateToken() {
    std::random_device rd;
    std::mt19937_64 gen(rd());
    std::uniform_int_distribution<> dis(0, 255);
    // 或使用 OpenSSL
}
```

### 快速定位核心操作 **[L1-L2]**

**L1 关键词扫描**:
- `rand()`, `srand()`, `time()`
- `random_device`, `mt19937`
- 令牌生成函数

**L2 跳读定位**:
- RNG 初始化
- 令牌生成代码

### 快速定位保护机制 **[L2-L4]**

**L2 跳读检测**:
- `<random>` 头文件使用
- OpenSSL 或 Crypto++ 库

**L3 逐行分析**:
- 使用系统 RNG 或密码学库
- 足够长的随机序列

---

## Classify

确认为漏洞: 使用 `rand()` 或弱 RNG
误报判定: 使用系统 RNG 或密码库

---

## Low risk

- 虽弱但有其他验证
