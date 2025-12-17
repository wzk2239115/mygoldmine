# JavaScript_TypedArray_Overflow

**漏洞类型**: TypedArray 溢出，使用 Int8Array、Uint32Array 等类型化数组时的溢出风险

**JavaScript/TypeScript**

---

专注于这一垂直漏洞类型研判任务，从漏洞成因触发，编写该md文件，包含一下三个小标题，【注意语言精炼，表达简洁，可以作为审计小抄，仅专注于审计，不包含攻击与修复】：

## Details

**代码示例**：`new Uint8Array(buffer)[index] = value`、`int32Array[i] = largeValue`、`typedArray.set(sourceArray, offset)`

### 核心操作定位技巧 (L1: 关键词扫描)
- 扫描 TypedArray 构造函数：`Int8Array`、`Uint8Array`、`Int16Array`、`Uint16Array`、`Int32Array`、`Uint32Array`、`Float32Array`、`Float64Array`、`BigInt64Array`、`BigUint64Array`
- 关注三类高风险操作：
  - **直接赋值**：`array[i] = externalValue` 或 `array.set(sourceArray, offset)`
  - **动态索引**：索引来自用户输入或计算结果（`for(let i=0; i<userInput; i++) array[i] = x`）
  - **Buffer 共享**：多个 TypedArray 视图共享同一 Buffer，修改需要追踪影响范围
- 检查赋值的值范围：Uint8 [0-255]、Int8 [-128-127]、Uint32 [0-4294967295]、Int32 [-2147483648-2147483647]

### 保护机制定位技巧 (L2: 跳读)
- **范围检查模式**（立即通过）：
  - `if (value > MAX_VALUE) throw new Error()`
  - `value & 0xFF` 或 `value % 256`（显式截断说明）
  - `Math.min(value, 255)`、`Math.max(value, 0)`
  - `if (index < 0 || index >= array.length) return`
- **异常处理**：`try-catch` 捕获 `RangeError` 或 `TypeError`
- **验证链条**：追踪值的来源，确认是否经过业务层验证

## Classify

### 漏洞判断标准（真实漏洞特征）
- **数据截断导致逻辑错误**：外部输入未验证直接赋给 Uint8Array，大值被截断后改变程序流程（如 ID 校验失败）
  - 示例：`const userId = userInput; array[userId] = 1;` 当 userId > 255 时被截断
- **越界读写泄露或破坏**：索引计算不当导致越界访问相邻 Buffer 内存
  - 示例：`array[userData.offset + userData.length]` 未校验 offset+length > buffer.length
- **SharedArrayBuffer 竞态条件**：多线程/Worker 环境下并发修改同一 TypedArray
  - 示例：Worker1 和 Worker2 同时修改 `new Int32Array(sharedBuffer)`

### 误报识别经验
- **预期截断**：位操作库故意使用 `value & 0xFF` 或模运算，这是设计功能而非漏洞
- **完整验证链**：值虽然最终赋给 TypedArray，但上游已有多层验证（参数检查、类型守卫、Schema 验证）
- **隐式范围保证**：循环条件已保证 `i < array.length`，即使值可能越界也不会访问越界
- **容错设计**：异常被捕获后有降级方案，不影响安全性（如 `try { arr.set(data) } catch { return fallback }`）
- **静态类型保障**：TypeScript 项目中使用 `number & {__brand: 'SafeUint8'}` 等品牌类型保证值域

## Low risk

### 安全赋值模式
- 赋值前进行范围验证：
  - 显式截断：`value & 0xFF` 或 `value % 256`（明确说明只需低 8 位）
  - 范围限制：`Math.min(value, 255)` 或 `Math.max(value, 0)`
  - 显式检查+异常：`if (value < 0 || value > 255) throw new Error()`
  - 类型断言：`value as Uint8`（TypeScript，前提经过验证）

### 安全索引计算
- 索引使用安全计算：
  - `index % array.length`（模运算保证范围）
  - `Math.min(index, array.length - 1)`（限制上界）
  - `if (index < 0 || index >= array.length) return;`（显式检查）
- Buffer 大小计算明确：`const buffer = new ArrayBuffer(1024);` 而非动态计算

### 安全使用场景
- TypedArray 用于明确的底层操作：WebGL 顶点数据、音频处理、加密算法（预期截断）
- 值来自已验证的可信源（如配置文件、数据库字段、已验证的用户输入）
- 有异常处理捕获越界访问（`try-catch RangeError` 或 `TypeError`）
- 使用成熟库（如 TweetNaCl.js、libsodium.js）而非自写溢出风险代码

