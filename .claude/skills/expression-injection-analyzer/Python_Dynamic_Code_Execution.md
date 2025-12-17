# Python 动态代码执行注入

**漏洞成因**：使用 `eval()`、`exec()` 等内置函数直接执行用户提供的代码字符串，或通过 `compile()` 编译后执行，代码执行环境未被沙箱化，导致用户可执行任意 Python 代码，访问应用上下文、文件系统、网络等系统资源。常见于动态表达式求值、代码生成、动态规则定义等场景。

---

## Details

**代码示例**：
```python
# 危险：直接使用 eval 执行用户输入
user_code = request.args.get('code')
eval(user_code)  # 用户可执行任意代码

# 危险：exec 执行用户输入的代码
formula = request.json.get('formula')
exec(formula)  # 用户可导入模块、修改全局变量

# 较安全：使用受限的命名空间和 eval 沙箱
user_expr = request.args.get('expr')
safe_dict = {'__builtins__': {}}  # 禁用内置函数
safe_dict['sum'] = sum
safe_dict['len'] = len
try:
    result = eval(user_expr, {"__builtins__": {}}, safe_dict)
except Exception as e:
    pass

# 较安全：使用 ast.literal_eval 仅解析字面量
import ast
user_data = request.json.get('data')
try:
    data = ast.literal_eval(user_data)  # 仅支持基础数据结构
except (ValueError, SyntaxError):
    return error_response()
```

**快速定位核心操作**：
- 关键词：`eval(`、`exec(`、`compile(`、`__import__`、动态代码执行
- 查看是否接收用户输入的代码字符串
- 检查 eval/exec 的全局和局部命名空间配置
- 追踪代码执行上下文中暴露的对象和函数
- 关注是否存在代码执行的超时和内存限制

**快速定位保护机制**：
- 是否完全避免使用 eval() 和 exec()
- 是否使用 `ast.literal_eval()` 替代 eval
- 是否创建了受限的命名空间禁用危险函数
- 是否对代码进行了静态分析或白名单验证
- 是否使用了 RestrictedPython 等沙箱库

**审计等级**：**L3-L4**
- **L3**：逐行分析 eval/exec 调用的命名空间配置
- **L4**：跨模块追踪用户输入到代码执行的完整链路

---

## Classify

**确认为漏洞**：
- 直接使用 eval() 或 exec() 执行用户输入
- 命名空间未被沙箱化，暴露了内置函数和模块
- 不存在代码执行的超时或内存限制
- 代码经过简单的字符串替换"清理"，可绕过

**误报**：
- 代码完全由应用内部定义，不接收用户输入
- 使用了 `ast.literal_eval()` 仅解析数据
- 使用了 RestrictedPython 等专业沙箱库
- 代码在隔离的子进程或容器中执行

**代码异味**：
- 存在 eval/exec 的使用有业务合理性但缺少验证
- 命名空间配置不规范，包含过多对象

---

## Low Risk

以下情况可评为低风险：
- **完全沙箱化**：使用 RestrictedPython 或类似库创建受限环境
- **使用 literal_eval**：仅解析数据结构，不执行代码
- **表达式能力弱**：仅支持基础算术运算，不支持函数定义或模块导入
- **严格超时控制**：代码执行有严格的时间限制（< 100ms）
- **内网应用**：仅由内部可信用户使用

**注意**：eval/exec 的风险极高，建议完全避免使用。
