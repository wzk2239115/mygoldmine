# JavaScript｜基于 action 的路由分发缺少授权

## Details

### 漏洞成因
一些 Node.js 服务使用 `action`、`event`、`type` 字段进行动态路由分发，将请求映射到不同处理函数。如果在执行前不验证 `action` 是否允许当前用户调用，就可能被普通用户伪造请求触发敏感操作。该模式常见于 Socket.IO、WebSocket 消息、队列处理、Webhook。

### 代码示例

**易受攻击示例：**
```js
const actions = {
  'user:update': updateUser,
  'admin:export': exportUsers // 应限制管理员
};

io.on('connection', socket => {
  socket.on('action', payload => {
    const handler = actions[payload.type];
    if (handler) {
      handler(socket, payload); // 未校验 socket.user 权限
    }
  });
});
```

**安全示例：**
```js
const actions = {
  'user:update': wrapWithAuth('user:update', updateUser),
  'admin:export': wrapWithAuth('admin:export', exportUsers)
};

function wrapWithAuth(permission, handler) {
  return (socket, payload) => {
    if (!socket.user || !socket.user.permissions.includes(permission)) {
      socket.emit('error', 'forbidden');
      return;
    }
    handler(socket, payload);
  };
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `actions`, `dispatch`, `switch (action)`, `socket.on`, `event`, `type`, `command`。

**定位步骤：**
1. 搜索基于字符串的路由分发；
2. 跳读（L2）确认 handler 是否封装权限逻辑；
3. 检查 action 表是否包含敏感操作。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- `wrapWithAuth`, `authorizeAction` 等封装；
- socket/user 对象含权限并被校验；
- 消息签名或服务端 ACL；
- 分离管理员 action 到独立通道。

**定位技巧：**
- 逐行读（L3）敏感 action，如导出、重启、支付；
- 跨模块追踪（L4）不同协议（HTTP、WS、MQ）是否复用同 action 表。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| action 注册即绑定权限 | **L0（快速跳过）** | 安全性高 |
| 少量 action 缺校验 | **L2（跳读）** | 需确认 |
| action 直接执行 handler | **L3（逐行读）** | 高风险 |
| 多通道共享 action 表 | **L4（跨模块追踪）** | 全链路审计 |

## Classify

### 研判标准

#### 确认漏洞
1. 参数控制 action；
2. 未校验权限；
3. 普通用户可触发敏感操作。

#### 误报
1. action 表仅包含非敏感操作；
2. handler 内部校验用户权限；
3. 通道仅供受信任服务使用。

#### 代码异味
1. 使用 `eval` 或动态 `require` 执行 action；
2. 依赖客户端 `isAdmin` 字段；
3. 缺少审计日志与告警。

## Low risk

### 低风险评级场景

#### 1. 动作只触发通知或查询
- **评估：** 可标低风险。

#### 2. 内部专用通道
- **评估：** 攻击面小。

#### 3. 将引入统一权限包装
- **评估：** 暂降级，跟踪执行。

#### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 非敏感动作 | 影响有限 | 低 |
| 内部通道 | 攻击面低 | 中 |
| 改造计划明确 | 可暂缓 | 低 |
