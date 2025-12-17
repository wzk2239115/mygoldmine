# TypeScript Shell 字符串拼接命令注入

**漏洞成因**：通过模板字符串、字符串拼接等方式动态构造 shell 命令，常见于 Node.js 后端服务、自动化任务、CI/CD 集成、日志分析、文件处理、系统监控等业务场景。

---

## Details

**审计等级：L3（逐行读）/ L4（跨模块追踪）**

**危险模式特征：**
```typescript
// 危险模式 1：模板字符串拼接
const file = req.query.filename;
exec(`cat /var/log/${file}`);

// 危险模式 2：字符串拼接
const cmd = "ls -la " + userPath;
child_process.execSync(cmd);

// 危险模式 3：字符串数组拼接后执行
const args = ['-c', `ping ${host}`];
spawn('sh', args);
```

**快速定位核心操作：**
1. **关键函数搜索**：
   - `child_process.exec(` / `child_process.execSync(`
   - `child_process.spawn(` / `child_process.spawnSync(` 配合 shell 参数
   - `execFile(` 配合 shell: true
   - `shelljs.exec(` / `shelljs.ShellString()`
2. **拼接特征识别**：
   - 模板字符串：`` `command ${variable}` ``
   - 字符串拼接：`"command " + variable`、`'command'.concat(input)`
   - 数组join：`[cmd, arg].join(' ')`
3. **数据流追踪**：
   - HTTP 输入源：`req.params`、`req.query`、`req.body`、`req.headers`
   - 外部数据：数据库查询结果、文件读取内容、环境变量、API 响应
   - 跨函数传递：`function build_command(input: string)` → `exec(cmd)`

**快速定位保护机制：**
- **参数数组化**：`spawn('ls', ['-la', userPath], { shell: false })`（最佳实践）
- **转义函数**：
  - `shell-quote` 库：`quote([cmd, arg])`
  - `escape-string-regexp`：`escapeStringRegexp(input)`
  - 自定义转义：`input.replace(/[;&|`$()]/g, '\\$&')`
- **白名单校验**：
  - 枚举匹配：`if (!['opt1', 'opt2'].includes(input)) return;`
  - 正则限制：`/^[a-zA-Z0-9_.-]+$/.test(input)`
  - 类型守卫：`if (typeof input !== 'string' || input.length > 50) throw;`
- **禁用 shell**：确认 `{ shell: false }` 或不传递 shell 选项

---

## Classify

**🔴 漏洞（Vulnerability）：**
- 用户输入直接或间接拼接进命令字符串
- 无任何过滤或仅黑名单过滤（易被 `$()` `` `...` `` `\n` `||` 绕过）
- 使用 `exec()` / `execSync()` 且命令包含变量
- `spawn()` 传递 `{ shell: true }` 且参数含用户输入
- 命令执行结果返回客户端或影响业务逻辑

**⚪ 误报（False Positive）：**
- 命令字符串完全硬编码：`` exec(`date +%s`) ``
- 输入来自常量/配置文件：`const CMD = process.env.FIXED_COMMAND`
- 使用 `spawn([cmd, arg1, arg2], { shell: false })` 参数数组形式（无 shell 解析）

**🟡 代码异味（Code Smell）：**
- 输入来自环境变量/配置文件但缺少校验
- 有白名单但范围过宽（如允许 `-` `.` `*` 等可利用字符）
- 部分过滤不完整（仅替换 `;` `|`，遗漏 `$()` `` `cmd` ``、换行符）
- 间接拼接：`userInput` → `buildCommand()` → `processTask()` → `exec()`（需 L4 追踪）
- 使用 `{ shell: true }` 但未做必要性评估

---

## Low Risk

**以下情况可评为低风险：**
- **严格鉴权**：仅管理员功能且有 RBAC/ABAC 权限控制 + 操作审计日志
- **完善防护**：
  - 使用 `shell-quote.quote()` 对所有外部输入转义
  - 白名单极严格：仅允许 2-3 个固定枚举值
  - 已改用 `spawn(cmd, [args], { shell: false })` 参数数组化
- **环境隔离**：
  - Docker 容器运行（`--read-only` + `--cap-drop=ALL`）
  - 非 root 用户 + 最小权限原则
  - 无敏感文件访问权限、无网络出站权限
- **输入约束**：
  - 长度限制 ≤ 16 字符
  - 正则严格限制为 `^[a-z0-9]{1,10}$`
  - 输入仅用于非关键部分（如日志标签、文件后缀）
- **业务价值低**：开发/测试环境、内网工具、已下线功能、POC 代码

**⚠️ 注意**：低风险需结合实际部署环境、Node.js 版本、系统权限、攻击面综合研判，建议优先重构为参数数组化调用。