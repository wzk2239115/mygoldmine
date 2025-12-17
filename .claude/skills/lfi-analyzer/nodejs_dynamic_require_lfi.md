# Node.js 动态 require/import 本地文件包含

## Details

### 代码示例

**漏洞场景：动态模块加载**
```javascript
// Express 路由 - 插件系统
app.get('/plugin/:name', (req, res) => {
  const pluginName = req.params.name;
  const plugin = require(`./plugins/${pluginName}`);
  plugin.execute(res);
});

// CLI 工具 - 命令加载器
const command = process.argv[2];
const handler = require(`./commands/${command}`);

// SSR - 动态组件加载
const componentName = req.query.component;
const Component = require(`../components/${componentName}`).default;

// 配置加载器
const configFile = req.body.config;
const config = require(configFile);

// ES Module 动态导入
const modulePath = userInput;
const module = await import(modulePath);
```

**关键危险模式：**
- `require(变量)`：变量来自外部输入
- `import(变量)`：ES Module 动态导入
- 路径拼接：`require('./dir/' + input)` 或 `` require(`./dir/${input}`) ``
- JSON.parse 后直接 require：`require(JSON.parse(body).modulePath)`

### 快速定位核心操作技巧（L1-L3）

**L1 - 关键词扫描：**
- 搜索正则：`require\s*\([^'"]*\$|require\s*\([^'"]*\+|import\s*\([^'"]*\$|import\s*\([^'"]*\+`
- 关键函数：`require()`、`import()`、`requireFrom()`、`proxyquire()`
- 高危上下文：`req.params`、`req.query`、`req.body`、`process.argv` 出现在 require 附近

**L2 - 跳读定位：**
- 追踪数据流：从 HTTP 参数/命令行参数 → 变量赋值 → require/import 调用
- 关注模板字符串拼接：`` require(`${baseDir}/${moduleName}`) ``
- 查找对象解构：`const { module } = req.body; require(module)`

**L3 - 逐行审计：**
- 确认输入源：参数是否完全或部分由外部控制
- 检查路径拼接逻辑：是否存在 `../` 注入可能
- 验证文件扩展名处理：有无强制添加 `.js`/.json 后缀
- 注意 Node.js 模块解析优先级：`./file.js` > `./file.json` > `./file.node` > `./file/index.js`

### 快速定位保护机制技巧（L2-L4）

**L2 - 跳读防御关键点：**
- 白名单检查：`if (!allowedModules.includes(moduleName))`
- 路径遍历过滤：`path.basename()`、`.replace(/\.\./g, '')`
- 扩展名验证：`.endsWith('.js')` 或正则匹配
- 前缀限制：`path.join(__dirname, 'safe-dir', userInput)`

**L3 - 逐行验证防御：**
- `path.basename()` 是否被正确使用（仅提取文件名，过滤目录遍历）
- `path.join()` + `path.resolve()` 组合是否检查最终路径在预期目录内
- 正则过滤是否可绕过：`replace(/\.\./g, '')` → `....//` 绕过
- 白名单是否完整：允许列表是否包含敏感模块（如 `child_process`）

**L4 - 跨模块追踪：**
- 工具函数封装：`loadModule(name)` 内部实现是否安全
- 中间件处理：路径规范化中间件是否被所有路由使用
- 配置文件：`allowedModules` 配置是否可被用户修改
- 依赖库风险：使用的模块加载器库（如 `require-from-string`）是否存在已知漏洞

**典型防御模式识别：**
```javascript
// ✓ 强防御示例
const allowList = ['plugin1', 'plugin2'];
if (!allowList.includes(req.params.name)) throw new Error();
require(`./plugins/${req.params.name}`);

// ✓ 路径限制
const safePath = path.join(__dirname, 'modules', path.basename(userInput));
if (!safePath.startsWith(path.join(__dirname, 'modules'))) throw new Error();
require(safePath);

// ✗ 弱防御 - 可绕过
const module = userInput.replace('../', ''); // ....// 绕过
require(`./modules/${module}`);
```

## Classify

**漏洞判定条件：**
1. **数据流可控**：require/import 的路径参数直接或间接来自外部输入（HTTP、命令行、文件、环境变量）
2. **路径可操控**：攻击者可构造 `../` 序列或绝对路径访问预期目录外的文件
3. **影响范围**：可读取敏感文件（配置、密钥）或加载恶意模块执行代码

**误报识别：**
- 路径完全硬编码：`require('./config/database.js')`（无动态部分）
- 输入仅作为键值索引：`require(moduleMap[userInput])`（映射表查询，非路径拼接）
- 完整白名单防御：严格的枚举检查且列表安全
- 路径后验证生效：`path.resolve()` 后检查是否在安全目录内，且逻辑无误

**代码异味（需人工复核）：**
- 部分路径动态：`require('./modules/' + config.defaultModule)`（config 来自本地配置文件）
- 复杂路径处理：多次字符串替换/正则过滤后的路径，难以确认最终值
- 条件加载：`if (env === 'dev') require(userPath)`（特定环境下启用）
- 依赖第三方验证：使用外部库进行路径验证，需评估库的安全性

**研判流程：**
1. 确认输入源可信度：用户可直接控制 > 间接控制 > 配置文件 > 硬编码
2. 评估路径构造方式：完全可控 > 拼接可控部分 > 映射表查询
3. 验证防御有效性：无防御 > 黑名单 > 不完整白名单 > 严格白名单 + 路径验证
4. 测试可达性：功能是否被实际调用、是否需要认证

## Low Risk

以下场景可评为低风险（但仍建议修复）：

1. **受限攻击面**：
   - 功能仅对管理员开放，且管理员账户无法被普通用户获取
   - 需要多重身份验证（2FA、IP 白名单）才能访问
   - 本地 CLI 工具，仅开发者使用，无生产部署

2. **有限文件访问范围**：
   - 可访问目录仅包含非敏感文件（如公开插件模板）
   - Node.js 进程权限极低，无法读取系统敏感文件
   - 容器/沙箱隔离，文件系统受严格限制

3. **部分防御措施**：
   - 存在白名单但覆盖不全（如允许 10 个插件中的 8 个安全插件）
   - 路径规范化后限制在较大但相对安全的目录（如整个项目目录，但无 `.env`）
   - 扩展名强制限制为 `.json`（JSON 文件通常危害小于 `.js`）

4. **利用难度高**：
   - 需要知道精确文件路径（无目录遍历功能）
   - require 结果未返回给用户（仅内部使用，难以确认成功）
   - 需要配合其他漏洞链才能造成实际危害

5. **影响受限**：
   - 只能读取文件内容，无法执行代码（如仅 require JSON 配置）
   - 错误处理完善，异常不会导致服务崩溃或信息泄露
   - 日志和监控完善，异常行为会被及时发现

**注意：** 低风险不等于无风险，应根据实际业务场景、数据敏感度、合规要求综合评估。