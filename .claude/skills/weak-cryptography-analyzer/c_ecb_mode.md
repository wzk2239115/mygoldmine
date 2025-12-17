# C/C++ ECB 模式明文模式泄露审计

## Details

### 典型代码特征
```c
// OpenSSL EVP接口使用ECB模式
EVP_CIPHER_CTX *ctx = EVP_CIPHER_CTX_new();
EVP_EncryptInit_ex(ctx, EVP_aes_128_ecb(), NULL, key, NULL);
EVP_EncryptUpdate(ctx, out, &outlen, in, inlen);

// mbedTLS使用ECB
mbedtls_aes_context aes;
mbedtls_aes_setkey_enc(&aes, key, 256);
mbedtls_aes_crypt_ecb(&aes, MBEDTLS_AES_ENCRYPT, input, output);

// 传统DES ECB模式
DES_key_schedule schedule;
DES_ecb_encrypt(&input, &output, &schedule, DES_ENCRYPT);

// 显式配置ECB
const EVP_CIPHER *cipher = EVP_get_cipherbyname("AES-256-ECB");
EVP_CipherInit_ex(ctx, cipher, NULL, key, NULL, 1);
```

### 快速定位核心操作（L1-L3）

**关键符号扫描（L1）：**
```bash
grep -E "_ecb|ECB_|MBEDTLS.*ECB" *.c *.cpp
grep -E "EVP_[a-z0-9]+_ecb|crypt_ecb|NID_.*ecb" *.c
nm binary | grep -i "ecb_encrypt"
strings binary | grep -i "ecb\|electronic"
```

**高危API模式（L2 跳读）：**
- `EVP_aes_*_ecb()` / `EVP_des_ecb()` / `EVP_camellia_*_ecb()`
- `mbedtls_*_crypt_ecb()` 系列函数
- `DES_ecb_encrypt()` / `DES_ecb3_encrypt()`
- `EVP_get_cipherbyname("*-ECB")` 字符串配置
- `AES_ecb_encrypt()` OpenSSL底层接口（已废弃）
- 魔数特征：无IV参数 / `iv=NULL` / IV长度为0

**函数调用链追踪（L3 逐行）：**
- 定位 `EVP_CipherInit*` / `EVP_EncryptInit*` 第二参数cipher类型
- 检查IV参数：`EVP_EncryptInit_ex(ctx, cipher, NULL, key, NULL)` 最后为NULL
- 配置文件关键词：`mode: "ECB"` / `cipher_mode = 0` / `"AES-ECB"`
- 条件分支：`if(mode == MODE_ECB)` / `case CIPHER_MODE_ECB:`
- 函数指针表：`cipher_funcs[ECB_MODE] = aes_ecb_encrypt;`

### 快速定位保护机制（L2-L4）

**无保护特征（L2 跳读）：**
- 硬编码 `_ecb()` 函数无模式选择逻辑
- 初始化时直接跳过IV生成：`// IV not needed for ECB`
- 配置解析代码允许 `"ecb"` 关键词
- 无模式校验或安全策略检查

**伪保护识别（L3 逐行）：**
```c
// 误认为AES就是安全的（忽略模式问题）
if(use_strong_cipher) {
    ctx = EVP_aes_256_ecb();  // 强算法+弱模式仍不安全
}

// 性能优化导致的降级
if(data_size < 1024) {
    mode = ECB_MODE;  // 小数据量仍可能泄露模式
}

// 错误的IV省略逻辑
if(!iv_available) {
    cipher = EVP_aes_cbc();  // 应拒绝而非降级ECB
} else {
    cipher = EVP_aes_ecb();  // 逻辑错误
}
```

**跨模块保护追踪（L4）：**
- 检查算法白名单：`allowed_modes[]` 是否包含ECB
- 配置验证函数：`validate_cipher_mode()` 实现逻辑
- SSL/TLS套件：`SSL_CTX_set_cipher_list()` 是否排除ECB
- 依赖库编译选项：是否禁用ECB模式支持
- 上层框架过滤：ORM/序列化库的加密配置钩子
- 日志审计：搜索 "using ECB" / "mode=0" 的运行时记录

## Classify

**确认漏洞：**
- 加密结构化数据（数据库记录/配置文件/JSON）
- 图像/视频加密（经典ECB企鹅图案问题）
- 重复字段明文（用户列表/批量密码/固定格式协议）
- 长数据流分块加密（日志文件/网络传输）
- 无论数据内容是否敏感，模式泄露本身即为漏洞

**研判误报：**
- 单次加密单个随机块（如加密随机生成的单一密钥）
- 测试代码/性能基准对照组
- 仅用于密钥包装且每次密钥唯一（实际应用极少）
- 已废弃代码明确标注且编译时排除
- 教学示例代码演示ECB缺陷

**代码异味：**
- 注释"数据无重复可用ECB"（错误假设）
- 可配置模式但ECB为默认值
- 文档声称"性能优先"省略IV
- 仅在"调试模式"使用ECB（仍存在泄露风险）
- 对数据先压缩/编码后ECB加密（治标不治本）

**关键判断点：**
1. 数据特征：是否存在重复模式（固定头/周期性字段/相同记录）
2. 数据长度：是否超过单个块（AES 16字节，DES 8字节）
3. 业务场景：单次随机块 vs 批量结构化数据
4. 泄露影响：模式是否揭示敏感信息结构
5. 替代成本：切换CBC/GCM/CTR的实现难度

## Low risk

**可接受的低风险场景：**
- 加密单个16字节随机会话密钥（密钥包装场景且密钥不重复）
- 加密预加盐哈希值（SHA256输出已无模式特征）
- 一次性随机Nonce加密（长度≤单块且不重复）
- 测试桩/Mock对象（非实际执行路径）
- 已有应用层去重机制（数据加密前已随机化，实际极少见）

**降级条件：**
- 数据已充分随机化（HMAC/KDF输出且不含结构）
- 单块加密（长度严格≤16字节AES/8字节DES）
- 明文空间极大无碰撞（UUID/密钥材料）
- 外层有CBC/GCM封装（双层加密的内层，罕见架构）
- 攻击者无法观察多次加密输出（完全离线场景）

**注意：** ECB模式在绝大多数场景下不应被使用，即使数据"看似随机"也可能存在隐藏模式。强烈建议统一使用 CBC/GCM/CTR 等带IV的模式。低风险评级仅适用于严格单块随机数据的极端场景。
