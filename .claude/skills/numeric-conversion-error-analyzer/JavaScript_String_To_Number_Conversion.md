# JavaScript_String_To_Number_Conversion

**漏洞类型**: 字符串到数字的转换，字符串转换为数字时的隐式转换导致的逻辑错误

**漏洞成因**

JavaScript 中字符串转数字时，存在隐式类型转换宽松的特性，导致：

- 字符串前导/尾随空格被忽略，可能绕过验证
- 十六进制字符串（"0xFF"）在某些场景被正确解析，其他场景则失败
- 空字符串转换为 0，可能导致值验证失败
- 非数字字符串转换为 NaN，后续逻辑未检查
- 字符串包含多余字符时隐式强制转换行为不一致
- 指数表示法（"1e10"）的隐式转换可能导致大数值误解
- parseInt/parseFloat 的基数未明确指定导致解析错误
- 转换后的数字用于关键操作（索引、权限检查、缓冲区大小），无验证

---

## Details

### 代码示例

**危险模式1：字符串空格被忽略的验证绕过**
```javascript
function validateUserId(user_id) {
    const blocked_users = [1, 2, 3];
    const id = Number(user_id);  // "  2  " → 2
    return !blocked_users.includes(id);
}

console.log(validateUserId("  2  "));  // true，空格被忽略，被阻用户通过验证
```

**危险模式2：十六进制字符串解析不一致**
```javascript
function parseConfig(value) {
    const num = Number(value);  // "0xFF" → NaN（Number 不识别 0x）
    if (num > 100) {
        grant_admin();
    }
}

console.log(parseConfig("0xFF"));  // NaN > 100 = false，权限检查失败
```

**危险模式3：空字符串转为零的逻辑错误**
```javascript
function processAmount(amount_str) {
    const amount = Number(amount_str);  // "" → 0
    if (amount) {
        transfer_money(amount);
    }
}

processAmount("");  // 0 转 false，不执行，但可能不是预期
```

**危险模式4：NaN 未被检查导致计算错误**
```javascript
function calculateDiscount(discount_str) {
    const discount = parseFloat(discount_str);  // "abc" → NaN
    const price = 100 * (1 - discount);  // 100 * (1 - NaN) = NaN
    return price;  // NaN
}

calculateDiscount("abc");  // 返回 NaN
```

**危险模式5：parseInt 无基数导致解析错误**
```javascript
function parsePermissionLevel(level) {
    const num = parseInt(level);  // "08" 可能被当作八进制 → 0
    if (num >= 5) {
        grant_access();
    }
}

console.log(parseInt("08"));     // 8（现代浏览器）或其他值（不同环境）
```

**危险模式6：指数表示法的大数误解**
```javascript
function validateFileSize(size_str) {
    const size = Number(size_str);  // "1e10" → 10000000000
    if (size < 1000000) {
        save_file(size);
    }
}

validateFileSize("1e10");  // 1e10 = 10 billion，超限却被接受
```

**危险模式7：字符串作为数组索引转换**
```javascript
function getConfig(config, key) {
    const index = Number(key);  // "3.9" → 3.9，浮点索引
    return config[index];  // config[3.9] 寻找不存在的键
}

getConfig([1, 2, 3, 4], "3.9");  // undefined
```

**危险模式8：用户输入字符串的符号位变化**
```javascript
function allocateBuffer(size_str) {
    const size = Number(size_str);  // "-100" → -100
    const buffer = Buffer.alloc(size);  // 负数，可能分配异常大小
    return buffer;
}

allocateBuffer("-100");  // 负数转换，可能导致异常
```

### 快速定位核心操作 **[L1-L2]**

**关键词扫描:**
- 隐式转换：`value + 0`、`+value`、`value * 1` 字符串隐式转数字
- 显式转换：`Number(string)`、`parseInt(string)`、`parseFloat(string)`
- 字符串来源：用户输入、URL 参数、API 响应、JSON 数据
- 转换后用途：数组索引、权限检查、缓冲区大小、数学运算
- 对象/JSON 转换：`JSON.parse()`、`Number(jsonField)` 等
- 比较操作：`string > 100`、`string <= 50` 隐式转换
- 条件检查：`if (Number(str))` 判断 NaN/0

**快速定位保护机制 [L2-L3]**
- 转换前是否检查字符串格式：`/^\d+$/.test(str)` 等正则
- 是否指定 parseInt 的基数：`parseInt(str, 10)`
- 转换后是否检查 NaN：`!Number.isNaN(num)` 或 `!isNaN(num)`
- 是否验证转换后的值范围：`if (num >= MIN && num <= MAX)`
- 是否剔除前导/尾随空格后再转换
- 是否使用 `Number.isSafeInteger()` 验证整数范围
- 是否显式处理 Infinity：`if (!Number.isFinite(num))`
- 是否使用 TypeScript 类型检查

---

## Classify

**研判为真漏洞的特征：**

1. 字符串直接转数字用于关键操作（索引、权限检查、内存分配），无验证
2. 转换后未检查 NaN 或 Infinity，直接用于计算
3. parseInt 未指定基数，导致不同环境解析不一致
4. 字符串前导/尾随空格被隐式忽略，可能绕过验证
5. 用户输入字符串直接转数字，无格式验证
6. 负数/超大数字转换后未检查，导致异常分配或计算

**误报/代码异味的特征：**
- 转换前通过正则验证字符串格式
- 转换后明确检查 NaN 和 Infinity
- parseInt 显式指定基数：`parseInt(str, 10)`
- 转换值在使用前进行范围检查
- 来自内部常量或受控数据源
- 使用 TypeScript 类型提示强制检查

---

## Low risk

**以下场景可评为低风险：**

1. **完整的格式验证**
   - 转换前通过正则验证：`/^\d+$/.test(str)` 或 `/^0x[0-9a-f]+$/i.test(str)`
   - 验证范围：`if (num >= MIN && num <= MAX)`
   - 检查特殊值：`if (!Number.isFinite(num)) return error`

2. **明确的转换参数**
   - parseInt 指定基数：`parseInt(str, 10)` 或 `parseInt(str, 16)`
   - 有注释说明转换意图和预期范围

3. **内部受控数据**
   - 字符串来自内部常量或固定数据，格式已知
   - 如：循环计数器、预定义配置值

4. **安全的使用场景**
   - 转换后的数字仅用于日志、统计、显示
   - 不用于数组索引、内存操作、权限检查

5. **完整的错误处理**
   - 转换失败时有明确的错误路径
   - NaN/Infinity 被显式处理并拒绝

