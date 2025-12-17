# JavaScript/TypeScript 自定义哈希函数审计

## Details

### 典型代码特征
```javascript
// 简单字符码累加"哈希"
function simpleHash(str) {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
        hash += str.charCodeAt(i);
    }
    return hash.toString();
}

// 位运算"混淆"函数
function customHash(password) {
    let h = 0;
    for (let i = 0; i < password.length; i++) {
        h = ((h << 5) - h) + password.charCodeAt(i);
        h = h & h;  // 转换为32位整数
    }
    return h.toString(16);
}

// XOR链式"加密"
function xorHash(input, salt = "mysecret") {
    let result = "";
    for (let i = 0; i < input.length; i++) {
        result += String.fromCharCode(input.charCodeAt(i) ^ salt.charCodeAt(i % salt.length));
    }
    return btoa(result);  // Base64编码误当加密
}

// 自定义"SHA256"替代
const mySecureHash = (data) => {
    return data.split('').reduce((acc, char) => {
        return ((acc << 7) + acc) ^ char.charCodeAt(0);
    }, 5381).toString(36);
};

// TypeScript自定义哈希类
class CustomHasher {
    private seed = 0x9e3779b9;
    
    hash(input: string): string {
        let h = this.seed;
        for (const c of input) {
            h ^= c.charCodeAt(0);
            h = Math.imul(h, 0x85ebca6b);
            h ^= h >>> 13;
        }
        return (h >>> 0).toString(16);
    }
}

// 组合Base64和反转充当"哈希"
function pseudoHash(str) {
    return btoa(str.split('').reverse().join(''));
}

// 取模运算"摘要"
const quickHash = (s) => {
    let h = 0;
    for (let i = 0; i < s.length; i++) {
        h = (h * 31 + s.charCodeAt(i)) % 100000;
    }
    return h;
};

// React组件中自定义哈希
const hashPassword = (pwd) => {
    return pwd.split('').map(c => 
        (c.charCodeAt(0) * 17 + 42).toString(16)
    ).join('-');
};

// Node.js后端自实现
function tokenHash(userId, timestamp) {
    const raw = `${userId}_${timestamp}_${SECRET_KEY}`;
    let hash = 0;
    for (let i = 0; i < raw.length; i++) {
        hash = ((hash << 5) + hash) + raw.charCodeAt(i);
    }
    return hash.toString(36);
}
```

### 快速定位核心操作（L1-L3）

**关键符号扫描（L1）：**
```bash
grep -rn "charCodeAt.*hash\|hashCode\|customHash" --include="*.js" --include="*.ts"
grep -rn "function.*[Hh]ash.*{" --include="*.js" --include="*.ts" | grep -v "crypto\|bcrypt\|pbkdf2"
grep -rn "btoa\|atob" --include="*.js" --include="*.ts"
grep -rn "toString(16)\|toString(36)" --include="*.js" | grep -v "Math.random\|Date"
grep -rn "\.reduce.*charCodeAt\|\.map.*charCodeAt" --include="*.js" --include="*.ts"
```

**高危API模式（L2 跳读）：**
- 自定义函数名包含 `hash` / `digest` / `checksum` 但不调用标准库
- `charCodeAt()` 结合 `for` 循环和位运算（`<<`, `^`, `&`, `|`）
- `btoa()` / `atob()` 用于"加密"而非编码（无crypto库配合）
- 累加/XOR操作后 `toString(16)` / `toString(36)` 作为"摘要"
- `reduce()` / `map()` 链式调用处理密码字段
- `Math.imul()` / `>>> 0` 等位运算模拟哈希
- 魔数特征：`0x9e3779b9` / `5381` / `31` 等常见哈希种子
- 无 `import crypto` / `require('crypto')` 但有哈希逻辑
- 密码/Token相关变量直接进入自定义函数

**函数调用链追踪（L3 逐行）：**
- 登录逻辑：`if (customHash(password) === user.passwordHash)`
- JWT签名：`const signature = myHash(header + payload + secret)`
- 密码存储：`user.password = simpleHash(rawPassword)` 插入数据库
- Token生成：`localStorage.setItem('token', customHash(userId))`
- API签名：`headers['X-Signature'] = hashFunc(body + apiKey)`
- 会话ID生成：`sessionId = quickHash(Date.now() + userId)`
- 配置引用：`hashFunction: config.security.customHasher`
- TypeScript类型：`type Hasher = (input: string) => string` 实现检查
- React Hook：`useMemo(() => hashPassword(pwd), [pwd])`

### 快速定位保护机制（L2-L4）

**无保护特征（L2 跳读）：**
- 哈希函数实现少于20行且仅用基础操作
- 无加盐参数：`hash(password)` 单参数签名
- 无迭代/工作因子：单次遍历字符串
- 注释显示 "simple hash" / "fast checksum"
- 直接比较输出：`===` / `==` 无时序安全比较
- 前端代码包含密码哈希逻辑（易逆向）

