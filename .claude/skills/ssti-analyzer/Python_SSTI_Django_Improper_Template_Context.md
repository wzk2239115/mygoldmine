# Python_SSTI_Django_Improper_Template_Context

**漏洞类型**: Django 模板中不当的上下文配置导致用户可访问危险对象

---

## Details

### 代码示例

**易受攻击的代码模式**:
```python
# 传递整个 request 对象到模板
from django.shortcuts import render
return render(request, 'page.html', {'req': request})

# 传递危险的全局对象
import os, sys
context = {'os': os, 'sys': sys}
return render(request, 'template.html', context)

# 模板名称用户可控
template_name = request.GET.get('template') + '.html'
return render(request, template_name, context)

# 使用 safe 过滤器
# 模板中: {{ user_input | safe }}
return render(request, 'page.html', {'user_input': request.POST['data']})

# 自定义模板标签未转义
from django import template
register = template.Library()
@register.simple_tag
def custom_tag(value):
    return value  # 未转义直接返回
```

### 快速定位核心操作 **[L1-L2]**

**L1 关键词扫描**:
- 渲染函数: `render()`, `render_to_string()`, `Template().render()`
- 模板类: `django.template.Template`, `django.template.Engine`
- 过滤器: `| safe`, `| escape`
- 用户输入: `request.GET`, `request.POST`, `request.body`
- 配置: `TEMPLATES`, `OPTIONS`, `autoescape`

**L2 跳读定位**:
- 从视图函数追踪到 `render()` 的 context 参数
- 检查 context 字典中是否包含危险对象
- 搜索模板中的 `| safe` 过滤器
- 定位模板名称是否来自用户输入
- 关注自定义模板标签和过滤器的实现

### 快速定位保护机制 **[L2-L4]**

**L2 跳读检测**:
- 自动转义: Django 默认启用 autoescape
- 模板白名单: 模板名称白名单验证
- 安全上下文: 仅传递必要的数据对象
- 模板沙箱: 限制可访问的属性和方法
- CSP 策略: Content-Security-Policy 配置

**L3 逐行分析**:
- settings.py 配置:
  - `TEMPLATES['OPTIONS']['autoescape']` 设置
  - `TEMPLATES['DIRS']` 模板目录限制
  - `TEMPLATES['OPTIONS']['context_processors']` 配置
- Context 内容:
  - 是否传递了 request、os、sys 等危险对象
  - 对象的方法和属性是否可被模板访问
  - 是否仅传递简单的 DTO 或字典
- 模板语法:
  - 是否使用 `| safe` 绕过转义
  - 是否使用 `{% autoescape off %}`
  - 模板标签和过滤器是否安全
- 自定义扩展:
  - 自定义标签是否转义输出
  - 自定义过滤器是否验证输入
  - 是否限制了可调用的方法

**L4 跨模块追踪**:
- 追踪从 URL 配置 → 视图 → 模板的数据流
- 检查全局 Django 设置
- 验证中间件的上下文处理器
- 检查模板继承和包含的安全性
- 追踪模板标签库的注册和使用

---

## Classify

### 漏洞判定标准

**确认为漏洞**:
- Context 包含 request、os、sys 等危险对象
- 模板名称完全由用户输入决定
- 使用 `| safe` 输出用户可控数据
- 禁用 autoescape 且输出用户数据
- 自定义标签/过滤器未转义输出

**误报判定**:
- 模板完全预定义，context 仅包含安全数据
- 启用 autoescape 且无 `| safe` 使用
- 模板名称经过严格白名单验证
- Context 对象仅包含基本类型和 DTO
- 自定义扩展经过安全审计

**代码异味**:
- Context 包含复杂的业务对象
- 虽用 autoescape 但大量使用 `| safe`
- 模板名称通过拼接构造
- 自定义标签/过滤器未经安全审计
- 在模板中使用 `{% load %}` 加载不可信库
- Django 版本过低存在已知漏洞

---

## Low risk

### 低风险场景

**功能与权限隔离**:
- 模板渲染仅限管理员使用
- 需要强身份验证
- 功能部署在内网
- 严格访问控制

**架构设计防护**:
- 强制启用 autoescape
- Context 仅包含安全的 DTO 对象
- 模板全部预定义
- 实现完善的 CSP 策略

**输入与输出保护**:
- 模板名称严格白名单验证
- 禁止使用 `| safe` 过滤器
- Context 对象类型严格限制
- 所有用户输入经过验证

**监控与运行环保**:
- 模板目录权限严格控制
- 完整审计日志
- 实时监控异常模板访问
- WAF 检测注入特征
