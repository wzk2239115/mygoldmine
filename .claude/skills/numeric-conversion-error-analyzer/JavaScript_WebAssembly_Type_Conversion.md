# JavaScript_WebAssembly_Type_Conversion

**漏洞类型**: WebAssembly 类型转换，WebAssembly 接口中的类型转换导致精度丢失、溢出、符号错误

**JavaScript/TypeScript**

JavaScript/TypeScript 中数值类型转换错误常见于字符串到数字转换、位运算类型转换、TypedArray 操作、BigInt 使用等场景。JavaScript 使用双精度浮点数表示数字，但在位运算、TypedArray、BigInt 等场景中可能出现类型转换问题，导致精度丢失、溢出等安全问题。

WebAssembly 类型转换特别指：JavaScript 与 WebAssembly 边界的数值交换、ArrayBuffer/TypedArray 与 WebAssembly 内存的交互、浮点数/整数的隐式转换、32位与64位数值的截断。

**漏洞成因**

WebAssembly 类型转换安全风险源于：
- JavaScript Number 类型（64位浮点）与 WebAssembly 基础类型（i32、i64、f32、f64）的转换差异
- ArrayBuffer 作为共享内存，字节序、数据类型的混淆读写
- 大数值转换到 WebAssembly i32/i64，溢出或截断
- 浮点精度在 f32 与 JavaScript Number 之间丢失
- 传递给 WebAssembly 的参数未验证范围或类型
- 从 WebAssembly 返回的结果误解为有符号/无符号
- TypedArray 视图转换导致字节解释错误
- WebAssembly 内存越界读写导致类型混淆

---

## Details

### 代码示例

**危险模式1：大数值传入 WebAssembly i32 导致溢出**
```javascript
// WebAssembly 定义：(func $compute (param i32) (result i32))
function computeHash(largeNumber) {
    if (wasmInstance.exports.compute) {
        // 大于 2^31-1 的数被截断为 i32
        return wasmInstance.exports.compute(largeNumber);
    }
}

computeHash(0x100000000);  // 4294967296 → 0（截断）
computeHash(0xFFFFFFFF);   // 4294967295 → -1（有符号解释）
```

**危险模式2：JavaScript Number 浮点精度丢失**
```javascript
function processTemperature(temp) {
    // 大数浮点数作为 i64 传入，精度丢失
    const wasm_temp = wasmInstance.exports.processTemp(Math.floor(temp));
    return wasm_temp;
}

processTemperature(12345678901234.5);  // 精度丢失，JavaScript 只保留 53 位有效数字
```

**危险模式3：ArrayBuffer 字节序混乱**
```javascript
function readWasmData(offset) {
    const buffer = wasmInstance.exports.memory.buffer;
    const view = new DataView(buffer);
    // 大端写入（WebAssembly），小端读取（JavaScript）
    const value = view.getUint32(offset, true);  // 小端读取
    return value;
}

// WebAssembly 以大端写入 0x12345678，但以小端读取得到 0x78563412
```

**危险模式4：i32/i64 符号扩展错误**
```javascript
function validatePermission(perm) {
    // i32 返回的 -1 被误解为 4294967295
    const allowed = wasmInstance.exports.checkPerm(perm);
    if (allowed > 0) {  // -1 不大于 0，但无符号解释为大数
        grantAccess();
    }
}

validatePermission(0);  // 返回 -1，符号扩展后变为 -1
```

**危险模式5：f32 精度丢失导致边界绕过**
```javascript
function verifyCoordinate(x, y) {
    // f32 只有 24 位有效数字，精度丢失
    const result = wasmInstance.exports.checkBounds(x, y);
    if (result > 0.5) {
        return true;  // 精度丢失后边界检查失效
    }
    return false;
}

verifyCoordinate(0.30000000001, 0.20000000001);  // f32 精度不足，值可能被舍入
```

**危险模式6：负数转无符号 WebAssembly i32**
```javascript
function maskPermissions(flags) {
    // JavaScript -1 通过 WebAssembly 作为 u32 0xFFFFFFFF 处理
    const masked = wasmInstance.exports.applyMask(flags);
    return masked;
}

maskPermissions(-1);  // 作为 i32 是 -1，但作为 u32 是 0xFFFFFFFF
```

**危险模式7：TypedArray 与 WebAssembly 内存交互**
```javascript
function processImage(imageData) {
    // 直接将 Uint8Array 关联到 WebAssembly 内存
    const wasmMemory = new Uint8Array(wasmInstance.exports.memory.buffer);

    // 数据转换或覆盖导致类型混淆
    for (let i = 0; i < imageData.length; i++) {
        wasmMemory[wasmMemPtr + i] = imageData[i];  // 字节顺序或解释错误
    }

    // WebAssembly 读取该内存为 i32/i64
    return wasmInstance.exports.analyze(wasmMemPtr);
}

processImage(new Uint8Array([0xFF, 0xFF, 0xFF, 0xFF]));  // 可能被解释为 -1 或 4294967295
```

**危险模式8：WebAssembly 返回值未验证范围**
```javascript
function allocateBuffer(size) {
    // WebAssembly 返回指针，未验证有效性
    const ptr = wasmInstance.exports.malloc(size);

    if (ptr > 0) {  // 简单检查，未验证指针有效性
        return ptr;
    }
    throw new Error("Allocation failed");
}

allocateBuffer(0xFFFFFFFF);  // 可能返回无效指针或负数
```