**伪保护识别（L3 逐行）：**
```javascript
// 加盐但算法过弱
function hashWithSalt(password, salt) {
    let h = 0;
    const combined = password + salt;
    for (let i = 0; i < combined.length; i++) {
        h = (h << 5) - h + combined.charCodeAt(i);
    }
    return h;  // 仍可暴力破解
}

// 多轮迭代但基数过低
function iterativeHash(input) {
    let hash = input;
    for (let i = 0; i < 100; i++) {  // 迭代数不足
        hash = customHash(hash);
    }
    return hash;
}

// Base64多次编码误当加密
function secureHash(pwd) {
    let encoded = btoa(pwd);
    for (let i = 0; i < 5; i++) {
        encoded = btoa(encoded);  // 仍可逆
    }
    return encoded;
}

// 前端"加密"传输
async function login(username, password) {
    const hashedPwd = customHash(password);  // 前端哈希可被绕过
    await fetch('/api/login', {
        body: JSON.stringify({ username, password: hashedPwd })
    });
}

// 误认为复杂度等于安全性
const complexButWeak = (s) => {
    return s.split('').map(c => c.charCodeAt(0))
           .reduce((a, b) => a ^ b)
           .toString(16).padStart(8, '0');  // 8位十六进制易碰撞
};
```

**跨模块保护追踪（L4）：**
- 依赖检查：`package.json` 是否缺少 `bcrypt` / `argon2` / `scrypt`
- 环境隔离：`NODE_ENV=production` 是否仍使用自定义哈希
- 中间件审计：认证中间件 `auth.middleware.ts` 哈希方法
- TypeScript类型：`@types` 定义是否约束为标准库类型
- 前后端一致性：前端哈希是否与后端验证匹配（双重弱点）
- 配置文件：`.env` 中 `HASH_ALGORITHM=custom` 配置项
- Webpack/构建产物：打包后是否暴露自定义哈希源码
- 测试覆盖：单元测试是否验证哈希碰撞抵抗能力
- ESLint规则：`.eslintrc` 是否配置禁止自定义密码哈希
- 日志审计：运行时日志 "using custom hash function" 警告

## Classify

**确认漏洞：**
- 密码存储使用自定义哈希（注册/修改密码逻辑）
- JWT/JWS签名用自定义摘要算法
- API签名验证（HMAC替代品）
- 会话令牌/CSRF Token生成
- 支付/交易签名计算
- OAuth state参数哈希
- 用户身份凭证派生（userId → token）
- Cookie签名/完整性校验
- 无标准库调用的任何密码学操作

**研判误报：**
- 非密码学用途：哈希表键生成（`Map` / `Set` 内部使用）
- 数据结构算法：快速查找/去重（非持久化）
- 调试/开发工具：生成唯一ID用于日志关联
- 测试代码：`*.test.js` / `*.spec.ts` 中Mock哈希
- 示例/教程代码：文档注释中演示哈希原理
- 已废弃代码：Git历史中已删除或标注 `@deprecated`
- 字符串处理：生成DOM元素ID（非安全边界）

**代码异味：**
- 注释 "temporary hash, use bcrypt later" 无迁移计划
- 开发环境用自定义哈希，生产环境 "应配置" 标准库
- 前端密码预哈希（即使后端再次bcrypt仍降低安全性）
- 函数命名误导：`secureSHA256()` 实际为简单位运算
- 性能理由：注释 "bcrypt too slow, use custom"
- 可配置但默认自定义：`hashAlgorithm: config.get('hash') || customHash`
- 部分用户迁移：新用户bcrypt，老用户仍用自定义哈希

**关键判断点：**
1. 哈希目标：密码/密钥/令牌 vs 数据结构内部ID
2. 调用位置：认证/授权逻辑 vs 工具函数
3. 存储时长：数据库持久化 vs 内存临时变量
4. 攻击面：前端可见/API暴露 vs 服务端内部
5. 替代方案：项目是否引入 `bcrypt` / `crypto` 但未使用

## Low risk

**可接受的低风险场景：**
- 内存缓存键生成（Redis key无需密码学强度）
- WebSocket消息去重ID（临时会话内标识）
- 日志追踪ID（仅用于快速检索非验证）
- 前端路由哈希（`#/page` URL片段生成）
- DOM元素唯一ID生成（避免冲突但无安全需求）
- 开发环境Mock数据（`NODE_ENV=development`）

**降级条件：**
- 数据完全随机且不可预测（UUID/Nonce后再哈希）
- 极短生命周期（单次请求内存变量 < 100ms）
- 无外部可观察性（完全内部逻辑无API暴露）
- 已有外层标准加密（TLS内部额外混淆非主保护）
- 碰撞不影响安全（仅性能退化如哈希表冲突）
- 明确非安全用途的工具函数（有文档说明）

**注意：** JavaScript环境下自定义哈希尤为危险，因为前端代码完全可见可逆向。即使后端再次验证，前端弱哈希仍可能被中间人攻击利用。任何密码/令牌处理应使用 Node.js `crypto.pbkdf2()` / `bcrypt` / `argon2`。前端不应进行密码哈希，应通过TLS直接传输明文密码至后端处理。自定义哈希通常基于Java `hashCode()` / C++ `std::hash` 等非密码学设计，输出空间小（32位）且无抗碰撞能力。低风险评级仅适用于明确的非安全场景，任何身份认证/授权相关均为高危。
