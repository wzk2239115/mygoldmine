# SPA 路由守卫不完整漏洞审计指南

## Details

**漏洞成因**  
SPA（Vue/React/Angular）路由守卫逻辑存在缺口，允许未授权用户通过特定路径、条件分支或时序差异绕过权限检查直接访问受保护页面或功能。

**代码示例**

```typescript
// Vue Router - 不完整的守卫逻辑
router.beforeEach((to, from, next) => {
  if (to.path.startsWith('/admin')) {  // 仅检查路径前缀
    if (isAdmin()) next();
    else next('/login');
  }
  next();  // 其他路径直接放行，/admin123 可绕过
});

// React Router - 组件级守卫缺失
<Route path="/dashboard" element={<Dashboard />} />  // 无权限检查
<Route path="/admin/*" element={<ProtectedRoute><Admin /></ProtectedRoute>} />

// 条件分支不完整
function canAccess(user, resource) {
  if (user.role === 'admin') return true;
  if (resource.isPublic) return true;
  // 缺少 else 默认拒绝，隐式返回 undefined（可能被解释为真）
}
```

**快速定位核心操作**  
- 搜索关键词：`beforeEach`、`beforeEnter`、`canActivate`、`ProtectedRoute`、`PrivateRoute`、`useAuth`
- 识别路由配置文件：`router.ts`、`routes.tsx`、`app-routing.module.ts`
- 关注动态路由：`path: '/:id'`、通配符路由、懒加载模块的嵌套路由

**快速定位保护机制**  
- 守卫函数：`next()`/`redirect()`/`navigate()` 调用链的所有分支
- 高阶组件：`withAuth()`、`RequireAuth`、`AuthGuard` 的包裹范围
- Hooks：`useEffect` 中的权限检查时机（页面加载后检查存在时序窗口）
- 元数据：`meta.requiresAuth`、`meta.roles` 的配置与消费点是否一致

**审计等级：L3（逐行读）→ L4（跨模块追踪）**  
- L3：逐行审查每个守卫函数的条件分支，验证所有路径都有明确的 `next(false)` 或 `redirect`
- L4：追踪权限检查函数（如 `isAdmin()`）的实现，确认 token 验证、角色判断无漏洞；追踪嵌套路由的父子守卫关系

---

## Classify

**漏洞（确认存在安全风险）**  
- 守卫函数存在逻辑短路，部分路径未执行权限检查即调用 `next()`
- 条件判断不完整，缺少默认拒绝分支（如无 `else return false`）
- 仅在组件内部检查权限（`useEffect`），存在短暂渲染敏感数据的时序窗口
- 懒加载模块的子路由缺少独立守卫，依赖父路由守卫但父守卫未覆盖
- 路径匹配使用 `startsWith`/正则但未精确锚定，可被相似路径绕过（`/admin` vs `/admin123`）
- 守卫依赖客户端状态（`localStorage.role`）而非服务端验证的 token

**误报（实际无风险）**  
- 公开路由本就无需守卫（如 `/`、`/about`、`/login`）
- 权限检查在服务端 API 层严格实施，前端路由守卫仅为 UX 优化（需确认后端检查完备）
- 看似直接放行，但在更上层的全局守卫或中间件已统一处理
- 动态路由的权限检查通过路由元数据 + 全局守卫集中实施，单个路由配置无守卫属正常

**代码异味（潜在风险）**  
- 守卫逻辑分散在多处（全局守卫 + 路由级守卫 + 组件内守卫），难以确保一致性
- 使用隐式返回值（函数末尾无明确 `return false`），依赖 JavaScript 真值判断
- 权限检查逻辑复杂且缺少单元测试，难以验证所有分支
- 嵌套路由的守卫继承关系不明确，需人工梳理执行顺序

---

## Low Risk

**以下情况可评为低风险**  
- 受保护资源仅为非敏感 UI 界面，实际数据由后端 API 强制鉴权（需确认 API 检查完备）
- 绕过路径仅能访问功能框架，无法触发实际业务操作（按钮置灰、API 调用被拦截）
- 漏洞仅存在于已废弃或开发中的路由模块（需确认生产环境未启用）
- 影响范围限于低价值功能（如主题设置、通知偏好等个性化配置）
- 需同时满足其他严苛前置条件（如特定设备指纹、IP 白名单）才能利用
- 服务端实施了速率限制和异常行为检测，可有效阻止批量利用