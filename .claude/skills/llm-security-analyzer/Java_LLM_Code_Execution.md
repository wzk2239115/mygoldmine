# **Java LLM Code Execution**

当 Java 应用将 LLM 输出用于代码执行上下文（如通过反射、表达式语言、脚本引擎），攻击者可以通过提示注入使模型生成恶意代码，实现任意代码执行。

## Details

**代码示例位置识别技巧（L1: 关键词扫描）**
- 搜索危险方法：`Runtime.getRuntime().exec()`、`ProcessBuilder`、`ScriptEngineManager`
- 查找反射调用：`Class.forName()`、`Method.invoke()`、`Constructor.newInstance()`
- 搜索表达式语言：`SpEL`、`OGNL`、`EL`、`parseExpression()`
- 查找脚本执行：`engine.eval()`、`Nashorn`、`GraalVM`
- 定位 JDBC 动态查询：`Statement.execute()`

**核心操作保护机制（L2: 跳读）**
- 检查是否使用了 LLM 输出进行代码执行
- 验证是否有沙箱环境（Java SecurityManager）
- 查看是否使用了白名单限制可执行的方法/表达式
- 检查是否禁用了危险的语言功能
- 查看是否有运行时权限限制

**快速定位到具体漏洞（L3: 逐行读）**
- 追踪 LLM 输出到代码执行的路径
- 检查输入是否经过验证
- 审查反射或脚本执行的上下文
- 查看是否有异常处理隐藏了问题
- 检查是否有多个代码执行点

**数据流追踪（L4: 跨模块追踪）**
- 追踪 LLM 输出的完整处理链
- 检查是否有中间步骤进行了验证
- 验证所有执行点

## Classify

**确认为漏洞的特征：**
1. LLM 输出直接传递给 `Runtime.exec()`、`ScriptEngine.eval()` 等
2. 使用反射动态调用 LLM 选择的方法
3. SpEL 或 OGNL 表达式由 LLM 输出构造
4. 未使用 SecurityManager 限制权限
5. 可以通过 LLM 执行任意系统命令

**误报场景：**
1. 代码执行被限制在白名单的方法/表达式
2. 使用了 Java SecurityManager 进行权限隔离
3. 输入经过严格验证和清理
4. 使用了受限的脚本引擎配置
5. 仅使用参数化的表达式语言

**代码异味（需要深入审查）**
1. 动态构造表达式
2. 条件性地禁用安全检查
3. 多个代码执行点
4. 缺少输入验证

## Low risk

**评级为低风险的场景：**
1. 不使用任何代码执行机制
2. 代码执行被严格限制在白名单方法
3. Java SecurityManager 正确配置和启用
4. SpEL/OGNL 表达式由应用定义，不涉及 LLM 输出
5. 脚本引擎禁用了危险的函数（如 exec、system）
