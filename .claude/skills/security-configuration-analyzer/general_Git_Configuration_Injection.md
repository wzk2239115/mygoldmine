# 不安全的 Git 配置参数验证（Git Configuration Parameter Injection）

## Details

### 漏洞背景

当应用程序接受用户输入并将其直接传递给 Git 配置操作（如 `git config`、`git addConfig`）时，未经验证的参数可能导致恶意配置注入。攻击者可通过设置危险的 Git 配置项（如 `core.hooksPath`）指向包含恶意代码的目录，在执行后续 Git 操作（如 commit、push）时触发远程代码执行（RCE）。

**相关 CVE**：CVE-2025-65964（n8n Git Node 不安全配置）

### 代码示例

**场景1：直接接受用户输入作为 Git 配置**
```typescript
// TypeScript / n8n 示例
const key = this.getNodeParameter('key', itemIndex, '') as string;
const value = this.getNodeParameter('value', itemIndex, '') as string;

// 危险：未验证用户输入，直接传入 git config
await git.addConfig(key, value, append);
```

**场景2：通过 API 端点接收配置参数**
```python
# Python/Flask 示例
@app.route('/git/config', methods=['POST'])
def set_git_config():
    key = request.json.get('key')
    value = request.json.get('value')

    # 危险：直接执行 git config，无验证
    os.system(f'git config {key} {value}')
    return {'status': 'ok'}
```

**场景3：通过配置文件加载 Git 设置**
```json
{
  "git": {
    "config": {
      "user.name": "builder",
      "user.email": "builder@example.com",
      "core.hooksPath": "/tmp/evil-hooks"  // 恶意输入
    }
  }
}
```

**场景4：条件分支中的不安全配置**
```go
// Go 示例
if isDevelopment {
    // 危险：开发环境配置被复制到生产
    git.Config("core.hooksPath", devHooksPath)
}
```

**场景5：Git Hook 攻击链**
```bash
# 攻击者通过设置 core.hooksPath
git config core.hooksPath /attacker-controlled/hooks

# 后续的 git commit 会执行 hooks 目录中的脚本
git commit -m "trigger hook"  # 执行恶意代码
```

**场景6：环境变量控制的配置**
```javascript
// Node.js 示例
const gitConfig = {
    'core.hooksPath': process.env.GIT_HOOKS_PATH,  // 可被攻击者控制
    'user.signingKey': process.env.GPG_KEY_ID
};

for (const [key, value] of Object.entries(gitConfig)) {
    execSync(`git config ${key} ${value}`);  // 危险：命令注入
}
```

### 危险的 Git 配置项

| 配置项 | 危险性 | 说明 |
|--------|--------|------|
| `core.hooksPath` | **极高** | 指定 Git hooks 目录，hooks 会在 commit/push 等操作时执行 |
| `core.editor` | **高** | 指定编辑器路径，可执行任意命令 |
| `core.pager` | **高** | 指定分页器，可用于代码执行 |
| `receive.fsckObjects` | **中** | 控制对象检查，false 时可跳过安全检查 |
| `core.safecrlf` | **低** | CRLF 转换设置，可能导致文件内容变化 |
| `http.sslVerify` | **高** | 控制 SSL 证书验证，false 时存在 MITM 风险 |
| `http.proxy` | **中** | HTTP 代理设置，可用于流量劫持 |

### 快速定位核心操作的技巧

**（L1：关键词扫描）**
- 核心操作：`git config`、`git.config()`、`addConfig`、`setConfig`
- 参数来源：用户输入、API 参数、环境变量、配置文件
- 危险项：`hooksPath`、`core.editor`、`core.pager`、`http.sslVerify`
- 执行方式：`subprocess`、`execSync`、`system()`、`run()` 等

**（L2：跳读）**
- 配置加载函数：`loadGitConfig()`、`parseConfig()`、`readConfigFile()`
- 参数解析：`getNodeParameter()`、`request.args`、`request.json`、`os.environ`
- Git 操作：`git.addConfig()`、`git.setConfig()`、`subprocess.run(['git', 'config'])`
- 配置注册中心：Consul、etcd、配置管理服务中的 Git 配置

