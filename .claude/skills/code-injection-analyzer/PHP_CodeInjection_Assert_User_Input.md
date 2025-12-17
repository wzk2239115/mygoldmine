# PHP assert() 代码注入漏洞审计指南

## 漏洞成因

PHP 的 `assert()` 函数在特定配置下可执行任意代码。当用户输入直接或间接传入 `assert()` 函数作为断言条件时，攻击者可利用 PHP 表达式语法注入恶意代码。此漏洞的根本原因在于 `assert()` 将其参数作为 PHP 代码进行评估（当 `assert.active=1` 且 `zend.assertions=1` 时）。

## Details

### 核心代码示例

**危险用法：**
```php
// 场景 1: 直接传入用户输入
$user_id = $_GET['id'];
assert($user_id > 0);  // 攻击: id=system('whoami')

// 场景 2: 拼接用户输入到断言表达式
$value = $_POST['value'];
assert("$value !== null");  // 攻击: value=1);system('rm -rf /');die('

// 场景 3: 间接传入（通过变量）
$condition = $_REQUEST['condition'];
assert(eval("return " . $condition));
```

**快速定位到核心操作的技巧（L1: 关键词扫描）**
- 搜索关键词：`assert(` 与用户输入数据源的关联
- 追踪数据流：从 `$_GET`、`$_POST`、`$_REQUEST`、`$_COOKIE` 等输入源到 `assert()` 的路径
- 识别标志：直接变量插值 `assert("$var")` 或字符串拼接 `assert($a . $b)`
- 配置检查：查阅 php.ini，确认 `assert.active`、`zend.assertions` 的状态

**快速定位到保护机制的技巧（L2: 跳读）**
- 数据验证：检查是否存在类型检查（如 `is_int()`、`is_numeric()`）或白名单验证
- 编码防护：查找 HTML/URL 编码、反序列化过滤等防御措施
- 沙箱隔离：检查是否启用了 `disable_functions` 或其他 PHP 安全模式限制
- 框架防护：若使用框架（Laravel/Symfony），查看是否通过 ORM/验证器进行了数据清理

### 审计等级划分

| 审计等级 | 适用场景 | 关键要点 |
|---------|--------|--------|
| **L0: 快速跳过** | assert() 仅用于开发调试且已禁用 | php.ini 中 `assert.active=0` 或 `zend.assertions=0` |
| **L1: 关键词扫描** | 代码存在 assert() 调用 | 扫描是否有 assert 与用户输入的直接接触 |
| **L2: 跳读** | assert() 接收动态数据，但有初步防护 | 审查数据流中是否有白名单、类型验证、编码过滤 |
| **L3: 逐行读** | assert() 与用户输入紧邻，存在拼接或变量插值 | 详细追踪每个变量的来源与转换流程 |
| **L4: 跨模块追踪** | 复杂场景下用户输入通过多层函数、类传递到 assert() | 追踪控制流与数据流跨越多个文件、类、函数 |

## Classify

### 判定为漏洞的条件

1. **直接代码执行路径**：用户输入可未经验证地到达 `assert()` 且 `assert.active=1` 或 `zend.assertions=1`
2. **表达式注入**：用户输入作为 PHP 表达式的一部分被解析执行
3. **运行环境风险**：服务器未禁用 assert 代码执行模式，且无沙箱约束

### 判定为误报的条件

1. **环境保护**：php.ini 中明确配置 `assert.active=0` 或 `zend.assertions=-1`，assert 仅用于扩展 E_WARNING
2. **类型约束**：变量通过严格的类型强制（如 `(int)$var`、`array_filter()` 配合 `is_int()`）
3. **范围限制**：assert 仅在完全可信的环境（如 CLI 脚本、内部测试工具）中使用，不接收网络输入

### 判定为代码异味的条件

1. **配置不当**：代码本身无法控制的配置问题（assert 虽启用但无用户输入接触）
2. **防御不完善**：存在某些防护但防护不充分（如只过滤 SQL 注入但未防止代码注入）
3. **设计缺陷**：虽未达到可利用漏洞级别，但使用模式不当

## Low risk

### 低风险评级的情形

1. **静态值或常量验证**
   - assert() 仅用于常量、编译时确定的值或硬编码的条件
   - 示例：`assert(PHP_VERSION_ID >= 70000)` 或 `assert(defined('MY_CONST'))`

2. **内部控制流验证**
   - assert() 用于验证内部函数返回值或不变量，而非外部输入
   - 示例：`assert($db->query($sql) !== false)` 在已验证 SQL 前提下

3. **已禁用的 assert 执行**
   - php.ini 配置 `assert.active=0`，assert 退化为标准 PHP 函数调用
   - 此时 assert() 仅返回布尔值，不执行代码

4. **严格的类型转换与白名单**
   - 输入经过 `(int)`、`(bool)` 等强类型转换
   - 输入与严格白名单对比（如 `in_array($id, $allowed_ids, true)`）

5. **隔离的开发环境**
   - assert() 仅在本地开发或 CI/CD 测试阶段使用
   - 生产环境明确禁用 assert 执行
