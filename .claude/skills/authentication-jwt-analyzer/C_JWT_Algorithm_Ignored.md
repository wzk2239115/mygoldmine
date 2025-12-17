# C/C++ JWT 解析忽略算法字段

## Details

### 代码示例

**典型漏洞模式：**
```c
// 危险：忽略 header.alg 字段，硬编码验证算法
char* token = "eyJhbGc...header.eyJzdWI...payload.signature";
char* header = get_jwt_header(token);  
char* payload = get_jwt_payload(token);
char* signature = get_jwt_signature(token);

// 错误：未从 header 读取 alg，直接用固定算法验证
verify_with_hmac_sha256(payload, signature, secret);  // 攻击者可修改 header.alg="none"
```

**算法混淆攻击：**
```cpp
// 危险：HMAC/RSA 算法混用漏洞
jwt_t* jwt;
jwt_decode(&jwt, token, (unsigned char*)rsa_public_key, 0);

// 若 header.alg 被篡改为 "HS256"，将 RSA 公钥当 HMAC 密钥使用
// 攻击者可用公钥作为 HMAC 密钥重签 token
```

**无算法白名单：**
```c
// 危险：接受任意算法
cJSON* header_json = parse_jwt_header(token);
const char* alg = cJSON_GetObjectItem(header_json, "alg")->valuestring;

// 未验证 alg 是否在允许列表中，可接受 "none"/"HS256" 等非预期算法
if (strcmp(alg, "none") == 0) {
    return SKIP_SIGNATURE_VERIFY;  // 允许 none 算法
}
```

### 快速定位核心操作 【审计等级：L2-L3】

**L2 跳读关键点：**
- 搜索 JWT 解析函数：`jwt_decode` / `jwt::decode` / `JWT_decode`
- 算法提取：`cJSON_GetObjectItem(header, "alg")` / `header["alg"]`
- 签名验证：`HMAC` / `RSA_verify` / `EVP_DigestVerify` / `jwt_verify`
- 算法字段检索：`grep -r "\"alg\"" --include="*.c" --include="*.cpp"`

**L3 逐行研判标志：**
- Header 中 `alg` 字段被提取但未做白名单验证
- 直接使用硬编码算法（如 `EVP_sha256()`）而不依据 header.alg 动态选择
- 验证函数参数不包含算法类型检查（仅传入 key/token）
- 允许 "none" 算法存在（`strcmp(alg, "none") == 0` 后跳过验证）
- HMAC/RSA 密钥混用（未区分对称/非对称算法类型）

### 快速定位保护机制 【审计等级：L3-L4】

**L3 函数内验证：**
- 算法白名单：`if (strcmp(alg, "HS256") == 0 || strcmp(alg, "RS256") == 0)`
- 拒绝 none 算法：`if (strcmp(alg, "none") == 0) return ERROR;`
- 算法类型检查：`is_hmac_algorithm(alg)` / `is_rsa_algorithm(alg)`
- 密钥类型匹配：验证 RSA 算法时检查 `key_type == KEY_TYPE_RSA`

**L4 跨模块追踪：**
- 配置文件定义 `allowed_algorithms = ["RS256", "ES256"]`
- 全局验证中间件调用 `validate_jwt_algorithm(token)` 
- 初始化时注册算法过滤器：`jwt_set_alg_whitelist()`
- 密钥管理模块区分对称/非对称密钥存储（防混淆攻击）
- 检查 JWT 库版本是否默认禁用 none 算法

## Classify

**判定为漏洞：**
- 解析 JWT 时未从 header 中读取并验证 `alg` 字段
- 硬编码验证算法，不依据 token header 动态匹配算法与密钥类型
- 允许 "none" 算法且跳过签名验证
- 未实现算法白名单，接受任意 header.alg 值
- 存在 HMAC/RSA 算法混淆：对称密钥算法可使用公钥、或反之

**判定为误报：**
- 代码仅解析 alg 字段用于日志/监控，验证逻辑在其他模块且已正确实现
- 测试代码/示例代码明确标记非生产环境使用
- Header.alg 被提取后立即与配置中的单一强制算法比对（如仅允许 RS256）
- 使用成熟库（如 jwt-cpp latest）且未覆盖默认安全配置

**代码异味（需进一步确认）：**
- 手动实现 JWT 算法选择逻辑而非使用库的安全 API
- 算法验证依赖环境变量/可修改配置文件（可能运行时被篡改）
- 条件编译允许 DEBUG 模式下接受 none 算法
- 算法白名单仅检查前缀（如只判断 "HS" 而非完整算法名）
- 错误处理不当：算法不匹配时仅记录警告但仍继续验证

## Low risk

**满足以下条件可降低风险评级：**

1. **强制单一算法场景**
   - 系统架构明确规定仅使用单一算法（如全局仅 RS256）
   - 验证逻辑忽略 header.alg，强制用配置算法验证（但应明确拒绝 none）

2. **多层验证机制**
   - Token 经过网关/代理预验证，确保 alg 字段符合要求后才到达应用
   - 业务逻辑对 JWT claims 进行二次数据库校验

3. **受限密钥访问**
   - 签名密钥在硬件安全模块（HSM）/密钥管理服务（KMS）中
   - 非对称算法场景下，私钥完全隔离，公钥篡改无法伪造签名

4. **非认证关键路径**
   - Token 仅用于只读审计日志/统计分析
   - Claims 数据不影响授权决策，仅作展示用途

**注意：** 即使低风险，仍应要求：
- 明确拒绝 "none" 算法
- 实现算法白名单（即使只有一个元素）
- 区分 HMAC/RSA 密钥类型以防混淆攻击
- 遵循最小权限原则，header.alg 应被强制校验