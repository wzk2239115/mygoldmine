# PHP JWT 未校验声明 (Claim Not Checked)

## Details

### 代码示例

```php
// 漏洞示例1：仅验证签名，不验证声明
use Firebase\JWT\JWT;
use Firebase\JWT\Key;

$decoded = JWT::decode($token, new Key($secret, 'HS256'));
// 仅验证签名有效，未检查 exp/nbf/aud 等声明
$userId = $decoded->user_id;
// 直接使用，允许过期或时间未到的 token

// 漏洞示例2：手动解析但遗漏关键声明
$payload = JWT::decode($token, new Key($secret, 'HS256'));
if ($payload->iss === 'trusted-issuer') {
    // 仅验证 iss，忽略 exp/nbf/aud
    doSensitiveAction($payload->sub);
}

// 漏洞示例3：禁用自动验证
JWT::$leeway = 0;
$decoded = JWT::decode($token, new Key($secret, 'HS256'));
// 未手动调用 nbf_claim/exp_claim/aud_claim 验证
```

### 快速定位核心操作 【审计等级：L1-L2】

**L1 关键词扫描：**
- `JWT::decode()` - JWT 解析入口
- `JWT::encode()` - Token 生成点
- `$decoded->` - Claims 访问点
- `jwt_decode()` / `jwt_get_payload()` - 原生扩展函数

**L2 跳读审计路径：**
1. 定位 `JWT::decode()` 调用点
2. 检查 decode 后是否访问 `exp`/`nbf`/`aud`/`iat` 字段
3. 确认是否使用 `property_exists()` 或 `isset()` 检查关键声明
4. 观察业务逻辑是否直接使用 claims 进行授权决策

### 快速定位保护机制 【审计等级：L3-L4】

**L3 逐行读防护特征：**
- **时间声明验证：**
  - 检查 `$payload->exp` 与 `time()` 比较
  - 使用 `JWT::$leeway` 设置时间容差（需确认未过大）
  - 第三方库如 `firebase/php-jwt` v6+ 自动验证 exp/nbf
  
- **受众声明验证：**
  - 手动比对 `$payload->aud` 与预期值
  - 检查 `in_array()` 或 `===` 严格比较
  
- **其他关键声明：**
  - `iss` (签发者) / `sub` (主题) 验证
  - 自定义 claims 如 `roles`/`permissions` 的存在性检查

**L4 跨模块追踪检查点：**
1. JWT 中间件/拦截器是否统一验证声明
2. 配置文件是否定义 `required_claims` 清单
3. 是否存在独立的 `validateClaims()` 函数但未被调用
4. 不同路由/控制器是否遗漏调用验证逻辑
5. 自定义 JWT 处理类是否覆盖默认验证行为

## Classify

**判定为漏洞：**
- JWT 解析后直接使用 payload 数据，未验证 `exp` 过期时间
- 接受 `nbf` (not before) 未生效的 token 执行敏感操作
- 未校验 `aud` (audience) 导致 token 跨服务滥用
- 缺少 `iat` (issued at) 检查允许重放旧 token
- 可通过提交过期/无效声明的 token 绕过认证/授权

**判定为误报：**
- Token 仅用于公开 API 的非敏感数据传递
- 业务层通过 Redis/Memcached 实现 token 黑名单或会话管理
- 使用短期 token (≤5分钟) + refresh token 机制且后端有额外校验
- Token 由网关层统一验证声明，应用层仅解析使用
- 测试/示例代码或明确标注为调试用途

**代码异味识别：**
- 注释显示"临时跳过 exp 验证"但存在于生产代码
- 部分路由验证声明，部分路由遗漏（不一致）
- 过期时间设置过长（>24 小时）削弱时效性保护
- 使用 `@` 错误抑制符隐藏声明不存在的警告
- 混用多个 JWT 库导致验证行为不一致

## Low risk

**低风险场景评定：**

1. **仅内部服务调用**
   - JWT 用于内网微服务间短期通信（<5 分钟）
   - 服务间通过 VPC/防火墙隔离，外部无法访问
   - 有额外的服务认证机制（如 mTLS）

2. **只读操作授权**
   - Token 仅授权查询公开数据或用户自身信息
   - 不涉及状态变更、权限提升、敏感数据访问
   - 即使声明失效，业务影响有限

3. **双因素/多重验证兜底**
   - 解析 token 后，敏感操作仍需二次验证（OTP、密码确认）
   - 关键操作绑定设备指纹或生物识别
   - 支付/提现等高风险操作有独立验证流程

4. **有效期极短**
   - Token 过期时间 ≤ 60 秒
   - 攻击窗口期极小，且有速率限制防止暴力重放

5. **补偿性控制**
   - 已实现 IP 白名单、地理位置限制
   - 异常登录检测系统（如设备变更、异地登录告警）
   - 实时监控与告警机制，可快速响应异常 token 使用

**注意：** 即使低风险，仍应标记为缺陷建议修复。JWT 声明验证是基线安全要求，遗漏可能导致未来业务变更时引入高危漏洞。
