# Solidity 时间锁绕过

时间锁实现存在漏洞，允许绕过延迟直接执行提案、取消已批准的提案、或修改时间锁参数，导致恶意提案可立即执行而无等待期。

## Details

**代码示例：**
```solidity
// ❌ 漏洞示例：时间锁可被绕过
contract VulnerableTimelock {
    uint256 public delay = 2 days;
    address public admin;

    struct QueuedTx {
        uint256 eta; // estimated time of arrival
        bool executed;
    }

    mapping(bytes32 => QueuedTx) public queuedTransactions;

    // ❌ Admin 可以修改延迟为0
    function setDelay(uint256 newDelay) external {
        require(msg.sender == admin);
        delay = newDelay; // 可设为0绕过时间锁
    }

    function executeTransaction(
        address target,
        bytes memory data
    ) external returns (bytes memory) {
        bytes32 txHash = keccak256(abi.encode(target, data));
        QueuedTx storage queued = queuedTransactions[txHash];

        // ❌ 检查不严格，delay可能被改为0
        require(block.timestamp >= queued.eta);

        (bool success, bytes memory returnData) = target.call(data);
        require(success);

        return returnData;
    }
}

// ✅ 安全示例：时间锁不可绕过
contract SecureTimelock {
    uint256 public constant MINIMUM_DELAY = 2 days;
    uint256 public constant MAXIMUM_DELAY = 30 days;
    uint256 public delay;

    bytes32 public constant TIMELOCK_ADMIN_ROLE = keccak256("TIMELOCK_ADMIN");
    bytes32 public constant PROPOSER_ROLE = keccak256("PROPOSER");
    bytes32 public constant EXECUTOR_ROLE = keccak256("EXECUTOR");

    mapping(bytes32 => uint256) private _timestamps;

    constructor(uint256 minDelay) {
        require(
            minDelay >= MINIMUM_DELAY &&
            minDelay <= MAXIMUM_DELAY,
            "Invalid delay"
        );
        delay = minDelay;
    }

    // ✅ 修改延迟必须通过提案，且受时间锁保护
    function updateDelay(uint256 newDelay) external {
        require(msg.sender == address(this), "Must go through timelock");
        require(
            newDelay >= MINIMUM_DELAY && newDelay <= MAXIMUM_DELAY,
            "Invalid delay"
        );
        delay = newDelay;
    }

    function schedule(
        address target,
        uint256 value,
        bytes calldata data,
        bytes32 salt
    ) public onlyRole(PROPOSER_ROLE) {
        bytes32 id = hashOperation(target, value, data, salt);

        require(_timestamps[id] == 0, "Already scheduled");

        uint256 timestamp = block.timestamp + delay;
        _timestamps[id] = timestamp;

        emit CallScheduled(id, target, value, data, timestamp);
    }

    function execute(
        address target,
        uint256 value,
        bytes calldata data,
        bytes32 salt
    ) public payable onlyRole(EXECUTOR_ROLE) {
        bytes32 id = hashOperation(target, value, data, salt);

        // ✅ 严格检查时间戳
        uint256 timestamp = _timestamps[id];
        require(timestamp != 0, "Not scheduled");
        require(timestamp <= block.timestamp, "Too early");

        // ✅ 执行后删除，防止重复执行
        _timestamps[id] = 0;

        (bool success, ) = target.call{value: value}(data);
        require(success, "Execution failed");

        emit CallExecuted(id, target, value, data);
    }

    // ✅ 取消也需要权限
    function cancel(bytes32 id) public onlyRole(TIMELOCK_ADMIN_ROLE) {
        require(_timestamps[id] != 0, "Not scheduled");
        delete _timestamps[id];
        emit Cancelled(id);
    }
}
```

**快速定位核心操作技巧（L3-逐行读）：**
- 搜索延迟修改函数：`setDelay`、`updateDelay`
- 检查延迟的最小值限制：`MINIMUM_DELAY`、`MIN_DELAY`
- 查找执行时间检查：`block.timestamp >= eta`、`isReady`
- 定位取消函数：`cancel`、`cancelTransaction`
- 检查时间锁自引用：`msg.sender == address(this)`

**快速定位保护机制技巧（L2-跳读）：**
- 查找 OpenZeppelin `TimelockController` 的使用
- 检查角色权限：`PROPOSER_ROLE`、`EXECUTOR_ROLE`
- 验证延迟范围限制：MIN 和 MAX 常量
- 搜索自我管理逻辑：时间锁修改自身需要通过时间锁
- 查看事件发射：`CallScheduled`、`CallExecuted`

