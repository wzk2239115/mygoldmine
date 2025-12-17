# TypeScript/JavaScript - Math.random() 生成密钥/令牌

## Details

### 代码特征
```typescript
// 典型场景1: 生成 API Token
const token = Math.random().toString(36).substring(2);
const apiKey = Math.random().toString(36) + Math.random().toString(36);

// 典型场景2: 生成会话ID/密钥
const sessionId = `sess_${Math.random().toString(16).slice(2)}`;
const encKey = Array.from({length: 16}, () => Math.floor(Math.random() * 256));

// 典型场景3: 作为加密种子
const seed = Math.random() * 0xFFFFFFFF;
crypto.createCipheriv('aes-128-cbc', generateKey(seed), iv);

// 典型场景4: UUID/GUID 生成
const uuid = 'xxxx-4xxx-yxxx'.replace(/[xy]/g, c => 
  (c === 'x' ? Math.random() * 16 : (Math.random() * 4 + 8)).toString(16)
);
```

### 快速定位核心操作（L1-L2）
**L1 关键词扫描**：`Math.random()` + `token|key|secret|session|uuid|guid|nonce|salt` 组合出现  
**L2 跳读重点**：检查 `.toString(36|16)` `.substring()` `Array.from()` 等链式调用，确认生成结果用途（变量命名、后续传递）  
**特殊模式**：`Math.floor(Math.random() * 256)` 字节数组生成、`Date.now() + Math.random()` 时间戳混合

### 快速定位保护机制（L2-L3）
**L2 跳读检查**：向上追溯是否存在 `crypto.randomBytes()` `window.crypto.getRandomValues()` `uuid.v4()` 等安全替代  
**L3 逐行验证**：检查条件分支 `if (crypto.randomBytes)` 或环境判断 `process.env.NODE_ENV === 'development'`，确认 Math.random() 是否仅用于测试/开发环境  
**降级场景**：查找 try-catch 块，确认是否为 crypto API 不可用时的 fallback（真实漏洞）

## Classify

### 真实漏洞
- **生产环境使用**：无条件使用 Math.random() 生成 token/key/session，无环境判断
- **安全凭证生成**：用于认证令牌、API 密钥、密码重置令牌、OTP、加密密钥材料
- **缺失安全降级**：作为唯一随机源，无 crypto 模块兜底

### 误报
- **测试/Mock 数据**：位于 `__tests__` `fixtures` `mock` 目录，或函数名含 `mock` `fake` `stub`
- **非安全场景**：生成 UI 临时 ID（`tmp_${Math.random()}`）、随机颜色、动画延迟、随机排序
- **已有保护**：条件判断确保仅在开发环境使用，生产环境强制使用 crypto API

### 代码异味
- **过度设计**：非安全场景使用 crypto API（如随机 CSS 类名）
- **文档缺失**：使用 Math.random() 但无注释说明为何不需要密码学安全性
- **混合使用**：同一模块既有 crypto.randomBytes 又有 Math.random()，职责不清晰

## Low Risk

### 低风险情形
- **辅助字段**：用于生成日志追踪 ID、调试标识符、非敏感缓存键（无认证/授权逻辑依赖）
- **客户端临时数据**：前端组件内部状态 key、请求去重标识（后端有独立验证）
- **已废弃代码**：注释标记为 deprecated、TODO 待替换，且无调用引用
- **双重验证场景**：生成的 token 需后端二次校验真实性（如需数据库匹配），随机性弱化不直接导致权限绕过
- **有限生命周期**：生成值仅在内存中存活秒级（如防抖 ID），攻击时间窗口极短且无持久化