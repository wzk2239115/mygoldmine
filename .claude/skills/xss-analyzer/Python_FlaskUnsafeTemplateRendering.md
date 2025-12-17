# Python｜Flask 不安全模板渲染 XSS

## 基本信息

- **难度等级：** ★★★☆☆ (中级)
- **审计时间：** 15-30分钟（单个漏洞点）
- **先决知识：** Flask Jinja2 模板、自动转义配置、Python 字符串格式化
- **复杂度评估：**
  - 简单场景（单个模板调用）：15-20分钟
  - 复杂场景（多模板、继承、宏）：30-45分钟

## 🚀 30秒快速清单

- [ ] Flask 应用是否使用了 Jinja2 或其他模板引擎进行渲染？
- [ ] 是否在模板中使用了 `| safe` 过滤器或关闭了自动转义？
- [ ] 是否使用 `Markup()` 或 `| safe` 处理用户输入？
- [ ] Jinja2 的自动转义是否在应用配置中被正确启用？
- [ ] 是否对来自数据库或第三方 API 的数据进行了单独处理？

**判断：** 如果第 1-2 个问题打勾且第 4 个未打勾，需要进行 L3+ 深度分析

## Details

### 漏洞成因
Flask/Jinja2 默认对 `render_template` 中的变量进行自动转义。但若使用 `render_template_string` 动态拼接模板、调用 `Markup` 标记字符串安全、或在模板中使用 `|safe` 过滤器，就会绕过转义，导致 XSS。常见于富文本预览、动态邮件模板、调试接口。

### 代码示例

**易受攻击的代码：**
```python
from flask import render_template_string, request

@app.route('/preview')
def preview():
    content = request.args.get('content', '')
    return render_template_string('<div>%s</div>' % content)
```

**安全示例：**
```python
@app.route('/preview')
def preview():
    content = request.args.get('content', '')
    safe_content = html.escape(content, quote=True)
    return render_template('preview.html', content=safe_content)
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `render_template_string`, `Markup`, `markupsafe`, `|safe`, `autoescape`, `jinja_env`。

**定位步骤：**
1. 搜索 `render_template_string` 或 `Markup` 调用；
2. 跳读（L2）确认传入数据是否可控；
3. 检查模板中 `|safe`、`|tojson`、`|escape` 使用情况。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- 仅使用 `render_template` 配合自动转义；
- 对富文本使用 bleach/DOMPurify 白名单净化；
- 模板开启 `autoescape=True`；
- 使用自定义过滤器统一编码。

**定位技巧：**
- 逐行读（L3）确认在渲染前是否调用 `html.escape` 或 bleach；
- 跨模块追踪（L4）看富文本是否来自后台 CMS、消息系统等。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 未使用危险 API，依赖自动转义 | **L0（快速跳过）** | 风险低 |
| 个别地方使用 `|safe` | **L2（跳读）** | 核实场景 |
| 广泛使用 `render_template_string` 拼接 | **L3（逐行读）** | 高风险 |
| 富文本链路复杂 | **L4（跨模块追踪）** | 需完整分析 |

## Classify

### 研判标准

#### 确认漏洞
1. 使用危险 API 渲染用户可控字符串；
2. 缺乏净化或编码；
3. 可构造 payload 执行脚本。

#### 误报
1. 字符串来自常量或受控后台；
2. 渲染前已使用 bleach 等库净化；
3. 页面仅内网调试使用。

#### 代码异味
1. 大量 `|safe` 或 `Markup` 调用；
2. 依赖自定义正则过滤；
3. 模板关闭 `autoescape` 没有注释说明。

## Low risk

### 低风险评级场景

#### 1. 内容仅供管理员查看
- 攻击面小，可暂定低风险。

#### 2. 页面处于内部测试环境
- 仍建议修复，但优先级可低。

#### 3. 已计划接入统一净化方案
- 有明确时间表，暂降级并跟踪。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 管理员受控 | 攻击面小 | 中 |
| 内部环境 | 影响有限 | 低 |
| 改造计划明确 | 可暂缓 | 低 |
