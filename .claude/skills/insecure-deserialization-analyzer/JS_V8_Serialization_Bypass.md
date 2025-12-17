# JavaScript V8 序列化沙箱绕过

**漏洞概述**  
常出现在 Node.js 服务端接收客户端序列化对象、插件配置加载、模板引擎数据处理场景中，攻击者通过构造恶意序列化数据绕过 `vm` 沙箱限制、污染原型链或触发 `eval` 执行，实现远程代码执行。

---

## Details

### 典型代码示例

**场景1：vm.runInContext 配合 JSON.parse 污染原型**
```javascript
// 危险：通过 JSON.parse 解析外部数据后在 vm 中执行
const vm = require('vm');

function executeUserScript(userInput) {
    const sandbox = { console: console };
    const context = vm.createContext(sandbox);
    
    // 解析用户输入的 JSON 配置
    const config = JSON.parse(userInput); // {"__proto__": {"polluted": true}}
    
    // 污染后的对象被传入 vm
    const script = new vm.Script(`
        const result = ${JSON.stringify(config)};
        result.someMethod();
    `);
    script.runInContext(context); // 原型链污染可逃逸沙箱
}
```

**场景2：serialize-javascript 库缺陷**
```javascript
// 危险：serialize-javascript < 3.1.0 允许执行任意代码
const serialize = require('serialize-javascript');

app.post('/api/session', (req, res) => {
    const sessionData = req.body.data; // 外部可控
    
    // 反序列化时可注入函数调用
    const deserialized = eval('(' + sessionData + ')');
    // 示例 payload: {"rce": (function(){require('child_process').exec('calc')})()}
});
```

**场景3：自定义 JSON reviver 配合构造函数**
```javascript
// 危险：reviver 函数中动态实例化对象
function customReviver(key, value) {
    if (value && value.__type) {
        // 根据 __type 字段动态创建对象
        const Constructor = global[value.__type]; // 可指向 Function、eval 等
        return new Constructor(value.data);
    }
    return value;
}

const userInput = req.body.config;
const obj = JSON.parse(userInput, customReviver);
// payload: {"__type": "Function", "data": "return require('child_process').exec('calc')"}
```

**场景4：node-serialize 库反序列化**
```javascript
// 危险：node-serialize 自动执行序列化的函数
const serialize = require('node-serialize');

app.post('/api/restore', (req, res) => {
    const data = req.body.serialized;
    
    // 反序列化时自动执行 IIFE
    const obj = serialize.unserialize(data);
    // payload: {"rce":"_$$ND_FUNC$$_function(){require('child_process').exec('calc');}()"}
});
```

**场景5：vm2 沙箱逃逸（历史漏洞）**
```javascript
// 危险：vm2 < 3.9.11 存在多个沙箱逃逸漏洞
const { VM } = require('vm2');

const vm = new VM({ timeout: 1000 });

app.post('/api/eval', (req, res) => {
    const userCode = req.body.code;
    
    // 通过构造特殊对象逃逸沙箱
    const result = vm.run(userCode);
    // CVE-2023-29017: 通过 Error.prepareStackTrace 逃逸
    // CVE-2023-30547: 通过 Proxy + Exception 逃逸
});
```

**场景6：原型链污染配合模板引擎**
```javascript
// 危险：原型污染配合 lodash template 执行代码
const _ = require('lodash');

app.post('/api/render', (req, res) => {
    const userData = JSON.parse(req.body.data);
    _.merge({}, userData); // 原型链污染
    
    // lodash template 默认使用 Function 构造函数
    const compiled = _.template(req.body.template);
    const output = compiled({ user: 'admin' });
    // 若 Object.prototype.sourceURL 被污染，可触发代码执行
});
```

**场景7：v8.deserialize 内置 API 误用**
```javascript
// 危险：v8.deserialize 处理不可信数据
const v8 = require('v8');

app.post('/api/cache', (req, res) => {
    const serializedData = Buffer.from(req.body.data, 'base64');
    
    // v8.deserialize 可还原任意 JS 对象（包括函数）
    const obj = v8.deserialize(serializedData);
    obj.init(); // 可能执行恶意代码
});
```

**场景8：WebAssembly 配合反序列化**
```javascript
// 危险：动态编译 WASM 模块
app.post('/api/wasm', async (req, res) => {
    const wasmCode = Buffer.from(req.body.wasm, 'base64');
    
    // 编译外部提供的 WASM 字节码
    const module = await WebAssembly.compile(wasmCode);
    const instance = await WebAssembly.instantiate(module, {
        env: { memory: new WebAssembly.Memory({ initial: 256 }) }
    });
    
    // 执行 WASM 导出函数（可能包含恶意逻辑）
    instance.exports.main();
});
```

