# Java - 自定义Shell包装器命令注入

**场景：** 运维接口、文件导出、日志清理、第三方工具调用  
**成因：** 自定义工具类封装命令执行逻辑时，通过字符串拼接方式构造Shell命令

---

## Details

**典型代码示例：**
```java
// 危险模式：自定义Shell工具类
public class ShellUtil {
    public static String exec(String command) {
        return Runtime.getRuntime().exec(new String[]{"/bin/sh", "-c", command}).waitFor();
    }
}
// 业务调用：拼接用户输入
String result = ShellUtil.exec("cat /logs/" + fileName);

// 或通过包装类构造命令
public class CommandBuilder {
    public String build(String userParam) {
        return "ping -c 4 " + userParam;  // 字符串拼接
    }
}
```

**审计等级：L3-L4（逐行读-跨模块追踪）**

**快速定位核心操作：**
- 搜索自定义工具类：类名含 `ShellUtil`、`CommandUtil`、`ExecHelper`、`OSExecutor`
- 关键方法特征：方法名含 `exec`、`execute`、`runCommand`、`shell`
- 定位拼接点：`String.format()`、`StringBuilder.append()`、`+` 运算符、`StringUtils.join()`
- 追踪调用链：从Controller/Service → 工具类方法 → Runtime.exec()/ProcessBuilder

**快速定位保护机制：**
- 检查白名单校验：`Pattern.matches("^[a-zA-Z0-9_-]+$")`、`switch-case` 枚举值
- 检查参数转义：`StringEscapeUtils.escapeXSI()`、自定义 `sanitize()` 方法
- 检查是否使用参数数组模式：`exec(new String[]{"ls", "-l", userInput})` 而非 `-c` 模式
- 检查权限控制：方法上是否有 `@PreAuthorize`、`@RolesAllowed` 注解

---

## Classify

**✓ 确认漏洞：**
- 工具类方法使用 `/bin/sh -c` 或 `cmd.exe /c` 执行拼接的命令字符串
- 用户输入通过字符串拼接/格式化直接嵌入命令，无过滤
- 输入来源不可信：HTTP请求参数、文件上传路径、WebSocket消息、数据库查询结果

**△ 代码异味：**
- 使用黑名单过滤（仅过滤 `;`、`|`、`&`），但未覆盖反引号、`$()` 等
- 过滤逻辑在业务层，而工具类本身不做任何校验（分散的防御）
- 仅验证参数长度或简单正则，未限制特殊字符

**✗ 误报：**
- 工具类内部使用参数数组模式：`new String[]{"cmd", arg1, arg2}`（无 `-c`）
- 命令完全硬编码，用户输入仅作为 ProcessBuilder 的独立参数添加
- 输入经过严格白名单验证（如枚举类型映射）且代码逻辑清晰
- 工具类仅处理可信配置文件内容，不涉及用户输入

---

## Low risk

**以下情况评为低风险：**
- 工具类执行环境在隔离容器中（Docker），且容器无敏感挂载点
- 应用运行在低权限账户（非 root），且已通过 SecurityManager 限制文件访问
- 输入参数长度严格限制（< 16字符），且仅允许字母数字下划线
- 仅内网管理后台使用，需双因素认证 + IP白名单，且有完整操作审计日志
- 业务场景明确限定为安全操作（如：从预定义列表中选择日志文件名）
- 工具类方法已标记 `@Deprecated`，且团队已计划重构为安全API

**注意：** 即使评为低风险，建议优先重构为 ProcessBuilder 参数数组模式，彻底消除命令注入风险。