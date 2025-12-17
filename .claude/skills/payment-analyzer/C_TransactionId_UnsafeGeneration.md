# C_TransactionId_UnsafeGeneration

## Details

**核心漏洞特征**：C应用使用 `rand()`, `srand(time())` 等弱随机函数、本地时间、进程ID或其他低熵源生成交易ID，导致攻击者可预测或暴力枚举交易号，进行交易篡改、冒充。

**代码示例定位**：查找事务ID生成函数（常见命名：`generate_txn_id()`, `create_order_id()`, `make_transaction_id()`），关键词包括 `rand()`, `srand()`, `time()`, `sprintf`, `getpid()` 等。

**快速定位核心操作**（L1: 关键词扫描）：
- 搜索 `srand(time(NULL))` - 使用系统时间初始化随机数种子
- 搜索 `srand((unsigned)getpid())` - 使用进程ID作为种子
- 搜索 `rand() % bound` - 伪随机数模运算生成ID
- 搜索 `sprintf(txn_id, "%ld", (long)time())` - 直接格式化时间戳为ID
- 搜索 `strcpy` 或 `strcat` 用于ID拼接 - 缓冲区溢出风险

**快速定位保护机制**（L2: 跳读）：
- 检查是否使用操作系统提供的CSPRNG（`/dev/urandom`, `getrandom()`, `arc4random()`）
- 检查是否调用OpenSSL的 `RAND_bytes()` 或 `EVP_RAND_*()` 函数
- 检查是否有UUID生成库（`libuuid`, `uuid_t` 结构体）
- 检查ID生成后是否在数据库中验证唯一性（INSERT UNIQUE约束或SELECT检查）

## Classify

**漏洞判定标准**：
- 使用 `rand()` 或 `srand()` 生成交易ID → **漏洞**
- 直接使用 `time()` 作为交易ID或ID种子 → **漏洞**
- 使用 `getpid()`, `getuid()` 等系统调用作为ID源 → **漏洞**
- ID生成后无去重验证，允许重复 → **漏洞**
- ID存储于栈或全局变量，未初始化清零 → **漏洞+内存泄露**

**误报情况**：
- 使用 `arc4random()` (BSD) 或 `getrandom()` (Linux) + UUID库 → 低风险
- 调用OpenSSL的 `RAND_bytes()` 并检查返回值 → 低风险
- ID生成后通过数据库唯一约束或事务检查重复 → 低风险

**代码异味**：
- `rand()` 调用但无 `srand()` 初始化 → 审计
- 使用弱随机但有多层防护（时间戳+计数器+验证） → 审计
- 未显式检查 `RAND_bytes()` 的返回值 → 审计

## Low risk

**低风险评级条件**：
1. **强随机源**：使用 `arc4random()`, `getrandom()`, `RAND_bytes()` 等操作系统级CSPRNG
2. **充足熵**：至少128bit随机数（16字节），无可预测成分
3. **去重保障**：INSERT前或INSERT时使用数据库唯一约束（PRIMARY KEY或UNIQUE）
4. **内存安全**：ID缓冲区大小适当，无栈溢出或野指针；生成后及时清零敏感数据
5. **返回值检查**：随机数生成函数的返回值被检查，异常情况被正确处理
