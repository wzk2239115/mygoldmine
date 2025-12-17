# JS_ShellSpawn - child_process.spawn() Shell模式命令注入审计

## Details

**漏洞模式：** 通过 `child_process.spawn()` 设置 `shell: true` 选项，将用户输入作为命令参数执行

**典型代码示例：**
```javascript
const { spawn } = require('child_process');
spawn('sh', ['-c', `ls ${userInput}`], { shell: true });  // 危险
spawn(userCommand, args, { shell: true });  // 危险
spawn('bash', ['-c', req.body.cmd]);  // 危险
```

**快速定位核心操作：**
- 搜索关键词：`spawn(`、`child_process.spawn`、`{ shell: true }`
- 关注第三参数：检查是否存在 `shell: true` 或 `shell: '/bin/sh'`
- 追踪第一/二参数来源：直接执行用户可控命令或通过 `-c` 传递命令字符串
- 特别关注 `sh -c`、`bash -c`、`cmd /c` 模式

**快速定位保护机制：**
- 未设置 `shell` 选项（默认 `false`，参数化调用）
- 白名单校验命令：`allowedCmds.includes(cmd)` 或正则 `/^[a-z]+$/`
- 参数数组化且无 shell：`spawn('ls', ['-la', dir])` 无 `shell: true`
- 使用 `shellEscape()` 或 `shlex.quote()` 转义

**审计等级：L3（逐行读）**  
需逐行检查 `shell` 选项值，追踪命令字符串构造过程

---

## Classify

**确认漏洞（True Positive）：**
- 设置 `shell: true` 且用户可控输入拼接到命令字符串或参数
- 第一参数为用户可控变量（直接执行任意命令）
- 使用 `sh -c` 模式且 `-c` 后的命令包含用户输入

**误报（False Positive）：**
- 未设置 `shell` 选项且参数为数组（安全的参数化调用）
- 命令来自严格白名单枚举（如 `cmds[validated_key]`）
- 仅路径可变且经过 `path.normalize()` + `startsWith()` 目录限制

**代码异味（Code Smell）：**
- 设置 `shell: true` 但执行纯静态命令（无必要风险）
- 输入校验不完整（如仅过滤 `;` 未过滤 `$()` `\``）
- 注释标注 TODO 需改为 execFile

---

## Low Risk

**低风险场景：**
- 执行环境为受限容器，通过 seccomp/AppArmor 禁用危险命令
- 命令通过枚举映射（如 `{start: 'npm start', test: 'npm test'}[action]`）
- 仅管理员权限可触发，有完整审计日志和速率限制
- 使用 `timeout` + `maxBuffer` 限制，且输出重定向到安全位置

**注意：** 即使低风险也应标注，优先重构为无 `shell` 选项的 `spawn()` 调用