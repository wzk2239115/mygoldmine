# JavaScript_Type_Conversion_Overflow

**漏洞类型**: 类型转换溢出，字符串到数字转换、位运算时的溢出

**JavaScript/TypeScript**

---

专注于这一垂直漏洞类型研判任务，从漏洞成因触发，编写该md文件，包含一下三个小标题，【注意语言精炼，表达简洁，可以作为审计小抄，仅专注于审计，不包含攻击与修复】：

## Details

**代码示例**：`parseInt(userInput)`、`Number(stringValue)`、`value | 0`、`~~floatValue`、`value >>> 0`

- **核心操作定位技巧** (L1: 关键词扫描)：扫描类型转换函数（`parseInt`、`Number`、`parseFloat`）和位运算符（`|`、`~`、`>>`、`>>>`）。位运算会将操作数转为 32 位整数。关注转换结果用于数组索引、内存分配、循环边界的情况。

- **保护机制定位技巧** (L2: 跳读)：查找转换前的范围验证、使用 `Number.isNaN()` 和 `Number.isFinite()` 检查，或使用安全的解析方式（如限制输入格式、设置最大值）。检查是否验证 parseInt 的基数参数。

## Classify

判断是否为漏洞的要点：
- **确定漏洞**：字符串转数字无验证，位运算导致 32 位截断丢失精度，转换结果参与关键计算
- **误报**：转换前有格式验证、结果在安全范围内、仅用于显示或日志
- **代码异味**：使用位运算强制转换，需确认是否可能丢失数据

## Low risk

- 转换前进行格式和范围验证
- 使用 Number.isNaN() 和 Number.isFinite() 检查结果
- 位运算仅用于明确的 32 位整数场景
- parseInt 指定基数参数（如 parseInt(str, 10)）
- 转换失败有默认值或异常处理

## 审计专业技巧

### 1. 关键操作链识别

审计时需要追踪完整的数据流链路，不仅关注转换本身，更要追踪转换后的值使用场景：

- **数组索引链**：`const arr = []; const idx = parseInt(input); arr[idx]` - 检查 input 是否来自用户，是否验证范围
- **内存分配链**：`const size = Number(userInput); const buffer = new Array(size)` - 大值可导致 DoS
- **循环计数链**：`for(let i = 0; i < parseInt(param); i++)` - 检查是否可被控制为负数或超大值
- **业务逻辑链**：`const userId = parseInt(req.query.id); fetchUser(userId)` - 检查转换后是否直接用于身份验证或权限判断

**审计方法**：使用数据流追踪，从类型转换点回溯输入源，向前追踪输出使用。关注"黑暗数据流"（无验证直接使用）。

### 2. 位运算陷阱识别

JavaScript 的位运算会强制转换为 32 位有符号整数，审计时需特别关注：

- **截断陷阱**：`value >>> 0` 将负数转为无符号 32 位整数。`(-1 >>> 0) === 4294967295`
- **精度丢失**：Number.MAX_SAFE_INTEGER 为 9007199254740991，但 `2147483648 | 0` 得 -2147483648
- **符号翻转**：`(2147483648 | 0)` 从正数变为负数，导致权限检查绕过（如 `if (id < 0) reject()`）
- **混合场景**：同时使用位运算和比较操作，如 `(idx >> 2) < length` - 需验证 idx 的有效范围

**审计方法**：对所有位运算操作符（`|`, `&`, `^`, `~`, `<<`, `>>`, `>>>`）后的数值都需特别审视，特别是用于安全关键操作。

### 3. parseInt 隐藏风险

`parseInt()` 是高风险函数，常见审计误区：

- **基数推导陷阱**：未指定基数时，`parseInt("10")` 返回 10，但 `parseInt("010")` 在不同引擎可能返回 8（八进制）或 10。现代浏览器返回 10，但需要防守
- **前缀处理**：`parseInt("0x1F")` 返回 31，`parseInt("1e5")` 返回 1（停止在 'e'），容易被用于绕过检查
- **NaN 处理缺失**：`parseInt(null) === NaN`，`parseInt(undefined) === NaN`，但 `parseInt("abc") === NaN`。不检查返回值会导致 NaN 流入业务逻辑
- **尾数截断**：`parseInt("123.456", 10)` 返回 123，如用于金额计算可能丢失精度

**真实案例区分**：
- ❌ 真漏洞：`const amount = parseInt(req.body.price); charge(userId, amount)` - 无基数、无 NaN 检查、用于金融操作
- ✅ 误报：`const version = parseInt(config.version); console.log(version)` - 虽然无基数，但结果仅用于显示，非关键操作

### 4. 误报与真漏洞的实战区分

**误报特征**（L0 风险）：
- 转换后的值**明确为常量**或**可验证的范围**：`const pageSize = Math.min(parseInt(input), 100)`
- **非用户输入**的转换：`parseInt(apiResponse.status)` - 若 apiResponse 来自信任源
- 转换结果**仅用于显示层**：日志、UI 展示、统计数据
- **防守性编程**：虽然写法不优雅，但有 NaN 检查：`const id = parseInt(input); if (isNaN(id)) throw new Error()`
- **弱类型场景**：`const flag = parseInt(setting) ? true : false` - 用途明确，风险低

**真漏洞特征**（L2 风险）：
- 用户可控的输入**直接**被转换，转换后**直接参与**关键操作
- 链式操作，无中间验证：`getUserPermissions(parseInt(req.query.uid))`
- 转换后用于**安全决策**：权限检查、认证、授权
- 涉及**数组边界**：`arr[parseInt(index)]` 未验证 length
- 涉及**循环控制**：`for(let i=0; i<parseInt(limit); i++)` 未验证 limit 上界

**实战判断步骤**：
1. 确认输入源是否用户可控（追踪 req.*, URL, localStorage 等）
2. 转换前是否有格式验证（如正则表达式、长度检查）
3. 转换后的值是否用于关键操作（索引、计数、权限、金额）
4. 是否有转换失败处理（NaN/错误检查）
5. 转换后是否有范围验证（min/max 检查）

### 5. 深层审计技巧

- **类型强制转换链**：多次转换会增加风险，`Number(parseInt(input))` 虽然冗余，但反映代码质量问题
- **隐式转换**：字符串和数字的隐式转换如 `userInput - 0`、`+userInput` 等同样风险，需按显式转换规则审计
- **特殊数值处理**：关注 `Infinity`、`-Infinity`、`NaN` 的处理，如 `if (value === Infinity) {}` 缺失会导致异常行为
- **TypeScript 误区**：类型检查不能防止 runtime 整数溢出，需审查实际 JavaScript 行为
- **库函数信任问题**：某些库函数返回数字，审计时需验证其是否验证输入，如 `lodash.toNumber()`、`qs.parse()` 等的安全性

