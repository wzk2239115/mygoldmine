# Move_ResourceLayoutIncompatibility

**漏洞类型**：资源布局不兼容  
**风险等级**：高危  
**影响范围**：模块升级、状态迁移

## 概述

模块升级时修改资源结构定义（增删字段、调整字段顺序、修改字段类型），导致链上已存储的资源实例布局与新定义不匹配，造成反序列化失败、数据损坏或状态不可访问。

## Details

**代码示例特征**：
```move
// 升级前版本
module 0x1::token {
    struct TokenInfo has key {
        supply: u64,
        decimals: u8
    }
}

// 升级后版本（危险操作）
module 0x1::token {
    struct TokenInfo has key {
        name: vector<u8>,  // 新增字段在前
        supply: u64,
        decimals: u8,
        metadata: vector<u8>  // 新增字段在后
    }
}
```

**快速定位核心操作**（L3:逐行读）：
- 检查模块是否存在 `upgrade` 或多版本部署机制
- 定位所有 `struct` 定义，特别是带 `key`/`store` ability 的资源类型
- 对比历史版本（Git diff 或链上事件），识别结构体字段的增删改
- 关注 `borrow_global<T>`/`move_from<T>`/`move_to` 等资源访问点

**快速定位保护机制**（L4:跨模块追踪）：
- 查找版本兼容性检查：`version` 字段 + 分支逻辑处理不同版本
- 寻找迁移函数：`migrate_*`/`upgrade_*` 命名模式，确认是否批量更新旧数据
- 验证模块冻结状态：检查 `freeze` 或不可变性标记，禁止布局变更
- 确认是否使用资源包装器（wrapper）模式隔离版本差异
- 检查链上配置：是否启用严格兼容性策略（如 Aptos 的 `module_compatibility_check`）

## Classify

**归类为漏洞**：
- 升级后现有资源无法访问或反序列化报错
- 字段偏移错位导致数值被错误解析（如 u64 错读为 u128 高位）
- 无迁移脚本且旧资源持有者无法自救

**归类为代码异味**：
- 存在迁移逻辑但未强制执行，依赖用户主动调用
- 版本字段存在但分支覆盖不完整
- 新字段有默认值处理但未文档化

**归类为误报**：
- 仅新增带 `drop` ability 的临时结构体，不影响存储资源
- 使用 Aptos Framework 的兼容升级模式（仅追加字段到末尾）
- 已通过治理流程完成全量迁移且有链上证明

## Low risk

**低风险场景**：
- 资源实例数量极少（<10个）且由官方地址控制，可手动迁移
- 变更仅影响非关键元数据字段，核心资产字段未动
- 升级在测试网执行且主网采用全新部署地址
- 结构体仅用于事件（event）而非存储资源
- 存在回滚机制（旧版本模块备份+快速降级预案）

## 审计专业技巧与区分经验

### 一、真实漏洞的识别特征

**1. 字段序列化位移陷阱**
```move
// 真实案例：Aptos Move 升级事故
struct LiquidityPool has key {
    fee_rate: u64,        // 原版本占8字节
    reserve_x: u128,      // 原版本占16字节
    reserve_y: u128       // 原版本占16字节
}

// 升级版本中，在中间插入字段（致命）
struct LiquidityPool has key {
    fee_rate: u64,
    min_amount: u64,      // ← 这个新字段打破了对齐！
    reserve_x: u128,      // 现在数据偏移了8字节
    reserve_y: u128
}
```
- **审计要点**：计算字段字节大小，用 `u8/u16/u32/u64/u128/address` 的累加值验证偏移
- **真实危害**：反序列化时 reserve_x 会读取 min_amount + reserve_x 的高8字节，导致LP烧毁

**2. 存储能力检查**
```move
// 错误案例：丢失关键存储标记
struct UserBalance has key {  // 升级前有 store
    amount: u64
}

// 升级后（危险）
struct UserBalance has key {  // 缺少 store 能力
    amount: u64,
    vesting_schedule: VestingInfo  // VestingInfo 本身没有 store
}
```
- **审计技巧**：检查 `has key` → 必须能存储；检查 `vector<T>` 中的 T → 必须有 `store`
- **案例**：某DeFi升级后无法在存储中嵌套新数据结构，导致交易回滚

