# NodeJS_Auth_Middleware_Order

**漏洞类型**: Express 认证中间件顺序错误，导致某些路由在进行认证检查之前就被处理，可被绕过

---

## Details

### 代码示例

```javascript
// 错误的顺序
app.get('/admin', (req, res) => res.json({admin: true}));  // 先定义
app.use(authMiddleware);  // 后定义中间件，无法保护上面的路由

// 修复: 中间件先定义
app.use(authMiddleware);
app.get('/admin', (req, res) => res.json({admin: true}));

// 或使用路由级中间件
app.get('/admin', authMiddleware, (req, res) => res.json({admin: true}));
```

### 快速定位核心操作 **[L1-L2]**

**L1 关键词扫描**:
- `app.use()`, `app.get()`, `app.post()`
- 中间件定义顺序
- 路由定义顺序

**L2 跳读定位**:
- 路由定义顺序
- 中间件应用位置

### 快速定位保护机制 **[L2-L4]**

**L2 跳读检测**:
- 中间件在路由之前定义
- 路由级中间件应用

**L3 逐行分析**:
- 认证中间件全局应用
- 所有受保护路由有中间件

---

## Classify

确认为漏洞: 中间件在路由之后
误报判定: 中间件正确应用

---

## Low risk

- 虽无认证但资源无敏感数据
- 有其他防护
