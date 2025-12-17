# Java ProcessBuilder 命令注入

## Details

**核心漏洞模式**：通过 `ProcessBuilder` 类构造命令时，将用户输入直接拼接到命令参数中，未做安全隔离或转义。

**代码示例**：
```java
String fileName = request.getParameter("file");
ProcessBuilder pb = new ProcessBuilder("cat", "/logs/" + fileName);
Process p = pb.start();

// 或单参数形式
ProcessBuilder pb = new ProcessBuilder("/bin/sh", "-c", "cat /logs/" + fileName);
```

**快速定位核心操作**：
- 关键类：`ProcessBuilder`、`new ProcessBuilder()`
- 关键方法链：`.command()`、`.start()`
- 数据流向：从外部输入（`request.getParameter`/`@RequestParam`/`@PathVariable`）→ 字符串拼接 → ProcessBuilder 构造参数

**快速定位保护机制**：
- 白名单校验：`Pattern.matches()`、`contains()`、`equals()` 等预检查
- 参数转义：`Jsoup.clean()`、自定义 `escapeShellArg()` 函数
- 安全列表限定：参数从预定义 `Map/Enum` 中取值

**审计等级**：**L3（逐行读）**  
需逐行追踪外部输入从接口层→业务层→ProcessBuilder 调用的完整数据流，关注中间是否存在有效过滤。

---

## Classify

**【漏洞】确认条件**：
1. 外部可控输入直接拼接到命令或参数
2. 使用 `/bin/sh -c` 或 `cmd.exe /c` 等 shell 解释器形式
3. 无有效白名单或转义机制

**【误报】排除场景**：
1. 参数从固定配置文件/数据库枚举值读取，与用户输入无关
2. 已通过严格白名单校验（如 `^[a-zA-Z0-9_-]+$` 且限制长度）
3. 使用参数数组形式传递（`new ProcessBuilder("cat", userInput)`），且不涉及 shell 解释器

**【代码异味】灰区判定**：
- 参数经过简单黑名单过滤（如仅过滤 `;` `|` `&`），但未考虑换行符、引号闭合等绕过
- 间接拼接：参数先存储到变量，再经过多次传递后进入 ProcessBuilder

---

## Low risk

**降级为低风险的场景**：
1. **权限受限**：执行命令的进程已通过 `SecurityManager` 或容器沙箱严格限制系统调用
2. **输入长度极限**：参数被截断到极短长度（如 `substring(0,5)`），无法构造有效 Payload
3. **内网隔离**：接口仅允许内网特定 IP 访问，且需要额外身份认证
4. **只读操作**：命令固定为只读工具（如 `ls`、`cat`），且目标路径限定在无敏感数据的临时目录
5. **输出不可见**：命令执行结果未返回给用户，且系统日志监控完善