**场景9：require() 配合路径遍历**
```javascript
// 危险：动态 require 外部可控路径
app.post('/api/plugin', (req, res) => {
    const pluginName = req.body.plugin; // 外部可控
    
    // 路径遍历 + require 可加载任意模块
    const plugin = require(`./plugins/${pluginName}`);
    // payload: ../../package.json 或通过上传恶意 .js 文件
    plugin.execute();
});
```

**场景10：Function 构造函数动态执行**
```javascript
// 危险：使用 Function 构造函数拼接代码
app.post('/api/calculate', (req, res) => {
    const expression = req.body.expr; // 外部可控
    
    // Function 构造函数等同于 eval
    const calculate = new Function('x', 'y', `return ${expression}`);
    const result = calculate(10, 20);
    // payload: "require('child_process').execSync('calc')"
});
```

---

### 快速定位核心操作的技巧

**L0: 快速跳过**
- 代码中无任何序列化/反序列化操作（`JSON.parse`、`serialize`、`deserialize`、`vm`）
- 仅处理基础类型（字符串、数字、布尔）且无动态执行特性

**L1: 关键词扫描**
- `vm.runInContext`、`vm.runInNewContext`、`vm.Script`
- `serialize-javascript`、`node-serialize`、`serialize`/`unserialize`
- `v8.serialize`、`v8.deserialize`
- `JSON.parse` 第二参数（reviver 函数）
- `Function` 构造函数、`eval`、`require('vm2')`
- `_.template`、`_.merge`、`Object.assign` 处理外部数据
- `WebAssembly.compile`、`WebAssembly.instantiate`
- `require()` 配合动态路径拼接
- `__proto__`、`constructor`、`prototype` 出现在数据流中
- `child_process.exec`、`child_process.spawn` 在反序列化附近

**L2: 跳读定位**
- 检查 API 端点是否接收序列化数据（`req.body`、`req.query`、WebSocket 消息）
- 关注 `JSON.parse` 后的数据流向（是否进入 `vm`、模板引擎、对象合并）
- 查看 `vm` 沙箱上下文配置（`sandbox` 对象暴露了哪些危险对象）
- 检查第三方序列化库版本（`serialize-javascript < 3.1.0`、`vm2 < 3.9.19`）
- 确认动态 `require()` 的路径来源

**L3: 逐行追踪**
- 追踪外部输入数据流经过（HTTP body、Cookie、Header、文件上传）
- 验证 `JSON.parse` reviver 函数是否访问 `global`、`process`、`require`
- 检查 `vm` 沙箱是否暴露危险对象（`process`、`require`、`child_process`）
- 分析对象合并逻辑是否检查 `__proto__`、`constructor` 等关键字
- 确认 `v8.deserialize` 后的对象是否直接调用方法或访问属性
- 检查 `Function`/`eval` 的输入是否经过严格过滤
- 验证 WASM 字节码来源（是否可被外部控制）

**L4: 跨模块追踪**
- 识别所有使用 `vm` 的模块（插件系统、规则引擎、表达式求值）
- 检查全局依赖中的危险库版本（`npm audit`、`yarn audit`）
- 追踪原型链污染影响范围（是否影响其他模块的对象）
- 分析模板引擎配置（Handlebars、EJS、Pug 的执行上下文）
- 检查 session/cache 序列化机制（Redis、文件系统存储）
- 验证插件加载机制（是否允许上传 .js 文件、是否验证签名）
- 确认 CSP、Helmet 等安全中间件配置

---

### 快速定位保护机制的技巧

**L0: 快速跳过**
- 完全禁用动态执行（无 `vm`、`eval`、`Function` 构造函数）
- 不处理任何外部序列化数据，仅使用基础类型

**L1: 关键词扫描防护措施**
- `vm` 沙箱配置：`contextIsolatedCodeGeneration: true`
- `JSON.parse` 无 reviver 或 reviver 中有白名单校验
- `Object.freeze(Object.prototype)` 防止原型链污染
- `serialize-javascript` 使用 `space` 参数且版本 ≥ 3.1.0
- 使用安全的序列化方案（`JSON.stringify`/`JSON.parse` 仅处理 Plain Object）
- `helmet` 中间件配置 CSP
- `--disallow-code-generation-from-strings` Node.js 启动参数

