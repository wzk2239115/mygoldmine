# TypeScript/JavaScript RPC 不安全反序列化

**漏洞概述**  
在 Node.js 服务端接收客户端序列化对象、RPC 通信、插件加载或配置反序列化场景中，通过 `eval()`、`Function()` 构造器、`vm.runInContext` 配合 `JSON.parse` 误用、`serialize-javascript` 库缺陷、自定义反序列化逻辑等方式，导致任意代码执行。常见于 JSON-RPC、MessagePack-RPC、自定义二进制协议、WebSocket 消息处理等场景。

---

## Details

### 典型代码示例

**场景1：eval/Function 直接执行序列化数据**
```typescript
// 危险：直接 eval 用户输入
const data = req.body.payload;
const obj = eval('(' + data + ')');  // 触发点：代码执行

// 危险：Function 构造器
const config = new Function('return ' + userInput)();  // 触发点

// 危险：隐式 eval
setTimeout(userInput, 100);  // 触发点：字符串会被 eval
setInterval(userData, 1000);  // 触发点
```

**场景2：vm 模块沙箱逃逸**
```typescript
import vm from 'vm';

// 危险：context 对象污染
const sandbox = { result: null };
vm.runInContext(userCode, vm.createContext(sandbox));  // 触发点：原型链逃逸

// 危险：runInThisContext 无隔离
vm.runInThisContext(userInput);  // 触发点：等同于 eval

// 危险：Script 实例复用
const script = new vm.Script(userCode);
script.runInNewContext({});  // 触发点：prototype 污染
```

**场景3：serialize-javascript 库误用**
```typescript
import serialize from 'serialize-javascript';

// 危险：反序列化不可信数据
const serialized = req.query.state;
const obj = eval('(' + serialized + ')');  // 触发点：库本身不提供安全反序列化

// serialize-javascript < 3.1.0 XSS 漏洞
const html = `<script>var data = ${serialize(userInput)}</script>`;  // 触发点
```

**场景4：JSON-RPC 协议处理**
```typescript
// 危险：动态方法调用
app.post('/rpc', (req, res) => {
    const { method, params } = req.body;
    const result = this[method](...params);  // 触发点：method 可控
    res.json({ result });
});

// 危险：JSON.parse 后 eval
const rpcCall = JSON.parse(req.body);
if (rpcCall.method === 'eval') {
    eval(rpcCall.code);  // 触发点：逻辑绕过
}
```

**场景5：MessagePack-RPC 反序列化**
```typescript
import msgpack from 'msgpack-lite';

// 危险：反序列化后动态执行
const data = msgpack.decode(buffer);
if (data.type === 'function') {
    const fn = new Function(data.body);  // 触发点
    fn(data.args);
}

// 危险：自定义扩展类型
msgpack.codec.preset.addExtUnpacker(0x01, (buffer) => {
    return eval(buffer.toString());  // 触发点：扩展类型处理器
});
```

**场景6：WebSocket 消息反序列化**
```typescript
import WebSocket from 'ws';

wss.on('connection', (ws) => {
    ws.on('message', (message) => {
        // 危险：直接执行消息内容
        const cmd = JSON.parse(message);
        if (cmd.action === 'eval') {
            eval(cmd.code);  // 触发点
        }
        
        // 危险：vm 沙箱误用
        vm.runInNewContext(cmd.script, {});  // 触发点
    });
});
```

**场景7：自定义序列化协议**
```typescript
// 危险：自定义反序列化器包含代码执行
class CustomDeserializer {
    deserialize(data: string): any {
        const obj = JSON.parse(data);
        if (obj.__type === 'Function') {
            return eval(`(${obj.code})`);  // 触发点
        }
        return obj;
    }
}
```

**场景8：配置文件动态加载**
```typescript
// 危险：require 动态路径
const configPath = req.query.config;
const config = require(configPath);  // 触发点：路径遍历 + 代码执行

// 危险：import() 动态模块
const moduleName = userInput;
const mod = await import(moduleName);  // 触发点

// 危险：JSON5/YAML 解析器误用
import JSON5 from 'json5';
const config = JSON5.parse(userInput);  // 较安全，但检查是否有自定义 reviver
```

**场景9：gRPC/Protobuf 处理器逻辑漏洞**
```typescript
import grpc from '@grpc/grpc-js';

// 危险：方法名动态路由
server.addService(serviceDefinition, {
    [methodName]: (call, callback) => {  // 触发点：methodName 可控
        eval(call.request.code);
    }
});

// 危险：Protobuf Any 类型滥用
const anyMessage = call.request.payload;
const TypeUrl = anyMessage.type_url;  // 触发点：类型混淆
const value = anyMessage.unpack();
```

