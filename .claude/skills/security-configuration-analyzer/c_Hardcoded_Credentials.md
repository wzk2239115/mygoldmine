# C/C++ - Hardcoded Credentials

## Details

### 代码示例

```c
// 示例1: 硬编码数据库凭证
const char *db_password = "MyP@ssw0rd123";
mysql_real_connect(conn, "localhost", "root", db_password, "mydb", 0, NULL, 0);

// 示例2: 硬编码API密钥
#define API_KEY "sk_live_51H7x9y2eZvKYlo2C"
curl_setopt(curl, CURLOPT_HTTPHEADER, headers);

// 示例3: 硬编码加密密钥
unsigned char aes_key[] = {0x2b, 0x7e, 0x15, 0x16, 0x28, 0xae, 0xd2, 0xa6};
AES_set_encrypt_key(aes_key, 128, &enc_key);

// 示例4: 硬编码TLS证书密码
SSL_CTX_use_PrivateKey_file(ctx, "server.key", SSL_FILETYPE_PEM);
SSL_CTX_set_default_passwd_cb_userdata(ctx, (void*)"hardcoded_pass");

// 示例5: 硬编码SSH私钥路径及密码
ssh_options_set(session, SSH_OPTIONS_IDENTITY, "/root/.ssh/id_rsa");
ssh_userauth_password(session, "admin", "admin123");
```

### 快速定位核心操作（审计技巧）

**L1 - 关键词扫描：**
- 字符串字面量：`password`、`passwd`、`secret`、`token`、`api_key`、`private_key`、`credential`
- 函数调用：`*_connect()`、`*_auth()`、`SSL_CTX_*`、`ssh_*`、`mysql_*`、`curl_*`
- 宏定义：`#define SECRET`、`#define TOKEN`、`#define KEY`

**L2 - 跳读：**
- 全局变量/常量区：重点看 `const char*`、`static char[]`、`#define` 赋值
- 初始化函数：`init_*()`、`setup_*()`、`config_*()`、重点看参数传递
- 构造函数/析构函数：C++类初始化列表中的硬编码值

**L3 - 逐行读：**
- 字符串拼接：检查 `sprintf`、`snprintf`、`strcat` 是否拼接敏感字符串
- 指针赋值链：追踪 `char*` 指针的来源，确认是否来自字面量
- 条件判断：`strcmp(input, "hardcoded")` 形式的密码比对

**L4 - 跨模块追踪：**
- 头文件定义：检查 `.h` 中的 `#define` 宏定义是否被多处引用
- 静态库链接：关注第三方库初始化参数的来源
- 配置文件解析失败回退：当配置读取失败时是否使用硬编码默认值

### 快速定位保护机制（审计技巧）

**L1 - 关键词扫描：**
- 环境变量读取：`getenv()`、`secure_getenv()`
- 配置文件：`fopen()`、`read_config()`、路径包含 `.conf`、`.ini`、`.env`
- 密钥管理：`keyring_*`、`libsecret_*`、TPM相关API

**L2 - 跳读：**
- 检查字面量赋值前是否有环境变量/配置文件读取逻辑
- 查找 `if (!getenv("KEY"))` 类似的回退机制
- 确认是否存在密钥轮换或动态加载逻辑

**L3 - 逐行读：**
- 内存加密：检查敏感数据是否经过 `mlock()`、`memset_s()` 处理
- 权限检查：密钥文件读取前是否验证 `stat()` 权限位
- 混淆对抗：字符串是否经过简单异或/Base64（伪保护，仍属硬编码）

**L0 - 快速跳过：**
- 测试代码路径：`test/`、`mock/`、`example/` 目录
- 公开示例：README中的演示代码、注释中的伪代码

## Classify

### 确认为漏洞的判定标准：
- 生产环境代码中存在明文敏感凭证（密码、密钥、令牌）
- 凭证可直接用于访问受保护资源（数据库、API、加密数据）
- 无动态获取机制，硬编码为唯一来源
- 编译后二进制可通过 `strings` 命令提取

### 误报的常见场景：
- 示例代码、文档注释中的占位符（如 `"YOUR_PASSWORD_HERE"`）
- 测试套件中使用的Mock凭证，且测试环境与生产完全隔离
- 公开算法的标准测试向量（如AES-128的NIST标准测试密钥）
- 已废弃的代码路径（通过 `#ifdef DEPRECATED` 等条件编译排除）

### 代码异味的判定：
- 使用简单编码（Base64/XOR）"隐藏"凭证，实质仍为硬编码
- 凭证分片存储在多个源文件，通过拼接还原
- 开发环境默认凭证未通过编译选项区分生产环境
- 存在配置读取逻辑但失败后回退到硬编码值且无告警

### 研判流程：
1. 确认凭证真实性：是否为有效格式的密码/密钥/令牌
2. 评估作用域：通过符号表确认是 `static`（文件内）还是 `extern`（跨模块）
3. 检查生命周期：是否在编译时烧录到固件/嵌入式设备
4. 验证可达性：反编译确认字符串是否出现在 `.rodata` 段

## Low Risk

### 低风险场景评级标准：

**场景1：隔离环境的测试凭证**
- 仅用于单元测试或集成测试的Mock服务
- 凭证对应的资源不存在于生产网络
- 代码路径通过 `#ifdef TEST_BUILD` 明确隔离

**场景2：公开的非敏感标识**
- 公开API的免费服务层密钥（如地图SDK的公开Token）
- 开源项目中明确标注为示例的占位符凭证
- 加密算法的标准测试向量（可公开验证正确性）

**场景3：本地开发辅助**
- `localhost` 数据库的默认空密码（明确注释"仅限开发环境"）
- Docker Compose的默认凭证且服务仅绑定 `127.0.0.1`
- 配置文件模板（`.example` 后缀）中的占位值

**场景4：已失效的历史凭证**
- 代码考古发现的注释掉的旧凭证
- 提交历史中被删除的凭证（需确认已轮换）
- 文档中说明已废弃的API密钥

**评级降级条件（即使符合低风险也需提升等级）：**
- 凭证格式与生产凭证相同且未明确标注测试用途
- 嵌入式设备固件中的默认凭证（即使初始为低权限）
- 存在历史漏洞记录的同类硬编码问题
- 代码审计发现相同凭证在生产配置中复用