# NodeJS_Session_No_Concurrent_Limit

**漏洞类型**: Express/Node.js 认证中，未限制单个用户的并发会话数，导致用户可同时保持多个会话

---

## Details

### 代码示例

```javascript
app.post('/login', (req, res) => {
    const token = jwt.sign({ userId: user.id }, secret);
    res.json({ token });
    // 无任何并发限制检查
});

// 应该限制并发会话数
async function enforceMaxSessions(userId, maxSessions = 3) {
    const activeSessions = await getActiveSessions(userId);
    if (activeSessions.length >= maxSessions) {
        const oldest = activeSessions[0];
        await revokeSession(oldest.id);
    }
}
```

### 快速定位核心操作 **[L1-L2]**

**L1 关键词扫描**:
- 会话存储: `sessionStore[userId]`
- 会话限制: `maxSessions`, `concurrent_limit`
- 会话撤销: `revokeSession()`, `logout()`

**L2 跳读定位**:
- 登录处理逻辑
- 会话存储结构

### 快速定位保护机制 **[L2-L4]**

**L2 跳读检测**:
- 并发会话计数
- 超限时的撤销逻辑

**L3 逐行分析**:
- 登录时检查现有会话数
- 超限时撤销最旧会话
- 限制数量合理 (如 3-5)

---

## Classify

确认为漏洞: 无并发限制
误报判定: 有明确的并发限制机制
代码异味: 有会话列表但无限制检查

---

## Low risk

- 虽无限制但会话超时短
- 监控异常并发活动
