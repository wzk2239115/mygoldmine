# Rust - Insecure Random Config

## Details

### 代码示例

```rust
// 示例1: 使用固定种子初始化随机数生成器
use rand::{SeedableRng, rngs::StdRng};
let mut rng = StdRng::seed_from_u64(12345);  // 固定种子导致可预测
let session_token = rng.gen::<[u8; 32]>();

// 示例2: 使用非密码学安全的SmallRng生成密钥
use rand::rngs::SmallRng;
let mut rng = SmallRng::from_entropy();
let encryption_key = rng.gen::<[u8; 32]>();  // SmallRng不适合加密

// 示例3: 使用thread_rng但未正确处理加密场景
use rand::{thread_rng, Rng};
let nonce = thread_rng().gen_range(0..1000000);  // 范围过小导致熵不足

// 示例4: 自实现弱随机算法
fn weak_random(seed: u32) -> u32 {
    (seed * 1103515245 + 12345) & 0x7fffffff  // LCG算法可预测
}
let token = weak_random(std::time::SystemTime::now().elapsed().unwrap().as_secs() as u32);

// 示例5: getrandom使用不安全配置
use getrandom::getrandom;
let mut buf = [0u8; 16];
// 在某些嵌入式平台回退到不安全的伪随机源
```

### 快速定位核心操作（审计技巧）

**L1 - 关键词扫描：**
- RNG类型：`SmallRng`、`StdRng`、`XorShiftRng`、`Lcg`、`thread_rng`
- 初始化方法：`seed_from_u64`、`from_seed`、`from_rng`、`SeedableRng`
- 函数调用：`gen()`、`gen_range()`、`random()`、`fill_bytes()`
- 危险特征：硬编码数字作为种子、时间戳作为种子、固定数组初始化

**L2 - 跳读：**
- 依赖声明：检查 `Cargo.toml` 中 `rand` 版本及 features（是否启用 `getrandom`）
- 类型实例化：重点看 `let mut rng =` 赋值语句的右值类型
- 加密上下文：搜索 `token`、`session`、`key`、`nonce`、`salt` 等关键字附近的随机数生成

**L3 - 逐行读：**
- 种子来源追踪：回溯 `seed_from_u64()` 参数的计算链
- 熵源验证：确认 `from_entropy()` 是否被条件编译禁用
- 范围分析：检查 `gen_range()` 的上下界是否提供足够熵（如 `0..10` 仅3.3比特）
- 错误处理：查看 `getrandom()` 失败时的回退逻辑

**L4 - 跨模块追踪：**
- 全局RNG实例：搜索 `static` 或 `lazy_static!` 声明的RNG对象
- 特征约束：检查泛型函数 `<R: Rng>` 是否限制为 `CryptoRng`
- 平台条件编译：关注 `#[cfg(target_os = "...")]` 下的备用随机实现
- 依赖传递：确认第三方库（如JWT、加密库）使用的RNG来源

### 快速定位保护机制（审计技巧）

**L1 - 关键词扫描：**
- 安全RNG：`OsRng`、`ThreadRng`、`CryptoRng`、`rand_core::CryptoRng`
- 密码学库：`ring::rand`、`openssl::rand`、`sodiumoxide::randombytes`
- 特征标记：`: CryptoRng`、`impl CryptoRng`

**L2 - 跳读：**
- 检查是否使用 `OsRng` 作为加密材料的唯一来源
- 查找 `use rand::CryptoRng` 导入及其约束在函数签名的使用
- 确认测试代码是否通过 `#[cfg(test)]` 隔离使用确定性RNG

**L3 - 逐行读：**
- 类型安全：验证 `CryptoRng + RngCore` 特征绑定是否强制执行
- 混合熵源：检查是否组合多个熵源（如 `reseed_from` 机制）
- 错误传播：确认 `OsRng::new()` 失败时是否正确返回错误而非降级

**L0 - 快速跳过：**
- 测试桩代码：`tests/`、`benches/` 目录中的Mock RNG
- 文档示例：`///` 注释块中的演示代码
- 非安全场景：游戏逻辑、UI动画、负载均衡权重等明确非加密场景

## Classify

### 确认为漏洞的判定标准：
- 在生成密码学材料（密钥、令牌、nonce、盐值、IV）时使用非密码学安全的RNG
- 使用固定种子或可预测种子（时间戳、PID、简单计数器）初始化随机数生成器
- 在安全关键路径使用 `SmallRng`、`StdRng::seed_from_u64` 等非CryptoRng实现
- 生成的随机数熵不足（如使用过小的范围或截断）
- 嵌入式目标在 `getrandom` 失败时回退到确定性伪随机

### 误报的常见场景：
- 单元测试中使用固定种子实现确定性测试（通过 `#[cfg(test)]` 隔离）
- 非安全场景的随机化（负载均衡、抖动、采样、模拟）
- Benchmark代码中为性能测试使用快速但不安全的RNG
- 文档示例代码显式标注 "DO NOT USE IN PRODUCTION"
- 使用 `thread_rng()` 但上下文明确为非加密用途（如选择随机颜色）

### 代码异味的判定：
- 混用安全与不安全RNG，增加混淆风险
- 通过 `#[allow(clippy::weak_rng)]` 显式抑制Clippy警告
- 使用过时的 `rand` 0.6及以下版本（0.7引入 `CryptoRng` 标记）
- 在 `#[cfg(not(test))]` 分支使用 `OsRng`，但测试分支使用弱RNG，可能遗漏边界情况
- 将 `OsRng` 仅用于种子初始化，后续使用确定性推导

### 研判流程：
1. 识别随机数用途：通过变量命名和后续使用判断是否涉及安全
2. 确认RNG类型：检查是否实现 `CryptoRng` 特征或使用认可的安全RNG
3. 追踪种子来源：对于 `SeedableRng`，验证种子的不可预测性
4. 评估熵质量：计算有效熵位数（考虑范围限制和截断）
5. 检查平台差异：确认所有目标平台（特别是嵌入式）均有安全熵源

## Low Risk

### 低风险场景评级标准：

**场景1：明确隔离的测试代码**
- 通过 `#[cfg(test)]` 严格限定作用域
- 测试中使用固定种子实现可重现性验证
- 生产代码路径完全不可达该RNG实例

**场景2：非安全的随机化需求**
- 负载均衡器的权重随机选择
- UI元素的随机排列（如新闻卡片顺序）
- 游戏逻辑、动画效果的随机化
- 统计采样、性能抖动（jitter）

**场景3：已有上层保护**
- 随机数仅用于非关键的初始值，最终安全性由HMAC/签名保证
- 用于选择已有的安全密钥（随机源不影响密钥本身的安全性）
- 混淆或速率限制等纵深防御机制，而非唯一防线

**场景4：依赖库的已知限制**
- 使用的第三方库文档明确说明RNG限制并提供缓解建议
- 仅在特定Cargo feature关闭时存在问题，生产环境已启用
- 嵌入式平台使用硬件RNG但代码审计无法验证硬件配置

**评级升级条件（即使符合低风险也需提升等级）：**
- 代码中存在注释"临时使用，稍后更换"但长期未修复
- 相同代码库存在已知的随机数可预测漏洞历史
- 应用在金融、医疗、身份认证等高风险领域
- 生成的随机数持久化存储或跨会话复用