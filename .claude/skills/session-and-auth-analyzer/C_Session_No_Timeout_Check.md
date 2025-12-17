# C_Session_No_Timeout_Check

**漏洞类型**: C 自定义会话管理中，会话超时检查逻辑缺失或实现不完整，导致过期会话仍可被使用

---

## Details

### 代码示例

```c
typedef struct {
    char session_id[256];
    char username[128];
    int authenticated;
    // 缺少 created_time 或 expires_at
} Session;

int validate_session(Session *session) {
    return session->authenticated == 1;  // 仅检查认证
}

// 缺少: time_t created_time; 字段检查
```

### 快速定位核心操作 **[L1-L2]**

**L1 关键词扫描**:
- `time()`, `created_time`, `expires_at`
- `validate_session()`, `check_session()`
- `SESSION_TIMEOUT` 常量
- 时间比较逻辑

**L2 跳读定位**:
- 会话结构体定义
- 验证函数实现
- 中间件的超时检查

### 快速定位保护机制 **[L2-L4]**

**L2 跳读检测**:
- `time_t` 字段存在
- 超时比较逻辑

**L3 逐行分析**:
- 会话有 `created_time` 或 `expires_at`
- 验证时检查 `(current_time - created_time) > timeout`
- 过期会话被销毁

**L4 跨模块追踪**:
- 所有会话访问点
- 会话清理机制

---

## Classify

确认为漏洞: 缺少时间字段或超时检查
误报判定: 有明确过期时间和检查逻辑
代码异味: 时间字段未使用

---

## Low risk

- 虽无超时但有权限验证
- 定期强制重新认证