**场景10：对象原型污染导致 RCE**
```typescript
// 危险：合并用户输入到对象
function merge(target: any, source: any) {
    for (let key in source) {
        target[key] = source[key];  // 触发点：__proto__ 污染
    }
}

const userConfig = JSON.parse(req.body);
merge(config, userConfig);  // 污染 Object.prototype

// 后续代码触发执行
const fn = config.execPath || '/usr/bin/node';  // 被污染的属性
require('child_process').execSync(fn);  // RCE
```

**场景11：Electron IPC 反序列化**
```typescript
// 主进程
ipcMain.on('execute', (event, code) => {
    eval(code);  // 触发点：渲染进程可控
});

// 危险：remote 模块滥用
const { remote } = require('electron');
remote.require('child_process').exec(userInput);  // 触发点
```

**场景12：Node.js Worker Threads 数据传递**
```typescript
import { Worker } from 'worker_threads';

// 危险：postMessage 传递可执行代码
const worker = new Worker('./worker.js');
worker.postMessage({ type: 'eval', code: userInput });  // 触发点

// worker.js
parentPort.on('message', (msg) => {
    if (msg.type === 'eval') {
        eval(msg.code);  // 触发点
    }
});
```

---

### 快速定位核心操作的技巧

**L1 - 关键词扫描：**
- 代码执行函数：`eval(`、`Function(`、`new Function`、`setTimeout(string`、`setInterval(string`
- VM 模块：`vm.runInContext`、`vm.runInThisContext`、`vm.runInNewContext`、`vm.Script`
- 动态导入：`require(variable)`、`import(variable)`、`__non_webpack_require__`
- 反序列化库：`serialize-javascript`、`msgpack.decode`、`protobuf.decode`、`BSON.deserialize`
- 协议处理：`JSON-RPC`、`@grpc/grpc-js`、`ws`（WebSocket）、`socket.io`
- 危险属性：`__proto__`、`constructor.prototype`、`Object.prototype`

**L2 - 跳读定位数据来源：**
- HTTP 请求体：`req.body`、`req.query`、`req.params`、`req.headers`
- WebSocket/Socket.io：`socket.on('message')`、`io.on('connection')`
- gRPC 调用：`call.request`、`call.metadata`
- IPC 通信：`ipcMain.on()`、`process.on('message')`、`worker.on('message')`
- 消息队列：`amqp.consume()`、`kafka.consumer.run()`、`redis.subscribe()`
- 文件上传：`multer`、`formidable` 后处理文件内容
- 间接来源：数据库反序列化字段、Redis 缓存、外部 API 回调

**L3 - 逐行追踪数据流：**
- **动态方法调用链**：`obj[userInput]()`、`this[method](...args)`、`global[funcName]()`
- **字符串拼接执行**：`eval('(' + data + ')')`、`Function('return ' + code)()`
- **JSON reviver 函数**：`JSON.parse(data, reviver)` 中 reviver 逻辑是否有代码执行
- **对象合并函数**：检查 `Object.assign`、`_.merge`、`deepmerge` 是否过滤 `__proto__`
- **VM context 对象**：sandbox 对象是否包含 `process`、`require`、`global` 等危险引用
- **类型转换**：隐式调用 `toString()`、`valueOf()` 是否触发原型链方法
- **模板字符串**：`` `${userInput}` `` 是否传递给 `eval` 或动态导入

**L4 - 跨模块追踪攻击路径：**
- **原型链污染扩散**：全局搜索 `for...in` 循环、`Object.keys()` 未过滤、递归合并函数
- **RPC 方法注册表**：查找动态方法路由表（`handlers[method]`、`services[name]`）
- **中间件顺序**：反序列化是否在认证中间件之前（`app.use(bodyParser)` 位置）
- **依赖库漏洞**：检查 `package.json` 中已知有反序列化 CVE 的库版本
  - `node-serialize` < 0.0.4（已知 RCE）
  - `serialize-javascript` < 3.1.0（XSS）
  - `msgpack5` 自定义扩展处理
- **TypeScript 类型绕过**：`any` 类型、类型断言 `as` 是否掩盖危险操作
- **框架特定漏洞**：
  - **Express**：`bodyParser.json()` 配置 `reviver` 参数
  - **Koa**：`koa-bodyparser` 中间件顺序
  - **NestJS**：`@MessagePattern()` 装饰器处理器、gRPC 服务
  - **Electron**：`nodeIntegration: true` + `contextIsolation: false`
- **构建工具影响**：Webpack `externals` 配置可能引入不安全的 `require`

---

### 快速定位保护机制的技巧

**L1 - 关键词扫描防护措施：**
- 安全解析：`JSON.parse()`（无 reviver）、`JSON.stringify()`
- 输入验证：`validator.js`、`joi`、`yup`、`zod`、`class-validator`
- 白名单检查：`allowedMethods`、`methodWhitelist`、`SAFE_METHODS`
- 沙箱库：`vm2`、`isolated-vm`、`safeEval` 库
- CSP 头：`Content-Security-Policy` 限制脚本执行（前端）
- TypeScript 严格模式：`strict: true`、`noImplicitAny`

