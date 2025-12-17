# C# / .NET Process 命令执行

## Details

**代码特征示例：**
```csharp
// 使用 Process.Start() 直接执行命令
Process.Start("cmd.exe", "/c dir " + userInput);

// 使用 ProcessStartInfo 构造
var psi = new ProcessStartInfo("powershell.exe");
psi.Arguments = "-Command " + userCommand;
Process.Start(psi);

// 危险：直接拼接用户输入
var process = new Process();
process.StartInfo.FileName = "C:\\Windows\\System32\\cmd.exe";
process.StartInfo.Arguments = "/c " + userinput;
process.Start();

// 使用 shell=true 的变种
ProcessStartInfo psi = new ProcessStartInfo();
psi.UseShellExecute = true;  // 启用 shell 执行
psi.FileName = "cmd.exe";
psi.Arguments = "/c " + commandString;

// 危险：PowerShell 执行
Process.Start("powershell.exe", "-Command \"Get-ChildItem " + path + "\"");

// 使用 ShellExecute - 更危险
var psi = new ProcessStartInfo("notepad.exe")
{
    UseShellExecute = true,
    Arguments = userSuppliedPath
};
Process.Start(psi);

// 使用 .NET Core / .NET 5+ 的 ProcessStartInfo
var processInfo = new ProcessStartInfo
{
    FileName = "bash",
    Arguments = $"-c 'cat {filename}'",
    UseShellExecute = false
};
```

**快速定位核心操作：**
- 关键词：`Process.Start\(|ProcessStartInfo|\.Arguments|\.FileName`
- 查看参数是否包含字符串拼接（`+`、`String.Format`、`$"..."`）
- 重点关注 `UseShellExecute` 属性、`cmd.exe /c`、`powershell.exe -Command`
- 追踪命令字符串的数据流，定位用户输入来源（query params、POST data、environment variables）

**快速定位保护机制：**
- 是否使用参数化形式：`Arguments` 属性分离，而非在 FileName 中拼接
- 是否禁用 shell 执行：`UseShellExecute = false`
- 是否使用 `RedirectStandardOutput` 等安全属性
- 是否存在白名单校验：正则匹配、枚举、固定值比对
- 是否对特殊字符转义：检查是否使用了转义库

**审计等级：L3-L4**
- **L3**：逐行读取 Process 调用上下文，确认参数来源和拼接方式
- **L4**：跨模块追踪用户输入到 Process 调用的完整数据流，检查所有校验点

---

## Classify

**确认为漏洞：**
- 用户输入直接或间接参与命令字符串拼接
- 使用 `UseShellExecute = true` 执行拼接后的命令
- 使用 `cmd.exe /c` 或 `powershell.exe -Command` 执行拼接命令
- `Arguments` 属性包含用户输入且无任何过滤
- 过滤不完整：仅过滤部分特殊字符但遗漏某些 shell 元字符
- 白名单校验存在逻辑缺陷（路径遍历、编码绕过）

**误报：**
- 命令和参数均为硬编码常量
- 用户输入仅影响 `Arguments` 属性且经过严格的枚举或正则白名单
- 使用 `UseShellExecute = false` 且参数不包含 shell 特殊字符
- 已知安全的命令库（如 `System.IO` 文件操作）替代了 Process 调用

**代码异味：**
- 存在校验但不够严格（黑名单过滤、简单正则）
- 使用 `UseShellExecute = true` 但无特殊必要
- 依赖前端验证或弱权限控制
- PowerShell 脚本注入风险（如 `-Command` 参数未转义）

---

## Low Risk

以下情况可评为低风险，但仍建议修复：
- **受限执行环境**：容器化部署且无敏感挂载、最小权限运行
- **内网隔离接口**：仅限内网/管理员访问，有二次认证（MFA、IP 白名单）
- **业务价值低**：测试环境、沙箱环境、已下线功能
- **影响范围小**：仅能执行特定命令，无法读写敏感文件或反弹 shell
- **使用 UseShellExecute = false**：且参数中无危险特殊字符
- **存在部分防护**：有输入长度限制、命令超时控制、日志审计机制

**注意**：低风险≠可忽略，需结合实际业务场景和攻击面综合判断。
