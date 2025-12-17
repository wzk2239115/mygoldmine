---
name: command-injection-analyzer
description: 专业的审计工作流程，通过静态代码分析识别和验证命令注入（Command Injection）漏洞；重点关注检测应用程序中将用户可控输入拼接到操作系统命令中的问题，包括使用system()、exec()、ProcessBuilder、child_process等API时未对输入进行严格过滤或转义、直接拼接shell命令字符串、未使用参数化命令执行方式、错误使用shell模式执行外部程序、未采用白名单验证用户输入、对特殊字符（如;|&$`等）缺乏有效过滤等，从而导致攻击者通过精心构造的输入在服务器上执行任意系统命令、读取敏感文件、提权、建立后门、破坏系统等严重安全问题；利用按编程语言组织的参考资料目录中的参考指南。
---

**Attention**  
当项目中存在通过拼接用户可控输入来构造操作系统命令（如 shell、CLI 工具调用）的逻辑时，需高度警惕 command_injection 风险。此类漏洞通常出现在系统管理、文件处理、日志分析、运维自动化、CI/CD 脚本调用等涉及外部命令执行的模块中，尤其在未对输入进行严格过滤或未使用安全 API 的情况下极易触发。

**Early exit**

**在开始审计之前，必须首先运行命令注入扫描脚本完成初步检索**，快速识别代码中是否存在相关命令执行 API 调用。这是审计流程的强制性第一步，不可跳过。

**调用方式：**

```python
# 获取当前工作目录（项目路径）
target_path = get_cwd()