**L2 - 跳读检查防护强度：**
```typescript
// 有效：纯 JSON 解析
const data = JSON.parse(req.body);  // 安全（除非有 reviver）

// 有效：方法白名单
const ALLOWED_METHODS = ['read', 'write'];
if (!ALLOWED_METHODS.includes(method)) {
    throw new Error('Method not allowed');
}

// 有效：vm2 沙箱
import { VM } from 'vm2';
const vm = new VM({ timeout: 1000, sandbox: {} });
vm.run(userCode);  // 相对安全

// 弱防护：简单字符串检查
if (code.includes('eval') || code.includes('require')) {
    return;  // 可绕过：eval.call、global['eval']
}

// 弱防护：原生 vm 模块
vm.runInNewContext(code, {});  // 已知多个沙箱逃逸 CVE

// 无效：注释标记
// SAFE: user input is validated  // 需验证实际代码
eval(userInput);
```

**L3 - 逐行分析防护有效性：**
- **JSON.parse reviver 检查**：
```typescript
JSON.parse(data, (key, value) => {
    if (key === '__proto__') return;  // 检查是否过滤原型链
    if (typeof value === 'string' && value.startsWith('__')) return;
    return value;
});
```

- **对象合并防护**：
```typescript
// 有效
Object.assign({}, source);  // 仅复制 own properties，不触发 __proto__

// 有效
const sanitized = JSON.parse(JSON.stringify(untrusted));  // 深拷贝且移除原型链

// 无效
_.merge(target, source);  // lodash < 4.17.11 有原型污染漏洞
```

- **方法白名单严谨性**：
```typescript
// 有效
const handlers: Record<string, Function> = {
    'user.get': getUser,
    'user.update': updateUser,
};
if (!(method in handlers)) throw new Error('Invalid method');
const result = handlers[method](params);

// 无效：黑名单
if (method !== 'eval' && method !== 'exec') {
    this[method]();  // 可调用其他危险方法如 constructor
}
```

- **VM 沙箱配置**：
```typescript
// 弱隔离
const sandbox = { console, Buffer, process };  // 暴露危险对象
vm.runInNewContext(code, sandbox);

// 较强隔离（但仍可能逃逸）
import { VM } from 'vm2';
const vm = new VM({
    timeout: 1000,
    sandbox: {},  // 空沙箱
    eval: false,
    wasm: false,
});
```

**L4 - 架构层全局防护：**
- **Node.js 启动参数**：
  - `--disallow-code-generation-from-strings`（禁用 eval/Function）
  - `--no-experimental-worker`（禁用 Worker Threads）
  - `--frozen-intrinsics`（冻结内置对象原型）
  
- **依赖审计工具**：
  - `npm audit`、`yarn audit`、`pnpm audit`
  - `snyk test`、`retire.js`
  - CI/CD 集成 `audit-ci` 强制检查

- **运行时保护**：
  - 容器化：限制 `CAP_SYS_ADMIN`、禁用 `--privileged`
  - Seccomp：限制 `execve`、`fork` 系统调用
  - 只读文件系统：`readOnlyRootFilesystem: true`（Kubernetes）

- **代码质量检查**：
  - ESLint 规则：`no-eval`、`no-implied-eval`、`no-new-func`
  - TSLint 规则：`ban` eval/Function
  - SonarQube 静态分析

- **架构设计**：
  - 使用类型安全的 RPC：gRPC + Protobuf（严格 schema）
  - 避免动态方法路由：使用显式 switch/case 或路由表
  - 微服务隔离：反序列化操作在独立服务中，限制爆炸半径

- **监控与告警**：
  - 记录 RPC 方法调用审计日志
  - 监控异常：`process.on('uncaughtException')`、内存峰值
  - WAF 规则：检测 `__proto__`、`constructor`、`prototype` 关键词

---

## Classify

### 真实漏洞的判定标准
1. **外部可控数据**：反序列化的数据直接或间接来自客户端输入（HTTP/WebSocket/gRPC/消息队列），且数据流可追溯到不可信边界
2. **存在代码执行路径**：使用 `eval`、`Function`、`vm.run*`、动态 `require/import`、或触发原型链污染后导致的 RCE
3. **动态方法调用**：RPC 方法名、对象属性名、函数名由用户输入决定，且无严格白名单限制
4. **防护缺失或可绕过**：无输入验证、方法黑名单不完整、原生 vm 模块沙箱（非 vm2）、字符串过滤可绕过
5. **执行路径可达**：代码在实际业务逻辑中会执行（非测试/示例代码），且攻击者可控制触发时机