## Classify

**漏洞判定：**
- 时间锁延迟可被Admin直接修改为0或极小值
- 缺少最小延迟限制（MINIMUM_DELAY）
- 执行时间检查可被绕过（如使用可变的delay变量）
- 取消函数缺少权限控制，任何人可取消提案
- 时间锁自身参数修改无需通过时间锁

**误报识别：**
- 使用 OpenZeppelin TimelockController（已审计）
- 延迟修改必须通过 `address(this)` 调用（自引用）
- 存在硬编码的 MINIMUM_DELAY（≥ 1 天）
- 角色权限管理严格（PROPOSER、EXECUTOR分离）
- 时间戳使用不可变的排队时间而非可变delay

**代码异味：**
- delay 为 public 可写变量
- 执行检查使用 `>=` 而非 `==`（可能允许过早执行）
- 缺少取消后的清理逻辑
- 时间戳存储可被外部修改

## Low risk

**低风险场景：**
- 时间锁仅用于测试环境
- Admin 是高度可信的多签钱包（9/12等）
- 延迟修改需要链下治理投票
- 存在监控告警系统，可及时发现异常
- 时间锁保护的操作影响有限（非关键参数）

## 审计专业技巧

### 真实案例

**案例：Furucombo (2021，$15M)**
```solidity
// 简化漏洞
contract ProxyAdmin {
    // ❌ 代理合约的 Admin 未受时间锁保护
    function upgrade(address newImplementation) external onlyOwner {
        proxy.upgradeTo(newImplementation);
        // 可立即升级为恶意实现
    }
}

// 正确做法：Admin应为Timelock
constructor() {
    proxy = new Proxy(implementation, address(timelock));
    // Timelock 作为 ProxyAdmin，升级需要延迟
}
```

### 防护最佳实践

**方案1：OpenZeppelin TimelockController**
```solidity
import "@openzeppelin/contracts/governance/TimelockController.sol";

// 部署时配置
TimelockController timelock = new TimelockController(
    2 days,                    // 最小延迟
    proposers,                 // 可提交提案的地址
    executors,                 // 可执行提案的地址
    address(0)                 // Admin（设为0转移给Timelock自身）
);

// 将重要合约的Owner设为Timelock
importantContract.transferOwnership(address(timelock));
```

**方案2：双重时间锁**
```solidity
contract CriticalParameterTimelock {
    uint256 public constant NORMAL_DELAY = 2 days;
    uint256 public constant CRITICAL_DELAY = 7 days;

    function updateParameter(bytes32 param, uint256 value) external {
        uint256 requiredDelay = isCritical(param)
            ? CRITICAL_DELAY
            : NORMAL_DELAY;

        // 关键参数需要更长延迟
    }

    function isCritical(bytes32 param) internal pure returns (bool) {
        return param == keccak256("OWNER") ||
               param == keccak256("TIMELOCK_DELAY") ||
               param == keccak256("EMERGENCY_ADMIN");
    }
}
```

**方案3：不可变时间锁**
```solidity
contract ImmutableTimelock {
    uint256 public immutable DELAY; // 部署后不可修改

    constructor(uint256 _delay) {
        require(_delay >= 1 days, "Delay too short");
        require(_delay <= 30 days, "Delay too long");
        DELAY = _delay;
    }

    function execute(
        address target,
        bytes calldata data
    ) external {
        bytes32 txHash = keccak256(abi.encode(target, data));
        uint256 scheduledTime = scheduled[txHash];

        require(scheduledTime != 0, "Not scheduled");

        // ✅ 使用不可变的 DELAY
        require(
            block.timestamp >= scheduledTime + DELAY,
            "Too early"
        );

        // 执行...
    }
}
```

### 检查清单

| 检查项 | 高风险 | 中等风险 | 低风险 |
|--------|--------|----------|--------|
| 延迟修改 | 任意修改 | Owner可改 | 仅通过时间锁 |
| 最小延迟 | 无限制 | < 1天 | ≥ 2天 |
| 取消权限 | 任何人 | Owner | 严格角色控制 |
| 自引用保护 | 无 | 部分 | 完整实现 |
| 延迟类型 | 可变 | 常量但可改 | immutable |

---

**参考资料：**
- [OpenZeppelin TimelockController](https://docs.openzeppelin.com/contracts/api/governance#TimelockController)
- [Compound Timelock](https://github.com/compound-finance/compound-protocol/blob/master/contracts/Timelock.sol)
