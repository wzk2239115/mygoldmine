# Java Runtime.getRuntime().exec() 命令注入

**漏洞成因**：通过 `Runtime.getRuntime().exec()` 方法直接执行包含用户输入的命令，常见于运维接口、文件导出、日志清理、第三方工具调用等场景。

---

## Details

**代码示例**：
```java
// 危险：直接拼接用户输入
String userInput = request.getParameter("filename");
Runtime.getRuntime().exec("ls -l " + userInput);
Runtime.getRuntime().exec(new String[]{"/bin/sh", "-c", "cat " + userInput});

// 较安全：参数化调用（但仍需验证）
Runtime.getRuntime().exec(new String[]{"ls", "-l", userInput});
```

**快速定位核心操作**：
- 关键词：`Runtime.getRuntime().exec(`、`Runtime.exec(`
- 查看参数是否包含字符串拼接（`+`、`String.format`、`StringBuilder.append`）
- 重点关注 `/bin/sh -c`、`cmd /c`、`bash -c` 等 shell 解释器调用
- 追踪命令字符串的数据流，定位用户输入来源（request、headers、cookies、外部 API）

**快速定位保护机制**：
- 是否使用数组参数形式且无 shell 调用：`exec(new String[]{"cmd", "arg1", "arg2"})`
- 是否存在白名单校验：正则匹配、enum 枚举、固定值比对
- 是否对特殊字符转义：`;`、`|`、`&`、`$`、`` ` ``、`\n` 等
- 是否限制可执行命令范围：路径白名单、命令白名单

**审计等级**：**L3-L4**  
- **L3**：逐行读取 exec 调用上下文，确认参数来源和拼接方式
- **L4**：跨模块追踪用户输入到 exec 调用的完整数据流，检查所有校验点

---

## Classify

**确认为漏洞**：
- 用户输入直接或间接参与命令字符串拼接
- 使用 `/bin/sh -c` 或 `cmd /c` 执行拼接后的命令
- 过滤不完整（仅过滤部分特殊字符，可绕过）
- 白名单校验存在逻辑缺陷（路径遍历、二次编码绕过）

**误报**：
- 命令和参数均为硬编码常量
- 用户输入仅影响数组参数形式的某个参数，且无 shell 调用
- 存在严格的枚举或正则白名单，用户输入被完全限制在安全范围

**代码异味**：
- 存在校验但不够严格（黑名单过滤、简单正则）
- 使用 exec 但业务逻辑可用 Java API 替代（如文件操作、网络请求）
- 权限控制依赖前端校验或弱 token

---

## Low Risk

以下情况可评为低风险，但仍建议修复：
- **受限执行环境**：容器化部署且无敏感挂载、最小权限运行（无 sudo、suid）
- **内网隔离接口**：仅限内网/管理员访问，有二次认证（MFA、IP 白名单）
- **业务价值低**：测试环境、沙箱环境、已下线功能
- **影响范围小**：仅能执行特定命令（如 `ls`、`echo`），无法读写敏感文件或反弹 shell
- **存在部分防护**：有输入长度限制、命令超时控制、日志审计机制

**注意**：低风险≠可忽略，需结合实际业务场景和攻击面综合判断。