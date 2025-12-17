# JavaScript_Float_Precision_Conversion

**漏洞类型**: 浮点精度转换，浮点数精度丢失和转换问题

**JavaScript/TypeScript**

JavaScript/TypeScript 中数值类型转换错误常见于字符串到数字转换、位运算类型转换、TypedArray 操作、BigInt 使用等场景。JavaScript 使用双精度浮点数表示数字，但在位运算、TypedArray、BigInt 等场景中可能出现类型转换问题，导致精度丢失、溢出等安全问题。

浮点精度转换，浮点数精度丢失和转换问题，详见：[JavaScript_Float_Precision_Conversion.md](JavaScript_Float_Precision_Conversion.md)

---

---

## Details

### 核心漏洞操作

**字符串到数字转换精度丢失**
```javascript
// 字符串转数字导致精度丢失
const str = "9007199254740992";  // 超过 Number.MAX_SAFE_INTEGER
const num = Number(str);         // 9007199254740992
const num2 = num + 1;            // 9007199254740992 (预期 9007199254740993)

// parseFloat 精度问题
const price = "0.1";
const qty = "3";
const total = parseFloat(price) * parseInt(qty);  // 0.30000000000000004
```

**位运算类型转换溢出**
```javascript
// 位运算限制在 32 位有符号整数
const large = 2147483648;  // 超过 2^31-1
const result = large | 0;  // -2147483648 (溢出反转)
const check = (large >> 0); // 同样溢出

// 不安全的权限检查
const permission = 4294967296;  // 2^32
if ((permission & 1024) === 1024) {  // 位运算导致溢出，权限检查失效
  // 权限绕过
}
```

**TypedArray 越界读写**
```javascript
// 缓冲区溢出导致信息泄露
const buffer = new ArrayBuffer(4);
const view32 = new Int32Array(buffer);
const view8 = new Uint8Array(buffer);

view32[0] = 0x41414141;
const overflow = view8[10];  // 读取缓冲区外数据（取决于实现）

// 类型混淆导致精度丢失
const float32 = new Float32Array(1);
float32[0] = 1.23456789;  // Float32 精度丢失
console.log(float32[0]);  // 1.2345678806304932 (非预期值)
```

**BigInt 与普通数字混合**
```javascript
// BigInt 与 Number 混合导致意外转换
const big = 9007199254740992n;
const num = 9007199254740991;
const result = big === num;  // false，但可能发生隐式转换导致逻辑错误

// JSON 序列化丢失精度
const value = { id: 9007199254740993n };
JSON.stringify(value);  // TypeError: BigInt value can't be serialized
```

**审计快速定位技巧** `L1:关键词扫描`
- 关键词：`parseFloat`, `parseInt`, `Number()`, `toString()`, `toFixed()`
- 关键词：位运算符 `|`, `&`, `^`, `>>`, `<<`, `>>>`
- 关键词：`TypedArray`, `Float32Array`, `Int32Array`, `BigInt`
- 关键词：`MAX_SAFE_INTEGER`, `Number.EPSILON`
- 关键词：与金融、权限、ID、时间戳相关的数值操作

**保护机制定位** `L3:逐行读`
- 检查是否使用了 `Number.isSafeInteger()` 验证
- 检查是否使用了 `BigInt` 处理大数值
- 检查是否使用了字符串直接比较而非数值比较
- 检查是否使用了 `decimal.js`、`bignumber.js` 等精度库
- 检查金融/权限场景是否使用了整数运算而非浮点运算
- 检查是否对 TypedArray 的索引进行了边界检查

---

## Classify

**漏洞判定标准**

判定为**真实漏洞**需满足以下条件：

1. **精度丢失影响安全决策**
   - 金融交易中的金额计算（0.1 + 0.2 !== 0.3）
   - 权限检查中的位运算溢出（permission & mask 失效）
   - ID/Token 生成中的精度丢失导致碰撞

2. **类型转换导致逻辑绕过**
   - 字符串到数字的隐式转换导致比较失效
   - BigInt 与 Number 混合导致相等性判断错误
   - TypedArray 类型混淆读写不同类型数据

3. **缓冲区越界访问**
   - TypedArray 操作导致读取预期外的内存区域
   - 多个 view 对同一 buffer 的混合操作导致数据破坏

**误报判定标准**

以下情况应判定为**代码异味或误报**：

1. **展示层精度丢失**（无安全影响）
   - UI 显示浮点数四舍五入（如价格显示 $9.99）
   - 统计数据的近似表示

2. **已防护的场景**
   - 使用 `Number.isSafeInteger()` 进行验证
   - 使用 `decimal.js` 等库处理精度
   - 使用字符串比较而非数值比较

3. **非关键场景的类型转换**
   - 日志输出中的数值转换
   - 调试代码中的类型检查

---

## Low risk

**低风险评级标准**

以下场景应给予**低风险或通过**评级：

1. **非关键业务的数值操作**
   - 页面计数器、访问统计
   - UI 动画参数
   - 非金融相关的数学计算

2. **已隔离的精度问题**
   - 在沙箱环境中的转换
   - 用于本地存储而非业务决策
   - 结果仅用于日志记录而非逻辑判断

3. **防护充分的实现**
   - 使用专业数值库且配置正确
   - 进行了明确的边界检查和验证
   - 对大数值使用了 `BigInt` 或字符串存储

4. **信息丢失但无安全影响**
   - 浮点数精度丢失但用于非安全用途
   - 显示精度丢失但源数据完整性无损

5. **现代 JavaScript 引擎保证的场景**
   - 使用 `const` 声明避免意外重赋值
   - 使用严格相等 `===` 而非 `==`
   - 明确的类型注解（TypeScript）验证

