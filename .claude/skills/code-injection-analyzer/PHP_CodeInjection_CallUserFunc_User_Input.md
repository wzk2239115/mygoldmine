# PHP call_user_func() 用户可控函数调用

## 基本信息

- **难度等级：** ★★★★☆ (高级)
- **审计时间：** 30-60分钟（含上下文追踪）
- **先决知识：** PHP 动态函数调用机制、回调函数、变量函数、序列化利用链
- **复杂度评估：**
  - 直接函数名可控：30-40分钟
  - 方法名可控（对象+方法）：40-50分钟
  - 序列化 + 魔术方法链：50-60分钟

## 🚀 30秒快速清单

- [ ] 代码中是否存在 `call_user_func()`、`call_user_func_array()`、`array_map()`、`usort()` 等动态调用函数？
- [ ] 第一个参数（函数名或回调）是否包含用户输入或用户可控数据？
- [ ] 该参数是否直接使用，还是经过了白名单验证或严格过滤？
- [ ] 是否使用了 `is_callable()` 进行验证（注意：此函数并不安全）？
- [ ] 对象方法调用中，对象和方法名是否都可控或部分可控？
- [ ] 是否存在反序列化操作，且反序列化数据中包含对象属性可被赋值？

**判断：** 如果第 1-2 个问题打勾且第 3 个未打勾，**必须进行 L3+ 深度分析**

## Details

### 漏洞成因
`call_user_func()` 允许动态调用任意 PHP 函数。如果函数名来自用户输入，攻击者可以指定要调用的任意内置函数或自定义函数。类似的危险函数包括 `call_user_func_array()`、`array_map()`、`array_filter()` 等。组合序列化反序列化和魔术方法，可以构造复杂的利用链。

### 代码示例

**易受攻击的代码：**
```php
// 场景 1：直接函数名可控
$action = $_GET['action'] ?? 'default';
$result = call_user_func($action, $data);

// 场景 2：方法名可控（对象调用）
$method = $_POST['method'] ?? 'get';
$user = new UserService();
call_user_func([$user, $method], $id);

// 场景 3：回调组件中的可控
$callbacks = [
    'process' => $_GET['processor']  // 用户输入
];
array_map($callbacks['process'], $items);

// 场景 4：反序列化 + 魔术方法链
$obj = unserialize($_POST['data']);
foreach ($obj->handlers as $handler) {
    call_user_func($handler);  // 触发 __invoke() 等
}
```

**安全示例：**
```php
// 方案 1：使用白名单
$allowedActions = ['list', 'create', 'update', 'delete'];
$action = $_GET['action'] ?? 'list';
if (!in_array($action, $allowedActions, true)) {
    throw new Exception('Invalid action');
}
$result = call_user_func([$this, $action], $data);

// 方案 2：直接分支
$method = $_POST['method'] ?? 'get';
switch ($method) {
    case 'create': return $this->create($id);
    case 'update': return $this->update($id);
    case 'delete': return $this->delete($id);
    default: throw new Exception('Unknown method');
}

// 方案 3：检查函数存在且在安全列表中
$function = $_GET['fn'] ?? '';
$safeFunctions = ['strlen', 'trim', 'strtoupper'];
if (!function_exists($function) || !in_array($function, $safeFunctions, true)) {
    throw new Exception('Unsafe function');
}
$result = call_user_func($function, $input);
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `call_user_func`, `call_user_func_array`, `array_map`, `array_filter`, `usort`, `uasort`, `array_walk`, `array_reduce`，结合 `$_GET`, `$_POST`, `$_REQUEST`, `unserialize`, `json_decode`。

**定位步骤：**
1. 全局搜索动态调用函数（call_user_func* 系列）；
2. 追踪第一个参数的来源，判断是否包含用户输入；
3. 快速检查是否存在白名单或严格验证（L2 跳读）。

#### 保护机制定位（审计等级：L2-L4）
**检查是否存在：**
- 显式的函数/方法名白名单（in_array 严格模式）；
- 基于反射的限制（如只允许类的公开方法）；
- 反序列化的 `allowed_classes` 限制；
- 使用 closure/匿名函数替代动态调用；
- 统一的回调注册表而非用户直接输入。

**定位技巧：**
- 逐行读（L3）：审查是否使用了 `is_callable()`（易被绕过）或更强的检查；
- 跨模块追踪（L4）：如果存在反序列化，追踪数据来源、反序列化前是否验证、自定义类中是否有魔术方法可被链式利用。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 动态调用使用严格白名单 | **L0（快速跳过）** | 风险低 |
| 使用 is_callable() 或部分验证 | **L2（跳读）** | 需检查规则完整性 |
| 直接传递用户输入到动态调用 | **L3（逐行读）** | 高风险，需复现 |
| 结合反序列化 + 自定义类 | **L4（跨模块追踪）** | 最高风险，需完整链分析 |

## Classify

### 研判标准

#### 确认漏洞
1. 函数名或方法名直接来自用户输入；
2. 无白名单验证或仅使用 `is_callable()` 等不充分验证；
3. 能够调用危险函数如 `system()`, `exec()`, `shell_exec()`, `passthru()` 等；
4. 对于对象方法调用，对象的属性或魔术方法可被控制。

#### 误报
1. 用户只能从预定义的闭包列表中选择；
2. 函数名经过白名单验证（in_array 严格模式）；
3. 虽然可控但该函数不涉及代码执行（仅数据处理）；
4. 动态调用的对象由框架或系统创建，用户无法构造恶意对象。

#### 代码异味
1. 使用 `is_callable()` 验证但无白名单限制；
2. 在日志、缓存中存储用户输入的回调名，后续反序列化后调用；
3. 虽有白名单但白名单范围过大（包含部分危险函数）；
4. 动态调用存在但被注释或标记 TODO，表明曾有漏洞关注；
5. 使用 `eval()` 解析用户输入后作为函数名。

## Low risk

### 低风险评级场景

#### 1. 白名单验证完整且严格
- 使用 `in_array($fn, ['func1', 'func2'], true)` 且列表中无危险函数；
- 可认定为低风险或无风险。

#### 2. 回调仅限内部系统创建
- 框架自身定义的回调（如 PSR-4 自动加载器中的 class_exists 回调）；
- 用户无法直接干涉回调名；
- 可评为低风险。

#### 3. 函数调用的入参已充分转义
- 虽然函数名可控，但其入参经过严格校验和转义；
- 调用的是 `strlen()`、`trim()` 等无副作用的函数；
- 可降级为低风险，但仍建议修复。

#### 4. 反序列化使用了 `allowed_classes` 限制
- `unserialize($data, ['allowed_classes' => ['SafeClass']])` 且 SafeClass 无危险魔术方法；
- 风险大幅降低，可评为低风险。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 存在严格白名单 | 调用限制完全 | 无 |
| 调用的都是安全函数 | 恶意使用难度大 | 低 |
| 内部系统可控 | 攻击面最小化 | 低 |
| 反序列化有限制 | 防止链式利用 | 低 |
