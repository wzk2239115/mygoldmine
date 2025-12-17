# JavaScript (Node.js) - execSync 命令注入

**场景：** DevOps 脚本、文件批量处理、服务器端工具调用、自动化运维任务  
**成因：** 将用户输入拼接到 shell 命令字符串中，通过 `child_process.execSync()` 同步执行

---

## Details

**典型代码示例：**
```javascript
const { execSync } = require('child_process');

// 危险模式：直接拼接用户输入
const result = execSync(`ls -la ${userInput}`);

// 或使用模板字符串
const output = execSync(`convert ${fileName} output.png`);

// 或使用字符串连接
execSync('ping -c 4 ' + req.query.host);
```

**审计等级：L2-L3（跳读-逐行读）**

**快速定位核心操作：**
- 搜索关键词：`execSync(`, `exec(`, `spawnSync(`, `child_process`
- 关注字符串拼接模式：反引号模板 `` `cmd ${var}` ``、`+` 连接、`util.format()`
- 追踪变量来源：`req.query`、`req.body`、`req.params`、`process.argv`、文件读取
- 注意间接拼接：参数先赋值给中间变量再传入 execSync

**快速定位保护机制：**
- 检查是否使用参数数组形式：`spawn(cmd, [arg1, arg2])`（安全模式）
- 检查白名单验证：`/^[a-zA-Z0-9_-]+$/.test()`、`switch/case` 枚举
- 检查转义函数：`shellEscape()`、`shellescape.quote()`、自定义转义
- 检查 `shell: false` 选项（虽然 execSync 默认启用 shell）
- 检查黑名单过滤（但易绕过）：`replace(/[;|&]/g, '')`

---

## Classify

**✓ 确认漏洞：**
- 用户可控输入直接拼接到 shell 命令字符串中
- 使用 `execSync()`、`exec()` 等默认调用 shell 的 API
- 输入来源不可信（HTTP 请求、WebSocket、外部文件、命令行参数）
- 无有效过滤或仅使用不完整的黑名单

**△ 代码异味：**
- 使用黑名单过滤特殊字符，但未覆盖所有元字符（`;|&$><\`\n()`）
- 仅验证输入格式（如检查是否为数字），但未限制字符集
- 部分过滤：`replace(/\s+/g, '')` 仅过滤空格
- 间接拼接：输入先经过多次变量传递再进入 execSync

**✗ 误报：**
- 使用安全的参数数组模式：`spawn('ls', ['-la', userInput], {shell: false})`
- 输入经过严格白名单验证（如 `^[a-zA-Z0-9._-]{1,32}$`）
- 输入为硬编码常量或来自服务端配置文件（非用户可编辑）
- 使用专用库处理：如 `shell-escape`、`shell-quote` 正确转义

---

## Low risk

**以下情况评为低风险：**
- 命令执行在受限环境中（Docker 容器、VM、AWS Lambda）且配置了资源限制
- 进程以低权限用户运行（非 root），且已禁用 `setuid` 程序
- 输入长度严格限制（如 `< 16` 字符）且已过滤常见元字符
- 仅影响当前用户临时文件，无数据库/敏感文件访问权限
- 业务场景为内部管理后台，仅管理员可访问且有完整操作日志
- 输入来源虽不可信，但经过 `path.basename()` + `path.resolve()` 限制为文件名
- 已启用 `timeout` 选项防止命令执行时间过长
- 执行结果不返回给用户，且系统有异常监控告警
