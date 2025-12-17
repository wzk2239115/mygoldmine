# Rust_Session_Unencrypted_Storage

**漏洞类型**: Rust 会话数据存储在数据库或缓存中但未加密，导致敏感信息泄露

---

## Details

### 代码示例

```rust
// 未加密存储
let session_data = serde_json::to_string(&session)?;
redis.set(&session_id, &session_data)?;  // 明文存储

// 修复: 加密存储
let encrypted = encrypt_session(&session, &key)?;
redis.set(&session_id, &encrypted)?;
```

### 快速定位核心操作 **[L1-L2]**

**L1 关键词扫描**:
- `redis.set()`, `db.insert()`
- `serde_json::to_string()`
- 加密函数缺失

**L2 跳读定位**:
- 会话存储代码
- 数据库或缓存操作

### 快速定位保护机制 **[L2-L4]**

**L2 跳读检测**:
- 加密库使用: `aes`, `chacha20poly1305`
- 加密调用

**L3 逐行分析**:
- 存储前加密
- 检索后解密
- 密钥管理安全

---

## Classify

确认为漏洞: 明文存储敏感数据
误报判定: 加密存储
代码异味: 有加密库导入但不使用

---

## Low risk

- 虽无加密但数据库有访问控制
- 无高价值信息
