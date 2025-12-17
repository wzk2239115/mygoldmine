# Rust JWT Missing Validation

## Details

### 代码示例

**漏洞代码特征：**

```rust
use jsonwebtoken::{decode, decode_header, DecodingKey, Validation};

// 危险：使用默认Validation或未配置声明验证
let token_data = decode::<Claims>(
    &token,
    &DecodingKey::from_secret(secret.as_ref()),
    &Validation::default()  // 仅验证签名，不验证exp/iss/aud
)?;

// 危险：手动创建Validation但未启用关键声明检查
let mut validation = Validation::new(Algorithm::HS256);
// 缺失：validation.validate_exp = true;
// 缺失：validation.set_issuer(&["expected-issuer"]);
// 缺失：validation.set_audience(&["expected-audience"]);
let token_data = decode::<Claims>(&token, &key, &validation)?;

// 危险：显式关闭验证
let mut validation = Validation::new(Algorithm::HS256);
validation.validate_exp = false;  // 明确禁用过期检查
validation.insecure_disable_signature_validation();  // 极度危险
```

**安全代码特征：**

```rust
let mut validation = Validation::new(Algorithm::HS256);
validation.validate_exp = true;
validation.set_issuer(&["trusted-issuer"]);
validation.set_audience(&["my-service"]);
validation.leeway = 60;  // 允许60秒时钟偏移
let token_data = decode::<Claims>(&token, &key, &validation)?;
```

### 快速定位核心操作（审计等级：L1-L2）

**L1关键词扫描：**
- `decode<` - JWT解码入口
- `Validation::default()` - 危险默认配置
- `Validation::new(` - 需检查后续配置
- `validate_exp` - 过期时间验证开关
- `set_issuer` / `set_audience` - 声明校验方法
- `insecure_disable_signature_validation` - 极危险关键词

**L2跳读定位：**
1. 搜索所有`decode(`调用点
2. 向上追溯`Validation`对象的构造位置
3. 检查`validation.`开头的配置语句密度（少于3行配置通常有问题）
4. 关注`Validation::default()`直接使用场景

### 快速定位保护机制（审计等级：L2-L3）

**L2跳读检查点：**
- `validation.validate_exp = true` 是否存在
- `set_issuer` / `set_audience` / `set_required_spec_claims` 调用
- Claims结构体是否包含`exp: usize`字段定义
- 业务逻辑中是否有`claims.exp`的二次校验

**L3逐行验证：**
```rust
// 检查Claims结构是否声明必要字段
#[derive(Deserialize)]
struct Claims {
    sub: String,
    exp: usize,    // ✓ 必须有
    iss: String,   // ✓ 建议有
    aud: String,   // ✓ 建议有
}

// 验证配置完整性
let mut validation = Validation::new(algo);
validation.validate_exp = true;           // ✓ 必须
validation.set_issuer(&[expected_iss]);   // ✓ 强推荐
validation.set_audience(&[expected_aud]); // ✓ 强推荐
validation.leeway = 60;                   // ✓ 容错配置
```

**L4跨模块追踪：**
- 若`Validation`通过函数参数传入，需追踪调用链上游的构造点
- 检查配置文件/环境变量中的`VALIDATE_EXP`等开关
- 多租户场景需验证`iss`/`aud`是否动态获取且正确传递

---

## Classify

### 确认为漏洞的判定标准

1. **签名验证缺失** - 使用`insecure_disable_signature_validation()`或完全跳过解码验证
2. **过期不校验** - `validate_exp = false`且无业务层补偿校验
3. **issuer未校验** - 多方发行令牌场景下未配置`set_issuer`
4. **audience未校验** - 服务间共享密钥但未隔离受众
5. **关键Claims字段缺失** - Claims结构体未声明`exp`/`iss`等必要字段

### 归类为误报的场景

1. **内部令牌** - 完全内网环境且签发验证在同一可信进程
2. **二次校验** - `Validation`宽松但业务代码显式检查`claims.exp < now()`
3. **刷新令牌** - refresh token场景可能故意使用长期有效配置（需确认业务类型）
4. **测试代码** - 路径包含`test/`、`mock/`、`example/`

### 代码异味标记

1. `Validation::default()`频繁使用 - 配置集中度差
2. 硬编码`validate_exp = false` - 未提供配置化开关
3. 注释掉的验证配置 - `// validation.set_issuer(...)`
4. 空`iss`/`aud`配置 - `set_issuer(&[""])` 形同虚设

---

## Low Risk

### 降低风险等级的条件

1. **网络隔离** - 仅内网访问且有严格边界防护
2. **短有效期+业务校验** - token有效期≤5分钟且业务层验证时间戳
3. **单一签发方** - 无多租户，`iss`字段实际无意义
4. **补偿控制** - 通过API网关/中间件统一验证，应用层仅解码
5. **不可控外部令牌** - OAuth场景接收第三方token但无法要求对方修改声明
6. **只读操作** - 令牌仅用于查询非敏感数据，无写权限
7. **令牌类型特殊** - ID Token（仅用于身份展示）vs Access Token（需严格校验）

### 仍需关注的前置条件

即使评为低风险，需确认：
- 密钥管理无硬编码（另一独立漏洞）
- 签名算法固定为非`none`（防算法替换攻击）
- 无法通过`kid`头部注入（防密钥混淆）
- Claims字段类型匹配（防类型混淆攻击）