# 运行命令注入扫描脚本
scan_result = skill_run_command(path="bash", params=["scripts/scan.sh", target_path])
```

**快速退出条件：**

若扫描脚本结果显示项目代码中完全未调用任何操作系统命令（如无 system()、exec()、ProcessBuilder、child_process.exec 等相关 API 使用），且不涉及与 shell 或 CLI 工具的交互，则必须立即退出对该漏洞类型的审计。

---

## 通用命令注入缺陷模式（所有项目必审）

查看详细说明：[general.md](general.md)

快速概览：直接拼接用户输入到命令字符串（字符串拼接、模板字符串）、使用 Shell 模式执行命令（shell=True、sh -c、bash -c）、特殊字符未过滤或转义（分号、管道、重定向等元字符）、未使用参数化命令执行（命令与参数未分离）、环境变量注入（PATH、LD_PRELOAD、IFS 等污染）、通配符展开注入（* ? {} ~ 等 shell 通配符利用）、输入验证不足（黑名单绕过、弱白名单）

查看详细说明：
- 环境变量污染攻击，详见：[command_env_pollution.md](command_env_pollution.md)

---
**语言特定实现（根据项目语言选择性审计）**

以下漏洞场景与具体编程语言的命令执行 API 实现相关。根据项目所使用的编程语言，仅需审计对应语言章节中的漏洞模式。

**Java**  
- 通过 Runtime.getRuntime().exec() 方法直接执行包含用户输入的命令，详见：[Java_RuntimeExec.md](Java_RuntimeExec.md)  
- 通过 ProcessBuilder 类构造命令时未对参数做安全隔离或转义，详见：[Java_ProcessBuilder.md](Java_ProcessBuilder.md)  
- 自定义 Shell 包装器或工具类执行命令时拼接用户输入，详见：[Java_ShellWrapper.md](Java_ShellWrapper.md)
- ProcessBuilder 未清理环境变量导致注入，详见：[java_processbuilder_env_injection.md](java_processbuilder_env_injection.md)
- ProcessBuilder 接收包含通配符的参数列表，详见：[java_glob_command_injection.md](java_glob_command_injection.md)

**Python**  
- 通过 os.system() 函数直接执行包含用户输入的 shell 命令字符串，详见：[Python_OS_System.md](Python_OS_System.md)  
- 通过 subprocess.run(shell=True) 或 subprocess.call(shell=True) 等方式拼接用户输入，详见：[Python_SubprocessShellTrue.md](Python_SubprocessShellTrue.md)  
- 通过 os.popen() 函数以管道方式执行包含用户输入的命令，详见：[Python_PopenWithShell.md](Python_PopenWithShell.md)
- subprocess.Popen 传递受污染的 env 字典，详见：[python_subprocess_env_pollution.md](python_subprocess_env_pollution.md)
- glob.glob() 结果直接用于命令构造，详见：[python_glob_to_command.md](python_glob_to_command.md)

**Go**  
- 调用 exec.Command 时将用户输入作为整个命令字符串而非参数列表传入，详见：[Go_ExecCommandWithString.md](Go_ExecCommandWithString.md)  
- 通过 sh -c 或 bash -c 方式错误地将用户输入拼接到 shell 命令中，详见：[Go_ShellCInjection.md](Go_ShellCInjection.md)  
- 将未过滤的用户输入直接作为 exec.Command 的参数传递，详见：[Go_UserInputInArgs.md](Go_UserInputInArgs.md)
- exec.Command 继承父进程环境变量未清理，详见：[go_command_env_inherit.md](go_command_env_inherit.md)
- filepath.Glob 结果用于 exec.Command，详见：[go_filepath_glob_command.md](go_filepath_glob_command.md)

**PHP**  
- 通过 system()、exec() 等系统函数直接执行拼接用户输入的命令，详见：[PHP_SystemFunction.md](PHP_SystemFunction.md)  
- 通过 shell_exec() 函数或反引号运算符执行包含用户输入的 shell 命令，详见：[PHP_ShellExec.md](PHP_ShellExec.md)  
- 通过反引号（backtick）运算符执行动态构造的命令字符串，详见：[PHP_BacktickOperator.md](PHP_BacktickOperator.md)

**JavaScript (Node.js)**  
- 通过 child_process.exec() 方法将用户输入直接嵌入命令字符串执行，详见：[JS_ChildProcessExec.md](JS_ChildProcessExec.md)  
- 通过 child_process.execSync() 同步执行包含用户输入的 shell 命令，详见：[JS_ExecSyncWithInput.md](JS_ExecSyncWithInput.md)  
- 通过 child_process.spawn() 以 shell 模式执行拼接用户输入的命令，详见：[JS_ShellSpawn.md](JS_ShellSpawn.md)

**TypeScript**  
- 通过 child_process 模块的 exec() 方法执行包含用户输入的命令，详见：[TS_ChildProcessExec.md](TS_ChildProcessExec.md)  
- 构造命令字符串时未对用户输入做参数化处理导致注入，详见：[TS_ExecCommandInjection.md](TS_ExecCommandInjection.md)  
- 通过字符串拼接方式构造 shell 命令并传递给执行函数，详见：[TS_ShellStringConcat.md](TS_ShellStringConcat.md)

**C/C++**  
- 通过 system() 函数直接执行包含用户输入的命令字符串，详见：[C_CommandViaSystem.md](C_CommandViaSystem.md)  
- 通过 popen() 函数以管道方式执行拼接用户输入的 shell 命令，详见：[C_CommandViaPopen.md](C_CommandViaPopen.md)  
- 通过 execl()、execv() 等 exec 系列函数传递未过滤的用户输入作为命令参数，详见：[C_ExecWithUserInput.md](C_ExecWithUserInput.md)  

**Rust**
- 使用 std::process::Command 配合 sh -c 将用户输入拼接到 shell 命令中，详见：[Rust_CommandWithShell.md](Rust_CommandWithShell.md)
- 在构造 Command 时将未过滤的用户输入直接嵌入 shell 命令字符串，详见：[Rust_UserInputInShell.md](Rust_UserInputInShell.md)
- 通过 sh -c 方式执行动态构造的命令而非使用参数化方式，详见：[Rust_ExecViaShC.md](Rust_ExecViaShC.md)

**Ruby**
- 使用反引号或 %x{} 字符串插值执行用户输入的命令，详见：[Ruby_CommandExecution.md](Ruby_CommandExecution.md)
- 通过 system()、exec()、spawn() 等函数直接执行拼接用户输入的命令字符串，详见：[Ruby_CommandExecution.md](Ruby_CommandExecution.md)
- 使用 IO.popen() 以管道方式执行包含用户输入的命令，详见：[Ruby_CommandExecution.md](Ruby_CommandExecution.md)

**Perl**
- 使用反引号或 qx() 操作符执行包含用户输入的 shell 命令，详见：[Perl_CommandExecution.md](Perl_CommandExecution.md)
- 使用 system() 或 exec() 的字符串形式而非参数列表形式拼接用户输入，详见：[Perl_CommandExecution.md](Perl_CommandExecution.md)
- 使用 open() 进行管道调用时未对用户输入进行转义，详见：[Perl_CommandExecution.md](Perl_CommandExecution.md)

**C# / .NET**
- 通过 Process.Start() 或 ProcessStartInfo 直接执行包含用户输入的命令字符串，详见：[CSharp_ProcessStart.md](CSharp_ProcessStart.md)
- 使用 cmd.exe /c 或 powershell.exe -Command 执行拼接后的命令，详见：[CSharp_ProcessStart.md](CSharp_ProcessStart.md)
- 设置 UseShellExecute = true 导致命令通过 shell 执行，详见：[CSharp_ProcessStart.md](CSharp_ProcessStart.md)

**数据库相关命令执行**
- SQL Server 的 xp_cmdshell 或 OLE Automation 执行系统命令，详见：[Database_CommandExecution.md](Database_CommandExecution.md)
- MySQL 的 LOAD_FILE 或 INTO OUTFILE 读写文件，详见：[Database_CommandExecution.md](Database_CommandExecution.md)
- PostgreSQL 的 COPY TO/FROM PROGRAM 执行系统命令，详见：[Database_CommandExecution.md](Database_CommandExecution.md)
- MongoDB 的 $where 操作符执行用户提供的代码，详见：[Database_CommandExecution.md](Database_CommandExecution.md)
- Oracle DBMS_JAVA 或外部过程调用，详见：[Database_CommandExecution.md](Database_CommandExecution.md)

## 快速开始

### 步骤 0：理解项目功能与结构

**在开始审计之前，彻底理解项目的功能与结构，特别关注命令执行相关的实现：**

- 查阅项目文档，重点关注系统管理、文件处理、运维自动化等涉及命令执行的功能说明
- 理解业务领域和核心功能，识别涉及外部命令调用、脚本执行、系统工具调用的场景
- 识别关键组件、模块及其关系，特别是系统管理模块、文件处理模块、日志分析模块、CI/CD 集成
- 梳理应用流程（重点：用户输入 → 命令构造 → 命令执行 → 结果处理）
- 识别关键业务功能（文件操作、备份恢复、日志处理、批量操作、第三方工具调用等）
- 理解所用技术栈和框架（Web框架、命令执行库、shell 脚本调用方式）
- 查阅配置文件以理解系统行为（允许执行的命令列表、命令白名单、参数验证规则等）
- 定位命令执行的位置（命令构造函数、执行函数、输入处理逻辑）
- 定位用户输入的来源（HTTP 参数、表单数据、文件内容、配置文件等）
- 追踪用户输入到命令执行的数据流

**Early exit（早期退出）：**

**必须先执行前面 Early exit 章节中要求的扫描脚本**，根据扫描结果判断是否继续审计。如果扫描结果显示项目不符合条件（例如完全未调用任何操作系统命令、无命令执行 API 使用），必须立即退出该漏洞类型的审计，无需继续深入分析。

只有在扫描脚本确认项目存在命令执行逻辑并获得足够的项目背景信息后，才继续查阅各漏洞类型的参考指南并开始有针对性的漏洞分析。

### 步骤 1：查阅命令注入漏洞的参考指南

命令注入漏洞审计分为两个层次，需要按顺序进行：

**第一步：审计通用命令注入缺陷模式（所有项目必审）**

在 **通用命令注入缺陷模式** 章节中，列举了所有涉及命令执行的项目都必须审计的安全问题：
- 直接拼接用户输入到命令字符串（字符串拼接、模板字符串）
- 使用 Shell 模式执行命令（shell=True、sh -c、bash -c）
- 特殊字符未过滤或转义（分号、管道、重定向等元字符）
- 未使用参数化命令执行（命令与参数未分离）
- 环境变量注入（PATH、LD_PRELOAD、IFS 等污染）
- 通配符展开注入（* ? {} ~ 等 shell 通配符利用）
- 输入验证不足（黑名单绕过、弱白名单）

这些问题与编程语言无关，是命令执行安全设计和实现层面的通用缺陷，任何有命令执行功能的项目都需要检查。

**第二步：审计语言特定实现（根据项目语言选择性审计）**

在 **语言特定实现** 章节中，按编程语言组织了各语言命令执行 API 的特定问题：
- 按编程语言分类（Java、Python、Go、PHP、JavaScript、TypeScript、C/C++、Rust）
- 列出该语言命令执行 API 的典型误用模式和对应的参考文档链接

根据项目所用编程语言，仅需查找和审计对应语言章节中的漏洞场景。

### 步骤 2：深入学习具体的审计指南

根据 **通用命令注入缺陷模式** 和 **语言特定实现** 章节中的引用，打开对应的具体审计指南文件（如 `cmd_string_concatenation.md`、`Java_RuntimeExec.md`、`Python_OS_System.md` 等）。这些文件主要包含三个核心部分：

1. **Details（详细说明）**：漏洞成因、危险代码与安全代码对比示例、快速定位技巧（核心操作定位和保护机制定位）
2. **Classify（分类研判）**：明确的研判标准，包括确认漏洞、判定误报、识别代码异味的具体条件
3. **Low risk（低风险场景）**：列举可以降低风险等级的场景和条件

通过学习这些具体指南，可以准确识别代码中的漏洞模式，并进行有效的审计和评估。

## 审计等级定义

命令注入漏洞审计采用分层的审计等级制度，根据命令执行方式和输入处理来指导审计深度。

| 等级 | 名称 | 时间 | 执行特征 |
|------|------|------|---------|
| **L0** | 快速跳过 | 1-2 分钟 | 参数化执行 + 白名单隔离：`exec(['cmd', arg])`，无 shell，特殊字符被转义 |
| **L1** | 快速扫描 | 3-5 分钟 | 参数化执行 + 用户输入：需验证输入来源和隔离方式 |
| **L2** | 跳读 | 5-10 分钟 | 字符串拼接 + 有过滤：需验证过滤规则完整性和执行方式 |
| **L3** | 逐行读 | 15-30 分钟 | 直接拼接无防护或 shell 模式：`exec('cmd ' + input)`、`shell=True`、特殊字符未过滤 |
| **L4** | 跨模块追踪 | 30-60 分钟 | 链路复杂：多文件、文件读写、通配符展开、环境变量污染 |

### 快速判断流程

**第 1 步：是否存在命令执行 API？**
- `system()`, `exec()`, `sh -c`, `ProcessBuilder`, `subprocess`, `popen()`, 反引号等
- 无则 L0 跳过 | 有则继续第 2 步

**第 2 步：命令执行方式是什么？**
- 参数化（数组/列表形式）→ 继续第 3 步
- 字符串拼接或 shell 模式 → **L3+**

**第 3 步：输入如何处理？**
- 白名单限制或无用户输入 → **L0**
- 参数隔离但有用户输入 → **L1**
- 字符串拼接 + 有过滤 → **L2**
- 多文件/环境变量污染 → **L3-L4**

### 各等级操作指南

**L0**：参数化 + 白名单
```javascript
exec(['ls', userInput]);  // 参数分离
if (allowlist.includes(userInput)) { ... }  // 白名单
```

**L1**：参数化 + 用户输入
- 验证命令执行方式（数组/列表形式）
- 确认参数隔离
- 检查用户输入来源和是否经过验证

**L2**：字符串拼接 + 过滤
- 定位过滤逻辑：黑名单还是白名单？
- 核实过滤规则是否覆盖所有特殊字符：`;|&$`~()`
- 检查执行方式是否避免 shell：`exec(cmd)` vs `exec(cmd, {shell: true})`

