# JavaScript/TypeScript 中的 CSP unsafe-eval 漏洞审计指南

## Details

### 核心问题示例
```javascript
// 典型场景1：Express/Koa中的全局CSP设置
app.use((req, res, next) => {
  res.setHeader('Content-Security-Policy', "script-src 'unsafe-eval'");
  next();
});

// 典型场景2：脚本动态执行
const userCode = req.query.code;
eval(userCode);  // 与unsafe-eval配合，完全绕过CSP保护
```

```javascript
// 典型场景3：Function构造函数（等价于eval）
const dynamicFn = new Function('return ' + userInput);
dynamicFn();

// 典型场景4：setTimeout/setInterval接收字符串
setTimeout("alert('" + userData + "')", 1000);

// 典型场景5：模板引擎未经过滤
ejs.render("<%=" + userTemplate + "%>", {});

// 典型场景6：Vue/React动态模板编译（包含表达式注入）
const compiled = Vue.compile("<div>{{ " + userExpression + " }}</div>");
```

### 快速定位核心操作 **【L1: 关键词扫描】**
审计时通过以下关键词扫描定位动态代码执行：
- **eval()** - 最直接的动态执行方式
- **new Function()** / **Function()** - 构造函数方式构建可执行函数
- **setTimeout/setInterval** - 接收字符串参数时能执行脚本
- **vm.runInContext()** / **vm.runInThisContext()** (Node.js) - 虚拟机执行
- **child_process.exec()** 模板注入场景 - 虽属系统调用但需关联检查
- **compileExpression** / **compile()** - 模板引擎编译函数
- **.innerHTML** 赋值 (结合XSS，用户输入包含`<script>`时)
- **script.textContent** / **script.src** 动态设置 - 加载恶意脚本
- **$.globalEval()** (jQuery) / **eval()** 变种

### 快速定位保护机制 **【L2: 跳读】**
检查CSP头部配置策略：
```javascript
// 扫描Content-Security-Policy字段中的以下字符
script-src 'unsafe-eval'   // 高风险：完全禁用eval保护
script-src *               // 高风险：允许任意脚本源
script-src 'unsafe-inline' // 中风险：虽不直接影响eval，但削弱防护

// 关键配置点（L2跳读）
- 检查CSP header是否存在（无header = 无保护）
- 检查script-src指令是否包含unsafe-eval
- 检查是否存在default-src 'unsafe-eval'（无script-src时的后备）
- 检查开发环境vs生产环境的不同配置
- 中间件级别的全局CSP设置（Express.js的helmet, csurf等）
```

关键文件位置检查：
- **服务器入口** - app.js, server.js, index.js中的中间件链
- **配置文件** - config.js, .env, environment.config.ts
- **中间件定义** - middleware/, config/csp.js
- **模板引擎配置** - ejs.config, pug.config

## Classify

### 研判标准

**确定为漏洞的条件（同时满足）：**
1. 代码中存在动态代码执行（eval, Function, setTimeout字符串等）
2. CSP策略中明确包含`script-src 'unsafe-eval'`或`default-src 'unsafe-eval'`
3. 执行的代码内容来自用户可控源（query参数、POST body、数据库、文件、第三方API等）
4. 未进行有效的输入验证/白名单校验

**升级为高危的额外条件：**
- 未对用户输入进行任何过滤
- 涉及认证信息执行（如执行用户定义的业务逻辑）
- 可导致数据泄露、权限提升或远程代码执行

### 研判为误报的条件：

1. **动态代码来自可信源**
   - 代码在部署时静态嵌入（非运行时生成）
   - 代码来自受信任的内部系统，无外部输入通道

2. **受保护的执行环境**
   - 输入经过严格的白名单校验（仅允许数学表达式、枚举值等）
   - 使用AST解析+验证而非直接eval（如通过math.js、expression.js的安全模式）
   - 在Web Worker/iframe沙箱中执行（隔离权限）

3. **CSP有效保护**
   - 虽有unsafe-eval但通过script-src中的nonce/hash限制脚本来源
   - 同时配置object-src/frame-src等降低攻击面
   - 配合Cookie Secure/HttpOnly、X-Content-Type-Options等多层防护

### 代码异味的研判：

1. **低置信度的动态执行** - eval/Function代码量少且逻辑简单，但缺乏明确业务必要性 → 建议重构
2. **遗留CSP配置** - 注释中提及"临时unsafe-eval"或变更日志显示是为调试添加 → 确认是否应移除
3. **配置不一致** - 生产环境有unsafe-eval但开发无、或仅特定路由有 → 可能配置管理混乱

## Low risk

### 允许低风险评级的场景

1. **受限的表达式引擎**
   - 使用经过安全加固的表达式计算库（math.js safe mode、jexl、expr-eval等）
   - 库通过AST而非eval实现，源代码可验证
   - 输入限制在数学表达式、比较操作符范围内

2. **确认业务必要性的CSP配置**
   - 代码审视表明unsafe-eval确实用于非Web框架的Server-side动态代码（如Node.js脚本生成、模板处理）
   - 存在明确的技术文档说明为何必须使用

3. **隔离的执行环境**
   - 动态代码运行在Web Worker/Service Worker中（与主线程隔离）
   - 或在iframe沙箱中执行，具有受限的权限（sandbox属性配置完整）
   - iframe的src来自可信源（非用户可控）

4. **多层防护确保**
   - 虽有unsafe-eval但同时：
     - 使用CSP script-src的nonce/hash（虽不能完全禁用unsafe-eval功能但限制脚本载入）
     - 服务器端严格输入验证 + HTTPOnly Cookie
     - 没有用户输入直接进入eval的数据流
   - 此时安全边界由输入校验而非CSP承载