### 二、真实误报案例及规避方法

**3. 误报案例：向后兼容的字段追加**
```move
// Aptos 官方推荐模式（完全安全）
struct CoinStore<phantom CoinType> has key {
    coin: Coin<CoinType>,
    frozen: bool,
    deposit_events: EventHandle<DepositEvent>,
    withdraw_events: EventHandle<WithdrawEvent>
    // 升级时仅在末尾追加新字段
    // v2_new_field: vector<u8>,  // 位置固定，不会破坏反序列化
}
```
- **审计判断**：只有 **末尾追加，未删除，未重排** → 绿灯
- **验证工具**：链上运行 `borrow_global::<T>(&addr)` 成功 → 证明兼容

**4. 误报案例：非关键结构的修改**
```move
// 不影响存储的结构体修改
struct NFTMetadata {  // 无 key/store，仅用于 event/view function
    name: vector<u8>,
    description: vector<u8>
}

// 升级版本可以任意修改 ← 因为它不持久化存储
struct NFTMetadata {
    title: vector<u8>,    // 字段重命名
    desc: vector<u8>,
    uri: vector<u8>       // 新增字段
}
```
- **审计技巧**：搜索 `move_to<NFTMetadata>` / `borrow_global<NFTMetadata>`
  - 如果都找不到 → 非存储资源 → 改名自由
  - 搜索到 → 必须严格兼容

### 三、链上证据收集与验证

**5. 版本兼容性证明清单**
```move
module 0x1::safe_upgrade {
    struct UpgradeGuard has key {
        old_version: u64,
        new_version: u64,
        migration_completed: bool,
        migration_block_height: u64
    }

    // 审计检查清单
    // [✓] 存在版本记录结构体
    // [✓] migration_completed 在链上为 true
    // [✓] 链上事件日志显示所有用户已迁移
    // [✓] 时间戳表明迁移在升级前完成
}
```
- **验证方法**：查询链上事件（Explorer 日志），对比升级高度和迁移完成高度

**6. 反序列化安全性验证脚本**
```move
// 审计者应要求提供以下测试结果
#[test]
fun test_backward_compatibility() {
    // 1. 构造旧版本编码的字节序列（通过旧合约导出）
    let old_encoded = /* ... */;

    // 2. 用新版本反序列化
    let parsed: NewTokenInfo = deserialize(old_encoded)?;

    // 3. 验证核心字段数值正确
    assert!(parsed.supply == expected_supply, ERROR_DATA_CORRUPTION);
    assert!(parsed.decimals == expected_decimals, ERROR_OFFSET_MISMATCH);
}
```
- **要求**：升级前必须有官方提供的测试报告，包括所有已知数据的反序列化验证

### 四、常见漏报陷阱

**7. 序列化格式变化的隐形破坏**
- Move VM 使用 BCS（Bor<br/>sh Serialization）编码
- 某些字段类型在BCS中有可变长度：`vector<u8>`、`String` 等
- **漏报风险**：新增一个 `vector` 字段会改变后续所有字段的字节偏移
- **审计技巧**：在旧字段后添加 `vector` 类型 → 必然破坏兼容性

**8. 三层检查必备**
1. **代码层**：struct 定义是否有 key/store
2. **编译层**：模块是否能编译成功，是否有编译器警告
3. **链上层**：实际数据能否被反序列化，是否有失败交易日志

### 五、审计报告模板

```
## 资源布局兼容性评估

| 检查项 | 结果 | 证据 |
|--------|------|------|
| 字段追加位置 | ✓ 末尾仅追加 | Git diff 对比 |
| 存储能力 | ✓ 完整保留 | 代码审查 |
| 反序列化测试 | ✓ 通过 | 官方测试报告 |
| 数据迁移 | ✓ 100% 完成 | 链上事件日志 |
| 回滚预案 | ✓ 存在 | 治理文档 |
| 风险等级 | 🟢 低风险 | - |

**最终结论**：
- 无真实破坏性变更
- 已完成全量数据迁移验证
- 升级前后数据一致性可证明
```
