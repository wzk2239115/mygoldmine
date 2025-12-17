# Vyper 投票状态竞争条件

投票状态更新存在竞争条件，允许在同一区块内多次投票或改变投票选择，导致投票结果被操纵。

## Details

**代码示例：**
```python
# ❌ 漏洞示例
voted: public(HashMap[address, bool])
yes_votes: public(uint256)
no_votes: public(uint256)

@external
def vote(support: bool):
    # ❌ 检查和更新不是原子操作
    assert not self.voted[msg.sender]

    votes: uint256 = self.token.balanceOf(msg.sender)

    if support:
        self.yes_votes += votes
    else:
        self.no_votes += votes

    # ❌ 状态更新在后，可能被重入
    self.voted[msg.sender] = True

# ✅ 安全示例
voted: public(HashMap[address, bool])
yes_votes: public(uint256)
no_votes: public(uint256)
proposal_snapshot: public(uint256)

@external
@nonreentrant('vote')
def vote(support: bool):
    # ✅ 立即设置状态
    assert not self.voted[msg.sender]
    self.voted[msg.sender] = True

    # ✅ 使用快照余额
    votes: uint256 = self.token.balanceOfAt(msg.sender, self.proposal_snapshot)

    assert votes > 0

    if support:
        self.yes_votes += votes
    else:
        self.no_votes += votes
```

## Classify

**漏洞判定：**
- 状态检查与更新分离
- 缺少 @nonreentrant 装饰器
- 投票权基于实时余额

**误报识别:**
- 使用 @nonreentrant
- 状态先更新后计算
- 有快照机制

**代码异味：**
- 状态更新在函数末尾
- 多个外部调用
- 缺少事件发射
