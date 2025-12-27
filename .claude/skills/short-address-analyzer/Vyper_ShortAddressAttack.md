# 短地址攻击（Vyper）

**漏洞描述：** Vyper ERC20 代币实现中的 transfer 和 transferFrom 函数未验证地址参数有效性，攻击者可通过短地址（长度不足 20 字节）利用 Vyper 对 calldata 的处理特性，导致参数被错误解析

## Details

**Vyper 中的短地址攻击原理：**

与 Solidity 相同，Vyper 也使用标准 ABI 编码：
- 地址参数在 calldata 中占 32 字节
- 实际地址数据为 20 字节，前面补 12 字节的零
- 当地址长度不足 20 字节时，后续参数的偏移量错位

**对应代码示例：**

```vyper
# ❌ 易受攻击的 Vyper ERC20 实现

event Transfer:
    sender: indexed(address)
    receiver: indexed(address)
    value: uint256

balances: public(HashMap[address, uint256])

@external
def transfer(_to: address, _value: uint256) -> bool:
    """
    未验证地址有效性的 transfer 函数
    """
    assert self.balances[msg.sender] >= _value
    self.balances[msg.sender] -= _value
    self.balances[_to] += _value  # ← 如果 _to 是短地址，_value 会被改变
    log Transfer(msg.sender, _to, _value)
    return True


@external
def transferFrom(_from: address, _to: address, _value: uint256) -> bool:
    """
    未验证收款地址有效性的 transferFrom 函数
    """
    assert self.balances[_from] >= _value
    self.balances[_from] -= _value
    self.balances[_to] += _value  # ← 如果 _to 是短地址，参数可能被篡改
    log Transfer(_from, _to, _value)
    return True


# ✅ 安全的 Vyper ERC20 实现（添加地址验证）

@external
def transfer(_to: address, _value: uint256) -> bool:
    """
    带地址验证的安全 transfer 函数
    """
    assert _to != empty(address), "Invalid recipient"
    assert self.balances[msg.sender] >= _value, "Insufficient balance"

    self.balances[msg.sender] -= _value
    self.balances[_to] += _value
    log Transfer(msg.sender, _to, _value)
    return True


# 或使用外部库调用：
# from vyper.builtin_functions import convert

@external
def transfer(_to: address, _value: uint256) -> bool:
    """
    使用参数验证的 transfer 函数
    """
    # 基本验证
    assert _to != empty(address), "Invalid address"
    assert _value > 0, "Invalid amount"
    assert self.balances[msg.sender] >= _value, "Insufficient balance"

    # 执行转账
    self.balances[msg.sender] -= _value
    self.balances[_to] += _value
    log Transfer(msg.sender, _to, _value)
    return True
```

**快速定位核心操作的技巧（L1: 函数扫描）：**
- 扫描函数关键词：`transfer`, `transferFrom`, `approve`, `mint`, `burn`
- 查找所有包含 `address` 类型参数的函数
- 特别关注标记为 `@external` 的公开函数
- 检查是否包含资产转移操作：如 `self.balances[addr] +=`、`raw_call`

**快速定位保护机制的技巧（L2: 验证检查）：**
- 检查函数开始是否有 `assert _to != empty(address)` 或类似验证
- 查找是否有其他地址验证条件
- 检查是否调用了标准库函数进行验证
- 检查函数是否使用了 `raw_call`, `send`, `create_from_blueprint` 等低级操作

**Vyper 特有的短地址风险场景：**

```vyper
# 场景 1：raw_call 中的短地址风险
@external
def callFunction(_target: address, _data: Bytes32) -> bool:
    """
    使用 raw_call 时，如果 _target 是短地址，可能导致调用失败或路由错误
    """
    raw_call(_target, _data, gas=100000)  # ← _target 是短地址时存在风险
    return True


# 场景 2：create_from_blueprint 中的短地址风险
blueprint_contract: public(address)

@external
def deployProxy(_owner: address) -> address:
    """
    如果 _owner 是短地址，后续参数可能被篡改
    """
    new_proxy: address = create_from_blueprint(
        self.blueprint_contract,
        _owner  # ← 短地址会影响参数解析
    )
    return new_proxy
```

## Classify

**漏洞判定：**
- transfer/transferFrom 函数不验证地址参数
- 使用了 `address` 类型参数但无长度检查
- 直接将地址用于资产转移或合约调用

**误报判定：**
- 函数使用了 `assert _to != empty(address)` 验证（基础防护）
- 函数为 `internal`，不接收外部地址参数
- 使用了标准库的实现或 OpenZeppelin 的 Vyper 合约

**代码异味判定：**
- 同一文件中，transfer 有验证但 transferFrom 没有
- 使用了 raw_call 处理地址参数但无验证
- 注释说明防护但代码缺失

## Low risk

- **基础验证存在**：函数包含 `assert _to != empty(address)` 等验证
- **使用标准库**：使用了审计过的 ERC20 Vyper 实现
- **内部函数**：函数标记为 `@internal`，不接收外部地址参数
- **常数地址**：使用硬编码地址常数，不接收参数
- **已部署验证**：合约在链上长期运行未出现异常
