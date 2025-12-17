# Python_SSTI_Mako_Template_Evaluation

**漏洞类型**: Mako 模板引擎中用户输入被直接评估执行

---

## Details

### 代码示例

**易受攻击的代码模式**:
```python
# 直接渲染用户输入模板
from mako.template import Template
user_template = request.form['template']
tmpl = Template(user_template)
tmpl.render()

# 使用 ${} 表达式执行代码
template = Template('${exec(__import__("os").system(cmd))}')
template.render(cmd=request.args['cmd'])

# 禁用 HTML 转义
template = Template(text, default_filters=['h'])  # 'h' 是转义，但可被禁用

# 模板文件路径用户可控
from mako.lookup import TemplateLookup
lookup = TemplateLookup(directories=['/templates'])
tmpl = lookup.get_template(request.GET['name'] + '.html')

# 在模板中执行 Python 代码
# 模板中: <% import os; os.system('cmd') %>
template = Template(text)
```

### 快速定位核心操作 **[L1-L2]**

**L1 关键词扫描**:
- 模板类: `mako.template.Template`, `TemplateLookup`
- 渲染方法: `.render()`, `.render_unicode()`, `.render_context()`
- 表达式: `${}`, `<%`, `%>`, `<% ... %>`
- 用户输入: `request.form`, `request.args`, `request.get_json()`
- 配置: `default_filters`, `strict_undefined`

**L2 跳读定位**:
- 从用户输入追踪到 `Template()` 构造函数
- 检查模板字符串是否包含用户输入
- 搜索 `${}` 表达式和 `<% %>` 代码块
- 定位 default_filters 配置
- 关注 TemplateLookup.get_template() 路径参数

### 快速定位保护机制 **[L2-L4]**

**L2 跳读检测**:
- HTML 转义: `default_filters=['h']` 启用
- 模板白名单: 模板名称白名单验证
- 禁用表达式: 限制模板中的代码执行
- 路径限制: TemplateLookup 目录限制
- 沙箱环境: 限制可访问的模块和函数

**L3 逐行分析**:
- Template 参数:
  - `default_filters` 是否包含 'h'（HTML 转义）
  - `strict_undefined` 是否启用
  - `module_directory` 缓存配置
- 模板来源:
  - 是否接受用户提交的完整模板字符串
  - get_template() 路径是否可控
  - 是否仅从固定目录加载
- 表达式和代码:
  - `${}` 表达式内容是否可控
  - `<% %>` 代码块是否执行用户输入
  - `<%! %>` 模块级代码是否安全
- TemplateLookup 配置:
  - directories 是否限制范围
  - filesystem_checks 是否禁用
  - module_directory 权限设置

**L4 跨模块追踪**:
- 追踪从路由 → 控制器 → 模板渲染的数据流
- 检查全局 Mako 配置
- 验证模板继承和包含的安全性
- 检查自定义过滤器的实现
- 追踪模板缓存机制的安全性

---

## Classify

### 漏洞判定标准

**确认为漏洞**:
- 用户输入直接作为 `Template()` 参数
- `${}` 表达式执行用户可控代码
- `<% %>` 代码块包含用户输入
- get_template() 路径可被用户控制
- 未启用 default_filters 转义

**误报判定**:
- 模板完全预定义，用户仅控制简单变量值
- 启用 default_filters=['h'] HTML 转义
- 模板名称经过严格白名单验证
- TemplateLookup 限制在安全目录
- 禁用了模板中的代码执行功能

**代码异味**:
- 虽启用转义但可被模板中的 `| n` 绕过
- 模板路径通过拼接构造
- 使用了复杂的 Python 表达式
- 模板中大量使用 `<% %>` 代码块
- Mako 版本过低存在已知漏洞
- 模板缓存目录权限配置不当

---

## Low risk

### 低风险场景

**功能与权限隔离**:
- 模板渲染仅限管理员使用
- 需要强身份验证
- 功能部署在内网
- 严格访问控制

**架构设计防护**:
- 强制启用 default_filters=['h']
- 模板全部通过 TemplateLookup 预加载
- 禁止在模板中使用 `<% %>` 代码块
- 实现 CSP 策略

**输入与输出保护**:
- 模板名称严格白名单验证
- 禁止用户输入作为模板内容
- 表达式内容经过严格验证
- 路径规范化后检查前缀

**监控与运行环保**:
- 模板目录只读挂载
- module_directory 权限严格控制
- 完整审计日志
- 实时监控异常模板访问