**危险模式9：SharedArrayBuffer 竞态条件类型混淆**
```javascript
function readSharedValue(sharedBuffer, offset) {
    const view = new Int32Array(sharedBuffer);
    // 多线程环境下，值可能在读取过程中改变
    const value = view[offset];

    // 另一线程可能同时修改该值为不同类型
    if (value > 0) {
        processPositive(value);  // 值可能已被改变为负数或浮点
    }
}
```

**危险模式10：BigInt 与 WebAssembly i64 的隐式转换**
```javascript
function computeWithBigInt(x, y) {
    // BigInt 与 i64 交互，溢出未处理
    const bigValue = BigInt(Number.MAX_SAFE_INTEGER) + 1000n;
    return wasmInstance.exports.compute64(bigValue);
}

computeWithBigInt(9007199254740992n, 1000n);  // 超出范围，溢出
```

### 快速定位核心操作 **[L1:关键词扫描]**

**关键词扫描:**
- WebAssembly 调用：`wasmInstance.exports.*()`、`.wasm` 文件加载
- 内存操作：`wasmInstance.exports.memory.buffer`、`SharedArrayBuffer`
- TypedArray 创建：`new Uint8Array(wasmMemory.buffer)`、`new Int32Array(buffer)`
- ArrayBuffer 相关：`new DataView(buffer)`、`getUint32()`、`setInt32()`
- 大数值转换：`Math.floor(largeNum)`、`BigInt()` 与 WebAssembly 交互
- 符号转换：直接使用返回值作为索引或权限，未判断符号
- f32/f64 精度：`Math.abs()`、`parseFloat()` 结合 WebAssembly 计算
- 返回值验证缺失：`const result = wasmFunc(input);` 后直接使用

**快速定位保护机制 [L2-L3:跳读/逐行读]**
- 传入 WebAssembly 前是否验证值范围：`if (value >= MIN_i32 && value <= MAX_i32)`
- 浮点数转 i32 前是否验证精度：`Number.isSafeInteger(value)`
- 是否检查返回值的符号：`if (result < 0) handle_error()`
- ArrayBuffer 操作是否一致指定字节序
- 是否验证指针有效性（非负、在内存范围内）
- 是否使用 BigInt 时检查 i64 范围
- 是否对 SharedArrayBuffer 操作使用原子操作：`Atomics.load()`、`Atomics.store()`
- 是否有注释说明 WebAssembly 函数参数/返回值的类型期望

---

## Classify

**研判为真漏洞的特征：**

1. 大于 2^31-1 的 JavaScript 数字直接传入 WebAssembly i32，无范围检查
2. 浮点数传入要求整数的 WebAssembly 函数，未验证 `Number.isSafeInteger()`
3. WebAssembly 返回的 i32 直接用作数组索引、指针、权限值，未验证符号
4. ArrayBuffer 读写使用不一致的字节序或类型解释
5. 从 WebAssembly 返回的指针未验证有效性直接使用
6. SharedArrayBuffer 在多线程环境下的值读取未使用原子操作
7. BigInt 与 WebAssembly i64 交互，溢出未处理
8. f32 返回值用于安全关键比较（如边界检查），精度丢失可绕过

**误报/代码异味的特征：**
- 传入前使用 `Number.isSafeInteger()` 和范围检查
- WebAssembly 返回值存储前进行验证：`if (result < 0) throw`
- 使用 `DataView` 时一致指定字节序，有明确注释
- 指针返回值验证有效性：`if (ptr >= wasmMemSize) throw`
- SharedArrayBuffer 使用 `Atomics.load/store` 操作
- BigInt 使用时明确处理溢出：`if (value > BigInt(MAX_i64)) throw`
- 使用 TypeScript 类型注解明确 WebAssembly 函数签名

---

## Low risk

**以下场景可评为低风险：**

1. **完整的输入范围验证**
   - 传入 WebAssembly i32 前检查：`if (value < -2147483648 || value > 2147483647) throw`
   - 浮点值验证安全整数：`if (!Number.isSafeInteger(value)) throw`
   - 大数值明确转换：`const i32Value = value & 0xFFFFFFFF`

2. **返回值的显式验证**
   - WebAssembly 返回的 i32 符号检查：`if (ptr < 0) handle_error()`
   - 指针有效性验证：`if (ptr >= wasmMemorySize || ptr < 0) throw`
   - 返回值范围验证后使用

3. **一致的字节序和类型处理**
   - ArrayBuffer 操作指定一致字节序，配有注释
   - DataView 读写使用相同的字节序参数
   - 清晰记录 WebAssembly 函数的参数/返回类型

4. **安全的并发操作**
   - SharedArrayBuffer 使用 `Atomics.load(offset)` 读取
   - SharedArrayBuffer 使用 `Atomics.store(offset, value)` 写入
   - 不在竞态条件下假设值的类型或范围

5. **精度感知的浮点操作**
   - f32 用于非安全关键计算（如渲染、显示）
   - f64 用于需要精度的计算
   - 浮点结果不直接用于安全比较，使用 epsilon 或整数形式

6. **来自可信源的数据**
   - WebAssembly 模块来自应用内部加载，非外部下载
   - 传入的数据已过验证层（如配置、数据库）
   - 内部循环计数器或预定义常量，范围已知

