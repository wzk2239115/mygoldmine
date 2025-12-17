# CSRF 防护缺陷审计速查表

拿到任何基于 Cookie/Session 认证且包含状态修改操作的 Web 应用，以下通用 CSRF 防护缺陷都必须审计（与编程语言无关）。

## 1. Token 机制缺失或未启用

### 1.1 状态修改接口未实施 Token 验证
- **问题**：POST/PUT/DELETE 等操作完全缺少 Token 验证；表单未生成/验证 Token；AJAX 请求未携带 Token 头
- **检查点**：定位所有状态修改接口，验证是否在处理前检查了有效 Token；查看表单隐藏字段是否包含 Token；AJAX 请求是否在 headers 中添加了 Token

### 1.2 框架默认防护被显式禁用
- **问题**：框架内置 CSRF 防护被主动关闭（如 csrf().disable()）；中间件/过滤器未启用或被移除
- **检查点**：搜索禁用防护的配置语句；检查中间件链是否包含 CSRF 相关组件；查看启动配置和路由配置

### 1.3 敏感操作被错误豁免检查
- **问题**：敏感端点使用豁免装饰器（@csrf_exempt）；中间件配置中豁免了关键路由；路由被错误地白名单化
- **检查点**：搜索豁免注解/装饰器；审查中间件豁免规则列表；确认豁免列表中是否包含密码修改、权限变更、资金转账等敏感操作

## 2. Token 生成机制不安全

### 2.1 Token 生成可预测或使用弱随机数
- **问题**：使用时间戳、用户 ID 等可预测值；使用 rand()/Math.random() 等弱随机；熵不足
- **检查点**：查找 Token 生成函数；验证是否使用了加密强随机数生成器（如 /dev/urandom、crypto.getRandomValues、SecureRandom）；检查是否混入了可预测成分

### 2.2 Token 未与用户会话绑定
- **问题**：Token 与 Session ID/User ID 无绑定关联；Token 存储在全局/共享位置导致多用户共用；验证时未检查绑定关系
- **检查点**：查看 Token 生成时是否包含会话标识符；Token 存储位置是否隔离（每用户独立）；验证时是否检查了 `saved_token == request_token && token_user_id == current_user_id`

### 2.3 Token 固定不变或长期有效
- **问题**：Token 生成后固定，未更新；无过期时间或有效期过长；登出后未失效
- **检查点**：验证 Token 是否在每次请求/会话后重新生成；是否有时间戳或过期检查；登出时是否清除 Token；检查有效期时间窗口是否合理

## 3. Token 验证逻辑缺陷

### 3.1 仅检查 Token 存在性不验证值
- **问题**：仅验证字段是否存在，不校验值正确性；仅检查格式（长度、字符集），未与服务端值比对
- **检查点**：审查验证逻辑是否执行了 `==` 或 `constant_time_equal()` 比较；是否有实际的值比对代码

### 3.2 Token 验证可被空值/特殊输入绕过
- **问题**：空值、null、undefined 时验证被跳过；存在逻辑短路（如 `if(!token) return true` 错误写法）
- **检查点**：查看验证条件是否有 `if (!token)` 的提前返回；是否允许空 Token 通过；是否使用了容易出错的 falsy 检查

### 3.3 Token 比对算法存在缺陷
- **问题**：使用 `==` 而非 `===`/严格相等（类型转换风险）；大小写不敏感；未使用常量时间比较（时序攻击）
- **检查点**：验证使用了严格相等而非弱相等；若 Token 为 hash，使用了 `hash_equals()` 或 `constant_time_compare()` 等常量时间函数；大小写敏感

## 4. 不可靠的请求来源验证

### 4.1 仅依赖 Referer/Origin 头
- **问题**：仅检查 HTTP 头判断来源，未结合 Token；客户端只检查 document.referrer；验证逻辑不严格（子串匹配）
- **检查点**：确认是否仅使用了 Referer/Origin 验证而无 Token；是否有正则模糊匹配；是否仅在客户端验证

### 4.2 缺乏多层防护机制
- **问题**：单一验证方式；未结合 SameSite Cookie 与 Token 的多重防护
- **检查点**：验证是否同时实施了 Token + SameSite + (可选) Referer 验证；是否存在 fallback 防护

## 5. Cookie 安全属性配置不当

### 5.1 Session Cookie 未设置 SameSite 属性
- **问题**：无 SameSite 属性，浏览器默认跨站携带；SameSite=None 未配合其他防护；SameSite=Lax 仅限安全方法，POST 等仍可能有风险
- **检查点**：查看 Set-Cookie 响应头或框架配置，确认 `SameSite=Strict` 或 `SameSite=Lax` 已设置；若为 None 必须有 Token 验证；若为 Lax 对敏感 POST 需额外防护

### 5.2 Cookie 其他属性配置不完整
- **问题**：未设置 Secure 属性（可在非 HTTPS 下传输）；未设置 HttpOnly 属性（可被 JavaScript 读取）
- **检查点**：验证 Session Cookie 是否设置了 `Secure; HttpOnly` 属性

## 6. 敏感操作缺乏额外验证

### 6.1 高风险操作无二次认证
- **问题**：密码修改、账户删除仅需 Token，未要求重新输入密码；资金转账、权限变更无 2FA/OTP
- **检查点**：定位敏感操作接口，检查是否有密码再次验证或 MFA 验证逻辑

### 6.2 状态修改操作无用户交互确认
- **问题**：操作可被自动化触发，无 CAPTCHA；无明确的点击确认交互
- **检查点**：是否在敏感操作前进行了 CAPTCHA 验证；是否要求用户点击确认按钮（而非自动提交）