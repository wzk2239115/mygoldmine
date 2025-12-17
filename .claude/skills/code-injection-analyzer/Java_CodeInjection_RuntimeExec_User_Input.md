# Java Runtime.exec() 命令执行注入

**漏洞成因**：使用 `Runtime.getRuntime().exec()` 执行系统命令，当用户输入作为命令参数或命令字符串时，可导致命令注入漏洞。与代码注入重叠，属于命令执行范畴。

---

## Details

**代码示例**：
```java
// 危险：直接拼接用户输入到命令字符串
String userFile = request.getParameter("file");
Runtime.getRuntime().exec("cat " + userFile);

// 危险：使用 shell 执行拼接的命令
String command = "echo " + userInput + " >> /tmp/log.txt";
Runtime.getRuntime().exec(new String[]{"/bin/bash", "-c", command});

// 危险：数组参数仍可包含用户输入
Runtime.getRuntime().exec(new String[]{"ls", "-l", userFile});

// 较安全：参数化方式（但仍需验证）
Runtime.getRuntime().exec(new String[]{"ls", "-l", userFile});
```

**快速定位核心操作**（L1-L3）：
- 关键词：`Runtime.getRuntime().exec(`、`Runtime.exec(`
- 查看命令或参数是否包含用户输入
- 检查是否使用了 shell 模式（`/bin/sh -c`、`cmd /c`）
- 追踪数据流：`request.getParameter()`、`request.getInputStream()`

**快速定位保护机制**（L2-L3）：
- 是否使用数组参数形式且无 shell 调用
- 是否存在命令白名单：仅允许特定命令
- 是否对参数进行了转义：特殊字符处理
- 是否限制了可执行命令范围

**审计等级**：**L2-L4**
- **L2**：跳读 exec 调用，确认参数来源
- **L3**：逐行读取参数构造、防护机制
- **L4**：跨模块追踪用户输入到 exec 的完整流程

---

## Classify

**确认为漏洞**：
- 用户输入直接或间接参与命令/参数构造
- 使用 shell 模式执行拼接后的命令
- 无防护或防护不完整

**误报**：
- 命令和参数均为硬编码常量
- 用户输入仅作为数组参数，无 shell 调用
- 存在严格的参数白名单

**代码异味**：
- exec 存在但有部分防护
- 权限控制依赖前端验证
- 业务可用 Java API 替代执行命令

---

## Low Risk

以下情况可评为低风险：
- **受限执行环境**：容器/沙箱内，最小权限运行
- **权限隔离**：命令执行权限受限
- **内网保护**：仅限管理员、内网
- **严格的参数白名单**：限制可执行命令
- **审计监控**：命令执行被完整记录、监控