**（L3：逐行读）**
- 输入验证逻辑：是否存在 `if key in ALLOWED_KEYS`、正则验证
- 转义处理：是否调用 `shlex.quote()`、参数数组化避免 shell 注入
- 配置项检查：是否有黑名单或白名单验证
- 错误处理：配置设置失败时是否有安全的降级策略

**（L4：跨模块追踪）**
- 配置依赖链：配置来自何处，是否经过多次转发
- 权限模型：谁可以修改 Git 配置，是否有访问控制
- 日志审计：是否记录所有配置修改操作
- 部署流程：CI/CD 中 Git 配置的来源和应用时机

**（L0：快速跳过）**
- 测试文件：单元测试中的 Mock Git 配置
- 示例代码：文档、教程中的演示代码
- 注释代码：`//` 或 `/* */` 注释中的配置代码

### 快速定位保护机制的技巧

**（L1：关键词扫描）**
- 白名单检查：`ALLOWED_KEYS`、`VALID_CONFIG_KEYS`、`whitelist`
- 黑名单检查：`FORBIDDEN_KEYS`、`DANGEROUS_KEYS`、`blocked`
- 类型验证：`isinstance(value, str)`、`type checking`
- 正则验证：`re.match()`、`pattern.test()`

**（L2：跳读）**
- 验证函数：`validateGitKey()`、`isAllowedConfigKey()`、`sanitizeConfigValue()`
- 转义函数：`shlex.quote()`、shell escape utilities
- 参数化执行：`subprocess.run(['git', 'config', key, value])` vs `os.system(f'git config {key} {value}')`
- 配置预定义：应用层预定义所有允许的配置项，不接受用户自定义

**（L3：逐行读）**
- 验证函数体：是否真正执行了黑白名单检查
- 正则表达式：是否能覆盖所有危险配置项变体
- 错误处理：验证失败时是否拒绝操作并日志记录
- 提前退出：是否在检查失败时立即中止，避免条件竞争

**（L4：跨模块追踪）**
- 配置管理模块：集中式配置验证机制是否完整
- 访问控制：配置修改权限的细粒度控制
- 变更审计：配置变更的完整日志和审批流程
- 运行时检测：是否存在配置变更告警机制

## Classify

### 确认为漏洞的判定标准

- **用户输入直接用于 Git 配置**，未经任何验证（黑名单/白名单）
- 允许设置 `core.hooksPath`、`core.editor`、`core.pager` 等危险项
- 使用 `os.system()`、`subprocess.Popen()` 等方式执行 `git config` 命令，参数未转义
- 配置来自不可信来源（用户输入、HTTP 请求、配置文件）且无访问控制
- Git 操作（commit、push）后续会被执行，hooks 可被触发
- 应用有 Git 操作权限，攻击者可通过恶意配置注入执行任意代码

### 误报的常见场景

- 应用仅读取 Git 配置，不修改配置项（如 `git config --get`）
- 配置来自高度受信的源（如编译期常量、签名配置文件）且不涉及用户交互
- Git 操作在沙箱环境中执行（如容器、VM），且宿主机隔离良好
- 应用不执行任何 Git hooks（设置了 `core.hooksPath=`），且禁用了内置 hooks
- 配置修改仅在本地测试环境，永不部署到生产环境
- 存在严格的访问控制，只允许特定管理员修改 Git 配置

### 代码异味的判定

- 配置参数通过字符串拼接进行 Git 命令，未使用参数数组
- 存在 TODO/FIXME 注释提及"需要验证 Git 配置参数"
- 配置来自环境变量或配置文件，但无默认安全值或验证逻辑
- 不同环境（开发/测试/生产）的 Git 配置管理逻辑重复且不一致
- 日志中记录了所有 Git 配置修改，但应用层无对应的访问控制
- 代码注释表明"临时跳过验证"，已存在超过合理期限

### 研判流程