**L2: 跳读检查防护机制**
```javascript
// 安全：沙箱配置严格限制
const context = vm.createContext(Object.create(null), {
    codeGeneration: {
        strings: false,  // 禁止 eval/Function
        wasm: false      // 禁止 WebAssembly
    }
});

// 安全：冻结原型链
Object.freeze(Object.prototype);
Object.freeze(Object);
Object.freeze(Function.prototype);

// 安全：白名单校验 reviver
function safeReviver(key, value) {
    const allowedKeys = ['name', 'age', 'email'];
    if (!allowedKeys.includes(key) && key !== '') {
        throw new Error('Unauthorized key');
    }
    return value;
}
```

**L3: 逐行分析防护强度**
- 验证 `vm` 沙箱是否禁用代码生成（`codeGeneration.strings = false`）
- 检查原型污染防护是否完整（冻结 `Object/Array/Function` 原型）
- 确认 reviver 白名单是否覆盖所有危险字段（`__proto__`、`constructor`、`prototype`）
- 验证序列化库版本是否修复已知漏洞（CVE 检查）
- 检查动态 `require()` 是否限制路径（白名单、禁止 `../`）
- 分析异常处理是否泄露栈信息（可能被用于沙箱探测）

**L4: 跨模块验证全局防护**
- Node.js 启动参数：`--disallow-code-generation-from-strings`、`--frozen-intrinsics`
- 运行时环境：Docker seccomp profile 禁止危险系统调用（`execve`）
- 进程隔离：使用独立进程或容器执行不可信代码（gVisor）
- 依赖管理：配置 `npm audit` 自动检查漏洞、锁定依赖版本（`package-lock.json`）
- 网络隔离：限制出站连接（iptables、NetworkPolicy）
- 监控告警：记录所有 `vm` 执行、`eval` 调用、异常反序列化错误
- WAF 规则：拦截包含 `__proto__`、`constructor` 的 JSON 请求

---

## Classify

### 真实漏洞的判定标准
1. **外部可控性**：序列化数据来源可被攻击者控制（HTTP body、query、Cookie、WebSocket、文件上传、Redis/数据库存储的用户内容）
2. **动态执行存在**：使用 `vm`、`eval`、`Function` 构造函数或反序列化库（`serialize-javascript`、`node-serialize`）处理外部数据
3. **沙箱配置薄弱**：`vm` 沙箱暴露危险对象（`process`、`require`、`child_process`）或未禁用代码生成
4. **原型链未保护**：未冻结 `Object.prototype`、使用 `_.merge`/`Object.assign` 处理外部数据且无 `__proto__` 检查
5. **危险库版本**：使用存在已知漏洞的库（`serialize-javascript < 3.1.0`、`vm2 < 3.9.19`、`lodash < 4.17.21`）
6. **reviver 不安全**：`JSON.parse` 的 reviver 函数中访问 `global`、动态实例化对象或执行函数
7. **路径遍历风险**：`require()` 使用外部可控路径且无严格过滤
8. **WASM 动态编译**：接受外部 WebAssembly 字节码并直接编译执行

### 误报的典型特征
1. **可信数据源**：序列化数据完全来自服务端自身（编译时嵌入、管理员手动配置、内部 mTLS 服务）
2. **强沙箱隔离**：使用 `isolated-vm` 库或独立进程（child_process + IPC），配置严格的 CPU/内存限制和超时
3. **严格的输入验证**：使用 JSON Schema 验证外部输入，拒绝包含 `__proto__`、`constructor`、`prototype` 的数据
4. **禁用动态执行**：Node.js 启动参数包含 `--disallow-code-generation-from-strings`、`--frozen-intrinsics`
5. **原型链冻结**：全局冻结 `Object.prototype` 并在 `Object.assign`/`_.merge` 前检查危险键
6. **安全的序列化方案**：仅使用 `JSON.stringify`/`JSON.parse` 处理 Plain Object，不使用第三方反序列化库
7. **库版本安全**：所有依赖已更新至安全版本，定期运行 `npm audit` 且无高危漏洞
8. **死代码或测试**：反序列化逻辑在测试文件、已弃用功能或永远不会执行的分支中

### 代码异味的识别
1. **过度依赖 vm**：为简单的表达式求值使用 `vm` 模块（应使用 `mathjs`、`expr-eval` 等安全库）
2. **混合序列化方案**：部分使用安全的 JSON，部分使用危险的 `serialize-javascript`
3. **沙箱配置不明确**：未显式设置 `codeGeneration`，依赖默认行为
4. **原型污染防护不完整**：仅检查顶层 `__proto__` 但未处理嵌套对象或数组
5. **错误处理不当**：反序列化失败后继续使用部分解析的对象
6. **依赖版本模糊**：`package.json` 中使用 `^` 或 `~` 导致依赖版本不固定
7. **动态 require 路径拼接**：虽然有路径过滤，但正则表达式存在绕过风险
8. **模板引擎配置宽松**：lodash template 未禁用 interpolate 语法（`<%= %>`）
9. **WASM 代码未签名**：接受 WebAssembly 字节码但无完整性校验