**L3**：直接拼接或 shell 执行
```javascript
// 直接拼接无防护
exec(`tar -xf ${filename}`);  // 攻击：filename="evil.tar; rm -rf /"

// Shell 模式
subprocess.run(cmd, shell=True)  // 高风险

// 特殊字符未过滤
system("whois " + domain);  // domain可注入
```
完整分析命令构造和执行流程，追踪数据流，确认绕过方式

**L4**：复杂链路
- 多文件追踪：用户输入 → 文件处理 → 命令构造 → 执行
- 文件上传：`exec(\`file ${req.file.originalname}\`)`
- 通配符展开：`exec(\`tar -xf *.tar\`)`
- 环境变量污染：`exec(cmd, {env: {...process.env}})`

### 审计等级应用

```markdown
| 场景 | 等级 | 说明 |
|------|------|------|
| 参数化 + 白名单 | L0 | 无风险 |
| 参数化 + 用户输入 | L1 | 验证隔离 |
| 拼接 + 过滤 | L2 | 验证过滤 |
| 直接拼接无防护 | L3 | 高风险 |
| Shell 模式执行 | L3 | 高风险 |
| 多文件/环境污染 | L4 | 完整追踪 |
```

## 核心审计原则

### 验证要求

- 必须根据实际源代码验证发现结果，而非仅依赖模式匹配
- 必须验证完整的漏洞利用链：入口（用户输入）→ 命令构造 → 命令执行 → 系统影响
- 每一步都需要文件路径、函数名和行号的具体证据
- 考虑框架和项目中实现的自动防护（输入过滤、命令白名单、参数化执行等）
- **遇到保护机制时，必须参考绕过技巧文档**：[bypassTricks.md](bypassTricks.md)

