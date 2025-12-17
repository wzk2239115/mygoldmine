# JavaScript/TypeScript 反序列化漏洞（Eval 类）

**漏洞概述**  
常出现在服务端（如 Node.js）接收客户端序列化对象、插件加载或配置反序列化场景中，包括但不限于使用 `eval()`、`Function()` 构造函数、`vm.runInContext` 配合 `JSON.parse` 误用、`serialize-javascript` 库缺陷、或自定义反序列化逻辑等方式，实现远程代码执行。

---

## Details

### 典型代码示例

**场景1：直接 eval 反序列化**
```javascript
// 危险：直接 eval 用户输入
app.post('/api/deserialize', (req, res) => {
    const data = req.body.serialized;
    const obj = eval('(' + data + ')');  // 触发点
    processData(obj);
});

// 危险：通过 Function 构造函数
function deserialize(str) {
    return (new Function('return ' + str))();  // 等同于 eval
}
```

**场景2：vm 模块误用**
```javascript
// 危险：vm.runInContext 沙箱逃逸
const vm = require('vm');
const sandbox = { result: null };
vm.runInContext(userInput, vm.createContext(sandbox));  // 可通过 this.constructor.constructor 逃逸

// 危险：vm.runInNewContext 配合 JSON
function loadConfig(configStr) {
    const config = vm.runInNewContext('(' + configStr + ')');  // 仍可执行代码
    return config;
}
```

**场景3：node-serialize 库反序列化**
```javascript
// 危险：node-serialize 库可执行 IIFE
const serialize = require('node-serialize');
app.post('/session', (req, res) => {
    const session = serialize.unserialize(req.cookies.session);  // 可注入 _$$ND_FUNC$$_
    res.json(session);
});
```

**场景4：serialize-javascript 版本缺陷**
```javascript
// 危险：serialize-javascript < 3.1.0
const serialize = require('serialize-javascript');
const obj = serialize(userInput, { unsafe: true });  // unsafe 模式可注入代码
eval('(' + obj + ')');
```

**场景5：JSON.parse 配合 reviver**
```javascript
// 危险：reviver 函数动态执行
function parseWithReviver(jsonStr) {
    return JSON.parse(jsonStr, (key, value) => {
        if (typeof value === 'string' && value.startsWith('__func__')) {
            return eval(value.slice(8));  // 执行序列化的函数
        }
        return value;
    });
}
```

**场景6：配置文件动态加载**
```javascript
// 危险：require() 动态加载用户路径
function loadPluginConfig(pluginName) {
    const configPath = './plugins/' + pluginName + '/config.js';
    return require(configPath);  // 可加载恶意模块
}

// 危险：import() 动态导入
async function loadModule(modulePath) {
    const mod = await import(userInput);  // 可导入任意模块
    return mod.default;
}
```

**场景7：YAML 反序列化**
```javascript
// 危险：js-yaml 默认加载自定义类型
const yaml = require('js-yaml');
const config = yaml.load(fs.readFileSync(userFile));  // 可注入 !!js/function

// 安全替代：使用 safeLoad
const config = yaml.safeLoad(fs.readFileSync(file));
```

**场景8：WebSocket 消息反序列化**
```javascript
// 危险：WebSocket 接收对象直接反序列化
ws.on('message', (message) => {
    const cmd = JSON.parse(message);
    if (cmd.type === 'eval') {
        eval(cmd.code);  // 直接执行客户端代码
    }
});
```

**场景9：缓存反序列化**
```javascript
// 危险：Redis 缓存反序列化
async function getFromCache(key) {
    const cached = await redis.get(key);
    return eval('(' + cached + ')');  // 缓存数据可能被污染
}
```

**场景10：插件系统加载**
```javascript
// 危险：插件配置通过 eval 解析
function loadPlugin(pluginConfig) {
    const config = eval('(' + pluginConfig + ')');
    if (config.onLoad) {
        config.onLoad();  // 执行插件初始化代码
    }
}
```

---

### 快速定位核心操作的技巧

**L0: 快速跳过**
- 仅使用 `JSON.parse()` 且无 reviver 函数
- 无 `eval`、`Function`、`vm` 模块、动态 `require/import`
- 使用成熟框架的内置序列化（Express session 配合安全存储）

**L1: 关键词扫描**
- `eval(`、`new Function(`、`Function.constructor`
- `vm.runInContext`、`vm.runInNewContext`、`vm.runInThisContext`
- `serialize.unserialize`、`node-serialize`
- `serialize-javascript` 配合 `unsafe: true`
- `JSON.parse` 配合 reviver 参数
- `yaml.load(`（非 `safeLoad`）
- `require(` + 可控路径、`import(` + 可控路径
- `child_process.exec` + 字符串拼接

