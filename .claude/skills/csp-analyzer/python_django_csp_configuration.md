# Django CSP 配置中的 unsafe-inline 风险

## Details

### 代码示例

Django 使用 `django-csp` 中间件实现内容安全策略。以下是常见的不安全配置：

```python
# settings.py
MIDDLEWARE = [
    'csp.middleware.CSPMiddleware',
]

# 危险配置 1：script-src 包含 unsafe-inline
CSP_SCRIPT_SRC = (
    "'self'",
    "'unsafe-inline'",  # 允许内联脚本执行
    "https://trusted-cdn.example.com",
)

# 危险配置 2：style-src 包含 unsafe-inline
CSP_STYLE_SRC = (
    "'self'",
    "'unsafe-inline'",  # 允许内联样式
    "https://fonts.googleapis.com",
)

# 危险配置 3：混合使用 unsafe-inline 和通配符
CSP_DEFAULT_SRC = (
    "'self'",
    "'unsafe-inline'",
    "*.example.com",  # 过宽松的源限制
)

# 危险配置 4：完全禁用 CSP
CSP_DISABLE = True  # 不推荐用于生产环境
```

### 快速定位到核心操作的技巧（L1：关键词扫描）

**搜索目标关键词**：
- `'unsafe-inline'` - 直接在 CSP 指令中查找此字符串
- `CSP_SCRIPT_SRC`、`CSP_STYLE_SRC`、`CSP_DEFAULT_SRC` - 在 settings.py 中定位 CSP 配置
- `CSPMiddleware` - 确认中间件是否已启用

**扫描位置**：
- `settings.py` - 主配置文件，检查所有 CSP_* 配置变量
- `wsgi.py`/`asgi.py` - 检查是否有条件禁用 CSP
- 环境配置文件 - 检查开发/生产环境的差异配置

**快速识别方法**：
```bash
# 查找包含 unsafe-inline 的行
grep -r "unsafe-inline" . --include="*.py"

# 查找 CSP 配置的所有位置
grep -r "CSP_" . --include="*.py" | grep -E "(SCRIPT|STYLE|DEFAULT|IMG)_SRC"
```

### 快速定位到保护机制的技巧（L2：跳读）

**检查 CSP 指令完整性**：
- 逐个审查每个 CSP 指令（script-src、style-src、img-src、font-src 等）
- 检查是否存在 `'unsafe-inline'`、`'unsafe-eval'` 等危险指令
- 验证是否使用了具体的源限制而非通配符

**保护机制识别**：
- 使用 `'nonce-'` 或 `'hash-'` 替代 unsafe-inline
- 检查是否为特定环境（开发/测试）特殊处理
- 查看是否存在条件逻辑降低生产环境的安全性

**配置评估清单**：
```python
# 安全做法示例
CSP_SCRIPT_SRC = (
    "'self'",
    "'nonce-{random}'",  # 使用 nonce 替代 unsafe-inline
    "https://trusted-cdn.example.com",
)

# 环境差异检查
if DEBUG:
    CSP_SCRIPT_SRC += ("'unsafe-inline'",)  # 仅在开发环境允许
```

---

## Classify

### 漏洞 vs 误报 vs 代码异味的研判原则

**确定为漏洞的条件**：
1. **生产环境配置包含 unsafe-inline** - 任何生产环境的 CSP 指令中明确包含 `'unsafe-inline'`，且无条件判断（如 `if DEBUG`）
2. **多个关键指令同时宽松** - script-src 和 style-src 均包含 unsafe-inline，表明安全意识缺乏
3. **无替代保护机制** - 使用 unsafe-inline 但未配置 nonce、hash 或其他内容完整性验证

**确定为代码异味的条件**：
1. **仅在非关键指令中使用** - 如 img-src 或 font-src 中的 unsafe-inline（危害相对较小）
2. **存在环境差异处理** - 开发环境允许 unsafe-inline，但生产环境禁用
3. **临时配置或注释标记** - 代码中有明确的 TODO 或临时标记

**确定为误报的条件**：
1. **使用了适当的替代机制** - 已实现 nonce/hash 验证，unsafe-inline 仅为备选
2. **完全禁用但有明确原因** - 如注释说明为了兼容性而暂时禁用，有升级计划

---

## Low risk

### 低风险评级的应用场景

**以下情况可评为低风险**：

1. **内部系统或非公网服务** - 如仅在内网部署的管理后台，XSS 威胁来源受限

2. **静态内容场景** - 应用仅展示静态 HTML，无动态模板渲染或用户输入的 JavaScript 执行

3. **使用了补充防护措施** - 即使有 unsafe-inline，但：
   - 实现了严格的输入验证和输出编码
   - 使用了 HTML 模板自动转义（Django 默认启用）
   - 配置了 X-XSS-Protection 或其他浏览器防护头

4. **仅在特定环境** - unsafe-inline 仅在开发/测试环境存在，生产环境已移除

5. **指令范围受限** - 如仅在 font-src 或 image-src 中使用，对脚本执行威胁较小

**关键判断指标**：
- 是否存在用户可控的内容注入点
- 是否有其他安全防护层（WAF、输入验证）
- 代码的实际暴露面（内网 vs 公网）