### 常见保护机制与对应绕过技巧

**在审计过程中遇到以下保护机制时，应查阅 bypassTricks.md 中的对应章节：**

| 保护机制类型 | 检测特征 | 绕过技巧章节（bypassTricks.md） | 适用场景 |
|-------------|---------|-------------------------------|---------|
| **空格过滤** | 过滤`' '`、`\s`、`%20` | § 空格绕过技巧 - IFS变量替代 / Tab字符和重定向符 / 花括号展开 | 命令执行 |
| **命令分隔符过滤** | 过滤`;`、`\|`、`&&`、`\|\|` | § 命令分隔符绕过 - 条件执行符 / 命令分隔符绕过输出重定向 | 命令执行 |
| **关键字过滤** | 过滤`cat`、`flag`、`system`等 | § 文件读取命令替代 / § 反斜杠转义绕过关键字过滤 / § 单引号分割绕过关键字过滤 | 命令执行 |
| **通配符过滤** | 过滤`*`、`?` | § 通配符利用 / § 单引号分割绕过关键字过滤 | 命令执行 |
| **美元符号过滤** | 过滤`\$` | § 空格绕过技巧 - Tab字符和重定向符（使用`<>`替代`${IFS}`） | 命令执行 |
| **环境变量污染防护** | PATH、LD_PRELOAD、IFS校验 | § 环境变量污染高级技巧 - PATH环境变量高级污染 / LD_PRELOAD库注入 / IFS污染 | 命令执行 |
| **括号过滤（PHP）** | 过滤`(`、`)` | § include无括号包含技术 / § 过滤括号（PHP代码执行场景） | PHP代码执行 |
| **分号过滤（PHP）** | 过滤`;` | § 使用?>闭合PHP绕过分号 / § 命令分隔符绕过 | PHP代码执行 |
| **字母数字过滤（PHP）** | 过滤`[a-zA-Z0-9]` | § 无字母无数字执行 - PHP位运算绕过 / § math函数绕过字符限制 | PHP代码执行 |
| **字母数字过滤（Bash）** | 过滤`[a-zA-Z0-9]` | § $(( ))整数运算构造数字 / § Bash内置环境变量绕过字符限制 | 命令执行 |
| **禁用函数（PHP）** | `disable_functions`包含`system`、`exec` | § 突破禁用函数（disable_functions） - 文件读取函数替代 / FFI绕过 / SQL读取文件绕过 | PHP代码执行 |
| **open_basedir限制** | `open_basedir`限制访问目录 | § open_basedir绕过 - 使用glob://协议 | PHP代码执行 |
| **输出重定向** | 命令后附加`>/dev/null 2>&1` | § 命令分隔符绕过输出重定向 - 使用`\|\|`、`;`、`\|`中断原命令 | 命令执行 |
| **无回显执行** | 无输出或输出被抑制 | § 无回显RCE技术 - DNS外带 / HTTP外带 / 文件写入 / 盲打Time-based | 命令执行 & PHP代码执行 |
| **黑名单绕过** | `preg_match`或`in_array`黑名单 | § 编码和混淆技术 - 字符编码绕过 / 引号和大小写混淆 / 参数拆分和注入 | 命令执行 |
| **容器/沙箱环境** | Docker、chroot、jailed环境 | § 容器和沙箱环境特定绕过 | 命令执行 |
| **eval限制（PHP）** | `eval()`执行但受限 | § PHP代码执行函数绕过 - 类闭合绕过 / 嵌套调用绕过 / 反射类利用 | PHP代码执行 |
| **create_function过滤** | `create_function()`参数过滤 | § PHP代码执行函数绕过 - create_function反斜杠绕过 | PHP代码执行 |
| **include限制** | `include`后缀限制、协议过滤 | § include无括号包含技术 - data://协议利用 / 默认文件后缀绕过 / 日志包含绕过 | PHP代码执行 |
| **无参数限制（PHP）** | 所有参数被过滤或不允许传参 | § 无参数RCE（PHP代码执行场景） - 无参数文件读取 | PHP代码执行 |
| **字符编码混淆** | URL编码、十六进制、八进制 | § URL和其他协议编码绕过 - URL编码多层组合 / Unicode编码和规范化 | 命令执行 |
| **变量覆盖保护** | `extract()`、`parse_str()`限制 | § PHP特性利用 - 变量覆盖利用 / 反射类和内置类利用 | PHP代码执行 |

