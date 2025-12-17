# Node.js Express 路由参数 IDOR 漏洞审计

## Details

**典型代码示例：**
```javascript
app.get('/api/user/:userId', async (req, res) => {
  const user = await User.findById(req.params.userId);
  res.json(user);
});

app.get('/api/order', async (req, res) => {
  const order = await Order.findOne({ id: req.query.orderId });
  res.json(order);
});
```

**快速定位核心操作（L2-跳读）：**
- 定位路由定义：搜索 `app.get/post/put/delete`、`router.get/post/put/delete`、`@Get/@Post` 装饰器
- 追踪参数提取：`req.params.*`、`req.query.*`、`req.body.*` → 直接用于数据库查询
- 关注数据库操作：`.findById()`、`.findOne()`、`.find()`、`.query()`、ORM查询链
- 响应数据流向：查询结果直接 `res.json()`、`res.send()` 返回

**快速定位保护机制（L3-逐行读，L4-跨模块追踪）：**
- **L3-函数内检查**：查找 `req.user`、`req.session` 与查询结果的对比逻辑
  - `if (user.id !== req.user.id)` / `if (order.userId === req.user.id)`
  - `user.tenantId === req.user.tenantId` 等租户隔离检查
- **L4-中间件链**：追踪路由前的 middleware 栈
  - `authMiddleware` → 检查是否仅验证身份未验证权限
  - `checkOwnership`、`authorize` 等权限中间件 → 查看实现是否严密
  - 注意中间件顺序，权限检查必须在业务逻辑前执行
- **L4-ORM模型层**：检查 Model 的 hooks/scopes
  - Sequelize: `defaultScope`、`beforeFind` 钩子是否添加用户过滤
  - Mongoose: `pre('find')` 中间件、虚拟字段访问控制
  - TypeORM: `@BeforeLoad` 装饰器、QueryBuilder 的全局过滤器
- **L1-关键词扫描**：`checkPermission`、`isOwner`、`canAccess`、`authorize` 等函数调用

## Classify

**漏洞判定标准：**
- 用户可控ID参数直接查询敏感资源（订单、私信、个人信息等）
- 无任何所有权验证或资源隔离机制
- 攻击者可通过枚举ID访问他人数据

**误报场景：**
- 查询的是公开资源（文章列表、商品详情等无需权限控制的数据）
- 中间件或数据库层已实现全局过滤（需深度验证实现完整性）
- 查询条件中隐式绑定了用户身份（如 `{id: params.id, userId: req.user.id}`）

**代码异味（潜在风险）：**
- 权限检查分散在多个路由中而非统一中间件，易遗漏
- 使用前端传入的 `userId` 而非从 session/token 中提取
- 部分路由有检查、部分路由无检查，实现不一致

## Low Risk

**以下情况可降低风险等级：**
- **资源本身低敏感度**：访问日志、统计数据聚合结果、历史快照等非实时敏感信息
- **ID难以枚举**：使用 UUID/ULID 且未在其他接口泄露，攻击者难以猜测有效ID
- **数据脱敏返回**：即使访问到他人数据，返回结果已脱敏处理（姓名打码、手机号隐藏等）
- **读写分离且仅读取**：GET 请求可越权查看但无法修改/删除，且数据价值有限
- **生产环境额外防护**：WAF 规则、API 网关层的二次鉴权（需确认实际生效）

**注意**：低风险不等于无风险，仍应在审计报告中记录并建议修复。