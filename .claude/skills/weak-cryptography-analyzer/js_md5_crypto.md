# JavaScript/TypeScript crypto-js MD5 弱加密审计

## Details

### 典型代码特征

```javascript
// 场景1: crypto-js MD5 密码哈希
import CryptoJS from 'crypto-js';
const hash = CryptoJS.MD5(password).toString();
localStorage.setItem('userHash', hash);

// 场景2: MD5 用于 API 签名
const signature = CryptoJS.MD5(apiKey + timestamp + data).toString();
headers['X-Signature'] = signature;

// 场景3: Token 生成使用 MD5
const token = CryptoJS.MD5(userId + Date.now()).toString();
sessionStorage.setItem('token', token);

// 场景4: 前端数据加密传输（伪加密）
const encrypted = CryptoJS.MD5(sensitiveData).toString();
axios.post('/api/submit', { data: encrypted });

// 场景5: MD5 作为对称加密密钥
const key = CryptoJS.MD5(userPassword);
const encrypted = CryptoJS.AES.encrypt(data, key).toString();

// 场景6: HMAC-MD5 消息认证
const hmac = CryptoJS.HmacMD5(message, secretKey).toString();

// 场景7: Node.js crypto 模块使用 MD5
const crypto = require('crypto');
const hash = crypto.createHash('md5').update(password).digest('hex');

// 场景8: 文件指纹生成
const fileHash = CryptoJS.MD5(CryptoJS.lib.WordArray.create(fileBuffer));

// 场景9: JWT 错误使用 MD5
const header = { alg: 'HS256', typ: 'JWT' };
const payload = { userId: 123 };
const signature = CryptoJS.MD5(JSON.stringify(header) + JSON.stringify(payload)).toString();
```

### 快速定位核心操作（L1-L3）

**关键符号扫描（L1）：**
```bash
grep -rn "CryptoJS.MD5\|crypto-js.*MD5" --include="*.js" --include="*.ts" --include="*.jsx" --include="*.tsx"
grep -rn "createHash.*md5\|createHash('md5')" --include="*.js" --include="*.ts"
grep -rn "HmacMD5\|HMAC.*MD5" --include="*.js" --include="*.ts"
grep -rn "MD5.*password\|MD5.*token\|MD5.*secret" --include="*.js" --include="*.ts"
# npm/package.json 依赖检查
grep -n "crypto-js\|blueimp-md5\|js-md5" package.json
```

**高危 API 模式（L2 跳读）：**
- `CryptoJS.MD5(input)` / `CryptoJS.algo.MD5.create()`
- `CryptoJS.HmacMD5(message, key)` HMAC-MD5 签名
- `crypto.createHash('md5')` Node.js 原生 MD5
- `crypto.createHmac('md5', key)` Node.js HMAC-MD5
- `md5(password)` 直接调用第三方 MD5 库（js-md5/blueimp-md5）
- `.toString(CryptoJS.enc.Hex)` MD5 结果用于密钥/令牌
- `localStorage/sessionStorage.setItem()` 存储 MD5 哈希
- `axios/fetch` 请求头 `X-Signature` / `Authorization` 包含 MD5

**函数调用链追踪（L3 逐行）：**
- 定位 `CryptoJS.MD5()` 输入源：用户密码/API 密钥/会话标识
- 认证逻辑：`if(userInput === storedMD5Hash)` 模式
- 签名验证：`req.headers['signature'] === MD5(payload)` 服务端对比
- 配置文件：`config.hashAlgorithm = 'md5'` / `HASH_METHOD: 'MD5'`
- Redux/Vuex store：`hashPassword: (pwd) => CryptoJS.MD5(pwd)`
- 工具函数封装：`utils/crypto.js` 中 `export const hash = MD5`
- 环境变量：`process.env.HASH_ALGO === 'md5'`
- 第三方库集成：Auth0/Passport 自定义策略使用 MD5

### 快速定位保护机制（L2-L4）

**无保护特征（L2 跳读）：**
- 密码直接 MD5：`CryptoJS.MD5(password)` 无 salt 无迭代
- 单轮哈希：无 PBKDF2/bcrypt/scrypt 调用
- 硬编码算法：代码中固定 `MD5` 字符串无配置化
- 前端验证密码：将 MD5 hash 存储在 localStorage 对比
- 明文传输 hash：HTTP 传输 MD5（非 HTTPS 或降级场景）

**伪保护识别（L3 逐行）：**
```javascript
// 加盐但仍用 MD5
const salt = 'static-salt-value';
const hash = CryptoJS.MD5(password + salt).toString();  // 彩虹表攻击仍可行

// Base64 编码伪装安全
const hash = CryptoJS.MD5(password).toString(CryptoJS.enc.Base64);  // 仅编码转换

// 多轮 MD5 迭代不足
let hash = password;
for(let i = 0; i < 100; i++) {
  hash = CryptoJS.MD5(hash).toString();  // 迭代次数过低且算法弱
}

// HTTPS 传输但存储不安全
await axios.post('https://api.example.com/login', {
  passwordHash: CryptoJS.MD5(password).toString()  // 传输安全但后端存储风险
});

// 混淆算法名称
const secureHash = (input) => CryptoJS.MD5(input);  // 命名误导安全性
```

