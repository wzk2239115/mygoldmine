# JavaScript 对象合并批量赋值漏洞

## Details

### 漏洞成因
在 Node.js/前端同构应用中，开发者常使用 `Object.assign`, `lodash.merge`, `spread operator (...)`, `deepmerge` 等函数，将请求体数据合并到现有对象。如果缺乏字段白名单，攻击者可以利用这些合并函数覆盖敏感属性（如 `isAdmin`, `roles`, `status`, `tenantId`, `price`, `config`). 深度合并工具还可能创建原本不存在的嵌套字段或污染原型。

### 代码示例

**易受攻击的代码：**
```javascript
app.post("/profile", async (req, res) => {
  const user = await User.findById(req.user.id);
  Object.assign(user, req.body); // req.body 可包含 { role: "admin" }
  await user.save();
  res.json(user);
});
```

**另一个不安全示例（lodash.merge）：**
```javascript
const _ = require("lodash");

function updateSettings(current, payload) {
  // payload 可包含 { security: { allowDebug: true } }
  return _.merge(current, payload);
}

router.put("/settings", async (req, res) => {
  const settings = await loadSettings();
  const merged = updateSettings(settings, req.body);
  await saveSettings(merged);
  res.json(merged);
});
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- `Object.assign`, `{ ...obj, ...payload }`, `lodash.merge`, `_.assign`, `deepmerge`
- 函数名：`mergeConfig`, `applyPatch`, `hydrate`
- 使用请求数据：`req.body`, `ctx.request.body`, `payload`
- 受影响对象包含敏感字段：`role`, `permissions`, `settings`, `config`

**定位步骤：**
1. 搜索上述函数，查看合并目标对象类型。
2. 检查源数据是否来自用户输入。
3. 跳读（L2）确认是否过滤敏感字段或使用白名单。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **白名单：** `const allowed = ['name', 'email']; const data = pick(req.body, allowed);`
- **深度保护：** 对嵌套对象单独处理，不直接合并。
- **权限校验：** 在合并前验证当前用户权限。
- **默认值重写：** 合并后重写敏感字段。
- **使用不可变对象/DTO：** 防止任意属性写入。

**定位技巧：**
- 确认 `lodash.merge` 等函数对原型链处理是否安全（避免原型污染）。
- 检查合并结果是否直接保存到数据库/配置文件。
- 对多租户场景，确认租户 ID 不会被覆盖。

#### 审计等级标注

| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 使用 `pick`/白名单后再合并 | **L0（快速跳过）** | 风险低 |
| 合并后重写敏感字段 | **L2（跳读）** | 检查覆盖范围 |
| 直接 `Object.assign`/`merge` 用户输入 | **L3（逐行读）** | 高风险 |
| 递归合并配置/多租户设置 | **L4（跨模块追踪）** | 需分析全链路 |

## Classify

### 研判标准

#### 确认漏洞
需满足以下条件：
1. **合并函数** 直接使用外部输入。
2. **缺乏字段过滤或敏感字段重写**。
3. **导致敏感状态被覆盖**（权限、配置、安全选项等）。

#### 误报
可视为误报的情况：
1. 合并前已使用白名单提取字段。
2. 合并后立即重写敏感字段，确保不可修改。
3. 数据仅用于只读操作，无持久化或状态改变。

#### 代码异味
需关注的风险：
1. 依赖黑名单 `delete payload.role` 方式过滤。
2. 深度合并操作可能产生原型污染 (`__proto__`、`constructor`)。
3. 对象合并用于应用级配置，影响全局行为。
4. 同一函数被内部和外部调用，逻辑混用。

## Low risk

### 低风险评级场景

#### 1. 内部使用
- **场景：** 函数仅在受控内部流程被调用。
- **风险评估：** 攻击面有限，但需防误用。

#### 2. DTO 白名单
- **场景：** 先构造 DTO，再合并到目标对象。
- **风险评估：** 风险较低，需维护白名单。

#### 3. 配置签名/校验
- **场景：** 合并结果需通过签名或校验，防止未授权修改。
- **风险评估：** 降低危害，但非根治。

#### 4. 审计与告警
- **场景：** 对关键配置或权限变更记录日志并告警。
- **风险评估：** 有助于监测，但仍需修复根因。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 内部受控调用 | 攻击面有限 | 中 |
| DTO 白名单 | 技术防护完善 | 低 |
| 校验/签名机制 | 阻止未授权修改 | 中 |
| 审计告警 | 及时发现问题 | 高（持续改进）|

