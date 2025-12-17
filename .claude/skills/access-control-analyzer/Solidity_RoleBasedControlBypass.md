# 基于角色的访问控制绕过（Solidity）

**漏洞描述：** 角色权限设计存在逻辑漏洞，允许低权限角色通过特定操作序列获得高权限或绕过角色检查，常见于 AccessControl、Ownable 等权限管理模式

## Details

**对应代码示例：**
```solidity
// AccessControl.sol - 风险示例
contract ProtocolGovernance is AccessControl {
    bytes32 public constant ADMIN_ROLE = keccak256("ADMIN_ROLE");
    bytes32 public constant OPERATOR_ROLE = keccak256("OPERATOR_ROLE");
    
    // ❌ 风险：OPERATOR 可授予自己 ADMIN 权限
    function grantRole(bytes32 role, address account) public override {
        require(hasRole(OPERATOR_ROLE, msg.sender), "Not operator");
        _grantRole(role, account);  // 未限制可授予的角色范围
    }
    
    // ❌ 风险：角色层级关系错误配置
    function setupRoles() external {
        _setRoleAdmin(ADMIN_ROLE, OPERATOR_ROLE);  // OPERATOR 成为 ADMIN 的管理员
    }
    
    // ❌ 风险：检查缺失导致权限绕过
    function emergencyWithdraw(address token) external {
        // 仅检查是否有任意角色，未校验具体权限等级
        require(hasRole(OPERATOR_ROLE, msg.sender) || hasRole(ADMIN_ROLE, msg.sender));
        IERC20(token).transfer(msg.sender, IERC20(token).balanceOf(address(this)));
    }
}

// Ownable.sol - 风险示例
contract VaultManager is Ownable {
    mapping(address => bool) public operators;
    
    // ❌ 风险：operator 可调用 onlyOwner 函数
    modifier onlyAuthorized() {
        require(msg.sender == owner() || operators[msg.sender], "Unauthorized");
        _;
    }
    
    function transferOwnership(address newOwner) public override onlyAuthorized {
        // operator 可通过此函数获得 owner 权限
        _transferOwnership(newOwner);
    }
}
```

**快速定位核心操作的技巧（L2:跳读）：**  
- 扫描合约继承关系：`AccessControl`、`Ownable`、`Roles`、自定义权限库
- 定位权限变更函数：`grantRole`、`revokeRole`、`renounceRole`、`setRoleAdmin`、`transferOwnership`、`addOperator`
- 检查特权函数调用：搜索 `onlyOwner`、`onlyRole`、`onlyAdmin` 等 modifier
- 关注初始化逻辑：`constructor` 和 `initialize` 中的角色分配是否合理
- 识别多角色操作路径：同一函数被多个角色调用时的权限分支判断

**快速定位保护机制的技巧（L3:逐行读）：**  
- 检查 `_setRoleAdmin` 调用：确认角色层级关系是否形成权限倒挂（低权限管理高权限）
- 验证 `grantRole` 覆写：是否限制可授予的角色白名单，是否检查调用者与目标角色的层级关系
- 确认 modifier 实现：
  - `require(hasRole(ROLE, msg.sender))` - 标准检查
  - `require(_checkRole(ROLE, msg.sender))` - 带回退的检查
  - 搜索 `_msgSender()` 替代 `msg.sender` 的元交易场景
- 追踪角色管理权限：`DEFAULT_ADMIN_ROLE` 是否被唯一持有，是否存在放弃管理员的风险
- 检查权限聚合逻辑：使用 `||` 连接多个角色时，是否引入低权限绕过高权限的路径

## Classify

**漏洞判定：**  
- 角色层级配置错误：低权限角色通过 `_setRoleAdmin` 被设置为高权限角色的管理员
- 授权函数未限制：`grantRole` 无权限范围过滤，允许任意角色提升自身或他人权限
- 修饰符逻辑缺陷：`onlyRole` 检查使用 `||` 连接多个角色但未区分操作类型，导致低权限角色执行高权限操作
- 权限检查遗漏：特权函数缺少 modifier，或 modifier 实现中未调用权限验证函数

**误报判定：**  
- 角色授予操作受治理合约控制：`grantRole` 仅可通过时间锁或多签调用，链上已部署防护层
- 角色设计本身为平级关系：OPERATOR 和 ADMIN 在业务语义上为不同维度的权限，非上下级
- 函数虽可被多角色调用，但内部根据 `msg.sender` 的角色类型进行细粒度权限分支判断
- 测试环境或已弃用代码：合约未部署或仅用于开发测试

**代码异味判定：**  
- 角色定义过于宽泛：大量函数使用同一 `OPERATOR_ROLE`，未细分为 `MINTER_ROLE`、`PAUSER_ROLE` 等
- 权限检查分散：部分使用 modifier，部分使用函数内 `require`，一致性差
- 角色层级关系不透明：缺少文档说明 RoleAdmin 配置意图，需跨文件追踪 `_setRoleAdmin` 调用链
- 过度使用 `||` 复合条件：权限判断逻辑复杂，难以快速确认各角色的实际边界

## Low risk

- **单一角色设计：** 合约仅使用 `Ownable` 且无额外角色扩展，owner 转移受外部治理合约严格控制
- **只读权限：** 低权限角色仅具备查询或统计功能，无状态修改或资产转移能力
- **去中心化治理：** 所有角色变更需通过链上投票，且存在时间锁延迟和紧急暂停机制
- **权限衰减设计：** 高权限角色在合约部署后通过 `renounceRole` 永久放弃权限，后续仅保留受限的低权限操作
- **沙箱隔离环境：** 合约为测试网部署或实验性功能模块，即使权限被滥用不影响主协议安全
