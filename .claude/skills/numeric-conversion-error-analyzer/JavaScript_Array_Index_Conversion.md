# JavaScript_Array_Index_Conversion

**漏洞类型**: 数组索引转换，数组索引计算中的类型转换

**JavaScript/TypeScript**

JavaScript/TypeScript 中数值类型转换错误常见于字符串到数字转换、位运算类型转换、TypedArray 操作、BigInt 使用等场景。JavaScript 使用双精度浮点数表示数字，但在位运算、TypedArray、BigInt 等场景中可能出现类型转换问题，导致精度丢失、溢出等安全问题。

---

## Details

### 代码示例与核心操作定位

**关键场景**:
- `array[userInput]` - 直接用用户输入作为数组索引
- `array[parseInt(str)]` - 字符串转数字后作为索引
- `array[str | 0]` - 位运算隐式转换为索引
- `array[Number(value)]` - 显式转换后作为索引
- `typedArray[userInput]` - TypedArray 索引转换
- `array[BigInt(val) % n]` - BigInt 运算结果作为索引

**核心问题**:
```javascript
// 问题1: 浮点数转整数丢失精度
const idx = 2.5;
arr[idx]; // 等同于 arr[2.5] → 实际访问 arr['2.5']

// 问题2: 字符串隐式转换
const idx = "10abc";
arr[idx]; // "10abc" 转换为 NaN → 访问 arr['10abc']

// 问题3: 特殊值处理
arr[null];      // null → 0
arr[undefined]; // undefined → 不转换，访问 arr[undefined]
arr[true];      // true → 1
arr[false];     // false → 0

// 问题4: 对象转换
const idx = {valueOf: () => 10};
arr[idx]; // 调用 valueOf() → 10
```

**快速定位核心操作 [L1:关键词扫描]**:
- 扫描关键词: `[`, `indexOf`, `slice`, `splice`, `at`
- 查找数组访问操作后跟用户输入或外部数据
- 检查索引计算的来源：`userInput`, `params`, `query`, `body`, `env`

**快速定位保护机制 [L2:跳读]**:
- 检查索引前是否有 `Number.isInteger()` 验证
- 查找 `Math.floor()`, `Math.trunc()`, `parseInt()` 的使用
- 检查是否存在范围校验: `if (idx >= 0 && idx < array.length)`
- 寻找类型白名单: `typeof idx === 'number'`
- 查看是否使用 `Array.isArray()` 和 `Object.hasOwnProperty()`

---

## Classify

**漏洞判定标准**:
1. **直接索引转换**: 未经验证的用户输入直接作为数组索引，且存在数据泄露或内存访问异常
2. **隐式类型强制**: 通过位运算、算术运算实现隐式转换，导致预期外的索引值
3. **边界绕过**: 利用浮点数、特殊值（NaN、Infinity）绕过范围校验
4. **原型链污染**: 通过对象转换结合原型链访问敏感属性

**误报/代码异味判定**:
- 对已验证为整数的值进行索引访问 → 低风险
- 在封闭数据源内部使用转换操作 → 代码异味
- 对已知长度数组进行索引，使用 `const idx = calculateIndex()` 但 `calculateIndex()` 返回经过完整校验的整数 → 低风险

---

## Low risk

**低风险评级情况**:

1. **受信数据源**:
   - 对硬编码数组进行索引: `CONSTANTS[0]`, `CONFIG[1]`
   - 函数内部局部变量计算索引
   - 数据库查询结果经过 ORM 验证后作为索引

2. **完整校验**:
   - 索引访问前存在 `Number.isInteger(idx) && idx >= 0 && idx < arr.length`
   - 使用 `Array.prototype.at()` 且传入经验证的整数
   - TypedArray 场景下使用原生方法 `typedArray.set()`

3. **框架保护**:
   - 框架自动转义和校验（如 Express 的路由参数验证中间件）
   - GraphQL 中使用标量类型约束

4. **预期异常处理**:
   - 尝试访问不存在的索引返回 `undefined`，不导致任何状态改变或敏感信息泄露

