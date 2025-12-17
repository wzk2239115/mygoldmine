# JWT 解析时忽略 exp 校验

**漏洞成因**：JWT 解析时未校验 `exp`（过期时间）声明，或显式设置 `ignoreExpiration: true`，导致过期令牌仍被接受。

---

## Details

### 代码示例

**漏洞模式 1：显式忽略过期校验**
```javascript
const jwt = require('jsonwebtoken');
// 危险：ignoreExpiration 设为 true
const decoded = jwt.verify(token, secret, { ignoreExpiration: true });
```

**漏洞模式 2：未校验 exp 声明**
```javascript
const jwt = require('jsonwebtoken');
// 危险：仅解码不验证
const decoded = jwt.decode(token);
// 或手动验证但遗漏 exp 检查
```

**漏洞模式 3：自定义校验遗漏**
```javascript
const decoded = jwt.verify(token, secret);
// 危险：后续逻辑未检查 decoded.exp 与当前时间
if (decoded.userId) {
  // 直接使用，未验证过期
}
```

### 快速定位核心操作（L1: 关键词扫描）
- **搜索关键词**：`jwt.verify`、`jwt.decode`、`jsonwebtoken`、`ignoreExpiration`
- **关注点**：
  - `jwt.verify()` 的第三个参数（options 对象）
  - `jwt.decode()` 的调用场景（仅解码不校验签名和过期）
  - 手动解析 payload（如 `Buffer.from(token.split('.')[1], 'base64')`）

### 快速定位保护机制（L2: 跳读）
- **查找正向模式**：
  - `jwt.verify()` 不带 `ignoreExpiration` 或显式设为 `false`
  - 检查 `decoded.exp` 与 `Date.now() / 1000` 比较
  - 使用中间件（如 `express-jwt`）默认启用过期校验
- **审计等级**：
  - **L1**：搜索所有 JWT 解析调用点
  - **L2**：跳读 verify/decode 上下文，确认是否存在 exp 相关逻辑
  - **L3**：逐行检查 options 参数、decode 后的手动校验逻辑
  - **L4**：跨模块追踪自定义中间件或工具函数的 JWT 处理流程

---

## Classify

### 漏洞判定
- `jwt.verify()` 显式设置 `ignoreExpiration: true` → **确认漏洞**
- `jwt.decode()` 用于鉴权场景且无后续 exp 校验 → **确认漏洞**
- 手动解析 payload 且未实现过期检查 → **确认漏洞**

### 误报情形
- `jwt.decode()` 仅用于读取非敏感元数据（如展示用户名），不涉及权限判断 → **误报**
- 调用 `jwt.verify()` 后，在业务层通过数据库或缓存二次校验令牌有效性（如黑名单机制） → **低风险或误报**（需确认二次校验覆盖过期场景）

### 代码异味
- 存在 `jwt.verify()` 但 exp 逻辑分散在多处，难以全局审计 → **代码异味**，建议统一封装
- 使用第三方库（如 `passport-jwt`）但配置不明确 → **需进一步跟踪配置**

---

## Low risk

### 低风险场景
1. **令牌生命周期极短**（如 exp 设为 60 秒）且令牌用于一次性操作（如单次 API 调用），过期风险窗口极小
2. **受其他机制兜底**：
   - 应用层实现会话管理（如 Redis 存储有效令牌列表），过期令牌被动态阻断
   - 令牌仅用于低敏操作（如访问公开资源），即使过期也无安全影响
3. **测试/演示代码**：非生产环境的开发调试代码，带有明确注释说明 `ignoreExpiration` 仅用于测试
4. **refresh token 场景**：刻意允许 refresh token 不校验 exp，但限定在特定端点且与 access token 分离

### 评级依据
- 需综合评估：令牌作用域、权限级别、补偿控制措施
- 若无兜底机制且用于高敏操作（如转账、管理员权限）→ **不应降级**