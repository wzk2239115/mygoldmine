# Go｜Gin/Echo 响应未转义导致 XSS

## 基本信息

- **难度等级：** ★★★☆☆ (中级)
- **审计时间：** 15-30分钟（单个漏洞点）
- **先决知识：** Gin/Echo 框架、HTML 模板、JSON 响应、自动转义机制
- **复杂度评估：**
  - 简单场景（单个路由）：15-20分钟
  - 复杂场景（多个 HTML 响应、自定义渲染）：30-45分钟

## 🚀 30秒快速清单

- [ ] 应用是否使用 `c.HTML()` 或 `c.String()` 返回 HTML 内容？
- [ ] HTML 内容是否直接包含用户输入或动态数据？
- [ ] 是否使用了 Go 的 `html/template` 进行安全渲染？
- [ ] 如果使用 `c.String()`，响应的 Content-Type 是否为 `application/json` 或纯文本？
- [ ] 是否在响应前对敏感内容进行了 HTML 编码？

**判断：** 如果第 1-2 个问题打勾且第 3 个未被正确使用，需要进行 L3+ 深度分析

## Details

### 漏洞成因
Gin、Echo 等 Web 框架提供 `c.HTML()`, `c.String()` 等方法直接写入响应。若在返回 HTML 时手工拼接用户输入或未使用模板引擎，会导致 XSS。即使通过模板渲染，也需要确认使用 `html/template` 而非 `text/template`。

### 代码示例

**易受攻击的代码：**
```go
router.GET("/greeting", func(c *gin.Context) {
    name := c.Query("name")
    c.Header("Content-Type", "text/html; charset=utf-8")
    c.String(http.StatusOK, "<h1>Hello %s</h1>", name) // 未编码
})
```

**安全示例：**
```go
router.GET("/greeting", func(c *gin.Context) {
    name := htmltemplate.HTMLEscapeString(c.Query("name"))
    c.Header("Content-Type", "text/html; charset=utf-8")
    c.String(http.StatusOK, "<h1>Hello %s</h1>", name)
})
// 更推荐：使用 html/template 渲染
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `c.HTML`, `c.String`, `ctx.HTML`, `ctx.String`, `echo.Context`, `Render`, `fmt.Sprintf("<`。

**定位步骤：**
1. 搜索 HTML/字符串响应生成位置；
2. 跳读（L2）确认是否对变量进行编码；
3. 检查使用的模板是否来自 `html/template`。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- 统一的渲染函数对输入调用 `HTMLEscapeString`; 
- 使用 `html/template` 并通过 `c.HTML` 渲染；
- 返回 JSON 让前端渲染；
- 中间件记录并审计响应模式。

**定位技巧：**
- 逐行读（L3）确保每个响应路径都编码；
- 跨模块追踪（L4）公共响应函数是否被不同模块以不同方式调用。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 使用 `html/template` 或编码函数 | **L0（快速跳过）** | 风险低 |
| 少量响应遗漏编码 | **L2（跳读）** | 快速修补 |
| 多处使用 `c.String` 拼接输入 | **L3（逐行读）** | 高风险 |
| 公共响应函数被多模块复用 | **L4（跨模块追踪）** | 需完整梳理 |

## Classify

### 研判标准

#### 确认漏洞
1. 使用 `c.String`/`ctx.String` 等直接拼接 HTML；
2. 输入可被用户控制；
3. 能构造 payload 执行脚本。

#### 误报
1. 响应为纯文本或 JSON；
2. 输入来源受控或已编码；
3. 页面仅在内网调试使用。

#### 代码异味
1. 将 HTML 模板存放在字符串常量中；
2. 忽略 `HTMLEscape` 以追求性能；
3. 缺少统一的响应编码策略。

## Low risk

### 低风险评级场景

#### 1. 内部管理接口
- 攻击面小，可暂降级。

#### 2. 输出仅用于调试
- 影响有限，但建议编码。

#### 3. 已计划切换到模板渲染
- 明确时间表，可暂降级并跟踪执行。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 内部接口 | 攻击面小 | 中 |
| 调试输出 | 影响有限 | 低 |
| 改造计划明确 | 可暂缓 | 低 |
