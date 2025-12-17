# JavaScript_TypedArray_Conversion

**漏洞类型**: TypedArray 类型转换错误，TypedArray 之间的类型转换导致截断、溢出、精度丢失

**漏洞成因**

JavaScript/TypeScript 中 TypedArray 类型转换存在以下风险：
- 浮点数直接存储到整数型 TypedArray（Int8/Uint8/Int16/Uint16），精度丢失截断
- 大数值转换到小位宽类型（64-bit → 32-bit）溢出或截断
- 有符号/无符号类型转换导致符号误解或负数解释错误
- 通过 DataView 或位运算进行的类型转换，字节顺序混乱
- ArrayBuffer 视图转换导致读取错误的字节解释
- 位运算结果转存到 TypedArray 前的范围验证缺失
- 从 JSON、网络数据转换到 TypedArray，大数值超出范围

---

## Details

### 代码示例

**危险模式1：浮点存储到整数 TypedArray**
```javascript
function storeTemperature(value) {
    const temp = new Int8Array(1);    // -128 to 127
    temp[0] = value;                  // 38.7°C → 38（截断小数）
    return temp[0];
}

storeTemperature(38.7);   // 返回 38，精度丢失
storeTemperature(200);    // 返回 -56（溢出）
```

**危险模式2：大值转换到小位宽导致溢出**
```javascript
function compressCoordinate(x, y) {
    const coords = new Int16Array(2);  // -32768 to 32767
    coords[0] = x;
    coords[1] = y;
    return coords[0];  // x > 32767 时截断
}

compressCoordinate(100000, 50000);  // 第一个坐标溢出，值错误
```

**危险模式3：无符号数转有符号导致符号反转**
```javascript
function processPermissions(mask) {
    const perms = new Int32Array(1);
    perms[0] = mask;  // mask 作为无符号，但存储为有符号
    if (perms[0] > 0) {  // 大数值被解释为负数
        grantAccess();
    }
}

processPermissions(0xFFFFFFFF);  // 4294967295 → -1（有符号解释）
```

**危险模式4：DataView 字节序混乱**
```javascript
function readValue(buffer) {
    const view = new DataView(buffer);
    // 大端写入，小端读取（或反之）
    view.setUint32(0, 0x12345678, true);   // 小端写入
    return view.getUint32(0, false);       // 大端读取，值异常
}

readValue(new ArrayBuffer(4));  // 返回 0x78563412，字节序错误
```

**危险模式5：位运算结果溢出到 TypedArray**
```javascript
function calculateFlags(a, b) {
    const result = (a << 16) | b;  // 可能超出 Int32 范围
    const flags = new Int32Array(1);
    flags[0] = result;  // JavaScript 中 >> 运算结果自动转 32-bit
    return flags[0];
}

calculateFlags(0x10000, 0xFFFF);  // 左移后溢出
```

**危险模式6：JSON 大数值转 TypedArray**
```javascript
function parseConfig(jsonStr) {
    const data = JSON.parse(jsonStr);
    const values = new Uint32Array(data.numbers);  // 大数值转 Uint32
    return values[0];
}

parseConfig('{"numbers": [12345678901234]}');  // 精度丢失
```

**危险模式7：负数转无符号 TypedArray**
```javascript
function processSignedData(value) {
    const unsigned = new Uint8Array(1);
    unsigned[0] = value;  // -1 → 255, -128 → 128
    return unsigned[0];
}

processSignedData(-1);    // 返回 255（符号反转）
processSignedData(-128);  // 返回 128
```

**危险模式8：数组索引通过 TypedArray 转换**
```javascript
function accessArray(indexBuffer) {
    const arr = [10, 20, 30, 40, 50];
    const indices = new Float32Array(indexBuffer);
    // 浮点索引，Float32 精度丢失
    return arr[indices[0]];  // 3.9 → 3 或其他截断值
}

accessArray(new ArrayBuffer(4));  // 浮点值截断为整数
```

### 快速定位核心操作 **[L1-L2]**

**关键词扫描:**
- `new Int8Array()`, `new Uint8Array()`, `new Int16Array()`, `new Uint16Array()` 等 TypedArray 构造
- 直接赋值：`typed_arr[i] = value` 其中 value 来自浮点或大数计算
- `DataView.setInt*()`、`DataView.setUint*()` 的字节序参数
- `DataView.getInt*()`、`DataView.getUint*()` 的字节序不一致
- 位运算结果存储到 TypedArray：`(a << 16) | b` → `int32Array[0]`
- 从 JSON/API 返回的数值直接转 TypedArray，无范围验证
- 负数值存储到无符号 TypedArray：`uintArr[i] = -1`
- 浮点数直接赋值到整数 TypedArray：`int32Arr[i] = floatValue`

**快速定位保护机制 [L2-L3]**
- 赋值前是否验证值在目标类型范围内
- 是否对浮点值进行舍入或截断检查：`Math.floor()`、`Math.round()`
- 是否使用 `DataView` 时一致指定字节序
- 是否对有符号/无符号转换进行显式检查
- 位运算结果是否在存储前验证范围
- JSON 数值是否通过 `Number.isSafeInteger()` 验证
- 是否使用 `clamp()` 等方法约束值域
- 是否启用 TypeScript 类型检查

---

## Classify

**研判为真漏洞的特征：**
1. 浮点数直接赋值到整数 TypedArray，无舍入或截断验证
2. 大数值转换到小位宽类型，无溢出检查
3. 有符号/无符号混淆，导致值误解或权限绕过
4. DataView 读写使用不一致的字节序
5. 位运算结果直接存储到 TypedArray，无范围验证
6. 从不可信来源（JSON、网络）的数值直接转 TypedArray

**误报/代码异味的特征：**
- 浮点值存储前通过 `Math.round()` 或 `Math.floor()` 处理
- 赋值前进行范围检查：`if (value >= MIN && value <= MAX)`
- 有符号/无符号转换明确注释说明意图
- DataView 操作中字节序一致且有明确注释
- 值来自内部计算且范围已在代码逻辑上受限
- 使用 TypeScript 类型提示，编译期捕获类型错误

---

## Low risk

**以下场景可评为低风险：**

1. **完整的范围验证**
   - 赋值前检查范围：`if (value >= TypedArray.MIN_VALUE && value <= TypedArray.MAX_VALUE)`
   - 浮点值进行舍入：`typed_arr[i] = Math.round(value)`
   - 溢出时有明确处理

2. **内部生成的值**
   - 转换值来自内部循环计数器或受限计算
   - 范围已在代码逻辑上确定
   - 如：`for (let i = 0; i < 256; i++) { bytes[i] = i; }`

3. **显式类型转换**
   - 使用 TypeScript 类型注解强制类型检查
   - 或使用显式转换函数（如 `Math.trunc()`、`Math.floor()`）

4. **一致的字节序处理**
   - DataView 读写使用一致的字节序参数
   - 或有明确注释说明字节序处理

5. **已验证的数据源**
   - JSON 数值通过 `Number.isSafeInteger()` 验证
   - 网络数据在转换前已过验证层