**跨模块保护追踪（L4）：**
- 后端 API 验证：检查 `/api/auth` 是否接受 MD5 哈希且直接对比
- 依赖库版本：`package.json` 中 crypto-js 版本（旧版可能默认弱算法）
- 构建配置：Webpack/Vite `define` 插件注入算法配置
- 环境区分：`process.env.NODE_ENV` 生产环境是否仍用 MD5
- TypeScript 类型定义：`HashAlgorithm = 'md5' | 'sha256'` 联合类型
- 安全策略：CSP 头 / SRI 检查是否加载未知 crypto 库
- SSR/Next.js：服务端渲染中密码哈希逻辑
- Electron 桌面应用：主进程加密逻辑
- Service Worker：离线缓存数据加密方式
- React Native / Flutter WebView：移动端本地存储加密

## Classify

**确认漏洞：**
- 用户密码/PIN 码前端 MD5 后传输或存储
- JWT / OAuth Token 使用 MD5 签名生成
- API 签名验证依赖 HMAC-MD5
- 会话标识符 (Session ID) 生成使用 MD5
- 支付/交易数据校验和用 MD5
- 敏感文件上传后 MD5 作为访问凭证
- WebSocket 握手签名使用 MD5
- 单点登录 (SSO) Ticket 生成基于 MD5
- 双因素认证 (2FA) TOTP 种子用 MD5 派生

**研判误报：**
- 非加密用途的 ETag 生成（HTTP 缓存标识）
- 前端资源完整性校验（CDN 静态文件指纹，非安全边界）
- 开发环境 Mock 数据生成（明确标注 `// DEV ONLY`）
- 单元测试用例（`*.test.js` / `*.spec.ts` 文件）
- 示例代码/文档注释（JSDoc 示例演示）
- 日志追踪 ID 生成（内部 traceId 非认证凭证）
- 用户头像 URL 路径哈希（Gravatar 默认 MD5）
- Git commit hash 生成（历史原因只读数据）

**代码异味：**
- 配置可选但默认 MD5（`defaultHashAlgo: 'md5'`）
- 注释"临时方案"但已运行多年
- 函数命名 `secureHash` 但实现用 MD5
- TypeScript `any` 类型绕过算法枚举限制
- 条件判断优先 MD5：`if(fast) use MD5 else SHA256`
- ESLint / TSLint 规则禁用：`// eslint-disable-next-line no-md5`
- 依赖库 `crypto-js` 但仅用 MD5 模块（应迁移 SHA-256）
- 历史迁移标记：`// TODO: Replace MD5 with SHA-256`

**关键判断点：**
1. 数据敏感性：密码/密钥/凭证 vs 缓存键/追踪ID
2. 使用场景：认证授权 vs 性能优化（哈希表键）
3. 攻击面：公网暴露 API vs 内部管理后台
4. 存储时长：持久化数据库 vs 内存临时变量
5. 替代方案：项目是否已引入 Web Crypto API / Node.js crypto SHA-256

## Low risk

**可接受的低风险场景：**
- Gravatar 头像服务（邮箱 MD5 作为 URL 路径参数，第三方 API 要求）
- Webpack 打包文件 hash（`[contenthash:8]` 用于版本管理）
- 浏览器指纹库（FingerprintJS 设备标识，非认证凭证）
- 前端日志聚合（Sentry traceId 生成）
- A/B 测试分组（用户 ID MD5 取模分流）
- 开发者工具调试标记（Chrome DevTools 性能分析）

**降级条件：**
- 数据已公开或极低敏感度（公开资料目录索引）
- 仅用于性能优化非安全保证（布隆过滤器/哈希表）
- 历史兼容第三方接口强制要求 MD5（已申请迁移但对方未升级）
- 短生命周期临时数据（浏览器 sessionStorage 单次会话）
- 外层已有强加密保护（TLS 1.3 + HSTS + 证书钉扎）
- 攻击成本远高于资产价值（个人博客非商业系统）

**注意：** MD5 碰撞攻击已实用化（2^21 复杂度），浏览器 Web Crypto API 原生支持 SHA-256/SHA-512 且性能可接受。任何涉及身份认证、会话管理、API 签名的场景应立即迁移。前端密码哈希应使用 PBKDF2/bcrypt.js/scrypt.js 配合后端 KDF。Node.js 环境优先使用 `crypto.pbkdf2Sync()` 替代单轮 MD5。低风险评级不适用于 GDPR/PCI DSS/等保合规要求的系统。