# Python_SSTI_Flask_Render_Template_String

**漏洞类型**: Flask render_template_string 直接渲染用户输入作为模板内容

---

## Details

### 代码示例

**易受攻击的代码模式**:
```python
# 直接渲染用户输入
from flask import Flask, render_template_string, request
user_template = request.args.get('template')
return render_template_string(user_template)

# 字符串拼接后渲染
template = "Hello, " + request.form['name']
return render_template_string(template)

# 使用 |safe 过滤器
template = "{{ user_input | safe }}"
return render_template_string(template, user_input=request.args['data'])

# 模板中包含用户输入
template = "<h1>{{ title }}</h1>"
return render_template_string(template, title=request.args.get('t'))

# Jinja2 Environment 直接使用
from jinja2 import Environment
env = Environment()
tpl = env.from_string(request.form['template'])
return tpl.render()
```

### 快速定位核心操作 **[L1-L2]**

**L1 关键词扫描**:
- 渲染函数: `render_template_string()`, `Template()`, `env.from_string()`
- Jinja2 类: `Environment`, `Template`, `FileSystemLoader`
- 过滤器: `| safe`, `| escape`
- 用户输入: `request.args`, `request.form`, `request.json`, `request.values`
- 配置: `autoescape`, `select_autoescape`

**L2 跳读定位**:
- 从用户输入追踪到 `render_template_string()`
- 检查模板字符串是否包含用户输入拼接
- 搜索 `| safe` 过滤器的使用
- 定位 Environment 配置中的 autoescape
- 关注 from_string 的模板来源

### 快速定位保护机制 **[L2-L4]**

**L2 跳读检测**:
- 自动转义: Flask 默认启用 autoescape
- 模板白名单: 使用 `render_template()` 而非 `render_template_string()`
- 沙箱环境: `SandboxedEnvironment`
- 输入验证: 严格的模板内容验证
- 安全策略: 限制可访问的对象和方法

**L3 逐行分析**:
- Flask 配置:
  - `TEMPLATES_AUTO_RELOAD` 设置
  - `EXPLAIN_TEMPLATE_LOADING` 调试选项
  - Jinja2 环境配置
- 模板来源:
  - 是否使用 `render_template_string()`（危险）
  - 是否使用 `render_template()`（相对安全）
  - 模板字符串是否完全预定义
- Jinja2 环境:
  - `autoescape` 是否启用
  - `select_autoescape()` 配置
  - 是否使用 `SandboxedEnvironment`
- 过滤器和上下文:
  - 是否使用 `| safe` 绕过转义
  - 上下文变量是否包含危险对象
  - 是否限制了全局函数和变量

**L4 跨模块追踪**:
- 追踪从路由 → 视图函数 → 模板渲染的数据流
- 检查全局 Flask 和 Jinja2 配置
- 验证蓝图和应用工厂的配置
- 检查中间件和装饰器的输入验证
- 追踪自定义 Jinja2 扩展和过滤器

---

## Classify

### 漏洞判定标准

**确认为漏洞**:
- `render_template_string()` 接受用户输入
- 模板字符串通过拼接包含用户数据
- 使用 `| safe` 输出用户可控变量
- `Environment.from_string()` 处理用户输入
- autoescape 被禁用且输出用户数据

**误报判定**:
- 仅使用 `render_template()` 加载预定义模板
- 启用 autoescape 且无 `| safe` 使用
- 模板完全硬编码，用户仅控制变量值
- 使用 `SandboxedEnvironment` 且配置严格
- 所有用户输入经过白名单验证

**代码异味**:
- 虽用 `render_template()` 但模板名可控
- 大量使用 `| safe` 过滤器
- 自定义过滤器未经安全审计
- 上下文包含复杂对象和方法
- 在模板中使用 `{% include %}` 且路径可控
- Flask/Jinja2 版本过低存在已知漏洞

---

## Low risk

### 低风险场景

**功能与权限隔离**:
- 模板渲染仅限管理员使用
- 需要强身份验证
- 功能部署在内网
- 严格访问控制

**架构设计防护**:
- 强制使用 `render_template()`
- 启用 `SandboxedEnvironment`
- 模板全部预定义在文件中
- 实现完善的 CSP 策略

**输入与输出保护**:
- 模板名称严格白名单验证
- 禁止使用 `render_template_string()`
- 所有变量强制转义
- 上下文仅包含基本类型

**监控与运行环保**:
- 模板目录只读挂载
- 完整审计日志
- 实时监控异常模板访问
- WAF 检测 SSTI 特征
