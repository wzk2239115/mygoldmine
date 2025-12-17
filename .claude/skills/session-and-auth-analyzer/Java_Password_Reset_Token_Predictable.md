# Java_Password_Reset_Token_Predictable

**漏洞类型**: Java 密码重置功能中重置令牌由可预测的算法生成，导致令牌可被预测或枚举

---

## Details

### 代码示例

```java
public String generateResetToken() {
    return String.valueOf(System.currentTimeMillis());  // 可预测
}

// 修复
public String generateResetToken() {
    return new BigInteger(130, random).toString(32);  // 128+ bits
}
```

### 快速定位核心操作 **[L1-L2]**

**L1 关键词扫描**:
- `System.currentTimeMillis()`, `System.nanoTime()`
- `new BigInteger()`
- `SecureRandom`
- 令牌生成函数

**L2 跳读定位**:
- 重置令牌生成代码

### 快速定位保护机制 **[L2-L4]**

**L2 跳读检测**:
- `SecureRandom` 使用
- 足够的位数

**L3 逐行分析**:
- 使用 `SecureRandom`
- >= 128 bits 熵值

---

## Classify

确认为漏洞: 时间戳生成或过短
误报判定: 密码学安全的随机

---

## Low risk

- 虽可预测但令牌有验证和过期
- 短期有效令牌
