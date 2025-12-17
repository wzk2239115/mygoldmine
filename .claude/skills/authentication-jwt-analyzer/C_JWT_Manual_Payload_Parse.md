# C/C++ JWT 手动解析 Payload 跳过签名校验

## Details

### 代码示例

**典型漏洞模式：**
```c
// 危险：直接 base64 解码 payload 部分
char* token = "eyJ...header.eyJ...payload.signature";
char* payload = strchr(token, '.') + 1;
char* payload_end = strchr(payload, '.');
*payload_end = '\0';

// 直接解码 payload，完全跳过签名验证
char decoded[1024];
base64_decode(payload, decoded);
json_parse(decoded);  // 直接信任内容

// 或使用 JSON 库手动解析
cJSON* json = cJSON_Parse(decoded);
const char* user_id = cJSON_GetObjectItem(json, "sub")->valuestring;
```

**常见库的不安全用法：**
```cpp
// jwt-cpp 不当使用
auto decoded = jwt::decode(token);  // 仅解码，未验证
auto claims = decoded.get_payload_claims();  // 直接使用未验证数据

// libjwt 跳过验证
jwt_t* jwt;
jwt_decode(&jwt, token, NULL, 0);  // key=NULL, key_len=0 跳过验证
const char* sub = jwt_get_grant(jwt, "sub");
```

### 快速定位核心操作 【审计等级：L2-L3】

**L2 跳读关键点：**
- 搜索字符串操作：`strchr(token, '.')` / `strtok(token, ".")`
- Base64 解码函数：`base64_decode` / `EVP_DecodeBlock` / `BIO_read`
- JSON 解析：`cJSON_Parse` / `json_tokener_parse` / `rapidjson::Document`
- JWT 库解码：`jwt_decode` / `jwt::decode` / `JWT::decode`

**L3 逐行研判标志：**
- 分离 token 三段后仅处理前两段（header+payload）
- Base64 解码后直接进入业务逻辑（未见签名验证）
- 从 payload 提取 claims 直接用于授权决策
- 解码函数参数为 NULL/0（key 参数缺失）

### 快速定位保护机制 【审计等级：L3-L4】

**L3 函数内验证：**
- HMAC 计算：`HMAC(EVP_sha256(), key, ...)` 后与签名比对
- RSA 验证：`EVP_DigestVerifyFinal` / `RSA_verify`
- 库验证方法：`jwt_verify` / `verify()` / `validate()`
- 完整性检查：重新计算签名并使用 `memcmp` / `CRYPTO_memcmp`

**L4 跨模块追踪：**
- JWT 处理函数是否调用独立的 `validate_token()` 函数
- 中间件/拦截器是否在解码前强制验证
- 配置文件/全局变量是否禁用验证（`verify_signature = false`）
- 依赖函数返回值检查（返回 bool 的验证函数是否被忽略）

## Classify

**判定为漏洞：**
- JWT 字符串分割+Base64 解码+直接使用 payload 数据进行授权/认证决策
- 调用解码 API 但明确跳过签名验证参数（key=NULL 或 verify=false）
- 解码后未见任何 HMAC/RSA 验证逻辑即使用 claims
- 在数据流中，token payload 直达业务逻辑，签名部分被丢弃

**判定为误报：**
- 解码后的数据仅用于日志记录/调试输出（非信任场景）
- 代码位于测试/示例目录（test/examples/demo）
- 解码操作后紧接着调用验证函数（需确认调用链完整）
- payload 数据仅用于非敏感提示（如显示用户名），核心授权另有验证

**代码异味（需进一步确认）：**
- 手动实现 JWT 解析而非使用成熟库（易出错）
- 验证逻辑与解码逻辑跨多个文件分离（追踪困难）
- 条件编译下某些分支跳过验证（DEBUG/TESTING 宏）
- try-catch 捕获验证异常但未正确处理（吞异常）

## Low risk

**满足以下条件可降低风险评级：**

1. **非信任边界场景**
   - Token 来源为内部服务，调用链在可信网络内（仍需提示风险）
   - 仅用于解析自签 token 的 metadata（如日志追踪 ID）

2. **后续二次验证**
   - 解码后数据经过数据库/缓存二次校验（session 比对）
   - Claims 中关键字段（如 user_id）需额外认证确认

3. **受限影响范围**
   - 解码数据仅用于只读查询，无写/删/改权限
   - 业务逻辑有额外权限检查层（RBAC/ABAC）

4. **临时/调试代码**
   - 代码注释标记为"TODO: 添加验证"且在非生产分支
   - 明确的功能开关控制，默认关闭该代码路径

**注意：** 即使低风险，仍应标记为缺陷，建议加固。JWT 签名验证是基线安全要求。
