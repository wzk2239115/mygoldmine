# Node.js MongoDB ObjectId 直接访问 IDOR

## Details

**代码示例：**
```javascript
// 漏洞示例
app.post('/api/document/:id', async (req, res) => {
  const doc = await Document.findById(req.params.id);
  // 直接返回文档，无所有权验证
  res.json(doc);
});

app.put('/api/user/profile', async (req, res) => {
  const { userId } = req.body;
  const user = await User.findByIdAndUpdate(userId, req.body);
  res.json(user);
});
```

**快速定位核心操作（L2-跳读）：**
- 搜索关键模式：`findById`、`findOne({ _id:`、`findByIdAndUpdate`、`findByIdAndDelete`
- 关注ID来源：`req.params.id`、`req.body.userId`、`req.query.id`、`req.body._id`
- 跳读查询链：直接传参给Model方法 → 高风险；经过转换/验证 → 继续追踪
- 快速排查：`.select('-password')`只是字段过滤非权限控制

**快速定位保护机制（L3-逐行读 / L4-跨模块追踪）：**
- **L3-当前函数内**：查找`userId === req.user.id`、`doc.owner.equals(req.user._id)`、`doc.userId.toString() === sessionUserId`等比对逻辑
- **L4-中间件层**：追踪路由级中间件如`checkOwnership`、`validateAccess`，需进入实现确认非空检查
- **L4-数据库层**：检查查询条件是否包含用户上下文，如`findOne({ _id: id, userId: req.user.id })`
- **关键反模式**：仅检查`req.user`存在（认证）但未验证ID归属（授权）
- **Mongoose钩子陷阱**：pre/post钩子可能藏权限逻辑需跨文件追踪Model定义

## Classify

**漏洞判定**：ID参数源自客户端输入 + 数据库查询无用户上下文过滤 + 缺少显式所有权比对 = 确认IDOR

**误报识别**：  
1. 查询包含复合条件如`{ _id: id, organizationId: req.user.orgId }` → 数据库层隔离
2. 查询后有`if (!doc || doc.ownerId !== req.user.id) throw 403` → 代码层保护
3. 公开资源如文章详情页（需业务确认读取权限设计）

**代码异味**：  
- 存在权限检查但可绕过：`if (doc.userId) { /* 仅当字段存在时检查 */ }`
- 不一致保护：部分端点有验证、部分端点遗漏
- ID类型混淆：字符串比对ObjectId（`doc.userId == req.user.id`可能类型强制转换掩盖问题）

## Low risk

1. **只读公开数据**：资源设计为全员可读（如公共博客、产品目录），无敏感字段泄露
2. **功能受限资源**：虽可访问他人ID但无敏感操作（如查看用户公开昵称/头像）
3. **数据已脱敏**：返回聚合/统计数据而非原始记录
4. **后置无效利用**：读取他人数据但后续流程强制二次验证（如订单查看后支付需短信验证）
5. **生产环境ID不可预测**：使用UUID替代自增ID + 实施速率限制（降低枚举风险但非根本修复） 