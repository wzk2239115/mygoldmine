# JavaScript_Bitwise_Type_Conversion

**漏洞类型**: 位运算类型转换，位运算导致的 32 位整数转换

**JavaScript/TypeScript**

JavaScript/TypeScript 中数值类型转换错误常见于字符串到数字转换、位运算类型转换、TypedArray 操作、BigInt 使用等场景。JavaScript 使用双精度浮点数表示数字，但在位运算、TypedArray、BigInt 等场景中可能出现类型转换问题，导致精度丢失、溢出等安全问题。

**漏洞成因**

位运算在 JavaScript 中会将操作数强制转换为 32 位有符号整数，这种隐式转换可能导致：

- 超出 32 位范围的数字截断或溢出
- 浮点数转为整数时的精度丢失
- 负数的补码表示导致符号位反转
- 无符号右移 `>>>` 与有符号右移 `>>` 的行为差异
- 字符串作为位运算操作数的隐式强制转换
- 位运算结果用于数组索引、权限检查等关键操作
- NaN/Infinity 在位运算中被转为 0
- 用户输入经位运算后符号反转或范围改变

---

## Details

### 代码示例

**危险模式1：超大数字位运算后溢出**
```javascript
function validateId(id) {
    const MAX_ID = 0x7FFFFFFF;  // 2^31 - 1
    if ((id | 0) > MAX_ID) {    // 位运算强制转 32 位有符号整数
        return false;  // 超出范围的数字可能变成负数
    }
    return true;
}

console.log(validateId(0x80000000));  // (0x80000000 | 0) = -2147483648
```

**危险模式2：字符串位运算导致意外转换**
```javascript
function processPermission(perm_str) {
    const mask = perm_str & 0xFF;  // "128" & 0xFF → 128
    if (mask >= 64) {
        grant_access();
    }
}

console.log(processPermission("999"));  // "999" 被隐式转为 999，& 0xFF → 231
```

**危险模式3：浮点数位运算精度丢失**
```javascript
function calculateOffset(offset) {
    const aligned = (offset + 7) >> 3;  // 浮点数会被截断
    return buffer.slice(aligned);
}

calculateOffset(3.9);  // (3.9 + 7) >> 3 = 10 >> 3 = 1，小数部分丢失
```

**危险模式4：无符号右移导致符号翻转**
```javascript
function getUserRole(role_bits) {
    const high = role_bits >>> 16;  // 无符号右移
    if (high === 0xFFFF) {
        set_admin();
    }
}

console.log(getUserRole(-1 >>> 16));  // -1 >>> 16 = 65535，符号位处理差异
```

**危险模式5：NaN 位运算转 0 的验证绕过**
```javascript
function validateSize(size) {
    const aligned = (size | 0);  // NaN | 0 = 0
    if (aligned > 0) {
        allocate_memory(aligned);
    }
}

validateSize(NaN);  // NaN | 0 = 0，绕过验证
```

**危险模式6：位运算用于数组索引计算**
```javascript
function getArrayElement(arr, idx) {
    const safe_idx = idx & 0xFF;  // 限制在 0-255
    return arr[safe_idx];
}

console.log(getArrayElement([1,2,3], -1 & 0xFF));  // -1 & 0xFF = 255
```

**危险模式7：多次位运算导致值改变**
```javascript
function checkPermissions(user_id, permissions) {
    const mask = (user_id >> 8) & 0xFF;  // 多层位运算
    if ((permissions & mask) !== 0) {
        grant_access();
    }
}

checkPermissions(0x80000001, 0x01);  // 大数字右移后截断为 32 位
```

**危险模式8：Infinity 位运算转 0**
```javascript
function processValue(val) {
    const processed = (val | 0);  // Infinity | 0 = 0
    return process_data(processed);
}

processValue(Infinity);  // Infinity | 0 = 0
```

### 快速定位核心操作 **[L1:关键词扫描]**

