# **Python LLM Code Injection**

当 Python 应用将 LLM 生成的输出直接用于代码执行上下文（如 `eval()`、`exec()`、动态导入、ORM 查询构造），攻击者可以注入恶意代码，实现任意代码执行。

## Details

**代码示例位置识别技巧（L1: 关键词扫描）**
- 搜索危险函数：`eval()`、`exec()`、`compile()`、`__import__()`、`importlib.import_module()`
- 查找动态代码构造：`f"query = {llm_output}"`、`"code = " + llm_response`
- 搜索 pickle、yaml、json 不安全的反序列化：`pickle.loads()`、`yaml.load()`
- 查找动态 ORM 查询：`Model.objects.raw()`、`db.execute()`、`query.filter()`
- 定位模板引擎的动态编译：`Template(llm_output).render()`

**核心操作保护机制（L2: 跳读）**
- 验证是否使用了参数化的代码执行（如受限的表达式求值库）
- 检查是否有沙箱机制（如 `RestrictedPython`、`PyPy 沙箱`）
- 查看是否使用了 AST 解析进行验证而非直接执行
- 检查是否使用了白名单库（如 `ast.literal_eval()` 仅用于字面值）
- 审查是否有运行时权限限制或资源隔离

**快速定位到具体漏洞（L3: 逐行读）**
- 在 `eval()`、`exec()` 调用前追踪 LLM 输出的来源
- 检查输入是否进行了验证（如 AST 检查、正则表达式）
- 审查变量作用域和全局变量暴露情况
- 查看是否在多层嵌套的代码执行中累积 LLM 输出

**数据流追踪（L4: 跨模块追踪）**
- 追踪 LLM 输出从生成到代码执行的完整路径
- 检查是否有多个代码执行点
- 验证错误处理中是否也存在代码执行

## Classify

**确认为漏洞的特征：**
1. LLM 输出直接传递给 `eval()`、`exec()`、`compile()`
2. 动态 SQL 查询使用字符串拼接，未使用参数化查询
3. 使用 `pickle.loads()`、`yaml.load()` 处理 LLM 输出
4. ORM 框架使用原始 SQL 且包含 LLM 输出
5. 模板引擎直接编译 LLM 输出的模板内容

**误报场景：**
1. 仅对 LLM 输出进行 `ast.literal_eval()`，限制为字面值
2. 使用了沙箱化的代码执行库（RestrictedPython 等）
3. 代码执行仅限于特定的、预定义的函数集
4. 参数化查询正确使用，LLM 输出仅作为数据
5. 输出经过严格的格式验证（如 JSON schema 校验）

**代码异味（需要深入审查）：**
1. 动态生成的 SQL、Python 代码或查询字符串
2. 使用了 `globals()` 或 `locals()` 的动态执行
3. 通过字符串拼接构造模块路径进行动态导入
4. 条件性地使用参数化或非参数化查询

## Low risk

**评级为低风险的场景：**
1. LLM 输出用于参数化查询的值部分，完全与 SQL 语句分离
2. 仅使用了 `ast.literal_eval()` 且验证成功
3. 代码执行被限制在明确的沙箱环境，且沙箱配置正确
4. 输出内容完全来自系统提示，不涉及用户注入
5. 应用明确使用 ORM 框架的参数化接口（如 Django ORM）
