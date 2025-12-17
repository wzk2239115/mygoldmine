# **Java LLM Tool Command Injection**

当 Java 应用的 LLM function calling 工具可以执行系统命令，而参数未经充分验证时，攻击者可以通过提示注入使模型执行恶意命令。

## Details

**代码示例位置识别技巧（L1: 关键词扫描）**
- 搜索命令执行：`Runtime.getRuntime().exec()`、`ProcessBuilder`、`executeCommand()`
- 查找命令构造：`cmd = "..." + param`、`String.format()`
- 搜索工具定义：包含执行系统命令的工具
- 查找参数验证：缺失的参数清理
- 定位 shell 执行：使用 `/bin/sh -c` 等

**核心操作保护机制（L2: 跳读）**
- 检查是否使用了 ProcessBuilder（比 Runtime 更安全）
- 验证是否进行了命令参数的白名单验证
- 查看是否避免了 shell 解释
- 检查是否对命令进行了限制
- 查看是否有沙箱或权限限制

**快速定位到具体漏洞（L3: 逐行读）**
- 追踪命令的构造方式
- 检查参数传递方式（array vs string）
- 审查参数验证逻辑
- 查看是否有白名单
- 检查错误输出处理

**数据流追踪（L4: 跨模块追踪）**
- 追踪从 LLM 输出到命令执行的完整路径
- 检查参数处理步骤
- 验证所有执行点

## Classify

**确认为漏洞的特征：**
1. 直接使用 LLM 输出构造系统命令
2. 使用 `Runtime.exec(String)` 而非数组形式
3. 使用 shell 解释命令（`/bin/sh -c`）
4. 参数未经验证或清理
5. 可以执行任意命令

**误报场景：**
1. 使用 ProcessBuilder 的数组形式，避免 shell 解释
2. 严格的命令白名单
3. 参数被限制为特定的、预定义的值
4. 使用 Java SecurityManager 限制命令执行
5. 完全不执行系统命令

**代码异味（需要深入审查）**
1. 字符串拼接构造命令
2. 使用 shell（`/bin/sh -c`）
3. 多个命令执行点
4. 复杂的参数处理

## Low risk

**评级为低风险的场景：**
1. 不执行任何系统命令
2. 使用 ProcessBuilder 的数组形式
3. 严格的命令白名单
4. 参数白名单验证
5. Java SecurityManager 限制权限