**关键词扫描:**
- 位运算符：`|`、`&`、`^`、`~`、`<<`、`>>`、`>>>`
- 位运算方式：`(value | 0)`, `(value & 0xFF)`, `(value >> shift)`, `(value << 1)`
- 操作数来源：用户输入、URL 参数、JSON 数据、API 响应
- 位运算用途：`value | 0`, `value >>> 0`, `(value >> N) & 0xFF`, `(value << N) & MASK`
- 位运算后的使用：数组索引、权限检查、内存操作、密码学操作
- Math 函数前的位转换：`Math.floor(val | 0)`
- 缓冲区/TypedArray 操作中的位移：`buffer[idx >> 2]`, `(offset << 2)`

**快速定位保护机制 [L2:跳读]**
- 位运算前是否检查数字范围：`if (val >= MIN && val <= MAX)`
- 是否验证操作数类型：`typeof val === 'number'` 或 `Number.isInteger(val)`
- 是否检查特殊值：`if (!Number.isFinite(val))` 或 `if (Number.isNaN(val))`
- 是否显式验证位运算结果：`if (result < 0)` 或范围检查后的结果
- 是否使用 TypeScript 类型约束：`val: number` 且 `val: integer` 等
- 是否有注释说明位运算的意图和范围
- 是否先进行数据类型转换再位运算：`const num = Number(val); if (!Number.isFinite(num)) ...`

---

## Classify

**研判为真漏洞的特征：**

1. 用户输入、API 数据直接经位运算后用于关键操作（索引、权限、内存），无范围验证
2. 位运算前未检查数字是否在 32 位有符号整数范围内
3. 浮点数、NaN、Infinity 经位运算后直接使用，未验证转换结果
4. 字符串通过位运算隐式转为数字，可能产生意外值
5. 位运算结果用于数组访问、权限位检查、缓冲区偏移，无符号位检查
6. 多次位运算链，未在中间验证中间结果的有效性
7. 无符号右移 `>>>` 和有符号右移 `>>` 混用，导致符号位处理不一致

**误报/代码异味的特征：**
- 位运算前通过范围检查：`if (val >= MIN && val <= MAX)`
- 位运算前验证有限性：`if (!Number.isFinite(val) || !Number.isInteger(val))`
- 位运算结果在使用前进行符号位检查：`if (result < 0) return error`
- 来自内部常量或受控数据源（如配置文件中的标志位）
- 使用 TypeScript 数值类型约束（如 `val: number` 配合类型检查）
- 位运算仅用于性能优化（如快速取整），不用于安全关键操作

---

## Low risk

**以下场景可评为低风险：**

1. **完整的范围验证**
   - 位运算前明确检查：`if (val >= -2147483648 && val <= 2147483647)`
   - 验证特殊值：`if (!Number.isFinite(val)) return error`
   - 验证整数性：`if (!Number.isInteger(val)) return error`

2. **明确的位运算意图**
   - 有注释说明位运算的目的：`// 限制在 0-255 范围`
   - 位运算用于非安全关键场景：日志、显示、统计
   - 使用命名常量说明掩码值：`const PERM_MASK = 0xFF`

3. **内部受控数据**
   - 位运算对象来自硬编码常量或配置
   - 来自数据库的值已通过类型系统验证
   - 循环计数器或预定义的枚举值

4. **严格的类型约束**
   - TypeScript 类型系统确保输入为 `number` 或 `integer`
   - 类型检查 + 范围验证组合使用
   - 使用 `Number.isInteger()` 确保整数性

5. **安全的结果处理**
   - 位运算后的值仅用于显示、日志或统计
   - 不用于数组索引、权限检查、内存操作
   - 位运算结果经过额外的类型检查后才使用

6. **异常处理**
   - 使用 `try-catch` 包装可能产生异常的位运算（如在 TypedArray 中）
   - 对无效结果有明确的错误处理路径