**L2: 跳读定位**
- 检查函数参数是否来自外部输入（`req.body`、`req.query`、`req.params`、WebSocket message）
- 查看 `JSON.parse` 的第二个参数（reviver）实现
- 确认 `vm` 模块沙箱是否正确隔离（检查 `createContext` 参数）
- 检查序列化库版本（`package.json` 或 `yarn.lock`）

**L3: 逐行追踪**
- 追踪数据来源：HTTP body、Cookie、文件上传、消息队列（Kafka/RabbitMQ）、缓存（Redis/Memcached）
- 检查输入验证：是否有类型检查、白名单过滤、Schema 验证（如 Joi、Yup）
- 确认 `eval` 前是否有危险字符过滤（检查是否可绕过，如 Unicode 编码、注释符）
- 验证 `require` 路径是否限制（`path.resolve`、白名单目录）

**L4: 跨模块追踪**
- 识别自定义序列化协议（跨文件追踪 `serialize`/`deserialize` 函数实现）
- 检查中间件链：body-parser 配置、session 中间件（express-session、cookie-session）
- 分析插件系统架构：插件加载机制、插件间通信方式
- 追踪缓存数据流：Redis 数据写入点（是否可被其他漏洞污染）
- 检查依赖树：`npm ls node-serialize`、`npm ls serialize-javascript` 确认版本

---

### 快速定位保护机制的技巧

**L0: 快速跳过**
- 使用 `JSON.parse()` 且无 reviver、无后续 `eval`
- TypeScript 配置严格类型检查且无 `any` 类型
- 使用 Protobuf/MessagePack 等二进制序列化方案

**L1: 关键词扫描防护措施**
- `JSON.parse` 无第二参数（无 reviver）
- `yaml.safeLoad` 替代 `yaml.load`
- `vm2` 库（替代原生 `vm` 模块）
- CSP（Content Security Policy）配置 `script-src 'self'`
- `helmet` 中间件配置
- 输入验证库：`validator.js`、`joi`、`ajv`

**L2: 跳读检查验证逻辑**
```javascript
// 白名单示例
const allowedKeys = ['name', 'email', 'age'];
const parsed = JSON.parse(input);
Object.keys(parsed).forEach(key => {
    if (!allowedKeys.includes(key)) {
        throw new Error('Invalid key: ' + key);
    }
});

// 类型检查
const schema = Joi.object({
    name: Joi.string().required(),
    age: Joi.number().integer()
});
const { error } = schema.validate(input);
```

**L3: 逐行分析防护强度**
- 验证白名单是否完整（是否遗漏嵌套对象的键）
- 检查类型断言：TypeScript `as` 断言是否安全（运行时不生效）
- 确认沙箱隔离：`vm2` 配置是否正确（`timeout`、`sandbox` 对象）
- 验证 CSP 配置：是否禁用 `unsafe-eval`、`unsafe-inline`
- 检查异常处理：验证失败是否正确中断请求

**L4: 跨模块验证全局防护**
- Helmet 中间件配置：`contentSecurityPolicy`、`hsts`
- Node.js 启动参数：`--disallow-code-generation-from-strings`（禁用 eval）
- 容器安全：seccomp profile 限制系统调用
- WAF 规则：ModSecurity/Cloudflare 配置检测 `eval` 模式
- 依赖扫描：`npm audit`、`snyk test` 检查已知漏洞
- 运行时监控：RASP 方案（Sqreen/Contrast Security）

---

## Classify

### 真实漏洞的判定标准
1. **外部可控性**：反序列化数据来源可被攻击者控制（HTTP body/query/params、Cookie、WebSocket、文件上传、消息队列、缓存）
2. **代码执行路径**：使用 `eval`、`Function` 构造函数、`vm` 模块或存在代码执行缺陷的序列化库（`node-serialize`、`serialize-javascript < 3.1.0`）
3. **无有效验证**：缺少输入白名单、Schema 验证，或仅使用正则黑名单（易绕过）
4. **沙箱可绕过**：使用 `vm` 模块但未正确隔离，可通过 `this.constructor.constructor('return process')()` 逃逸
5. **可达性**：代码在生产环境执行路径中，非测试代码或死代码

