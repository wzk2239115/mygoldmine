# JavaScript/TypeScript 客户端授权依赖漏洞（Client-Side Authorization Reliance）

**漏洞成因**：前端代码中实现的价格计算、权限判断、折扣逻辑等业务规则被服务端直接信任或重复使用，攻击者通过篡改请求参数、跳过前端校验、伪造客户端状态绕过业务限制，导致越权操作、金额篡改、逻辑绕过。

---

## Details

**核心代码特征**：
```javascript
// 典型漏洞模式 1：前端计算价格后提交
const finalPrice = item.price * quantity - couponDiscount;
await fetch('/api/order', {
    method: 'POST',
    body: JSON.stringify({ itemId, quantity, finalPrice })  // 服务端直接信任 finalPrice
});
```

```typescript
// 典型漏洞模式 2：前端判断权限后调用接口
if (user.role === 'admin') {  // 可通过开发者工具篡改
    await deleteUserAPI(targetUserId);  // 后端未二次校验权限
}
```

```javascript
// 典型漏洞模式 3：隐藏的前端逻辑控制
<button disabled={!user.isPremium} onClick={downloadFile}>
    下载高清资源  {/* disabled 属性可被移除 */}
</button>
```

**审计定位技巧**：

**L1 - 关键词扫描**：
- **价格相关**：`price`、`amount`、`total`、`finalPrice`、`discount`、`coupon`
- **权限相关**：`role`、`permission`、`isAdmin`、`canAccess`、`hasPermission`
- **状态相关**：`isPremium`、`isVip`、`subscriptionLevel`、`trialExpired`
- **敏感操作**：`fetch()`、`axios.post()`、`$.ajax()`、`mutation()`（GraphQL）

**L2 - 跳读（核心操作）**：
1. **定位计算点**：搜索数学运算 `*`、`-`、`+` 与 `price/amount` 组合
2. **追踪参数流**：计算结果是否直接放入请求体 `body: JSON.stringify({...})`
3. **检查条件分支**：`if (user.xxx)` 后的 API 调用，判断条件是否可篡改

**L3 - 逐行审计（客户端逻辑）**：
- **Redux/Vuex 状态**：检查 `state.user.role` 等状态是否用于敏感判断
- **LocalStorage/Cookie**：`localStorage.getItem('userRole')` 后直接用于业务决策
- **URL 参数传递**：`?price=100&discount=50` 直接提交到后端
- **注释泄露**：代码中 `// TODO: move to backend` 但未实施

**L4 - 跨模块追踪（保护机制）**：
服务端对应接口是否有保护（需查看后端代码）：
- **重新计算**：服务端根据 `itemId + quantity` 独立计算价格
- **权限中间件**：`@RequireRole('admin')`、`verifyToken()`、JWT 校验
- **服务端验证**：数据库查询 `SELECT price FROM items WHERE id=?` 重新取值
- **签名校验**：请求参数附带 HMAC 签名，防止篡改

**危险信号**（审计等级提升至 L3）：
- 前端代码包含 `calculateTotal`、`applyDiscount` 等金额计算函数
- API 请求参数包含计算结果（`total`、`finalAmount`）而非原始数据
- 权限判断后直接调用删除/修改 API，URL 无 token 或签名
- GraphQL 查询中 `@client` 指令标记的客户端状态用于业务逻辑

---

## Classify

### ✅ 确认漏洞
- **前端算价后端信任**：客户端计算折扣价/总价，服务端 API 直接使用请求中的 `finalPrice` 参数
- **仅前端校验权限**：删除/修改接口无后端权限验证，仅依赖前端 `if (isAdmin)` 判断
- **可篡改状态决策**：LocalStorage/SessionStorage 中的 `userLevel` 直接影响功能开放
- **隐藏元素控制**：通过 CSS `display:none` 或 `disabled` 属性限制功能，后端无校验
- **客户端路由守卫**：仅前端路由 `beforeEach` 判断权限，直接访问路由可绕过

### ⚠️ 误报/需深入确认
- **仅 UI 展示逻辑**：前端判断是否显示按钮，但后端接口有独立权限校验（需确认后端实现）
- **已有服务端重算**：虽然前端传了 `price`，但后端有 `validatePrice()` 函数重新验证（需审计后端代码）
- **只读数据获取**：前端控制是否发起查询请求，但查询本身无敏感操作（如搜索、分页）
- **测试/调试代码**：`if (process.env.NODE_ENV === 'development')` 中的逻辑，生产环境未启用

### 🔍 代码异味
- **混合验证模式**：部分接口后端有校验，部分无校验（说明安全意识不统一）
- **注释标记待办**：`// FIXME: should validate on server` 但未实施
- **冗余前端逻辑**：前端复杂计算逻辑与后端重复，增加不一致风险
- **硬编码价格**：前端 JS 中写死 `const VIP_PRICE = 99`，与后端配置可能不同步

---

## Low Risk

以下场景可评为低风险（但仍需标注并建议修复）：

1. **非敏感功能控制**：仅控制 UI 主题、布局偏好等无金额/权限影响的功能
2. **价格仅供展示**：前端计算的价格仅用于实时展示，提交时只传商品 ID，后端独立计算
3. **双重验证机制**：虽然前端有判断，但服务端有完整的二次校验（需审计后端代码确认）
4. **只读操作**：客户端控制是否展示某些数据，但数据本身已通过后端权限过滤
5. **后台管理系统**：内网环境部署，用户均为可信员工（但不推荐依赖环境安全）

**风险升级条件**（低风险→高风险）：
- 涉及金额计算、折扣、优惠券等财务相关逻辑
- 控制删除、修改、导出等敏感操作权限
- 公网暴露的 API 接口，无任何后端校验
- 可通过浏览器开发者工具直接篡改并复现
- 历史出现过类似漏洞被利用的记录