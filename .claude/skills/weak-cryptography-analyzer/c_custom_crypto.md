# C/C++ 自定义加密算法审计

## Details

### 典型代码特征
```c
// 自定义XOR加密
void custom_encrypt(unsigned char* data, size_t len, unsigned char key) {
    for(size_t i = 0; i < len; i++) {
        data[i] ^= key;
    }
}

// 自定义轮换加密
void rotate_cipher(char* text, int shift) {
    for(int i = 0; text[i]; i++) {
        text[i] = (text[i] + shift) % 256;
    }
}

// 不安全的原语组合
unsigned char hash_password(const char* pwd) {
    unsigned char h = 0;
    while(*pwd) h ^= *pwd++;
    return h;
}
```

### 快速定位核心操作（L2-L3）
**关键函数模式：**
- `encrypt/decrypt/cipher/hash/sign` 等函数名但无标准库调用
- 循环中的位运算：`^= << >> & |` 组合
- 手动实现的轮换/置换：`(x + k) % n`、数组索引变换
- 自定义"魔数"常量：`0x5A5A`、`0xDEADBEEF`

**文件级扫描（L1）：**
```bash
grep -E "void.*(encrypt|cipher|hash|sign|obfuscate)" *.c
grep -E "for.*\^=|<<|>>" crypto*.c
```

**函数级审计（L3）：**
- 检查是否调用 OpenSSL/mbedTLS/libsodium
- 确认加密逻辑是否完全自实现
- 追踪密钥来源（hardcode/rand()/time()）

### 快速定位保护机制（L2-L4）

**无保护特征（L2 跳读）：**
- 函数内无 `#include <openssl/*>` 或第三方库调用
- 加密逻辑在单个文件内完整实现
- 无外部加密服务/HSM调用

**假保护识别（L3 逐行）：**
```c
// 看似复杂实则脆弱
#define ROUNDS 16
for(int r = 0; r < ROUNDS; r++) {
    data[i] ^= key[r % keylen];  // 多轮XOR仍可逆
}
```

**跨模块追踪（L4）：**
- 检查是否封装标准库（wrapper函数内部可能自实现）
- 追踪 `typedef` 类型别名（可能隐藏自定义结构）
- 确认配置文件/编译选项是否强制使用FIPS模式

## Classify

**确认漏洞：**
- 自定义对称加密用于敏感数据（密码/密钥/个人信息）
- 自定义哈希用于完整性校验/签名
- 绕过或替换标准加密库实现
- 混淆与加密概念混淆（obfuscate ≠ encrypt）

**研判误报：**
- 仅用于非安全场景（游戏数据混淆、协议魔数）
- 测试代码/示例代码/注释掉的历史代码
- 实际是标准算法的教学实现（明确标注为demo）

**代码异味：**
- 简单编码（Base64/Hex）被命名为encrypt
- 压缩算法（zlib）与加密混合
- 可配置切换到标准库但默认自实现

**关键判断点：**
1. 数据流向：是否保护认证凭证/密钥/敏感字段
2. 调用上下文：安全模块 vs 性能优化场景
3. 注释说明：是否明确标注"临时方案"
4. 替代方案：代码库中是否存在标准实现

## Low risk

**可接受的低风险场景：**
- 许可证校验/序列号生成（非安全边界）
- 本地游戏存档防篡改（无网络传输）
- 内部调试协议混淆（隔离环境）
- 文件格式专有标记（非加密目的）
- 已废弃代码路径（配置默认禁用）

**降级条件：**
- 数据不涉及身份认证/授权决策
- 仅防御意外修改非恶意攻击
- 纵深防御中的辅助层（外层有标准加密）
- 明确文档说明非加密用途
- 攻击成本远高于资产价值（嵌入式设备物理隔离）

**注意：** 即使低风险也应建议迁移到标准实现，自定义加密违反最佳实践。