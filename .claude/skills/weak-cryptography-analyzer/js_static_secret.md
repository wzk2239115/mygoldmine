# JavaScript/TypeScript 静态密钥硬编码 (Static Secret Hardcoding)

## Details

### 典型代码示例

在前端加密传输、后端服务认证、数据库连接等场景中硬编码的密钥，包括 API Key、JWT Secret、数据库密码、加密密钥、令牌等。

```javascript
// 场景1: API 密钥硬编码
const API_KEY = "sk_live_abc123def456789xyz";
const SECRET_KEY = "your-secret-key-12345";

// 场景2: JWT 签名密钥硬编码
const JWT_SECRET = "my-jwt-secret-key-super-secret";
const token = jwt.sign({ userId: 123 }, JWT_SECRET);

// 场景3: 对称加密密钥硬编码
const encryptionKey = "1234567890abcdef1234567890abcdef";
const cipher = crypto.createCipher('aes-256-cbc', encryptionKey);

// 场景4: 数据库连接字符串中的密码
const DB_URL = "mongodb://username:hardcoded_password@localhost:27017/dbname";

// 场景5: IV/Nonce 固定
const IV = "0123456789abcdef";
const cipheriv = crypto.createCipheriv('aes-256-cbc', key, Buffer.from(IV, 'hex'));

// 场景6: 加密 Cookie 密钥硬编码
app.use(express.session({ secret: "session-secret-key-12345" }));

// 场景7: HMAC 签名密钥硬编码
const HMAC_SECRET = "fixed-hmac-key-for-signing";
crypto.createHmac('sha256', HMAC_SECRET).update(payload).digest('hex');

// 场景8: 密钥派生盐值固定
const SALT = "fixed-salt-value-not-random";
crypto.pbkdf2Sync(password, SALT, 10000, 32, 'sha256');

// 场景9: 环境变量兜底值为硬编码
const API_SECRET = process.env.API_SECRET || "hardcoded-fallback-secret";

// 场景10: TypeScript 配置对象中的密钥
const config = {
    apiKey: "hardcoded-api-key",
    jwtSecret: "jwt-secret-in-config"
};

// 场景11: 类属性默认密钥
class CryptoService {
    private secret = "hardcoded-class-secret";
}

// 场景12: OAuth/OIDC 客户端密钥硬编码
const OAUTH_SECRET = "oauth2-client-secret-xyz";

// 场景13: 外部服务 Token 硬编码
const GITHUB_TOKEN = "ghp_abc123def456ghi789jkl012mnopqr";

// 场景14: WebSocket 认证令牌硬编码
const WS_TOKEN = "websocket-auth-token-hardcoded";

// 场景15: 多密钥密钥库硬编码
const KEYRING = {
    encryption: "encryption-key-abc123",
    signing: "signing-key-def456"
};
```

### 快速定位核心操作 (L1-L3)

**L1 - 关键词扫描：**
搜索 `const.*[Kk]ey\s*=|const.*[Ss]ecret\s*=|const.*[Pp]assword|Bearer\s*['\"]|apiKey|jwt.*=|HMAC|OAuth|Token.*=.*"|encryptionKey|IV.*=|SALT` 等关键词

**L2 - 跳读文件与常量区：**
- 检查 `.js|.ts|.jsx|.tsx` 文件顶部的 const/var/let 声明
- 导入相关库后立即检查：`crypto|jwt|axios|fetch|mongoose|pg`
- 全局变量声明和配置对象初始化：`const config = { ... }`
- 环境变量使用与兜底：`process.env.XXX || "hardcoded"`
- 查找 `process.env|import.meta.env` 以确认密钥是否从环境变量读取

**L3 - 逐行审计高危函数调用：**
- `jwt.sign(claims, secret)` → 追溯 secret 来源是否为常量
- `crypto.createCipher|createDecipher|createCipheriv(algorithm, key, iv)` → 检查 key 和 iv 来源
- `crypto.createHmac(algorithm, secret)` → 检查 secret 是否硬编码
- `crypto.pbkdf2Sync(password, salt, iterations, len, digest)` → 检查 salt 是否为固定值
- `CryptoJS.AES.encrypt(plaintext, key)` → 检查 key 来源
- `mongoose.connect|new MongoClient|pg.connect` → 检查连接字符串中的凭证
- `express.session({ secret: ... })` → 检查 session secret 来源
- `fetch|axios|httpClient` 请求头认证信息 → 检查 token/key 是否硬编码

### 快速定位保护机制 (L2-L4)