1. **确认输入来源**：Git 配置参数来自哪里（用户输入、API、文件、环境变量）
2. **评估可信度**：该参数来源是否可信，是否受访问控制保护
3. **追溯验证机制**：是否存在黑白名单检查、类型验证、正则验证
4. **检查执行方式**：是使用参数数组化还是字符串拼接，是否存在 shell 注入风险
5. **验证 Git 操作**：应用是否会执行后续 Git 操作（commit、push），hooks 是否可被触发
6. **权限评估**：应用以何种权限运行，攻击者可控制范围是什么

## Low Risk

### 低风险场景评级标准

**场景1：严格的白名单控制**
- 应用预定义了所有允许的 Git 配置项（如 `user.name`、`user.email` 仅包含字母数字）
- 配置键（key）来自代码常量，不接受用户输入
- 配置值（value）通过正则表达式验证，长度限制
- 使用参数数组执行命令：`['git', 'config', key, value]`

**场景2：只读 Git 配置操作**
- 应用仅读取 Git 配置（`git config --get`），不修改
- 未执行任何可能触发 hooks 的 Git 操作
- 配置读取仅用于展示或分析，不影响业务逻辑

**场景3：完全隔离的沙箱环境**
- Git 操作在容器、虚拟机或 chroot 环境中执行
- 宿主机与容器间无文件系统共享（只读挂载）
- 容器运行在低权限用户（如 nobody），无法访问系统命令
- 容器销毁前清理所有 Git 配置和 hooks

**场景4：预编译配置，运行时不可修改**
- Git 配置在应用编译/构建时确定，运行时只读
- 配置通过代码审查和安全测试
- 应用无任何 API 或接口允许运行时修改 Git 配置
- 配置变更需重新编译和部署

**场景5：默认安全，用户主动选择开放**
- 应用默认禁用所有 Git 配置修改功能
- 管理员或开发者需通过明确的管理界面启用功能
- 启用时显示安全警告和风险说明
- 所有配置修改需要多人审批或 2FA 认证

**场景6：完整的审计和检测机制**
- 所有 Git 配置修改都被记录到不可篡改的审计日志
- 存在实时告警：检测到危险配置项时立即告警
- 应用启动时验证 Git 配置，发现异常立即停止
- 定期审计报告，对异常配置进行人工审查

**评级升级条件（需提升风险等级）**
- 即使配置来自可信源，但应用以 root 权限运行
- 白名单配置项可被多处代码修改，难以统一管理
- 虽有验证，但验证逻辑可被绕过（如正则表达式不完整）
- Git 操作在公网可访问的服务中执行
- 缺少监控告警，无法检测异常 Git 配置行为
- 代码注释表明"临时跳过验证"，已存在超过 3 个月

## Real-world Attack Scenarios

### 攻击场景1：n8n 工作流 RCE（CVE-2025-65964）

```
1. 攻击者通过 n8n UI 创建 Git Node
2. 在 addConfig 操作中设置：
   - key: core.hooksPath
   - value: /tmp/attacker-hooks
3. 攻击者在服务器上创建 /tmp/attacker-hooks/post-commit
4. 后续 Git 操作触发该 hook，执行恶意代码
```

**防护方案**：
- 配置项白名单：仅允许 `user.name` 和 `user.email`
- 参数验证：key 匹配 `^[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+$`，value 长度 < 256
- 参数数组化：避免 shell 注入

### 攻击场景2：CI/CD 流程中的 Git Hook 注入

```
1. 攻击者在构建日志中注入恶意配置
2. CI/CD 系统读取日志并应用 Git 配置
3. 后续构建步骤中执行 git commit/push
4. 恶意 hook 执行，破坏构建产物或泄露密钥
```

**防护方案**：
- 配置来源隔离：构建脚本和配置分离
- 权限最小化：CI 系统以低权限用户运行
- 配置变更审计：所有 Git 配置修改需记录和审查

### 攻击场景3：供应链攻击

```
1. 攻击者贿赂或社工某个项目维护者
2. 在项目代码中注入恶意 Git 配置加载逻辑
3. 下游项目集成此依赖，受到 RCE 影响
```

**防护方案**：
- 依赖检查：审计所有第三方库的 Git 操作
- 代码签名：对关键配置文件进行数字签名
- 供应链防御：使用 SBOM、依赖锁定等机制

