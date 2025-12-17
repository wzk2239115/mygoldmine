# Go - 不必要的序列化（CosmWasm）

## 漏洞成因
在CosmWasm合约中，频繁对中间数据结构进行JSON序列化/反序列化操作，而非直接传递原生类型或复用已序列化的数据。每次`to_json_binary()`和`from_json()`调用都会产生额外的CPU周期和内存分配，尤其在循环、跨合约调用链、查询器回调中累积开销显著。

## Details

**典型代码模式：**
```rust
// 坏例：在循环中反复序列化同一结构
for user in users.iter() {
    let msg = to_json_binary(&QueryMsg::GetBalance { 
        address: user.clone() 
    })?;
    let result: BalanceResponse = deps.querier.query_wasm_smart(
        contract_addr.clone(), 
        msg
    )?;
    // 处理result...
}

// 坏例：跨合约通信中的双重序列化
let temp_data = query_external_contract(deps, addr)?; // 返回JSON
let parsed: TempStruct = from_json(temp_data)?;       // 反序列化
let re_serialized = to_json_binary(&parsed)?;         // 再次序列化传递
```

**快速定位核心操作（L2-跳读）：**
- 搜索`to_json_binary`、`to_json_vec`、`from_json`、`serde_json`关键字
- 查看消息构造函数、查询回调、SubMsg构建处是否存在序列化嵌套
- 关注循环体内是否重复构造相同的序列化对象

**快速定位保护机制（L1-关键词扫描）：**
- 检查是否存在结构体缓存逻辑（如`lazy_static`、`once_cell`）
- 查找`Binary`类型直接传递而非中间解析
- 验证批量查询接口（如`query_all`）是否替代了逐个序列化查询

## Classify

**漏洞判定标准：**
- **Gas消耗显著**：序列化操作在热路径（高频调用函数）中，且数据结构复杂度O(n)以上
- **可避免性**：技术上可通过类型重构、缓存、批量接口消除序列化

**归类为误报：**
- 序列化发生在初始化或低频管理操作中
- 跨合约协议强制要求特定JSON格式（接口兼容性约束）
- 数据结构极简（如单个u128），序列化开销可忽略

**归类为代码异味：**
- 性能影响边界模糊（如中等复杂度结构在中频路径）
- 存在优化空间但需大幅重构架构
- 测试显示gas增量<5%

## Low risk

以下场景应评为低风险：
1. **离链查询上下文**：仅在查询接口（非交易执行路径）中序列化，不消耗链上gas
2. **数据量受限**：结构体字段数≤3且无嵌套，单次操作序列化开销<1000 gas
3. **已有上限保护**：循环迭代次数受合约常量严格限制（如`MAX_BATCH_SIZE=10`）
4. **协议边界必需**：IBC数据包、跨链桥接等标准协议要求的序列化格式
5. **清晰的性能注释**：代码明确标注了trade-off选择（如为可读性牺牲微量性能）

## 审计专业技巧

### 1. 真实漏洞识别经验

**高危信号组合检测：**
- **信号组合A**：`for msg in msgs.iter() { ... to_json_binary(&msg)? ... }` + 未设置msg数组长度上限
  - 指标：循环内序列化 + 外部输入控制迭代次数 = 直接DoS向量
  - 案例：某Cosmos合约batch_execute接受任意数量SubMsg，未验证长度导致gas溢出

- **信号组合B**：跨合约call链中的`from_json -> to_json_binary`循环
  - 指标：query_wasm_smart返回Binary → from_json解析 → 传递给下一个合约前再serialize
  - 真实影响：在深度调用链（3+层）中，每层序列化开销指数增长
  - 实际数据：32字段复杂结构，3层链式调用可增加~15-20% gas消耗

- **信号组合C**：State存储循环遍历 + 每次迭代序列化查询
  ```rust
  // 红旗：在execute消息处理路径中
  let items = ALL_ITEMS.range(deps.storage, None, None, Order::Ascending);
  for (_, item) in items {
      let msg = to_json_binary(&QueryMsg::Process { data: item })?;
      // 问题：若ALL_ITEMS有1000项，要序列化1000次
  }
  ```