### 审计笔记
- **关键追踪点**：从 TypedArray 赋值点反向追踪值的来源，确认每一步验证
- **边界值测试**：心中模拟 MAX_VALUE、MIN_VALUE、-1、超大数（Number.MAX_SAFE_INTEGER）的结果
- **多视图陷阱**：同一 Buffer 若有多个 TypedArray 视图，修改其中一个会影响另一个（非漏洞，但需理解）
- **异步陷阱**：在 Promise/async 中修改 TypedArray，需检查竞态条件或 SharedArrayBuffer 问题

---

## 真实漏洞案例

### 案例 1：ID 截断导致身份认证绕过（真漏洞）
```javascript
// 危险代码
const userIds = new Uint8Array(256);
function markUser(userId) {
  userIds[userId] = 1; // userId > 255 时被截断
}
// 攻击：markUser(256 + adminId) 实际修改 adminId，绕过权限
```
**审计重点**：userId 来自 HTTP 参数未验证，且 Uint8Array 范围不符合应用需求（用户 ID 通常是 32 位整数）。这是真实漏洞。

### 案例 2：音频处理中的预期截断（误报案例）
```javascript
// 安全代码
const audioSamples = new Int16Array(44100);
function addNoise(amplitude) {
  const noise = (Math.random() * 2 - 1) * amplitude;
  const clipped = noise | 0; // 显式截断为整数
  audioSamples[frame % 44100] = clipped; // 范围保证
}
```
**审计重点**：amplitude 来自配置文件，clipped 通过位运算明确截断。frame 使用模运算保证索引安全。这是设计良好的代码，不是漏洞。

### 案例 3：Buffer 溢出导致内存泄露（真漏洞）
```javascript
// 危险代码
function parseData(data, maxLength) {
  const buffer = new ArrayBuffer(256);
  const view = new Uint8Array(buffer);
  view.set(data, 0); // data.length > 256 时越界写入
}
```
**审计重点**：set() 方法未校验源数据长度。data 来自网络，可能远大于 256 字节，导致越界访问相邻内存。真实漏洞。

### 案例 4：SharedArrayBuffer 竞态（多线程漏洞）
```javascript
// 危险代码
const sharedBuffer = new SharedArrayBuffer(4);
const sharedArray = new Int32Array(sharedBuffer);
// Main thread
sharedArray[0] = userInput; // Worker 并发访问
// Worker
while (sharedArray[0] === oldValue) { /* TOCTOU */ }
```
**审计重点**：多线程环境下非原子操作导致 TOCTOU。需要使用 `Atomics.compare_exchange()` 等原子操作。真实漏洞。

---

## 审计速查表

| 特征 | 判定 | 理由 |
|------|------|------|
| 直接赋值 `arr[i] = userInput` 无检查 | 🔴 漏洞 | 需要值范围验证 |
| 赋值前有 `if (v > MAX)` 检查 | 🟢 安全 | 显式验证存在 |
| `arr[idx & MASK] = v` 模运算截断 | 🟡 需确认 | 检查 MASK 是否对应类型范围 |
| `arr[Math.min(idx, len-1)] = v` | 🟢 安全 | 索引被限制 |
| 循环中 `for(let i=0; i<arr.length)` | 🟢 安全 | 循环条件保证索引范围 |
| `try-catch` 捕获越界 | 🟢 安全 | 异常被妥善处理 |
| TypedArray 用于 WebGL/音频 | 🟡 需确认 | 检查上游数据验证 |
| `new Uint8Array(userInput)` | 🔴 漏洞 | Buffer 大小可被控制 |
| 多个视图共享 Buffer 无文档 | 🟡 需确认 | 检查是否存在逻辑错误 |

## 常见漏洞模式速识

### 高风险赋值模式
- `array[userInput]` = 直接使用用户输入作为值或索引
- `array.set(untrustedData)` = 不验证数据长度
- `new TypedArray(userControlledSize)` = Buffer 大小由用户控制
- `array[offset + userLength]` = 索引由多个未验证的部分组成

### 低风险赋值模式
- `array[knownIndex] = preprocessedValue` = 索引和值都经过预处理
- `array.set(data, 0); if(lastValue !== expected) throw` = 赋值后验证
- `const safeValue = value & 0xFF; array[i] = safeValue` = 显式截断并说明意图
- `array[i % array.length]` = 索引被模运算限制

