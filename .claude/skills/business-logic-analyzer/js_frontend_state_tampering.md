# 前端状态篡改漏洞 (Frontend State Tampering)

**漏洞类型**：前端状态管理依赖本地存储或内存状态，可被用户篡改后绕过业务校验

---

## Details

**审计等级**：L2-L3（跳读至逐行读，关注权限/金额/状态字段）

### 代码示例

```javascript
// 典型漏洞场景1: localStorage存储权限信息
const userRole = localStorage.getItem('role');
if (userRole === 'admin') {
  showAdminPanel();  // 前端直接依赖本地角色判断
}

// 典型漏洞场景2: 内存状态控制业务逻辑
let isPremium = false;
function unlockFeature() {
  if (isPremium) downloadPremiumContent();
}

// 典型漏洞场景3: sessionStorage控制价格
const discountRate = sessionStorage.getItem('discount') || 0;
const finalPrice = originalPrice * (1 - discountRate);

// 典型漏洞场景4: Redux/Vuex状态控制权限
const canDelete = useSelector(state => state.user.permissions.delete);
if (canDelete) deleteRecord();
```

### 快速定位核心操作

1. **关键词搜索**：`localStorage.getItem|sessionStorage.get|useState|Vuex.state|Redux.store` + `if|&&|?`
2. **关注业务字段**：`role|permission|price|discount|balance|quota|isPremium|isVIP|canEdit`
3. **定位决策点**：查找前端条件判断后直接执行敏感操作（显示UI、提交请求、计算金额）
4. **追溯来源**：检查状态初始值来源，是否仅从前端赋值（`useState(false)`、`data() { return { isAdmin: false }}`）

### 快速定位保护机制

1. **后端校验**：检查API调用是否携带服务端签名/token验证
   - 搜索：`Authorization|X-Signature|verify`
   - 关注请求体是否包含关键字段，且服务端有独立校验
2. **只读展示**：前端状态仅控制UI显示，实际操作需后端鉴权
   - 查看：按钮是否仅disable样式，请求是否必经服务端检查
3. **状态加密/签名**：localStorage存储的数据是否加密或签名
   - 搜索：`crypto|sign|encrypt|HMAC` 
4. **服务端渲染**：SSR场景下状态从服务端注入
   - 查看：`getServerSideProps|serverMiddleware`

---

## Classify

### ✅ 确认为漏洞

1. **权限绕过**：`role/permission`字段仅存储在localStorage/state，控制管理功能入口，后端无独立鉴权
2. **金额篡改**：价格、折扣、余额计算依赖前端状态，提交订单时服务端不重算
3. **业务逻辑跳过**：试用/付费状态、次数限制存储在前端，篡改后可无限使用
4. **敏感操作依赖**：删除/编辑/导出等操作的权限判断仅在前端进行

### ⚠️ 疑似漏洞（需进一步验证）

1. 前端有状态控制，但API请求参数不包含该字段（可能服务端通过session独立判断）
2. 状态来自服务端响应，但不确定后续操作是否复用该值而非重查
3. 代码混淆/加密严重，无法直接判断保护逻辑

### ❌ 误报

1. **纯UI展示**：状态仅控制骨架屏/loading/提示文案，不影响业务逻辑
2. **双重验证**：前端校验仅为体验优化，关键请求经服务端强制二次鉴权
   - 如：前端disabled按钮，但点击后API返回403
3. **公开信息**：状态存储的是公开配置（如主题色、语言偏好）
4. **已有签名**：localStorage值带有HMAC/JWT签名，服务端校验签名有效性

### 🔧 代码异味（不是漏洞但建议优化）

1. 敏感字段命名存储在前端（如`isInternalUser`），虽有后端校验但容易误导
2. 过度依赖前端路由守卫（`beforeEach`检查权限），应配合SSR或API拦截

---

## Low Risk

以下情况可给予**低风险评级**：

1. **只读操作**：状态控制的是数据查询/展示功能，不涉及增删改
   - 如：控制是否显示"高级筛选"面板，但筛选结果仍由服务端返回
   
2. **非核心业务**：影响的是辅助功能（如换肤、折叠侧边栏）
   
3. **有限影响**：即使绕过前端限制，后端有硬性业务规则兜底
   - 如：前端限制上传10次，篡改后服务端仍通过数据库记录校验
   
4. **演示环境**：明确标识为Demo/Playground的功能模块
   
5. **时间窗口短**：状态值定期与服务端同步（如每5秒刷新token验证）

6. **降级方案**：状态篡改仅导致功能异常（如页面错乱），不产生实际收益