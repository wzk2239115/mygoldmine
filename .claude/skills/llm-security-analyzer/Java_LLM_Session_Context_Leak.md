# **Java LLM Session Context Leak**

当 Java 应用在多用户环境中，LLM 会话数据（聊天历史、用户信息）存储在会话或线程本地变量中，但未能正确隔离，可能导致敏感信息泄露给其他用户。

## Details

**代码示例位置识别技巧（L1: 关键词扫描）**
- 搜索线程本地存储：`ThreadLocal`、`threadLocal.set()`、`threadLocal.get()`
- 查找会话管理：`HttpSession`、`session.setAttribute()`、`session.getAttribute()`
- 搜索共享对象：`static` 变量、`Singleton`、`static List<Map>`
- 查找会话清理：`session.invalidate()`、`threadLocal.remove()`
- 定位多线程处理：线程池、`@Async`、`@WebSocket`

**核心操作保护机制（L2: 跳读）**
- 检查是否为每个用户创建了隔离的会话
- 验证 ThreadLocal 变量是否正确清理
- 查看是否有共享的可变对象
- 检查会话超时设置
- 查看是否使用了分布式会话存储

**快速定位到具体漏洞（L3: 逐行读）**
- 追踪会话对象的创建和销毁
- 检查是否有 ThreadLocal 清理逻辑（finally 块、try-with-resources）
- 审查会话属性的隔离
- 查看是否有共享的集合或缓存
- 检查线程池中任务的隔离

**数据流追踪（L4: 跨模块追踪）**
- 追踪会话生命周期
- 检查多个组件是否都正确隔离了会话数据
- 验证清理逻辑

## Classify

**确认为漏洞的特征：**
1. 使用 ThreadLocal 但未正确清理
2. 会话数据存储在 static 变量中
3. 使用共享的可变对象存储会话
4. 线程池重用线程但未清理 ThreadLocal
5. HttpSession 超时设置不合理

**误报场景：**
1. 正确使用 ThreadLocal 并在 finally 块中清理
2. HttpSession 由容器管理，正确隔离
3. 会话超时合理（如 30 分钟）
4. 使用分布式会话存储（Redis）
5. 敏感数据不在会话中存储

**代码异味（需要深入审查）**
1. ThreadLocal 没有 remove() 调用
2. 共享的可变对象
3. 静态集合存储会话数据
4. 线程池中的任务共享会话

## Low risk

**评级为低风险的场景：**
1. 正确使用 HttpSession，由容器管理隔离
2. ThreadLocal 在 finally 块中正确清理
3. 会话超时设置合理
4. 不使用共享的可变对象存储会话
5. 关键数据不在会话中缓存，仅在需要时从数据库查询