### 误报的典型特征
1. **数据源可信**：反序列化数据完全由服务端生成（配置文件、数据库 schema 定义、内部服务通信），用户无法篡改原始数据
2. **严格类型验证**：使用 TypeScript 严格模式 + `zod`/`io-ts` 运行时验证，拒绝不符合 schema 的数据
3. **纯 JSON 解析**：仅使用 `JSON.parse()`（无 reviver）处理数据，不涉及代码执行函数
4. **强沙箱隔离**：使用 `vm2` 或 `isolated-vm` 且配置正确（空 sandbox、禁用 eval、设置 timeout）
5. **方法完全枚举**：RPC 方法通过显式 Map/Object 定义，编译时确定，不涉及动态属性访问
6. **代码不可达**：反序列化逻辑在废弃接口、开发环境专用代码、条件永远不满足的分支中

### 代码异味的识别
1. **过度信任内部服务**：假设内网 RPC 调用安全，但未考虑横向移动场景
2. **弱字符串过滤**：黑名单检测 `eval` 关键词，可通过 `global['eval']`、`this['eval']`、`` eval`` 绕过
3. **原生 vm 模块**：使用 `vm.runInNewContext` 但未意识到存在多个已知沙箱逃逸 CVE
4. **方法名部分可控**：如 `user.${action}` 格式，虽然有前缀但 action 可控可能触发意外方法
5. **原型污染风险**：使用 `_.merge`、递归赋值但未过滤 `__proto__`、`constructor`、`prototype`
6. **依赖版本过期**：使用已知有反序列化漏洞的旧版本库（`node-serialize`、`lodash < 4.17.11`）
7. **TypeScript `any` 滥用**：大量使用 `any` 类型绕过类型检查，掩盖不安全操作
8. **配置灵活性过高**：支持从环境变量/配置文件动态加载模块路径、方法名，缺少白名单约束

---

## Low Risk

### 低风险场景的评判依据

**使用类型安全的序列化格式**
- 严格使用 `JSON.parse()`/`JSON.stringify()` 且无 reviver/replacer 自定义逻辑
- 采用 Protobuf + gRPC，schema 在编译时强制类型检查，无法注入任意类型
- 使用 MessagePack 但仅启用基本类型，禁用扩展类型（extension types）
- 配合 TypeScript 严格模式 + 运行时验证库（`zod`、`io-ts`、`typebox`）双重校验

**完全可信的数据源**
- 反序列化数据由服务端内部生成（配置文件只读挂载、环境变量、Kubernetes ConfigMap）
- 数据存储在隔离的内部缓存（进程内存、Redis 私有实例），用户无网络访问权限
- 跨服务通信使用 mTLS 双向认证 + 服务网格（Istio/Linkerd）强制加密

**严格的方法白名单**
- RPC 方法通过显式 Map 或 Switch 语句枚举，编译时确定所有可调用方法
- 方法名不由用户输入决定，或通过枚举类型（TypeScript enum）严格限制
- 使用装饰器（如 NestJS `@MessagePattern()`）声明式注册，避免动态路由

**强沙箱隔离**
- 使用 `vm2` 或 `isolated-vm` 配置空 sandbox、禁用 eval、设置 CPU/内存限制
- Node.js 启动时启用 `--disallow-code-generation-from-strings` 标志
- 代码执行在独立容器/进程中，使用 Seccomp 限制系统调用（禁止 execve）

**原型污染防护**
- 使用 `Object.create(null)` 创建无原型的对象存储用户数据
- 输入数据通过 `JSON.parse(JSON.stringify())` 深拷贝且移除原型链
- 使用 `--frozen-intrinsics` 启动参数冻结内置对象原型（Node.js 14+）
- 依赖库版本锁定且定期审计（`npm audit`、`snyk`）

**架构层安全隔离**
- 反序列化操作在认证后执行，且仅处理已授权用户的特定资源
- 微服务架构中将反序列化逻辑隔离到专用服务，限制权限和网络访问
- 容器化部署配置只读文件系统、禁用特权模式、限制资源（CPU/内存）
- 使用服务网格策略限制服务间调用白名单，防止横向移动

**监控与审计**
- 记录所有 RPC 方法调用的审计日志（方法名、参数摘要、调用者身份）
- 运行时监控异常行为（eval 调用、require 动态路径、原型链修改）
- 集成 SIEM 系统，异常模式触发告警（频繁失败、非预期方法调用）
- 定期进行渗透测试和代码审计

**业务场景限制**
- 功能仅对内部管理员开放，需要 VPN + MFA（多因素认证）
- RPC 接口有严格的速率限制和请求大小限制
- 使用 API Gateway 统一入口，配置 WAF 规则检测反序列化攻击特征
- 计划迁移到更安全的架构（REST + JSON、gRPC + Protobuf）
