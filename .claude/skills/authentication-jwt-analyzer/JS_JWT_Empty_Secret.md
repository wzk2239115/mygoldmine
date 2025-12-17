# JavaScript/TypeScript JWT 空密钥漏洞审计

## Details

### 代码示例

**典型漏洞模式：**
```javascript
// 危险：空字符串密钥
const jwt = require('jsonwebtoken');
const token = jwt.sign({ userId: 123 }, '');  // 签名密钥为空
const token2 = jwt.sign({ userId: 123 }, "");  // 同样危险

// 危险：未定义的密钥
const secret = process.env.JWT_SECRET;  // 环境变量未设置
const token3 = jwt.sign({ userId: 123 }, secret);  // secret 为 undefined

// 危险：变量初始化为空
let jwtSecret = '';
const token4 = jwt.sign(payload, jwtSecret);

// TypeScript 中的类似问题
const secret: string = '';
const token5 = jwt.sign(payload, secret);
```

**验证侧的空密钥问题：**
```javascript
// 验证时使用空密钥
jwt.verify(token, '');  // 可验证通过任何使用空密钥签名的 token

// 未检查密钥是否存在
const secret = config.jwtSecret;  // 可能未配置
jwt.verify(token, secret);  // secret 可能为 undefined/null/''
```

### 快速定位核心操作 【审计等级：L1-L2】

**L1 关键词扫描：**
- `jwt.sign(` - JWT 签名生成点
- `jwt.verify(` - JWT 验证点
- `jsonwebtoken.sign` / `jsonwebtoken.verify`
- `process.env.JWT_SECRET` - 环境变量密钥来源

**L2 跳读定位技巧：**
1. 定位 `sign()` 和 `verify()` 的第二个参数（密钥参数）
2. 检查密钥参数是否为：
   - 直接的空字符串字面量：`''` / `""`
   - 未初始化的变量
   - 未检查存在性的环境变量
   - 条件分支中可能为空的情况
3. 搜索密钥变量的赋值语句，确认初始值

### 快速定位保护机制 【审计等级：L2-L4】

**L2 跳读防护特征：**
- 密钥来源有默认值或抛出异常：`const secret = process.env.JWT_SECRET || throwError()`
- 启动时密钥检查：`assert(config.jwtSecret, 'JWT secret required')`
- 使用配置验证库（joi、yup）校验密钥强度

**L3 逐行检查点：**
- 密钥变量初始化前是否有存在性检查
- 是否使用 TypeScript 严格模式（`strictNullChecks`）防止 undefined
- 配置加载模块是否验证必填项
- 错误处理是否捕获密钥缺失异常

**L4 跨模块追踪：**
- 配置管理模块是否强制密钥非空（config.ts / config.js）
- 环境变量验证工具（dotenv-safe、envalid）的使用
- 启动脚本是否预检配置有效性
- CI/CD 中是否有密钥注入验证步骤

## Classify

**判定为漏洞：**
- `jwt.sign()` 或 `jwt.verify()` 的密钥参数直接传入空字符串
- 使用未检查存在性的环境变量作为密钥，且该变量可能未设置
- 密钥变量声明但未赋值，直接用于签名/验证
- 条件逻辑中存在密钥为空的执行路径且可达

**判定为误报：**
- 测试代码或 mock 数据中的空密钥（路径包含 test/spec/__tests__/__mocks__）
- 配置示例文件（.example / .sample / .template）中的占位符
- 已有启动时密钥验证且验证失败会阻止服务启动
- 密钥为空时代码会提前抛出异常，不会执行到签名/验证逻辑

**代码异味（需进一步研判）：**
- 密钥从环境变量读取但无默认值或校验，存在配置错误风险
- 多处重复读取 `process.env.JWT_SECRET` 而非统一配置管理
- 密钥变量类型为 `string` 但应为 `string`（不可为空）
- 开发环境使用空密钥但未隔离生产逻辑
- 错误处理过于宽松，吞掉签名失败异常

## Low risk

**低风险评定条件：**

1. **配置验证机制**
   - 应用启动时强制验证密钥非空且符合强度要求
   - 使用配置校验框架（joi、class-validator）确保密钥必填
   - 容器编排（Docker/K8s）中通过 secret 注入且有健康检查

2. **隔离的测试环境**
   - 空密钥仅存在于单元测试或本地开发环境
   - 生产部署流程强制注入有效密钥（CI/CD 验证）
   - 环境配置有明确文档说明密钥为必填项

3. **补偿性控制**
   - 即使密钥为空，仍有其他认证层（OAuth/SAML）
   - JWT 仅用于非敏感场景（如临时会话标识），核心授权依赖后端二次验证
   - 短期 token（<5分钟）+ 严格的刷新策略

4. **可观测性**
   - 监控系统检测到签名异常立即告警
   - 日志中记录密钥加载状态（不记录密钥本身）
   - 错误追踪系统（Sentry/Datadog）覆盖配置问题

**注意：** 即使存在补偿控制，空密钥本质上使 JWT 签名失效，应始终修复该问题而非仅依赖额外防护层。
