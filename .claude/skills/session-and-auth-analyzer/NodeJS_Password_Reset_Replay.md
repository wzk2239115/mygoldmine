# NodeJS_Password_Reset_Replay

**漏洞类型**: Express/Node.js 密码重置功能中，重置令牌未设置单次使用限制，导致同一令牌可被多次重放利用进行重置攻击

---

## Details

### 代码示例

**易受攻击的代码模式**:
```javascript
// 示例1: 令牌无使用标记
const PasswordResetToken = require('./models/PasswordResetToken');
app.post('/forgot-password', async (req, res) => {
    const token = crypto.randomBytes(32).toString('hex');
    await PasswordResetToken.create({
        userId: user.id,
        token: token,
        expiresAt: new Date(Date.now() + 3600000)
        // 缺少 used 或 used_at 字段
    });
});

// 示例2: 密码重置时未标记令牌
app.post('/reset-password/:token', async (req, res) => {
    const resetToken = await PasswordResetToken.findOne({ token: req.params.token });
    if (resetToken && resetToken.expiresAt > new Date()) {
        // 验证成功但未标记为已使用
        const user = await User.findById(resetToken.userId);
        user.password = hashPassword(req.body.password);
        await user.save();
        // 令牌仍然有效，可被重复使用
    }
});

// 示例3: 令牌验证后未删除
async function resetPassword(token, newPassword) {
    const record = await PasswordResetToken.findOne({ token });
    if (record && record.expiresAt > new Date()) {
        await updatePassword(record.userId, newPassword);
        // 缺少 await PasswordResetToken.deleteOne({ token })
    }
}

// 示例4: 令牌可重放的竞态条件
app.post('/reset/:token', async (req, res) => {
    const reset = await PasswordResetToken.findOne({ token: req.params.token });
    if (reset && !reset.used) {
        // 并发请求可能都通过此检查
        const user = await User.findById(reset.userId);
        user.password = req.body.password;
        await user.save();
        reset.used = true;
        await reset.save(); // 异步操作，竞态窗口大
    }
});

// 示例5: 缺少原子性操作
async function processReset(token, password) {
    const reset = await PasswordResetToken.findOne({ token });
    if (!reset.used) {
        // Step 1: 查询
        const user = await User.findById(reset.userId);
        user.password = hashPassword(password);
        await user.save();
        // Step 2: 标记使用 (可能失败)
        reset.used = true;
        await reset.save();
    }
}

// 示例6: 令牌验证后不清理相关数据
app.post('/confirm-reset/:token', async (req, res) => {
    const token = await PasswordResetToken.findOne({ token: req.params.token });
    if (token && !token.used) {
        const user = await User.findById(token.userId);
        user.passwordHash = hashPassword(req.body.newPassword);
        await user.save();
        // 未删除所有该用户的重置令牌
    }
});
```

### 快速定位核心操作 **[L1-L2]**

**L1 关键词扫描**:
- 密码重置令牌: `PasswordResetToken`, `ResetToken`, `password_reset_token`
- 令牌验证: `findOne({ token })`, `PasswordResetToken.findOne()`, `verifyToken()`, `validateToken()`
- 使用标记: `used`, `used_at`, `consumed`, `redeemed`, `valid`
- 令牌删除: `deleteOne()`, `remove()`, `destroy()`, `delete()` on reset token
- 竞态相关: 异步操作中缺少锁或事务

**L2 跳读定位**:
- 密码重置路由: `/forgot-password`, `/reset-password`, `/password-reset/:token`
- 追踪令牌从生成 -> 验证 -> 使用标记的流程
- 检查是否存在 `used` 或 `used_at` 字段
- 验证令牌使用后是否删除或标记
- 查看是否有原子性保护或数据库事务

### 快速定位保护机制 **[L2-L4]**

**L2 跳读检测**:
- 使用状态检查: `if (!reset.used)`, `if (!reset.consumed)`, `reset.isValid()`
- 令牌删除操作: `await PasswordResetToken.deleteOne()`, `reset.destroy()`
- 原子操作: 数据库事务 `transaction()`, `findOneAndUpdate()` 原子更新

**L3 逐行分析**:
- 使用标记实现:
  - 是否有 `used` boolean 字段或 `used_at` timestamp 字段
  - 是否在验证时检查了此字段: `if (!reset.used)`
  - 标记时是否原子化: `findOneAndUpdate()` vs 分离的 query & update
- 删除策略:
  - 验证成功后是否立即删除令牌: `await PasswordResetToken.deleteOne()`
  - 是否删除该用户的所有旧令牌
  - 是否有过期令牌的清理任务
- 并发安全:
  - 是否使用数据库事务: `db.transaction()`, `session.startTransaction()`
  - 是否使用 findOneAndUpdate() 进行原子操作
  - 是否有分布式锁 (如 Redis)
  - 错误处理是否恰当，失败是否回滚
- 令牌验证逻辑:
  - 检查顺序: 先检查 `used` 还是先检查 `expiresAt`
  - 是否同时检查了 `userId` 防止跨用户使用

**L4 跨模块追踪**:
- 追踪数据库事务的实现 (Sequelize, TypeORM, Prisma 等)
- 检查中间件或钩子是否有额外的令牌验证
- 审查邮件发送模块，确认令牌生成和发送的原子性
- 检查是否有备用重置方法 (安全问题等)，它们是否同样安全
- 验证审计日志是否记录了令牌使用

---

## Classify

### 漏洞判定标准

**确认为漏洞**:
- 令牌模型缺少 `used` 或 `consumed` 字段
- 令牌验证时未检查使用状态，可无限次重放
- 验证成功后未删除或标记令牌
- 令牌标记的操作非原子性，存在竞态窗口
- 同一用户有多个有效令牌时，旧令牌未被撤销
- 可通过并发请求同时使用一个令牌多次更改密码

**误报判定**:
- 令牌验证后立即删除，查询时即不存在
- 使用 `findOneAndUpdate()` 原子操作标记使用
- 实现了数据库事务确保原子性
- 每个令牌有唯一约束，且验证后删除，无法重用
- 应用有发送邮件等重置流程中的恢复机制

**代码异味**:
- 存在 `used` 字段但仅在某些验证路径中检查
- 令牌删除被注释掉或有条件地执行
- 验证和标记之间有其他查询或操作
- 使用全局变量或缓存跟踪已使用令牌，不可靠
- 日志中记录了明文令牌

---

## Low risk

### 低风险场景

**访问限制**:
- 密码重置仅限已认证的用户，通过邮箱验证的二次确认
- 令牌与特定 IP 或设备绑定，跨环境使用无效

**检测与监控**:
- 实时监控单个用户密码重置频率，异常时告警
- 记录每次令牌验证尝试，包括失败的尝试
- 检测多个账户同时重置时，可能为批量攻击

**补偿控制**:
- 密码重置后自动登出所有会话
- 重置后在敏感操作前需要额外验证
- 用户邮箱中有重置活动的通知
