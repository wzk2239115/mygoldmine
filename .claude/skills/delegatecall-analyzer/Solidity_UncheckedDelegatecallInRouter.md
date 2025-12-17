# Solidity_UncheckedDelegatecallInRouter

**漏洞类型**: 路由器中未检查 Delegatecall  
**适用场景**: 可升级合约、中心化逻辑路由器、插件化治理模块、UUPS 代理升级、自定义 fallback 转发器、权限委托执行器

## Details

**代码示例**：
```solidity
contract Router {
    mapping(bytes4 => address) public implementations;
    
    fallback() external payable {
        address impl = implementations[msg.sig];
        require(impl != address(0), "Not found");
        (bool success, ) = impl.delegatecall(msg.data);  // 未验证 impl 合法性
        require(success);
    }
}
```

**快速定位核心操作技巧**（审计等级：L2 跳读）：
- 搜索关键词：`delegatecall`、`fallback`、`_fallback`、`_delegate`
- 关注函数签名路由模式：`mapping(bytes4 => address)`、`router`、`dispatcher`
- 检查目标地址来源：存储变量、参数传入、计算生成

**快速定位保护机制技巧**（审计等级：L3 逐行读）：
- 查找目标地址白名单验证：`whitelist`、`approved`、`trusted`
- 确认权限控制：`onlyOwner`、`onlyGovernance`、角色检查
- 检查地址验证逻辑：`require(isValid(target))`、`_checkImplementation()`
- 追踪地址赋值点：是否有准入检查、初始化保护、时间锁

## Classify

**判定为漏洞**：
- 目标地址可由外部任意控制（参数传入且无白名单）
- 存储地址可被非授权角色修改（缺失权限控制）
- 代理初始化函数可被重入或二次调用修改实现地址

**判定为误报**：
- 目标地址来自不可变白名单（immutable 或严格权限控制）
- delegatecall 仅在内部可信合约间调用
- 已有健全的实现地址注册审核机制（DAO 投票+时间锁）

**判定为代码异味**：
- 权限控制仅依赖单一 EOA（中心化风险但非直接漏洞）
- 缺少事件日志记录实现地址变更
- 未实现紧急暂停机制

## Low risk

**低风险场景**：
- 目标地址由多签钱包控制且有时间锁保护（治理风险可控）
- 仅在测试网部署或明确标注为实验性功能
- 调用前有状态快照+回滚机制（损失可控）
- 受调用频率限制或金额上限约束
- 仅委托调用只读函数（view/pure 标记且已验证）

## 审计专业技巧

### 1. 真实漏洞的常见特征

**漏洞特征识别**（高确信度）：
```solidity
// 特征1: 参数直接作为 delegatecall 目标，无验证
function execute(address target, bytes calldata data) external {
    (bool success,) = target.delegatecall(data);  // ❌ 任何地址都可被调用
}

// 特征2: 存储地址可被无限制修改
address public implementation;  // 公开修改器无权限检查

// 特征3: 初始化函数在构造器外仍可调用
function initialize(address _impl) public {  // ❌ 缺少 initializer 守卫
    implementation = _impl;
}

// 特征4: delegatecall 与易变状态结合
function route(bytes4 selector) public {
    address target = implementations[selector];
    if (target == address(0)) {
        implementations[selector] = msg.sender;  // 攻击者可自注册
    }
    (bool success,) = target.delegatecall(msg.data);
}
```

### 2. 常见误报情况（实际无漏洞）

**误报案例1: 受信内部调用**
```solidity
// 虽然看起来危险，但实际安全
contract InternalRouter {
    address private immutable trustedImpl;  // 不可变，部署后固定

    constructor(address _impl) {
        require(_impl.code.length > 0, "Invalid");
        trustedImpl = _impl;
    }

    // 结论：是误报，目标地址固定不变
}
```

**误报案例2: 严格的权限控制**
```solidity
// mapping 虽然公开但修改受严格控制
mapping(bytes4 => address) public implementations;
address private governance;

function updateImpl(bytes4 selector, address newImpl)
    external
    onlyGovernance {  // 多签治理
    require(newImpl != address(0));
    require(_isAuditedContract(newImpl));  // 白名单检查
    implementations[selector] = newImpl;
}
// 结论：误报，有完整的权限和白名单控制
```

### 3. 区分技巧的检查清单

**第一步：目标地址溯源**
- [ ] 是参数传入还是存储变量？
- [ ] 如果是存储变量，谁可以修改？是否有权限修饰符？
- [ ] 是否在 immutable 或 constant 中声明？
- [ ] 地址来自 abi.decode 还是外部合约调用？

**第二步：权限控制验证**
- [ ] 修改地址的函数是否有 `onlyOwner` 或角色检查？
- [ ] 是否存在只读的 getter（不是 public 映射）？
- [ ] 权限是否由多签钱包控制？
- [ ] 是否有 AccessControl 或类似的 RBAC 机制？

**第三步：保护机制检查**
- [ ] 是否有初始化护卫（initializer 修饰符）？
- [ ] 是否有时间锁延迟执行？
- [ ] 是否在调用前验证目标合约代码长度？
- [ ] 是否有白名单或官方实现列表？

**第四步：调用上下文分析**
```solidity
// 分析调用的上下文很关键
fallback() external payable {
    address target = implementations[msg.sig];
    require(target != address(0), "Not found");

    // 🔍 关键问题：msg.sender 是否被验证？
    // 🔍 delegatecall 是否可以修改 implementations 本身？
    (bool success,) = target.delegatecall(msg.data);
    require(success);
}
```

### 4. 实战案例分析

**案例1: Parity 钱包冻结漏洞相关的 delegatecall 问题**
```
背景：delegatecall 可用于扩展钱包功能，但地址验证不当导致灾难
教训：
- 不要假设 delegatecall 目标的安全性
- 库函数应该是无状态的（不应修改合约变量）
- 所有 delegatecall 的目标都应该是官方审计的库合约
```

**案例2: 代理合约模式的正确实现**
```
标准做法：
✅ 使用官方的 UUPSUpgradeable 或 TransparentProxy
✅ 在 initialize() 上使用 initializer 修饰符
✅ 新实现地址必须通过 DAO 投票
✅ 实现变更后需要时间锁生效（通常 2-7 天）

反面教材：
❌ 在 fallback 中动态解析 delegatecall 目标
❌ 允许任意地址作为 delegatecall 目标
❌ 在单个 EOA 手中掌握实现地址变更权限
```

### 5. 审计报告建议

**高危漏洞判定条件**（三选一）：
1. 目标地址来自不受信来源且无白名单
2. 存储地址可被外部账户直接修改且无时间锁
3. delegatecall 前未验证目标合约代码有效性

**中等风险判定条件**：
1. 权限控制存在但过于中心化（单一 EOA）
2. 有白名单但缺少时间锁保护
3. 存在初始化护卫但 delegatecall 可能受外部影响

**低风险/误报判定条件**：
1. 目标地址完全不可变（immutable 变量）
2. 修改权限由多签+时间锁保护
3. delegatecall 仅在已审计的库合约之间调用
4. 有完整的事件日志和访问控制日志
