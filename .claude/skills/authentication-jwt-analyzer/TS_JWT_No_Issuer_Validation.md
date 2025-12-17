# JWT Issuer 验证缺失 (TypeScript/JavaScript)

## Details

### 代码示例
```typescript
// 有漏洞：未验证 issuer
jwt.verify(token, secret);
jwt.verify(token, secret, { algorithms: ['RS256'] });

// 有漏洞：验证配置中缺少 issuer
const decoded = jwt.verify(token, publicKey, { 
  algorithms: ['RS256'],
  audience: 'myapp'
});

// 安全：正确验证 issuer
jwt.verify(token, secret, { 
  issuer: 'https://trusted-auth.example.com',
  algorithms: ['RS256'] 
});
```

### 快速定位核心操作技巧 (L1-L2)
- **L1 关键词扫描**：搜索 `jwt.verify(`, `jsonwebtoken.verify(`, `.decode(`, `jwt.decode(`
- **L2 跳读**：定位 JWT 库验证入口点，目标库包括：`jsonwebtoken`, `jose`, `njwt`, `express-jwt`
- 重点关注认证中间件、API 鉴权函数、Token 解析逻辑

### 快速定位保护机制技巧 (L2-L3)
- **L2 跳读**：检查 `verify` 第三参数（options 对象）是否存在 `issuer` 或 `iss` 字段
- **L3 逐行读**：确认 issuer 值是否为硬编码的可信域名（非变量传入或从 Token 中提取）
- **L3 逐行读**：检查是否使用 `{ complete: true }` 获取 header 后再手动验证 issuer（容易绕过）
- **审计陷阱**：部分项目在 `decode()` 后才验证，但 `decode` 不验证签名，无意义

## Classify

### 漏洞研判标准
- **确认漏洞**：多租户系统/联合身份场景中，缺少 issuer 验证，攻击者可伪造受信第三方 Token
- **确认漏洞**：验证逻辑中仅校验签名和过期时间，未限制 Token 来源
- **误报**：单一授权服务器场景，且通过其他机制（如独立密钥、数据库白名单）已隐式验证来源
- **代码异味**：虽未验证 issuer，但业务架构保证仅有一个签发方，且密钥未泄露风险极低

### 关键判断点
1. 是否存在多个可信的 JWT 签发源（多租户/SSO/联合认证）
2. 攻击者是否可获取任意合法签发方的有效 Token 用于跨域攻击
3. 相同密钥是否被多个服务共享（增加伪造风险）

## Low risk

### 低风险场景
1. **架构限制**：整个系统仅有唯一的内部授权服务，且使用专用密钥对（密钥轮换机制完善）
2. **网络隔离**：Token 验证服务与签发服务在同一内网段，外部无法注入第三方 Token
3. **已有补偿控制**：验证后通过数据库白名单二次确认用户来源或权限（非依赖 Token 声明）
4. **非敏感操作**：Token 仅用于只读资源访问，无法触发状态变更或敏感数据泄露

## 审计专业技巧

### 1. Issuer 验证缺失的真实威胁场景

#### 多租户系统中的跨租户攻击
```typescript
// ✗ 真实漏洞 - 多租户 SSO 场景
const middleware = (req, res, next) => {
  const token = req.headers.authorization?.split(' ')[1];

  // 仅验证签名和过期时间，未验证 issuer
  const decoded = jwt.verify(token, publicKey, {
    algorithms: ['RS256']
    // ❌ 缺少 issuer 验证
  });

  // 直接使用 Token 中的租户 ID
  const tenantId = decoded.iss;  // 攻击者可声称任意租户身份
  req.userId = decoded.sub;
  next();
};
```

**攻击场景**：
- 攻击者获取 TenantA 的有效 Token（通过社工或已知员工身份）
- 修改 Token 的 `iss` 声明为 TenantB（需要重新签名，但如果使用共享密钥则可能成功）
- 若 issuer 未验证，系统将错误地认为该 Token 来自可信的 TenantB 签发方

#### 第三方 OAuth/SAML 集成中的身份伪造
```typescript
// ✗ 真实漏洞 - OAuth 多源验证场景
const validateExternalToken = (token) => {
  // 来自多个外部 IdP（Google, Microsoft, GitHub 等）
  // 如果不验证 issuer，攻击者可用非预期来源的签名 Token

  try {
    const decoded = jwt.verify(token, externalPublicKey, {
      algorithms: ['RS256', 'HS256']  // 多算法支持，但未限制来源
    });
    return decoded;
  } catch (e) {
    return null;
  }
};

// 正确的做法
const validateOAuthToken = (token, expectedIssuer) => {
  const decoded = jwt.verify(token, getPublicKeyForIssuer(expectedIssuer), {
    algorithms: ['RS256'],
    issuer: expectedIssuer,  // ✓ 必须指定预期的签发方
    audience: 'my-app'
  });
  return decoded;
};
```

### 2. 真实漏洞 vs 误报的关键区分

#### 误报场景一：单一可信签发方的明确架构
```typescript
// ✓ 这不是漏洞 - 单一签发源，已通过其他机制验证
const verifyInternalToken = (token) => {
  // 系统设计保证：仅有内部 AuthService 签发 Token
  // Token 通过 HTTPS + mTLS 传输（无中间人风险）
  const decoded = jwt.verify(token, INTERNAL_SECRET, {
    algorithms: ['HS256']
  });

  // 额外补偿控制：Token 中的 userId 必须在数据库中存在且未被禁用
  const user = db.users.findById(decoded.sub);
  if (!user || user.isDisabled) throw new Error('Invalid user');

  return decoded;
};
```