**使用说明：**

1. **识别保护机制**：在代码审计过程中，首先识别代码中存在哪些保护机制（如正则过滤、黑名单、白名单等）
2. **查找对应章节**：根据上表中的"绕过技巧章节"列，定位到 bypassTricks.md 中的具体章节
3. **分析绕过可行性**：仔细阅读对应章节中的"⚠️ 适用条件"，确认绕过方法是否适用于当前过滤规则
4. **构造绕过payload**：根据章节中的示例和说明，构造适合当前场景的绕过payload
5. **验证绕过效果**：确保构造的payload不包含被过滤的字符，并且能够成功绕过保护机制

**⚠️ 关键注意事项：**

- **必须严格检查过滤规则**：如果过滤规则禁止了某个字符（如`\$`），则所有包含该字符的绕过方法都不可用
- **区分函数类型**：命令执行函数（`system()`、`exec()`等）和PHP代码执行函数（`eval()`、`assert()`等）使用的绕过技巧完全不同，不可混用
- **多次尝试绕过**：如果第一种绕过方法不适用，应尝试其他替代方法（参考 bypassTricks.md 中的多种方案）
- **组合使用技巧**：复杂的保护机制可能需要组合多种绕过技巧（参考 bypassTricks.md 末尾的"CTF常见组合"章节）

# 输出要求

确认漏洞后，加载 `bug-report` 技能获取标准化报告格式，生成漏洞报告文件。

**加载技能**：`bug-report`

**输出路径**：`.workspace/findings/BUG-command-injection-{file}-L{line}-{source}-{sink}.md`

**约束**：
- 每个漏洞必须生成独立的 BUG 文件，禁止合并或省略
- 漏洞报告格式严格遵循 `bug-report` 技能定义的模板