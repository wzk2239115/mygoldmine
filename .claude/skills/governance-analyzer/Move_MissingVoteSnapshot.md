# Move 缺少投票快照

投票权基于实时余额而非快照，允许代币在投票期间转移以获得多次投票机会，或投票后立即出售代币逃避决策后果。

## Details

**代码示例：**
```move
// ❌ 漏洞示例
module governance::vulnerable_dao {
    use std::signer;
    use aptos_framework::coin::{Self, Coin};

    struct Proposal has key {
        yes_votes: u64,
        no_votes: u64,
    }

    struct VoteRecord has key {
        voted: bool,
    }

    public entry fun vote(voter: &signer, proposal_addr: address, support: bool) {
        // ❌ 使用当前余额
        let vote_power = coin::balance<GovernanceToken>(signer::address_of(voter));

        let proposal = borrow_global_mut<Proposal>(proposal_addr);

        if (support) {
            proposal.yes_votes = proposal.yes_votes + vote_power;
        } else {
            proposal.no_votes = proposal.no_votes + vote_power;
        };

        move_to(voter, VoteRecord { voted: true });
    }
}

// ✅ 安全示例
module governance::secure_dao {
    use std::signer;
    use std::table::{Self, Table};

    struct Proposal has key {
        snapshot_time: u64,
        yes_votes: u64,
        no_votes: u64,
    }

    struct VotingPowerSnapshot has key {
        powers: Table<address, u64>,
    }

    public entry fun create_proposal(creator: &signer) {
        // ✅ 创建提案时立即创建快照
        let snapshot = create_snapshot();

        move_to(creator, Proposal {
            snapshot_time: timestamp::now_seconds(),
            yes_votes: 0,
            no_votes: 0,
        });

        move_to(creator, snapshot);
    }

    public entry fun vote(
        voter: &signer,
        proposal_addr: address,
        support: bool
    ) acquires Proposal, VotingPowerSnapshot {
        let snapshot = borrow_global<VotingPowerSnapshot>(proposal_addr);
        let voter_addr = signer::address_of(voter);

        // ✅ 使用快照时的投票权
        let vote_power = *table::borrow(&snapshot.powers, voter_addr);

        let proposal = borrow_global_mut<Proposal>(proposal_addr);

        if (support) {
            proposal.yes_votes = proposal.yes_votes + vote_power;
        } else {
            proposal.no_votes = proposal.no_votes + vote_power;
        };
    }
}
```

## Classify

**漏洞判定：**
- 投票权基于 `coin::balance` 实时余额
- 提案创建时未记录快照
- 代币可在投票期间自由转移

**误报识别：**
- 使用 Table 存储快照数据
- 投票权在提案创建时冻结
- 代币被锁定在投票资源中

**代码异味：**
- 直接读取 coin balance
- 缺少快照表结构
- 无代币锁定机制
