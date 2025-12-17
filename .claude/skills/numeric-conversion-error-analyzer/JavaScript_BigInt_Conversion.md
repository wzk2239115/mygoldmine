# JavaScript_BigInt_Conversion

**漏洞类型**: BigInt 转换，BigInt 与 Number 之间的转换问题

**JavaScript/TypeScript**

JavaScript/TypeScript 中数值类型转换错误常见于字符串到数字转换、位运算类型转换、TypedArray 操作、BigInt 使用等场景。JavaScript 使用双精度浮点数表示数字，但在位运算、TypedArray、BigInt 等场景中可能出现类型转换问题，导致精度丢失、溢出等安全问题。

---

## Details

### 代码示例与核心操作定位

**关键场景**:
- `BigInt(userInput)` - 未验证用户输入直接转换为 BigInt
- `Number(bigIntValue)` - BigInt 转换回 Number 导致精度丢失
- `BigInt value + Number value` - 混合类型运算（不允许直接运算）
- `parseInt(bigIntValue.toString())` - 通过字符串中转转换
- `bigIntValue.toString(10)` - BigInt 转为十进制字符串后再转回
- `bigIntValue % divisor` - 大数取模运算中的转换问题

**核心问题**:
```javascript
// 问题1: 超出 Number 范围的精度丢失
const big = BigInt(Number.MAX_SAFE_INTEGER) + 1n;
const num = Number(big); // 精度丢失！
console.log(big === BigInt(num)); // false

// 问题2: 字符串转换中的注入
const input = "999n"; // 注意 'n' 后缀
BigInt(input);  // TypeError: Cannot convert 999n to a BigInt

// 问题3: 无效格式字符串转换
BigInt("0xFF");    // 工作正常 → 255n
BigInt("12.5");    // TypeError: Cannot convert decimal to BigInt
BigInt("12e3");    // TypeError: Cannot convert exponential to BigInt

// 问题4: 混合运算类型错误
const big = 10n;
const num = 5;
big + num;  // TypeError: Cannot mix BigInt and other types

// 问题5: 比较操作的隐式转换
10n == 10;   // true (宽松比较，发生类型转换)
10n === 10;  // false (严格比较)

// 问题6: JSON 序列化失败
JSON.stringify({value: 100n}); // TypeError: BigInt value can't be serialized
```

**快速定位核心操作 [L1:关键词扫描]**:
- 扫描关键词: `BigInt(`, `toString()`, `.toString(`, `Number(.*BigInt`, `JSON.stringify`
- 查找 BigInt 的来源：`userInput`, `params`, `query`, `body`, `API response`
- 检查 BigInt 值的使用方式：算术运算、比较、序列化、数据库存储
- 追踪通过字符串中转的转换链: `.toString()` → `parseInt()`

**快速定位保护机制 [L2:跳读]**:
- 查找类型检查: `typeof value === 'bigint'`
- 检查转换前的验证: `if (/^\d+n?$/.test(input))` 或 `Number.isSafeInteger()`
- 寻找范围校验: `if (big <= MAX_VALUE && big >= MIN_VALUE)`
- 查看是否用 `try-catch` 包装 `BigInt()` 调用
- 检查 JSON 序列化的替换函数: `JSON.stringify(..., replacer)`
- 查找字符串格式校验: 是否验证 16 进制、八进制等格式

---

## Classify

**漏洞判定标准**:
1. **不受信转换**: 用户输入直接传入 `BigInt()` 且无格式验证，导致拒绝服务 (TypeError)
2. **精度丢失流**: BigInt 转 Number 再用于计算或比较，导致结果错误
3. **隐式类型混合**: BigInt 与 Number 混合运算/比较，在宽松比较中导致类型转换
4. **序列化失败**: BigInt 值进入 `JSON.stringify()` 导致运行时异常
5. **字符串中转注入**: 通过 `toString()` 转字符串后再解析，允许格式注入 (如指数记法)

**误报/代码异味判定**:
- BigInt 由硬编码或数据库 BigInt 列生成 → 低风险
- `BigInt()` 前有完整的格式验证: `/^\d+$/.test(input) && Number.isSafeInteger(input)`→ 代码异味
- BigInt 与 Number 的比较使用了严格比较 `===` → 不存在隐式转换风险
- BigInt 转 Number 后仅用于展示，未用于逻辑计算 → 代码异味

---

## Low risk

**低风险评级情况**:

1. **受信数据源**:
   - BigInt 值来自应用内常量: `const EPOCH_MS = 1000n`
   - BigInt 来自数据库 BigInt 列的原生驱动解析
   - 区块链库返回的原生 BigInt (如 ethers.js `BigNumber.toString()` 后转回)

2. **完整验证**:
   - 转换前验证: `if (/^\d+$/.test(input) && input.length <= 20)`
   - 范围校验: `BigInt(input) >= 0n && BigInt(input) <= MAX_SAFE_BIGINT`
   - 类型检查后使用: `if (typeof value === 'bigint') { ... use value ... }`

3. **安全运算**:
   - BigInt 仅用于大整数算术，不与 Number 混合: `big1 + big2` (都是 BigInt)
   - 比较操作使用严格相等: `big === 10n`
   - 序列化前转换为安全格式: `BigInt value → string → JSON`

4. **异常处理**:
   - `try-catch` 包装 `BigInt()`, `JSON.stringify()`, 混合类型运算
   - 捕获 TypeError 后返回合理默认值或错误响应

5. **格式限制**:
   - 仅接受十进制字符: `if (!/^[0-9]+$/.test(input))`
   - 拒绝指数、浮点、16 进制记法在用户输入中
   - 对外部 API 返回的数字字符串加格式白名单

