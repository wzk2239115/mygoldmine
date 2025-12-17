# Python｜Django mark_safe / |safe 滥用 XSS

## 基本信息

- **难度等级：** ★★★☆☆ (中级)
- **审计时间：** 15-30分钟（单个漏洞点）
- **先决知识：** Django ORM、模板语言、HTML 编码、mark_safe() 函数
- **复杂度评估：**
  - 简单场景（单处 mark_safe）：15-20分钟
  - 复杂场景（多处标记、数据流追踪）：30-45分钟

## 🚀 30秒快速清单

- [ ] 代码中是否使用了 `mark_safe()` 或模板中的 `|safe` 过滤器？
- [ ] `mark_safe()` 或 `|safe` 处理的数据是否来自用户输入或不可信数据源？
- [ ] 数据在被标记为安全前是否经过了严格的验证和净化？
- [ ] 是否对 HTML 标签和属性进行了白名单限制？
- [ ] 是否存在将多个数据源拼接后再标记为安全的情况？

**判断：** 如果第 1-2 个问题打勾且第 3 个未打勾，需要进行 L3+ 深度分析

## Details

### 漏洞成因
Django 模板会默认对变量输出进行转义。但若在视图中使用 `mark_safe`、`format_html` 或在模板中使用 `|safe` 过滤器，就会把字符串标记为安全。若该字符串来源于用户输入或第三方数据，就会绕过转义，触发 XSS。

### 代码示例

**易受攻击的代码：**
```python
from django.utils.safestring import mark_safe

def profile(request):
    bio = request.GET.get('bio', '')
    context = { 'bio': mark_safe(bio) }
    return render(request, 'profile.html', context)
```

```django
<!-- 模板 -->
{{ comment|safe }}
```

**安全示例：**
```python
from django.utils.html import escape

def profile(request):
    bio = escape(request.GET.get('bio', ''))
    return render(request, 'profile.html', { 'bio': bio })

# 或使用 bleach 白名单过滤后再 mark_safe
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `mark_safe`, `format_html`, `|safe`, `autoescape off`, `SafeString`。

**定位步骤：**
1. 搜索 `mark_safe`、`|safe` 出现位置；
2. 跳读（L2）确认变量来源是否可控；
3. 检查模板是否在 `{% autoescape off %}` 块内输出变量。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- 仅对受控常量使用 `mark_safe`；
- 使用 bleach/HTML5lib 白名单净化；
- 将富文本存储为 Markdown 并安全渲染；
- 在视图层统一编码函数。

**定位技巧：**
- 逐行读（L3）确认所有 `safe` 变量都经过可信净化；
- 跨模块追踪（L4）后台富文本 → 前台渲染链路。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 无 `mark_safe` / `|safe` 使用 | **L0（快速跳过）** | 风险低 |
| 少量受控场景使用 | **L2（跳读）** | 核实来源 |
| 广泛标记用户输入为安全 | **L3（逐行读）** | 高风险 |
| 富文本链路复杂 | **L4（跨模块追踪）** | 必须梳理 |

## Classify

### 研判标准

#### 确认漏洞
1. `mark_safe`/`|safe` 用于用户可控数据；
2. 无净化或白名单；
3. 能构造 payload 执行脚本。

#### 误报
1. 数据为常量或已白名单过滤；
2. 模板片段仅在内网调试使用；
3. `safe` 用于不可控的受信 HTML（如本地化资源，经审计）。

#### 代码异味
1. 依赖 `str.replace` 去除 `<script>`；
2. 在模板块中关闭 autoescape 而无说明；
3. 无审计日志记录富文本提交来源。

## Low risk

### 低风险评级场景

#### 1. 富文本仅管理员可编辑
- 攻击面小，可暂列低风险。

#### 2. 页面部署在受限环境
- 仍建议净化，但优先级较低。

#### 3. 即将接入统一富文本过滤
- 明确计划，可暂降级并跟踪。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 受控来源 | 攻击面小 | 中 |
| 受限环境 | 影响有限 | 低 |
| 改造计划明确 | 可暂缓 | 低 |
