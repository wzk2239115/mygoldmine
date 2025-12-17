# Python｜Jinja2 关闭自动转义导致 XSS

## 基本信息

- **难度等级：** ★★★☆☆ (中级)
- **审计时间：** 15-30分钟（单个漏洞点）
- **先决知识：** Jinja2 模板引擎、自动转义配置、环境设置、Flask/Django 集成
- **复杂度评估：**
  - 简单场景（单个模板文件）：15-20分钟
  - 复杂场景（多个环境配置、自定义过滤器）：30-45分钟

## 🚀 30秒快速清单

- [ ] Jinja2 环境是否禁用了自动转义（`autoescape=False` 或 `autoescape=select_autoescape`）？
- [ ] 模板中是否存在未转义的用户输入或动态数据输出？
- [ ] 是否为特定文件类型启用了选择性自动转义（如仅对 .html 文件）？
- [ ] 是否为需要输出 HTML 的内容使用了 `| safe` 过滤器但未进行净化？
- [ ] 自定义过滤器和宏是否考虑了转义问题？

**判断：** 如果第 1-2 个问题打勾且第 4 个未打勾，需要进行 L3+ 深度分析

## Details

### 漏洞成因
Jinja2 支持在 Environment 或模板级别关闭 `autoescape`。若关闭后直接渲染用户可控数据，就会失去自动转义保护，导致 XSS。常见于将模板拓展为邮件、Markdown、富文本预览时设置 `autoescape=False`。

### 代码示例

**易受攻击的代码：**
```python
from jinja2 import Environment, FileSystemLoader

env = Environment(loader=FileSystemLoader('templates'), autoescape=False)
template = env.get_template('comment.html')
html = template.render(content=request.args.get('c', ''))
```

**安全示例：**
```python
env = Environment(loader=FileSystemLoader('templates'), autoescape=True)
html = env.get_template('comment.html').render(content=request.args.get('c', ''))
# 若必须输出富文本，使用 bleach.clean(content, tags=...) 后再渲染
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `autoescape=False`, `Environment(...`, `select_autoescape`, `{% autoescape false %}`, `Markup`。

**定位步骤：**
1. 搜索关闭 autoescape 的配置；
2. 跳读（L2）检查模板中输出的变量；
3. 检查是否针对某些模板（邮件、导出）禁用了自动转义。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- 仅针对安全模板关闭 autoescape；
- 使用 bleach、markupsafe 对富文本进行白名单过滤；
- 手动调用 `jinja2.filters.do_escape`; 
- 输出改为 JSON/纯文本。

**定位技巧：**
- 逐行读（L3）确认所有输出变量在关闭 autoescape 的环境中是否经过净化；
- 跨模块追踪（L4）模板继承链路是否引入未净化数据。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 全局 autoescape 开启 | **L0（快速跳过）** | 风险低 |
| 部分模板关闭但有净化 | **L2（跳读）** | 核实策略 |
| 广泛关闭 autoescape 并渲染用户输入 | **L3（逐行读）** | 高风险 |
| 模板继承复杂 | **L4（跨模块追踪）** | 需完整分析 |

## Classify

### 研判标准

#### 确认漏洞
1. `autoescape=False` 环境渲染用户可控数据；
2. 缺少净化或转义；
3. 可插入脚本执行。

#### 误报
1. 模板仅渲染后端常量或受控数据；
2. 渲染前使用 bleach 等严格过滤；
3. 输出类型非 HTML（纯文本邮件等）。

#### 代码异味
1. 为方便调试临时关闭 autoescape；
2. 依赖自定义正则过滤；
3. 模板继承中混合开启/关闭 autoescape。

## Low risk

### 低风险评级场景

#### 1. 模板仅管理员查看
- 攻击面小，可暂列低风险。

#### 2. 输出作为纯文本附件
- 不会在浏览器执行，风险较低。

#### 3. 已计划重新启用 autoescape 并引入净化
- 有时间表，可暂降级并跟踪。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 管理员受控 | 攻击面小 | 中 |
| 非 HTML 输出 | 影响有限 | 低 |
| 改造计划明确 | 可暂缓 | 低 |