**为什么不是漏洞**：
- 架构保证仅有一个签发源
- 既然已通过其他机制验证来源，缺少 issuer 字段的风险很低
- Token 仅在受控的内部网络中流转

#### 误报场景二：验证逻辑分离但仍有保护
```typescript
// ✓ 这不是漏洞 - issuer 在外层验证
class TokenValidator {
  // 先在上层验证 Token 的来源
  validateTokenSource(token) {
    const decoded = jwt.decode(token, { complete: true });
    const issuer = decoded.payload.iss;

    // 检查 issuer 是否在白名单中
    if (!ALLOWED_ISSUERS.includes(issuer)) {
      throw new Error('Untrusted issuer');
    }
    return issuer;
  }

  // 再进行签名验证
  verifySignature(token, issuer) {
    const publicKey = this.getPublicKeyForIssuer(issuer);
    return jwt.verify(token, publicKey, {
      algorithms: ['RS256']
      // issuer 已在上层检查，这里可以省略
    });
  }
}
```

**为什么不是漏洞**：
- issuer 验证存在，只是位置不同
- 两步验证都已实现，防护是完整的

#### 真实漏洞场景一：多来源且无 issuer 验证
```typescript
// ✗ 真实漏洞 - 必须立即标记
class MultiProviderAuth {
  verifyToken(token) {
    // 尝试用多个密钥验证，谁成功就信谁
    const publicKeys = [
      this.googlePublicKey,
      this.githubPublicKey,
      this.internalAuthPublicKey
    ];

    for (const key of publicKeys) {
      try {
        const decoded = jwt.verify(token, key, {
          algorithms: ['RS256']
          // ❌ 未验证 issuer - 无法确认 Token 真正来自哪个提供商
        });

        // 危险：无法判断该 Token 的真实来源
        return decoded;
      } catch (e) {
        // 继续尝试下一个密钥
      }
    }
  }
}

// 攻击场景：
// 1. 攻击者从 GitHub OAuth 获取有效 Token
// 2. 将其 issuer 修改为 'internal-auth'（使用该来源的公钥签名可能重复或泄露）
// 3. 系统无法区分真实来源，错误地信任它
```

#### 真实漏洞场景二：audience 验证但缺少 issuer 验证
```typescript
// ✗ 真实漏洞 - 部分验证，但不完整
const middleware = (req, res, next) => {
  const token = req.headers.authorization?.split(' ')[1];

  const decoded = jwt.verify(token, publicKey, {
    algorithms: ['RS256'],
    audience: 'myapp'  // ✓ 验证了 audience
    // ❌ 但缺少 issuer 验证
  });

  // 风险：攻击者可能用其他系统签发的 Token（audience 相同但来源不同）
  req.user = decoded;
  next();
};
```

### 3. 审计检查清单

| 检查项目 | 真实漏洞表现 | 正常防御表现 |
|---------|-----------|-----------|
| issuer 字段 | `verify()` 的 options 中缺少 `issuer` | 显式指定 `issuer: '预期值'` |
| 多签发源场景 | 无法区分不同来源的 Token | 为每个来源指定不同的 issuer 和密钥 |
| 验证顺序 | 签名验证后才检查 issuer（太晚） | 通过 options 在验证时同步检查 |
| 架构设计 | 支持动态 issuer（从 Token 中读取） | issuer 值写死或从配置读取（不变） |
| 补偿控制 | 仅依赖 Token 声明判断身份 | Token 验证后还有数据库二次确认 |

### 4. 审计工程化方法

#### 第一步：快速过滤（低代价）
```bash
# 搜索所有 JWT 验证点
grep -r "jwt.verify\|jsonwebtoken.verify" --include="*.ts" --include="*.js"

# 搜索已知防御模式
grep -r "issuer:" --include="*.ts" --include="*.js"
```

#### 第二步：上下文分析（中代价）
对每个 `verify()` 调用：
1. 检查第三参数 options 对象
2. 查找 `issuer` 字段
3. 若没有，查看是否有多个签发源
4. 确认 issuer 值是硬编码还是可变的

#### 第三步：确认漏洞可利用性（高代价）
- 在多租户/多源场景中：尝试用一个来源的 Token 冒充另一个来源
- 在 OAuth 场景中：混用不同提供商的 Token 验证结果
- 检查是否能通过修改 `iss` 声明实现越权

### 5. 实战经验

#### 高频误报原因
1. **验证逻辑分离**：issuer 检查在中间件或上层完成，不在 verify() 调用处
2. **架构单一性**：确实只有一个签发源，多余的 issuer 验证
3. **使用 decode() 后再手工验证**：逻辑虽然分散，但覆盖了 issuer 检查

#### 高确信度的真实漏洞特征
- 支持多个 JWT 签发源（OAuth/SAML 集成或多租户），但没有 issuer 验证
- 无法通过代码追踪找到 issuer 验证逻辑（即使分散）
- Token 中的 `iss` 声明被直接用于业务逻辑（如确定用户归属租户）
- 验证后直接使用 Token 声明，无数据库二次确认

#### 典型的真实漏洞审计确认过程
1. 搜索 `jwt.verify(` 找所有验证点
2. 逐一检查 options 对象，统计缺少 `issuer` 的调用
3. 对于缺少的验证点，检查：
   - 是否支持多个签发源？（多源 = 高风险）
   - 是否有其他地方验证了 issuer？（分散 = 中风险）
   - Token 声明是否直接用于授权决策？（直接使用 = 高风险）
4. 若同时满足多源、无验证、直接使用，判定为**确实漏洞**