---

## Low Risk

### 低风险场景的评判依据

**强沙箱隔离环境**
- 使用 `isolated-vm` 库替代 `vm`，配置严格的 CPU（10ms）和内存（8MB）限制
- 或在独立进程中执行（`child_process.fork`），通过 IPC 通信且子进程运行在 Docker 容器中
- 容器配置 seccomp profile 禁止危险系统调用（`execve`、`socket`、`ptrace`、`mount`）
- 使用 gVisor 或 Kata Containers 运行时提供额外的内核隔离

**严格的输入验证**
- 使用 JSON Schema（Ajv）验证所有外部输入，定义严格的类型和属性白名单
- 拒绝包含 `__proto__`、`constructor`、`prototype`、`__defineGetter__` 的 JSON 数据（深度递归检查）
- 限制 JSON 深度（maxDepth < 5）和大小（maxSize < 100KB）
- 使用 `content-security-policy` 禁止不安全的 inline script

**原型链完整防护**
- 应用启动时立即冻结所有内置原型（`Object.freeze(Object.prototype)`、`Array.prototype`、`Function.prototype`）
- 使用 `Object.create(null)` 创建无原型对象
- 对象合并前使用专用库（如 `@fastify/deepmerge` 且配置 `proto: false`）
- 部署运行时监控（RASP）拦截原型链污染尝试

**安全的序列化方案**
- 完全避免 `serialize-javascript`、`node-serialize`、`v8.serialize` 等危险库
- 仅使用 `JSON.stringify`/`JSON.parse` 且不传递 reviver 函数
- 或使用 Protocol Buffers、MessagePack 等强类型序列化方案
- session/cache 使用签名方案（JWT + HS256、express-session 配合 Redis）

**禁用动态代码执行**
- Node.js 启动参数：`--disallow-code-generation-from-strings --frozen-intrinsics`
- 禁用 `eval`、`Function` 构造函数、`vm` 模块（通过 ESLint 规则 `no-eval`、`no-new-func`）
- 使用安全的表达式求值库（`mathjs`、`expr-eval`、`jexl`）替代 `vm`
- 模板引擎使用逻辑无关模式（Handlebars `noEscape: false`、Mustache）

**依赖安全管理**
- 所有依赖版本锁定（`package-lock.json` 提交到版本控制）
- CI/CD 集成 `npm audit`、`Snyk`、`Dependabot` 自动检查漏洞
- 使用 `npm outdated` 定期更新依赖至安全版本
- 配置 `.npmrc` 禁止安装未签名的包

**网络与运行环境隔离**
- 处理反序列化的服务运行在隔离 VPC，需通过堡垒机或 VPN 访问
- 出站连接限制为特定内部服务（iptables/NetworkPolicy 白名单）
- 使用 mTLS 双向认证验证服务间通信
- 部署 WAF 拦截包含原型污染特征的请求（`__proto__`、`constructor.prototype`）

**监控与响应机制**
- 记录所有反序列化操作（数据来源、大小、解析时间），日志写入 SIEM
- 异常检测：监控 `JSON.parse` 错误、`vm` 执行失败、进程异常退出
- 部署 RASP 拦截危险函数调用（`eval`、`child_process.exec`、动态 `require`）
- 告警触发自动隔离实例并回滚至安全版本

**业务场景限制**
- 反序列化仅用于内部管理工具，需硬件 Token 或 Yubikey 认证
- 需要双人审批（Four-Eyes Principle）才能提交序列化数据
- 系统设计为只读查询（无状态变更、无文件写入、无命令执行）
- 数据流量监控显示反序列化端点访问量极低（< 1% 总流量）

**迁移计划明确**
- 代码已标记为 `@deprecated`，有明确迁移到 Protocol Buffers 或禁用动态执行的 roadmap
- 通过 Feature Flag 限制仅测试环境启用，生产环境已禁用
- 团队已评估风险并分配工程资源进行替换（预计 2 个 Sprint 内完成）

**注意**：JavaScript 反序列化和动态代码执行风险极高，即使评为低风险，仍应推动团队：① 优先禁用所有动态执行特性；② 使用 JSON Schema 严格验证输入；③ 冻结原型链并定期审计依赖漏洞；④ 迁移到安全的序列化方案。务必全局搜索所有反序列化相关代码（`JSON.parse`、`vm`、`eval`、`Function`、`require` 动态路径）并逐一评估数据源可信度和防护机制有效性。