**L2 - 跳读配置加载逻辑：**
- 查找 `require('dotenv')|import dotenv|config()` → 确认 .env 文件加载机制
- 查找 `fs.readFile|fs.readFileSync|path.resolve` 配合 `.env|.key|.pem` 文件
- 条件逻辑 `if (process.env.NODE_ENV === 'production')` → 区分环境处理

**L3 - 逐行检查密钥管理模式：**
- 导入密钥管理服务：`aws-sdk|azure-keyvault|@google-cloud/secret-manager|vault`
- 函数调用 `secretsManager.getSecret|kms.decrypt|vault.read` → 动态获取密钥
- 入口文件（`index.js|app.js|main.ts`）的初始化逻辑
- 错误处理：`process.on('uncaughtException')|throw new Error` 缺少密钥时的容错

**L4 - 跨模块追踪密钥流转：**
- 定位全局变量或 config 模块初始化 → 追踪赋值链路
- 检查 `src/config|src/constants|src/secrets` 目录中的密钥管理
- 分析编译条件标志 `NODE_ENV|isDev|process.env.ENVIRONMENT`
- 检查 `docker-compose.yml|kubernetes|.env.example` 了解部署时密钥配置
- 检查构建配置 `webpack.DefinePlugin|rollup.define` 是否替换环境变量
- 追踪密钥在模块间的传递链路：`module.exports|export default|import`
- 检查版本历史确认是否存在泄露的密钥记录

---

## Classify

### 确认为漏洞

- 生产代码（非测试文件）中密钥字符串直接写死在源码中
- 密钥长度和格式符合实际使用标准（API Key ≥ 32 字符，JWT Secret ≥ 32 字节）
- 密钥被实际用于敏感操作（加密、签名、API 认证、数据库连接）
- 密钥在版本控制历史中可追溯
- 代码已合并到主分支
- 同一密钥或其变体多次出现 → 表明非随机生成而是手工硬编码

### 判定为误报

- 密钥仅存在于测试文件（`*.test.js|*.spec.ts|__tests__|test/`）且数据为测试专用
- 明显的示例值（`"example-secret"|"changeme"|"demo-key"|"xxx"`）
- `.env.example` 中的占位符，README 明确说明需修改
- 注释标注 `// DEMO|// Test only|// Example`
- 密钥长度过短（3-5 字符）明显用于演示
- 文档示例代码（`docs/|examples/|tutorial/`）且有替换说明
- 开发专用标记：`// +build dev|NODE_ENV === 'development'|if (isDev)`
- RFC 标准文档中的测试向量

### 归类为代码异味

- **环境变量兜底**：`process.env.KEY || "fallback"` → 需确认生产环境变量已配置
- **脱敏前缀**：仅保留密钥协议前缀如 `"sk_live_"` → 确认完整密钥不在代码中
- **TODO 注释**：`// TODO: Use env variable` → 检查是否有追踪计划
- **非生产分支**：密钥仅在 `dev|demo|staging` 分支 → 确认主分支已删除
- **临时标记**：`// Temporary for testing` → 若未被 merge 则为代码异味，已 merge 则为漏洞
- **配置默认值可覆盖**：构造函数有默认密钥但应用传入真实值 → 需确认所有实例化点

---

## Low Risk

以下场景可评为低风险，但仍需标注为改进建议：

1. **演示/示例代码**
   位于 `examples/|docs/|demo/` 目录，README 或注释明确说明需替换，且无生产用途。

2. **本地开发环境专用**
   明确的开发环境限制如 `if (process.env.NODE_ENV !== 'production') { hardcoded_key }`，且生产环境使用环境变量覆盖。

3. **单元测试 Mock 密钥**
   测试文件中的 fixture 或 Mock 数据，确认该文件不被包含在生产构建中。

4. **已轮换的历史密钥**
   Git 历史中的密钥已被轮换，注释标注了轮换日期和新密钥位置。

5. **公开文档的测试密钥**
   官方 SDK 文档中的测试专用密钥（如 Stripe test key），明确标注为测试且无实际权限。

6. **占位符模板变量**
   代码中的参数化占位符在实际部署时被替换，非运行时的实际密钥值。

7. **非安全上下文密钥**
   用于本地缓存加密、开发数据混淆等非关键场景，泄露不导致业务风险。

8. **环境隔离的临时密钥**
   CI/CD 环境或 Docker 测试容器中的临时密钥，无法访问生产网络。

**判定依据**：结合代码注释、部署文档、Git 历史、环境配置模板综合评估实际暴露风险。