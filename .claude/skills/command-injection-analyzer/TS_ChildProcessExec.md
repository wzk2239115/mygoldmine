# TypeScript child_process.exec() 命令注入

**漏洞成因**：通过 `child_process` 模块的 `exec()` 方法执行包含用户输入的 shell 命令字符串，常见于 Node.js 后端服务、自动化任务、CI/CD 集成、DevOps 工具、日志分析、文件处理等业务场景。

---

## Details

**代码示例**：
```typescript
import { exec } from 'child_process';

// 危险：模板字符串拼接用户输入
const userFile = req.query.file as string;
exec(`cat /logs/${userFile}`, (error, stdout) => {
  res.send(stdout);
});

// 危险：字符串拼接
const command = 'git log --author=' + req.body.author;
exec(command, callback);

// 危险：模板字面量
exec(`ping -c 4 ${req.params.host}`, (err, result) => {
  console.log(result);
});

// 危险：动态命令构造
const cmd = `convert ${uploadedFile} output.png`;
exec(cmd);
```

**快速定位核心操作**：
- 关键函数：`exec()`、`execSync()`（来自 `child_process` 模块）
- 导入语句：`import { exec } from 'child_process'` 或 `require('child_process').exec`
- 查看参数是否包含字符串拼接（`+`、模板字符串 `` `${var}` ``、`.concat()`）
- 重点关注 shell 特殊字符：`;`、`|`、`&`、`&&`、`||`、`$()`、`` `...` ``、`\n`、`>`、`<`
- 追踪命令字符串数据流：`req.query`、`req.body`、`req.params`、`req.headers`、`req.cookies`、外部 API 响应、数据库查询结果

**快速定位保护机制**：
- 是否改用 `execFile()` 或 `spawn()`：`execFile('ls', ['-la', userDir])` 或 `spawn('ping', ['-c', '4', host])`（不经过 shell 解析）
- 是否存在白名单校验：正则匹配 `/^[a-zA-Z0-9_.-]+$/`、枚举值、Map/Object 映射、switch-case
- 是否使用 `shell-quote` 或 `shell-escape` 库转义：`shellEscape([cmd, arg])`
- 是否限制可执行命令范围：路径白名单、命令白名单、参数类型校验（Zod、Joi、class-validator）
- 检查 TypeScript 类型注解是否提供额外约束（联合类型、字面量类型）

**审计等级**：**L3-L4**  
- **L3**：逐行读取 `exec()` 调用上下文，确认参数来源、拼接方式和数据类型
- **L4**：跨模块追踪用户输入到 `exec()` 调用的完整数据流，检查所有中间件、校验器、数据转换函数

---

## Classify

**确认为漏洞**：
- 用户输入（HTTP 请求、WebSocket、文件上传名称、环境变量）直接或间接参与命令字符串拼接
- 未对 shell 特殊字符进行转义或过滤
- 过滤不完整（仅黑名单部分字符，可通过 `$IFS`、换行符、编码等绕过）
- 白名单校验存在逻辑缺陷（路径遍历 `../`、空字节 `%00`、Unicode 规范化绕过）
- 使用 `eval()` 或 `Function()` 构造命令字符串

**误报**：
- 命令字符串完全硬编码，无任何动态部分：`exec('ls -la /tmp/logs')`
- 用户输入仅用于选择预定义命令（通过 Map/Object 映射，键值严格枚举校验）
- 存在严格的正则白名单且命令参数被正确转义：`/^[a-z0-9]{1,10}$/` 且使用 `shell-escape`
- 已改用 `execFile()` 或 `spawn()` 且参数以数组形式传递，未设置 `shell: true`

**代码异味**：
- 存在校验但不够严格（黑名单过滤、简单 `.replace(';', '')` 或 `.replace(/[|&]/g, '')`）
- 使用 `exec()` 但业务逻辑可用 Node.js 内置模块替代（如 `fs`、`path`、`http`、`child_process.spawn`）
- 输入来自数据库/Redis 但缺少字段约束说明或数据来源审计
- 权限控制依赖前端校验或弱认证机制（JWT 未验证、session 可伪造）
- 注释标注 "TODO: use execFile" 或 "FIXME: sanitize input" 但长期未修复
- 使用 `// @ts-ignore` 或 `any` 类型绕过类型检查

---

## Low Risk

以下情况可评为低风险，但仍建议修复：
- **受限执行环境**：Docker 容器以非 root 运行、Kubernetes SecurityContext 限制、VM2 沙箱、AWS Lambda 只读文件系统
- **内网隔离接口**：仅限内网/管理员访问，有二次认证（OAuth2、SAML、IP 白名单、VPN）
- **业务价值低**：开发/测试环境、内部工具、已下线功能、临时脚本、日志查询 API
- **影响范围小**：仅能执行只读命令（如 `ls`、`cat`、`grep`、`head`），无法写入文件或建立外部网络连接
- **存在部分防护**：
  - 输入长度限制（如 `substring(0, 20)` 或 `maxLength: 15`）
  - 命令执行超时设置：`exec(cmd, { timeout: 5000 })`
  - 审计日志记录（Winston、Pino）+ 异常监控告警（Sentry、Datadog）
  - Rate Limiting / 限流机制（express-rate-limit）
- **已有监控**：命令执行有日志审计、异常命令触发告警、定期安全扫描

**注意**：低风险≠可忽略，需结合实际部署环境、Node.js 版本、依赖库漏洞、数据敏感度和攻击面综合判断。优先建议使用 `child_process.execFile()` 或 `spawn()` 的参数化调用。