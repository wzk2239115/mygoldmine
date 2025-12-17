# Node.js child_process.exec() 命令执行注入

## 漏洞成因

Node.js 的 `child_process.exec()` 函数在系统 shell 中执行命令字符串。当用户可控的输入被用于构造命令时，攻击者可注入恶意 shell 命令在应用的权限下执行任意系统命令，造成完整的命令执行。不同于 `child_process.execFile()` 或 `spawn()` 基于参数数组，exec 通过拼接字符串，容易受到 shell 元字符注入。此漏洞本质上是代码注入和命令注入的交集。

---

## Details

### 代码示例

```javascript
const { exec, execFile, spawn } = require('child_process');
const express = require('express');
const app = express();

// 危险模式1：直接在 exec 中使用用户输入
app.post('/execute', (req, res) => {
    const command = req.body.cmd;
    // 危险：command 完全可控，可注入 shell 元字符
    exec(command, (error, stdout, stderr) => {
        if (error) {
            res.status(500).send(error.message);
            return;
        }
        res.json({ output: stdout });
    });
});

// 危险模式2：使用用户输入拼接命令
app.get('/ping', (req, res) => {
    const host = req.query.host;
    // 危险：使用字符串拼接构造命令
    const command = `ping -c 4 ${host}`;
    exec(command, (error, stdout, stderr) => {
        res.json({ output: stdout });
    });
});

// 危险模式3：使用模板字符串拼接
app.post('/convert', (req, res) => {
    const inputFile = req.body.file;
    const outputFormat = req.body.format;
    // 危险：模板字符串中的 ${} 可被注入
    const command = `ffmpeg -i "${inputFile}" output.${outputFormat}`;
    exec(command, (error, stdout, stderr) => {
        res.json({ success: !error });
    });
});

// 危险模式4：从数据库或环境变量获取命令
app.get('/exec/:task_id', (req, res) => {
    const taskId = req.params.task_id;
    // 从数据库获取命令模板
    db.query('SELECT command FROM tasks WHERE id = ?', [taskId], (err, rows) => {
        if (rows.length > 0) {
            // 危险：数据库中的命令也可被污染
            const command = rows[0].command;
            exec(command, (error, stdout, stderr) => {
                res.json({ output: stdout });
            });
        }
    });
});

// 危险模式5：shell 参数传递不当
app.post('/search', (req, res) => {
    const query = req.body.q;
    // 危险：grep 的搜索参数未被引用
    const command = `grep "${query}" /var/log/app.log | head -10`;
    exec(command, (error, stdout, stderr) => {
        res.json({ results: stdout });
    });
});

// 危险模式6：使用 shell 重定向和管道
app.post('/process-data', (req, res) => {
    const inputData = req.body.data;
    // 危险：重定向和管道可被用于信息泄漏或代码执行
    const command = `echo "${inputData}" | tr a-z A-Z > /tmp/output.txt`;
    exec(command, (error, stdout, stderr) => {
        res.json({ success: !error });
    });
});

// 危险模式7：执行用户指定的脚本
app.post('/run-script', (req, res) => {
    const scriptName = req.body.script;
    const args = req.body.args;
    // 危险：脚本名和参数都可被控制
    const command = `bash ./scripts/${scriptName} ${args}`;
    exec(command, (error, stdout, stderr) => {
        res.json({ output: stdout });
    });
});

// 危险模式8：忽略 exec 返回的错误
app.post('/silent-exec', (req, res) => {
    const cmd = req.body.command;
    // 危险：没有检查命令执行是否成功，也没有限制超时
    exec(cmd);  // 错误处理被忽略
    res.json({ executed: true });
});

// 危险模式9：使用 execSync（同步阻塞）
app.get('/sync-cmd', (req, res) => {
    const command = req.query.cmd;
    try {
        // 危险：同步执行，可导致服务卡顿或被 DoS
        const output = require('child_process').execSync(command);
        res.json({ output: output.toString() });
    } catch (error) {
        res.status(500).send(error.message);
    }
});

// 危险模式10：命令拼接中的双引号逃逸
app.post('/file-op', (req, res) => {
    const fileName = req.body.name;
    // 危险：双引号可被闭合，导致注入
    // 输入: test".txt"; rm -rf / ; echo "
    // 结果: cat "test".txt"; rm -rf / ; echo "
    const command = `cat "${fileName}"`;
    exec(command, (error, stdout, stderr) => {
        res.json({ content: stdout });
    });
});

// 比较：相对安全的做法 (示意，仅供参考)
app.post('/safe-ping', (req, res) => {
    const host = req.query.host;
    // 更安全的方式：使用 execFile 或 spawn，参数分离
    execFile('ping', ['-c', '4', host], (error, stdout, stderr) => {
        if (error) {
            res.status(500).send(error.message);
            return;
        }
        res.json({ output: stdout });
    });
});
```

### 快速定位核心操作 (L1-L3)

