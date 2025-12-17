# C/C++ DES 弱加密算法审计

## Details

### 典型代码特征
```c
// OpenSSL EVP接口使用DES
EVP_CIPHER_CTX *ctx = EVP_CIPHER_CTX_new();
EVP_EncryptInit_ex(ctx, EVP_des_cbc(), NULL, key, iv);
EVP_EncryptUpdate(ctx, out, &outlen, in, inlen);

// OpenSSL 传统DES接口
DES_key_schedule schedule;
DES_cblock key = {0x01, 0x23, 0x45, 0x67, 0x89, 0xAB, 0xCD, 0xEF};
DES_set_key_unchecked(&key, &schedule);
DES_ecb_encrypt(&input, &output, &schedule, DES_ENCRYPT);

// 3DES仍使用DES原语
DES_ede3_cbc_encrypt(in, out, len, &ks1, &ks2, &ks3, &iv, DES_ENCRYPT);

// mbedTLS使用DES
mbedtls_des_context des;
mbedtls_des_setkey_enc(&des, key);
mbedtls_des_crypt_ecb(&des, input, output);
```

### 快速定位核心操作（L1-L3）

**关键符号扫描（L1）：**
```bash
grep -E "EVP_des|DES_|MBEDTLS_DES|des_|EVP_DES" *.c *.cpp
grep -E "NID_des|EVP_CIPHER.*des" *.c
nm binary | grep -i "des_encrypt"
```

**高危API模式（L2 跳读）：**
- `EVP_des_cbc()` / `EVP_des_ecb()` / `EVP_des_cfb()`
- `DES_set_key*()` / `DES_ecb_encrypt()` / `DES_cbc_encrypt()`
- `DES_ede3_*()` 3DES系列（56位密钥强度×3仍不足）
- `MBEDTLS_CIPHER_DES_*` 宏定义
- 魔数：密钥长度 8字节 / `DES_KEY_SZ`

**函数调用链追踪（L3 逐行）：**
- 定位 `EVP_EncryptInit*` 第二参数：必须检查cipher类型
- 配置文件/宏定义：`CIPHER_ALG "DES"` / `USE_DES 1`
- 条件编译：`#ifdef LEGACY_CRYPTO` 包含DES调用
- 函数指针赋值：`cipher_func = DES_encrypt;`

### 快速定位保护机制（L2-L4）

**无保护特征（L2 跳读）：**
- 直接硬编码 `EVP_des_*()` 无动态选择逻辑
- 初始化代码无版本检查或弱算法警告
- 配置文件允许列表包含 `"des"` / `"des3"`

**伪保护识别（L3 逐行）：**
```c
// 3DES仍基于DES核心（有效密钥强度112位，不足128位标准）
if(security_level > 1) {
    cipher = EVP_des_ede3_cbc();  // 仍是弱算法
}

// 配置降级逻辑
if(!EVP_aes_available()) {
    fallback_to_des();  // 危险的降级路径
}
```

**跨模块保护追踪（L4）：**
- 检查 OpenSSL 编译选项：`openssl ciphers -v | grep DES`
- 确认是否禁用：`OPENSSL_NO_DES` 宏 / `no-des` 编译参数
- 运行时检查：`SSL_CTX_set_cipher_list(ctx, "!DES:!3DES")`
- 配置文件审计：`ssl_ciphers` 是否排除DES套件
- 依赖库版本：旧版本（OpenSSL < 1.1.0）默认启用DES

## Classify

**确认漏洞：**
- 加密传输敏感数据（网络通信/文件传输）
- 保护身份凭证（密码/令牌/会话密钥）
- TLS/SSL 握手允许DES密码套件
- 存储加密的密钥派生使用DES
- 无替代算法的强制DES实现

**研判误报：**
- 仅兼容性测试代码（单元测试/互操作性验证）
- 已废弃代码路径（明确标注deprecated且默认禁用）
- 仅用于解密历史遗留数据（只读模式，新数据用强算法）
- 文档示例/教学代码（非生产环境）
- 条件编译已排除（`#if 0` / `#ifdef NEVER_DEFINED`）

**代码异味：**
- 可配置但默认DES（应默认强算法）
- 日志显示"使用DES（临时）"无迁移计划
- 3DES作为"安全"升级（应直接AES-256）
- 算法协商中DES优先级过高
- 注释"TODO: 替换为AES"但未实施

**关键判断点：**
1. 加密目标：测试数据 vs 生产敏感数据
2. 调用时机：系统初始化 vs 实际业务逻辑
3. 替代方案：是否存在AES/ChaCha20并行实现
4. 生命周期：活跃维护 vs 遗留兼容代码
5. 攻击面：内部组件 vs 外部暴露接口

## Low risk

**可接受的低风险场景：**
- 解密10年前归档数据（一次性迁移任务，非常驻服务）
- 与遗留硬件互操作（对方仅支持DES且物理隔离）
- 开发环境快速原型（明确标注非生产代码）
- 性能基准测试对照组（比较加密开销）
- 已有外层强加密的二次混淆（纵深防御非主保护）

**降级条件：**
- 数据已公开或低敏感度（非PII/认证信息）
- 短期过渡方案有明确迁移时间表
- 访问受严格物理/网络隔离（air-gapped环境）
- 仅向后兼容读取，所有写入已用强算法
- 攻击窗口极短（临时会话密钥 < 1分钟有效期）

**注意：** DES 56位密钥可在数小时内暴力破解（现代硬件），任何生产环境应立即计划迁移至 AES-256/ChaCha20。低风险评级不代表接受长期使用。