### 2. 误报常见陷阱

**误报场景A：错误判定查询路径的影响**
- 错误：将`query()`函数中的序列化标记为gas漏洞
- 正确判断方法：
  - 查询函数执行成本由节点全节点承担，不消耗用户gas
  - 仅当query结果直接被execute路径继承并多次使用时才计算gas开销
  - 检查query返回值是否被store、跨合约传递或循环处理

**误报场景B：协议必需的序列化**
- Cosmos中SubMsg、IBC Packet、跨链桥接等类型必须遵循特定JSON编码
- 区分方法：搜索`to_json_binary`使用位置
  - 若紧邻`SubMsg::new()`或`IbcPacket::new()`构造，大概率是协议必需
  - 若在业务逻辑层对数据进行冗余序列化（如convert struct A → JSON → struct B）才是真问题

**误报场景C：单次调用的序列化开销忽略**
- 一次性初始化或管理员操作中的序列化实际开销<100 gas
- 检查方法：确认调用频率
  ```rust
  // 示例：该序列化不是漏洞
  pub fn admin_setup(deps: &mut DepsMut) -> Result<Response, ContractError> {
      let config = to_json_binary(&Config { ... })?;  // 仅在初始化调用一次
      ...
  }
  ```

### 3. 定量评估框架

**快速Gas消耗估算：**
| 结构类型 | 字段数 | 序列化开销(gas) | 评估阈值 |
|---------|------|----------------|---------|
| 简单结构 | 1-3 | 50-200 | <5次/tx时忽略 |
| 中等结构 | 4-10 | 300-800 | 需控制在<10次 |
| 复杂结构 | 11+ | 1000+ | 任何循环都高危 |

**实际审计检查清单：**
1. 搜索所有`to_json_binary`调用，统计频率
2. 对每处调用追踪：是否在loop中、是否输入受限、gas消耗是否可量化
3. 验证数据结构定义：字段数和嵌套深度
4. 检查是否存在`Query`路径复用（大幅降低风险权重）

### 4. 审计报告模板

建议格式在报告中包含：
- **受影响路径**：具体执行函数名 + 行号范围
- **触发条件**：需要多少次调用或多大数据才能产生明显gas增加
- **定量影响**：基于结构复杂度和调用频率估算gas增长百分比
- **修复优先级**：
  - P0：循环+外部输入控制 + execute路径 → 直接DoS
  - P1：多层跨合约调用中的冗余序列化 → 10%以上gas增加
  - P2：代码异味，优化空间清晰但影响<5% → 建议优化
  - P3：查询路径或初始化路径 → 文档记录即可

### 5. 常见修复模式

**修复方案一：消除冗余往返序列化**
```rust
// 改进：传递Binary而非反序列化后再序列化
let binary_data: Binary = query_wasm_smart(deps, ...)?;
// 直接使用binary_data，避免from_json -> to_json_binary
```

**修复方案二：批量操作替代逐个序列化**
```rust
// 改进：使用批量查询接口而非循环单个查询
let all_balances = query_all_balances(deps)?;
// 一次序列化返回所有数据，而非循环n次序列化
```

**修复方案三：添加迭代上限保护**
```rust
const MAX_BATCH_SIZE: usize = 100;
let msgs = execute_msgs;
require!(msgs.len() <= MAX_BATCH_SIZE, "Batch size exceeds limit");
for msg in msgs.iter() {
    let serialized = to_json_binary(&msg)?;
    // 现在已被限制在安全范围内
}
```

### 6. 审计工作流总结

在面对不必要序列化问题时，建议按以下顺序判断：
1. **第一步**：确认序列化发生的代码路径（execute/query/sub_message）
2. **第二步**：估算数据结构复杂度（字段数、嵌套层级）
3. **第三步**：检查调用频率（单次、循环次数、迭代量）
4. **第四步**：评估协议约束（是否必需、是否可替代）
5. **第五步**：量化gas影响（基于上表估算，<2%可忽略）
6. **第六步**：出具优先级（P0-P3分级）
