# Python compile() 代码编译注入

**漏洞成因**：使用 `compile()` 函数动态编译用户输入的代码字符串，常见于代码缓存、动态模块加载、规则引擎等场景。`compile()` 将代码字符串转换为字节码对象，可随后通过 `eval()`/`exec()` 执行，攻击者可编译并执行任意代码。

---

## Details

**代码示例**：
```python
# 危险：直接编译用户输入
user_code = request.args.get('code')
code_obj = compile(user_code, '<string>', 'exec')
exec(code_obj)

# 危险：compile 与字符串拼接
compiled = compile(f"result = {user_input}", '<dynamic>', 'eval')
eval(compiled)

# 危险：compile 配合缓存机制
cache = {}
if user_code not in cache:
    cache[user_code] = compile(user_code, '<cached>', 'exec')
exec(cache[user_code])

# 虚假安全：编译后的对象仍然是恶意代码
try:
    code_obj = compile(user_code, '<string>', 'exec')
    # 检查是否安全，但已经编译完成
except SyntaxError:
    pass
```

**快速定位核心操作**（L1-L2）：
- 关键词：`compile(`、`co_code`、字节码操作相关调用
- 查看 compile 的第一个参数是否来自用户输入
- 检查是否使用了 f-string、字符串拼接、格式化
- 追踪编译后对象的使用：是否立即 `eval()`/`exec()`
- 查找数据流：`request.args`、`request.json`、上传文件

**快速定位保护机制**（L2-L3）：
- 是否存在编译前的代码审查：AST 检查、语法验证
- 是否限制了 compile 的 mode 参数（'eval', 'exec', 'single'）
- 是否存在黑名单/白名单：禁止导入、限制函数调用
- 是否使用了沙箱执行：RestrictedPython 等

**审计等级**：**L2-L4**
- **L2**：跳读含有 compile 的代码，确认参数来源
- **L3**：逐行读取 compile 调用及其参数构造、执行方式
- **L4**：跨模块追踪用户输入到 compile 的完整数据流

---

## Classify

**确认为漏洞**：
- 用户输入直接或间接作为 compile() 的第一个参数
- 编译后的代码对象随后被 exec()/eval() 执行
- 无防护或防护机制不完整

**误报**：
- compile() 仅编译硬编码的常量代码
- compile() 的第一个参数来自受信任源（硬编码配置、服务器本地文件）
- 用户输入被严格限制在固定的安全代码片段

**代码异味**：
- compile() 存在但有部分防护（需评估防护完整性）
- 权限依赖前端或弱加密验证
- 代码逻辑可用动态导入或配置替代

---

## Low Risk

以下情况可评为低风险：
- **受限执行环境**：沙箱/容器内执行，无敏感资源访问权限
- **权限隔离**：编译代码在最小权限用户下执行
- **内网保护**：仅限管理员、内网访问
- **输入严格限制**：用户输入限制在预定义的安全代码集合
- **代码审计**：所有编译的代码被完整审计、监控、记录
