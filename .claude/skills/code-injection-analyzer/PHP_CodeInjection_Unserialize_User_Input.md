**PHP Unserialize User Input Code Injection**

使用 unserialize() 反序列化执行用户输入数据，可能导致任意代码执行（通过对象注入和魔术方法触发）。

## Details

### 代码示例与核心操作定位

```php
// 危险示例1：直接反序列化用户输入
$user_data = $_GET['data'];
$obj = unserialize($user_data);  // 核心危险操作

// 危险示例2：从文件/缓存读取且未验证来源
$cache_data = file_get_contents('/tmp/cache');
$result = unserialize($cache_data);  // 若缓存被污染则危险

// 危险示例3：使用options但保护不充分
$data = $_POST['serialized'];
$obj = unserialize($data, ['allowed_classes' => true]);  // 允许所有类，等同于无保护

// 安全示例：HMAC验证
$data = $_GET['data'];
$sig = $_GET['sig'];
if (hash_hmac('sha256', $data, SECRET_KEY) === $sig) {
    $obj = unserialize($data);  // 数据完整性已验证
}
```

### 快速定位核心操作技巧（L1: 关键词扫描）

**扫描重点**：
- **关键函数**：搜索 `unserialize()` 所有调用点
- **参数追踪**：检查参数是否包含 `$_GET`, `$_POST`, `$_REQUEST`, `$_COOKIE` 或直接使用用户输入变量
- **数据源**：`file_get_contents()`, `fread()`, `stream_get_contents()`, 数据库查询结果未验证的值
- **正则模式**：`unserialize\s*\(\s*\$` 快速锁定可疑调用

**L1 判断标准**：若 unserialize() 接收的参数能被追踪到用户输入，则进入 L2 评估。

### 快速定位保护机制技巧（L2-L4）

**L2 跳读**：检查 unserialize() 调用上下文的防护
- 检查函数调用前 2-5 行是否存在数据验证：`hash_hmac()`, `hash_equals()`, 签名验证
- 检查 unserialize() options 参数：是否设置了 `allowed_classes` 限制
- 检查是否使用了 `json_decode()` 等更安全的替代方案

**关键检查点**：
```php
// 防护等级1：有HMAC验证 - 相对安全
hash_hmac('sha256', $data, $key) === $signature

// 防护等级2：禁止对象反序列化 - 最安全
unserialize($data, ['allowed_classes' => false])

// 防护等级3：受限白名单 - 需进一步检查
unserialize($data, ['allowed_classes' => ['ClassName1', 'ClassName2']])

// 无防护 - 极度危险
unserialize($data)
unserialize($data, ['allowed_classes' => true])
```

**L3 逐行读**：深入评估保护层级
- **无防护**（unserialize($data) 或 allowed_classes => true）：直接升级为漏洞
- **HMAC防护**：检查密钥是否可预测、hash_equals() 是否正确使用（防时序攻击）
- **白名单防护**：进入 L4 追踪白名单中的类定义

**L4 跨模块追踪**（当发现 allowed_classes 白名单时）：
- 查找白名单中所有类的定义文件
- 检查这些类是否定义了 `__wakeup()`, `__destruct()`, `__toString()`, `__invoke()` 等魔术方法
- 追踪这些魔术方法的函数调用链，查找是否调用了：
  - 函数执行：`eval()`, `assert()`, `system()`, `exec()`, `shell_exec()`, `passthru()`, `proc_open()`
  - 对象属性动态调用：`call_user_func()`, `call_user_func_array()`
  - 文件操作：`include()`, `require()`, `file_get_contents()`, `fopen()`，若可写入恶意数据则危险
- 追踪 property hoisting：检查类属性是否在魔术方法中被无验证地使用
- 确认漏洞链是否完整可利用

## Classify

### 真实漏洞的充要条件

**必须同时满足**：
1. **存在反序列化危险点**：unserialize() 接收来自不可信来源的数据（用户输入、未验证的缓存/文件）
2. **未防护或防护不完整**：
   - 无 HMAC/签名验证，或
   - allowed_classes 未设置或设为 true，或
   - 白名单存在可利用的魔术方法链
3. **存在可利用的魔术方法链**：反序列化对象的魔术方法链最终触发 RCE、任意文件操作、信息泄露等危险操作

### 判断为误报的条件

**以下情况评为误报**：
1. **完整的 HMAC/签名验证**：
   - 使用 `hash_equals()` 进行常量时间比较
   - 密钥足够强大且存储安全
   - 序列化数据和签名一一对应

2. **严格的 allowed_classes 白名单**：
   - `allowed_classes => false`（完全禁止对象）
   - 或白名单仅包含经审计确认无危险魔术方法的类

3. **数据来源确实可信**：
   - 数据仅由系统内部生成且立即存储
   - 存储位置不可被外部访问或篡改
   - 数据流的每个环节都受到访问控制保护

4. **二次防护层**：
   - 反序列化后对对象属性进行严格类型验证
   - 检查对象状态是否符合预期

### 代码异味的判断

**标记为代码异味（非直接漏洞）**：
- 使用了 unserialize() 但数据来源不明确，需追踪上下文
- 白名单存在但包含过多类，难以完全审计其安全性
- 存在 unserialize() 但无明显防护机制（可能是隐晦的防护，需深入确认）

## Low risk

### 评级为低风险的场景

**以下情况可评为低风险**：

1. **完整的密钥型 HMAC 验证**
   - 使用 `hash_equals(hash_hmac('sha256', $data, $secret), $provided_sig)`
   - 密钥存储在环境变量或配置文件中，不可被用户控制
   - 该防护机制在 unserialize() 之前强制执行

2. **绝对禁止对象反序列化**
   - `unserialize($data, ['allowed_classes' => false])`
   - 确认数据结构中不包含 Object 对象，仅包含数组、字符串等基础类型

3. **受限且经审计的白名单**
   - allowed_classes 仅包含 3 个以内的类
   - 这些类不包含任何魔术方法或其魔术方法无副作用
   - 例如：只包含数据容器类，不包含业务逻辑类

4. **强制的二次验证**
   - 反序列化后立即进行严格的 instanceof 检查和属性验证
   - 例如：验证对象类型、属性数量、属性类型
   - 任何异常立即抛出异常或返回错误

5. **受信任的内部系统生成**
   - 数据仅来自系统内部的受控组件（如管理后台）
   - 该生成组件本身已验证无代码注入等漏洞
   - 数据存储在内部数据库，不可被客户端篡改

**降分建议**：即使满足上述条件之一，如果存在其他安全隐患（如 SQL 注入可污染缓存），仍需关注整体风险。
