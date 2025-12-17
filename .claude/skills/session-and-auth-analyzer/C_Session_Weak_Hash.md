# C_Session_Weak_Hash

**漏洞类型**: C 自定义会话管理中会话令牌使用弱哈希算法（如 MD5），导致令牌容易被伪造

---

## Details

### 代码示例

```c
#include <openssl/md5.h>
void generate_session_id(char *id) {
    unsigned char md[MD5_DIGEST_LENGTH];
    MD5((unsigned char*)random_data, 32, md);
    // MD5 已被破坏，应使用 SHA-256
}

// 修复: 使用 SHA-256
#include <openssl/sha.h>
unsigned char sha256[SHA256_DIGEST_LENGTH];
SHA256((unsigned char*)random_data, 32, sha256);
```

### 快速定位核心操作 **[L1-L2]**

**L1 关键词扫描**:
- `MD5`, `md5`, `SHA1`, `sha1`
- `openssl/md5.h`, `openssl/sha.h`
- 令牌生成函数

**L2 跳读定位**:
- 令牌生成代码
- 哈希库的使用

### 快速定位保护机制 **[L2-L4]**

**L2 跳读检测**:
- SHA-256 或更强的哈希

**L3 逐行分析**:
- 使用 SHA-256 或 SHA-512
- 不使用 MD5 或 SHA1

---

## Classify

确认为漏洞: 使用 MD5 或 SHA1
误报判定: 使用 SHA-256+
代码异味: 使用弱哈希但受其他保护

---

## Low risk

- 虽然哈希弱但令牌还有签名验证
- 其他防护措施