### 误报的典型特征
1. **内部可信数据**：仅反序列化服务端自身生成的数据（本地配置文件、环境变量、编译时嵌入的常量）
2. **静态代码路径**：`require()` 或 `import()` 使用硬编码路径，无动态拼接
3. **严格类型检查**：TypeScript 严格模式且无 `any` 类型，运行时配合 Zod/io-ts 验证
4. **不可达代码**：反序列化逻辑在测试文件、示例代码、已弃用模块中
5. **安全库版本**：使用 `serialize-javascript >= 3.1.0`、`js-yaml.safeLoad`、`vm2` 等安全方案
6. **仅 JSON.parse**：仅使用 `JSON.parse()` 无 reviver，且解析后无 `eval` 或动态执行

### 代码异味的识别
1. **弱过滤机制**：使用正则黑名单过滤 `eval` 关键词（可通过 `eval` → `this['ev'+'al']` 绕过）
2. **不必要的 eval**：功能可通过 `JSON.parse` 实现但使用 `eval` 以支持"更灵活"的配置
3. **vm 模块误用**：认为 `vm` 提供安全沙箱但未意识到可通过原型链污染逃逸
4. **动态 require 路径**：路径部分可控但"仅限内部模块"（可能通过路径遍历绕过）
5. **reviver 函数复杂**：`JSON.parse` 配合复杂的 reviver 逻辑，难以审计是否安全
6. **缓存数据未验证**：Redis/Memcached 数据直接反序列化，未考虑缓存污染风险
7. **过期依赖**：使用老版本序列化库但未在 `npm audit` 中报告（因无 CVE 编号）
8. **TypeScript 类型放松**：关键路径使用 `any` 或 `unknown` 类型，绕过类型检查

---

## Low Risk

### 低风险场景的评判依据

**严格的输入验证**
- 使用 JSON Schema（ajv）或 TypeScript runtime validator（Zod、io-ts）验证所有字段
- Schema 定义严格（`additionalProperties: false`、明确类型、长度/范围限制）
- 验证失败立即返回 400 错误且记录日志

**安全的序列化方案**
- 仅使用 `JSON.parse()` 且无 reviver 函数
- 采用 Protobuf（protobuf.js）、MessagePack（msgpack）等类型安全方案
- 使用 `js-yaml.safeLoad` 禁用自定义类型
- `serialize-javascript` ≥ 3.1.0 且 `unsafe: false`（默认）

**运行时沙箱隔离**
- 使用 `vm2` 库替代原生 `vm` 模块，配置严格 timeout 和白名单 API
- 运行在 Worker Threads 或独立进程中，通过 IPC 通信
- 容器化运行且配置 seccomp profile（禁用 `execve`、`ptrace`）

**强认证与授权**
- 反序列化端点需要 JWT/OAuth2 认证且验证 signature
- 使用 HMAC-SHA256 验证数据完整性（签名在反序列化前验证）
- 实施严格 RBAC，仅管理员可触发反序列化操作

**网络隔离**
- 服务仅监听 localhost 或内网 IP
- 通过 API Gateway 统一入口，配置 WAF 规则
- 反序列化服务与公网隔离（需通过跳板机或 VPN 访问）

**监控与限制**
- CSP 配置 `script-src 'self'; unsafe-eval 禁用`
- Helmet 中间件强制 HTTPS、禁用 X-Powered-By
- 部署 RASP 监控 `eval` 调用并告警
- 限流机制：每用户每分钟 ≤10 次反序列化请求
- 完整审计日志：记录所有反序列化操作、来源 IP、用户 ID

**业务场景受限**
- 仅用于内部管理工具（非面向用户功能）
- 反序列化结果仅用于只读展示（无状态变更、无命令执行）
- 数据源完全可控（开发者手动上传配置文件，无自动化接口）

**TypeScript 类型安全**
- 启用 `strict` 模式、`noImplicitAny`、`strictNullChecks`
- 所有反序列化数据使用明确类型（无 `any`、`unknown`）
- 配合 runtime validator（Zod）确保类型匹配

**迁移计划明确**
- 功能标记为 `@deprecated`，计划迁移到 GraphQL/gRPC
- 使用率低（监控显示 <5% 流量），仅向后兼容老客户端
- 通过 Feature Flag 限制仅开发/测试环境启用

**注意**：JavaScript 反序列化风险极高，即使评为低风险，仍应推动团队：① 完全禁用 `eval` 和 `Function` 构造函数；② 使用 `JSON.parse` 或 Protobuf；③ 启用 CSP 和 Node.js `--disallow-code-generation-from-strings` 参数；④ 部署 RASP 监控异常代码执行。务必全局搜索 `eval`、`Function(`、`vm.run`、`serialize.unserialize`、动态 `require/import`，逐一评估数据源可信度和防护机制有效性。