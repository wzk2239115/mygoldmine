# C_Auth_Timing_Attack

**漏洞类型**: C 认证函数中密码比较使用字符串比较而非安全比较，存在时序攻击风险

---

## Details

### 代码示例

```c
// 不安全: strcmp 会在第一个不匹配时返回
int authenticate(const char *input, const char *correct) {
    return strcmp(input, correct) == 0;  // 时序泄露
}

// 修复: 常时间比较
int secure_compare(const unsigned char *a, const unsigned char *b, size_t len) {
    unsigned char result = 0;
    for (size_t i = 0; i < len; i++) {
        result |= a[i] ^ b[i];
    }
    return result == 0;
}
```

### 快速定位核心操作 **[L1-L2]**

**L1 关键词扫描**:
- `strcmp()`, `password == `
- 密码比较函数
- 缺失安全比较

**L2 跳读定位**:
- 认证代码中密码比较部分

### 快速定位保护机制 **[L2-L4]**

**L2 跳读检测**:
- 常时间比较函数

**L3 逐行分析**:
- 所有比较都是常时间
- 使用 XOR 或其他方式

---

## Classify

确认为漏洞: 使用 `strcmp()`
误报判定: 使用常时间比较

---

## Low risk

- 虽有时序泄露但很难利用
- 配合其他限制
