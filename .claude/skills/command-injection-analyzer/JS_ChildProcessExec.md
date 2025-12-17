# JS_ChildProcessExec - child_process.exec() 命令注入审计

## Details

**漏洞模式：** 通过 `child_process.exec()` 将用户输入拼接到 shell 命令字符串中执行

**典型代码示例：**
```javascript
const exec = require('child_process').exec;
exec(`ls -la ${userInput}`);  // 危险
exec('ping -c 4 ' + req.query.host);  // 危险
exec(`convert ${filename} output.png`);  // 危险
```

**快速定位核心操作：**
- 搜索关键词：`exec(`、`child_process.exec`、`require('child_process')`
- 关注字符串模板/拼接：反引号、`+` 运算符
- 追踪变量来源：req.body/query/params、函数参数、外部输入

**快速定位保护机制：**
- 白名单校验：`allowedCommands.includes()` 或正则 `/^[a-zA-Z0-9]+$/`
- 使用 `execFile()` 替代 `exec()`（参数化）
- 使用 `spawn()` 且不传 `shell: true` 选项
- `shell-quote` 或 `shell-escape` 库转义

**审计等级：L3（逐行读）**  
需逐行追踪用户输入流向，检查是否经过有效过滤

---

## Classify

**确认漏洞（True Positive）：**
- 用户可控输入直接拼接到命令字符串
- 无任何输入校验或仅做弱校验（如 `length` 检查）
- 使用 `eval()`、动态构造命令字符串

**误报（False Positive）：**
- 输入来自严格白名单（如硬编码数组索引选择）
- 使用 `execFile()` 并正确传参数数组
- 命令固定，仅文件路径可变且经过 `path.resolve()` + 目录限制

**代码异味（Code Smell）：**
- 使用 `exec()` 但仅执行静态命令（无变量）
- 输入经过部分校验但不够严格（如仅过滤 `;` 但未过滤 `|`、`&`）
- 注释表明"待加固"但未实现

---

## Low Risk

**低风险场景：**
- 执行环境为低权限容器/沙箱，限制可执行命令范围
- 输入经枚举值映射（如 `const cmds = {a: 'ls', b: 'pwd'}; exec(cmds[input])`）
- 仅内部管理员可触发，且有审计日志记录
- 使用 `timeout` + 资源限制，仅允许查询类命令（如 `ps`、`df`）且输出过滤敏感信息

**注意：** 即使低风险也应标注，建议重构为参数化调用