**L1 关键词扫描**：
- 搜索 `exec(`（包括 `exec`, `execSync`）
- 搜索字符串拼接或模板字符串用于命令构造：`'...' + variable`、`` `${variable}` ``、`"..." + variable`
- 搜索用户输入来源：`req.query`、`req.params`、`req.body`、`req.headers`、`req.cookies`、`getenv`
- 搜索 shell 元字符：`;`、`|`、`&`、`>`、`<`、`` ` ``、`$(...)`、`$(())`
- 搜索命令模板相关变量：`command`、`cmd`、`script`、`query`
- 搜索文件读取操作：读取脚本、配置等
- 注意：`execFile` 和 `spawn` 相对安全（参数分离）

**L2 跳读**：
- 定位所有 `exec(` 或 `execSync(` 调用，记录行号
- 检查第一个参数（命令字符串）的来源：用户输入、环境变量、数据库、文件
- 检查命令字符串是否通过字符串拼接或模板字符串构造
- 检查是否有命令白名单或黑名单验证
- 检查是否使用了 shell 元字符过滤（但通常不足以防止注入）
- 检查是否设置了超时（`timeout` 选项）
- 检查是否限制了输出大小（`maxBuffer` 选项）
- 检查错误处理：是否检查了返回值、是否捕获了异常

**L3 逐行读**：
- 确认用户输入的确切来源和传输路径
- 检查输入是否进行了验证、清理、沙箱化
- 逐行追踪所有影响 exec 参数的中间变量
- 检查是否使用了 `shlex.quote()` 或等效的 shell 转义函数（Node.js 无内置函数）
- 检查命令构造的完整过程：是否有多处拼接
- 检查执行环境：执行用户、所有权、权限
- 检查是否在循环中执行命令（DoS 风险）
- 检查超时和资源限制的配置

### 快速定位保护机制 (L2-L4)

**L2 跳读**：
- 检查 exec 前是否有条件判断或命令白名单验证
- 搜索白名单关键词：`allowedCommands`、`PERMITTED_OPERATIONS`、`validScripts`
- 搜索黑名单关键词：`rm`, `mv`, `cp`, `dd`, `chmod`, `chown`, `sudo`, `su`
- 检查是否使用了 `execFile` 或 `spawn`（参数分离的方式）
- 检查是否配置了 `timeout` 和 `maxBuffer` 选项
- 检查是否限制了执行用户（如 `uid`、`gid` 选项）
- 检查是否禁用了 shell：`{ shell: false }`

**L3 逐行读**：
- 分析命令白名单实现：精确匹配还是前缀/后缀匹配？
- 分析黑名单实现：是否全面？可否被绕过？
- 检查参数转义：是否使用了 shell 安全的转义函数
- 检查是否验证了文件路径（防止路径遍历）
- 检查超时配置的合理性
- 分析 `shell` 选项的值：`true` 或 `/bin/bash` 都有风险
- 检查执行环境变量：是否清理了危险的环境变量（如 `LD_PRELOAD`、`LD_LIBRARY_PATH`）

**L4 跨模块追踪**：
- 追踪自定义的命令白名单库实现
- 检查是否使用了专门的命令执行安全库（如 `shell-escape`、`shellwords` 等）
- 查找是否有全局的命令执行监控或审计中间件
- 追踪是否使用了沙箱机制（如 firejail、Docker 等）
- 检查是否使用了 SELinux、AppArmor 等强制访问控制
- 查找操作系统级别的命令执行限制（如 seccomp、pledge）
- 检查是否有日志记录所有执行的命令

---

## Classify

### 漏洞判定

- **直接在 exec 中使用用户输入作为命令字符串** → **确认漏洞**
  - 示例：`exec(req.body.cmd)`、`exec(argv[1])`

- **使用用户输入拼接命令字符串** → **确认漏洞**
  - 示例：`exec('ping -c 4 ' + host)`、`` exec(`command ${param}`) ``

- **命令参数未被引用或转义** → **确认漏洞**
  - 示例：`exec(`grep "${query}" file`)` 其中 query 可包含 shell 元字符

- **从不可信源（数据库、环境变量、文件）获取命令，无验证** → **确认漏洞**
  - 即使来自数据库，若数据库可被用户污染，仍需验证

- **使用 exec 而不是 execFile 或 spawn** → **高风险**
  - exec 使用 shell 解析，容易注入

- **使用了 shell 重定向、管道、命令替换等** → **确认漏洞**
  - 示例：`exec(`echo "${data}" | grep pattern > /tmp/file`)`

- **使用黑名单而非白名单进行命令过滤** → **高风险**
  - 黑名单容易被绕过

### 误报判定

- **命令字符串完全来自硬编码常量** → **误报**
  - 示例：`exec('ls -la /var/log')`

- **严格的命令白名单验证**：仅允许特定的预定义命令 → **误报**
  - 示例：`const ALLOWED = ['ls', 'cat']; if (!ALLOWED.includes(cmd)) throw Error(); exec(cmd)`

- **使用 execFile 或 spawn，参数分离** → **误报**
  - 示例：`execFile('ping', ['-c', '4', host])` 参数不经过 shell 解析

- **所有参数均来自安全的来源且已验证** → **误报**
  - 示例：命令仅来自配置文件，参数来自白名单

- **在沙箱或容器中执行，无法访问系统资源** → **误报**
  - 示例：在 Docker 容器中执行，容器无法访问宿主机

### 代码异味

- **使用黑名单过滤 shell 命令** → **需进一步测试**
  - 可被大小写、编码、命令替换等绕过

- **仅检查某些 shell 元字符，不全面** → **潜在风险**
  - 示例：检查了 `;` 但未检查 `|`、`&`、`` ` `` 等

- **使用客户端验证** → **确认可绕过**
  - 后端未验证，可直接请求绕过

- **验证后又进行了字符串处理** → **需追踪完整数据流**
  - 示例：先验证再 URL 解码等

- **无超时限制的 exec 调用** → **DoS 风险**
  - 可能导致服务卡顿

- **在循环中执行 exec** → **DoS 风险**
  - 可能导致资源耗尽

- **使用 execSync** → **高风险**
  - 同步执行可导致服务阻塞

- **命令输出未限制大小** → **DoS 风险**
  - 大量输出可导致内存耗尽

### 审计等级

- **L1**：关键词扫描，快速定位所有 exec/execSync 调用
- **L2**：跳读确认命令来源、拼接方式、防护机制
- **L3**：逐行读取数据流、分析验证逻辑、检查参数转义
- **L4**：跨模块追踪命令白名单、执行环境配置、沙箱隔离

---

## Low risk

### 低风险场景

- **命令字符串完全来自硬编码常量**：所有可能的命令在代码中明确列举，无用户输入
  - 示例：`const CMDS = { list: 'ls -la', tree: 'tree -L 2' }; exec(CMDS[key])`

- **严格的命令白名单验证**：仅允许特定的预定义命令，白名单不可被用户修改
  - 示例：`const ALLOWED = ['ping', 'tracert']; if (!ALLOWED.includes(cmd)) throw new Error(); exec(cmd)`

- **使用 execFile 或 spawn，参数分离**：命令和参数分离，参数不经过 shell 解析
  - 示例：`execFile('ping', ['-c', '4', userInput])`，参数不经过 shell 解析，避免了 shell 元字符注入

- **严格验证所有参数**：参数通过正则表达式或白名单限制为安全值（如 IP 地址、文件名）
  - 示例：`if (!ip.match(/^\d{1,3}(\.\d{1,3}){3}$/)) throw Error(); execFile('ping', ['-c', '4', ip])`

- **参数来源完全受控**：命令和参数仅来自配置文件、环境变量（已验证）、硬编码常量
  - 示例：配置文件仅允许管理员编辑，已验证其完整性

- **功能权限隔离**：此功能仅限管理员或特定角色访问
  - 示例：`if (!user.isAdmin()) { throw new Error('Permission denied'); }`

- **执行环境隔离**：命令在容器、VM、沙箱中执行，无法访问系统资源或敏感数据
  - 示例：在 Docker 容器中执行，容器无 root 权限、无网络访问

- **配置了严格的超时和资源限制**：exec 调用配置了 `timeout` 和 `maxBuffer`
  - 示例：`exec(command, { timeout: 5000, maxBuffer: 1024 * 1024 })`

- **完整的审计日志和监控**：所有命令执行被记录，包含命令内容、用户、时间戳、返回值
  - 示例：记录每次执行的完整上下文，支持实时告警

### 注意事项

即使满足低风险条件，仍应在审计报告中说明：
- `child_process.exec()` 本身属于高风险操作，建议优先使用 `execFile()` 或 `spawn()`（参数分离）
- 应定期审查命令白名单的完整性，确保无遗漏可执行危险操作的路径
- 应建立完整的测试覆盖，确保命令注入、shell 元字符绕过等攻击向量被充分检验
- 应评估业务场景是否真的需要 exec，是否可以使用内置库、模块等替代系统命令
- 即使使用了 execFile 或 spawn，仍需确保参数来自安全的来源或已验证
- 应清理执行环境的危险环境变量（如 `LD_PRELOAD`、`PATH`、`IFS` 等）
- 应限制执行命令的用户权限（使用 `uid`、`gid` 选项，或低权限账户运行）
- 应设置合理的超时（通常为秒级）和输出大小限制，防止 DoS
- 应避免在循环或频繁调用的函数中执行系统命令，考虑缓存或异步处理
- 应定期审计执行的命令日志，检查是否存在异常执行
- 若必须使用 exec，应在沙箱或容器中运行，使用 seccomp 等限制系统调用
