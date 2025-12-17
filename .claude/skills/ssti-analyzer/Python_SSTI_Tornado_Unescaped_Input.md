# Python_SSTI_Tornado_Unescaped_Input

**漏洞类型**: Tornado 模板引擎中用户输入未转义直接渲染

---

## Details

### 代码示例

**易受攻击的代码模式**:
```python
# 直接渲染用户输入模板
from tornado import template
t = template.Template(request.get_argument('template'))
t.generate()

# 使用 {% raw %} 输出未转义内容
t = template.Template('{% raw user_content %}')
t.generate(user_content=self.get_argument('data'))

# 禁用自动转义
t = template.Template(tpl_str, autoescape=None)

# 字符串拼接后渲染
tpl = "Hello {{ " + self.get_argument('field') + " }}"
template.Template(tpl).generate()

# Loader 加载用户可控路径
loader = template.Loader("./templates/")
t = loader.load(self.get_argument('name') + '.html')
```

### 快速定位核心操作 **[L1-L2]**

**L1 关键词扫描**:
- 模板类: `template.Template`, `template.Loader`
- 渲染方法: `.generate()`, `.render()`
- 未转义标签: `{% raw %}`, `{% autoescape None %}`
- 用户输入: `self.get_argument()`, `self.get_arguments()`, `self.request`
- 配置: `autoescape`, `whitespace`

**L2 跳读定位**:
- 从用户输入追踪到 `Template()` 构造函数
- 检查模板字符串是否包含用户输入拼接
- 搜索 `{% raw %}` 标签的使用
- 定位 autoescape 参数设置
- 关注 Loader.load() 的路径参数

### 快速定位保护机制 **[L2-L4]**

**L2 跳读检测**:
- 自动转义: `autoescape="xhtml_escape"` 默认启用
- 模板白名单: 模板名称白名单验证
- 模板预加载: 使用 Loader 预加载模板
- 路径限制: Loader 目录限制
- 输入验证: 严格的模板内容验证

**L3 逐行分析**:
- Template 参数:
  - `autoescape` 是否设置为 None（危险）
  - `whitespace` 设置是否影响安全
  - 模板字符串来源
- 模板来源:
  - 是否接受用户提交的完整模板字符串
  - Loader.load() 路径是否可控
  - 是否仅从固定目录加载
- 输出标签:
  - `{{ }}` 自动转义（安全）
  - `{% raw %}` 不转义（危险）
  - `{% autoescape None %}` 禁用转义（危险）
- Loader 配置:
  - 模板目录是否受限
  - 是否检查文件扩展名
  - 路径是否规范化

**L4 跨模块追踪**:
- 追踪从 RequestHandler → 模板渲染的数据流
- 检查全局 Tornado 应用配置
- 验证 UIModule 的安全性
- 检查中间件的输入验证
- 追踪自定义模板函数和过滤器

---

## Classify

### 漏洞判定标准

**确认为漏洞**:
- 用户输入直接作为 `Template()` 参数
- 设置 `autoescape=None` 禁用转义
- 使用 `{% raw %}` 输出用户可控数据
- Loader.load() 路径可被用户控制
- 模板字符串通过拼接包含用户输入

**误报判定**:
- 模板完全预定义，用户仅控制变量值
- 启用 autoescape 且无 `{% raw %}` 使用
- 模板名称经过严格白名单验证
- Loader 限制在安全目录
- 所有用户输入经过转义和验证

**代码异味**:
- 虽启用 autoescape 但使用 `{% raw %}`
- 模板路径通过拼接构造
- 自定义模板函数未经安全审计
- 在模板中使用 `{% include %}` 且路径可控
- Tornado 版本过低存在已知漏洞
- 模板变量名可被用户影响

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
- 模板全部通过 Loader 预加载
- 禁用 `{% raw %}` 和动态模板
- 实现 CSP 策略

**输入与输出保护**:
- 模板名称严格白名单验证
- 禁止用户输入作为模板内容
- 所有变量强制转义
- 路径规范化后检查前缀

**监控与运行环保**:
- 模板目录只读挂载
- 完整审计日志
- 实时监控异常模板访问
- 容器环境文件系统只读
