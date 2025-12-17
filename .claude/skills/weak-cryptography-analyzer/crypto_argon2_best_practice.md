# Weak Cryptography - Argon2 密码派生函数最佳实践

## Details

### 什么是 Argon2

**Argon2** 是由 NIST 推荐的现代密码派生函数（KDF），专门设计用于密码哈希和密钥派生。相比 PBKDF2、Bcrypt 和 Scrypt，Argon2 具有以下优势：

- **内存困难**：抗 GPU 和 ASIC 攻击
- **时间困难**：调整迭代次数增加计算成本
- **抗通道侧信息**：设计用于防止某些类型的侧信息泄露
- **现代推荐**：Password Hashing Competition 获胜者

Argon2 有两个变种：
- **Argon2i**：针对隐私敏感应用（抗侧信息泄露，但速度慢）
- **Argon2d**：针对高性能应用（更快，但可能受到侧信息泄露）
- **Argon2id**（推荐）：混合模式，平衡性能和安全性

### 不安全的密码派生实现

**Java - Argon2 使用不当：**
```java
import de.mkammerer.argon2.Argon2Factory;

public class PasswordService {
    private Argon2 argon2 = Argon2Factory.create();

    // 危险 1：参数设置过低
    public String hashPassword(String password) {
        // 内存只有 16KB（太小），迭代次数只有 2（太少）
        return argon2.hash(2, 16, 1, password);
    }

    // 危险 2：使用默认参数但未验证
    public boolean verifyPassword(String password, String hash) {
        // 假设没有验证参数是否符合安全标准
        return argon2.verify(hash, password);
    }

    // 危险 3：使用 Argon2i 而非 Argon2id
    public String weakHash(String password) {
        Argon2 weakArgon2 = Argon2Factory.createArgon2i();
        return weakArgon2.hash(3, 65536, 1, password);
    }
}
```

**Python - Argon2 使用不当：**
```python
from argon2 import PasswordHasher
from argon2 import VerifyMismatchError

def unsafe_hash(password):
    # 危险 1：使用默认参数但未检查
    ph = PasswordHasher()
    hash = ph.hash(password)
    return hash

    # 危险 2：自定义参数过低
    # ph = PasswordHasher(
    #     time_cost=1,      # 太少迭代
    #     memory_cost=8,    # 太少内存（8KB）
    #     parallelism=1
    # )

def verify_unsafe(password, hash):
    ph = PasswordHasher()
    try:
        # 危险 3：验证时参数变化会导致验证失败
        ph.verify(hash, password)
        return True
    except VerifyMismatchError:
        return False

# 危险 4：使用了 Argon2i 而非 Argon2id
from argon2 import PasswordHasher, Algorithm
ph = PasswordHasher(type=Algorithm.I)  # 应使用 ID
```

**Node.js - Argon2 使用不当：**
```javascript
const argon2 = require('argon2');

// 危险 1：参数设置过低
async function hashPassword(password) {
    const hash = await argon2.hash(password, {
        type: argon2.argon2i,  // 应使用 argon2id
        memoryCost: 1024,      // 太小（1MB）
        timeCost: 1,           // 太小
        parallelism: 1
    });
    return hash;
}

// 危险 2：未设置参数导致默认值变更
async function weakHash(password) {
    // 可能使用了过时的默认参数
    const hash = await argon2.hash(password);
    return hash;
}

// 危险 3：验证时参数不一致
async function verifyPassword(password, hash) {
    const options = {
        memoryCost: 65536,  // 参数与哈希时不同
        timeCost: 3
    };
    return await argon2.verify(hash, password, options);
}
```

**PHP - Argon2 使用不当：**
```php
<?php
// PHP 7.2+ 内置 Argon2 支持

// 危险 1：使用 PASSWORD_BCRYPT 而非 PASSWORD_ARGON2ID
$hash = password_hash($password, PASSWORD_BCRYPT);

// 危险 2：Argon2 参数设置过低
$options = [
    'memory_cost' => 512,   // 太小（512KB）
    'time_cost'  => 2,      // 太小
    'threads'    => 1
];
$hash = password_hash($password, PASSWORD_ARGON2ID, $options);

// 危险 3：未正确验证参数
$hash = password_hash($password, PASSWORD_ARGON2ID);
// 默认参数可能随 PHP 版本变化

// 危险 4：重新哈希逻辑缺陷
if (!password_verify($password, $hash)) {
    return false;
}
// 应该检查是否需要重新哈希（参数变化时）
```

### 安全的 Argon2 实现

**正确的参数设置：**

```
现代推荐（2023-2024）：
- memory_cost: 64MB (65536 KB) - 抗 GPU 攻击
- time_cost: 3 - 迭代次数
- parallelism: 4 - 并行线程数（可根据 CPU 核心数调整）
- type: Argon2id - 混合模式（推荐）
- salt: 自动生成，至少 16 字节（大多数库自动处理）

调整建议：
- 移动设备：降低 memory_cost 到 32MB
- 高性能场景：增加 parallelism 到 8 或更多
- 严格安全：增加 time_cost 到 4-5
```

**Java - 正确的 Argon2：**
```java
import de.mkammerer.argon2.Argon2Factory;
import de.mkammerer.argon2.Argon2;

public class SecurePasswordService {
    private final Argon2 argon2 = Argon2Factory.create(Argon2Version.V_13);

    public String hashPassword(String password) {
        // 推荐参数：
        // iterations: 3
        // memory: 65536 (64MB)
        // parallelism: 4
        return argon2.hash(3, 65536, 4, password);
    }

    public boolean verifyPassword(String password, String hash) {
        try {
            return argon2.verify(hash, password);
        } finally {
            argon2.wipePassword(password);  // 清除内存中的密码
        }
    }
}
```

**Python - 正确的 Argon2：**
```python
from argon2 import PasswordHasher, Algorithm

def hash_password(password):
    # 推荐参数
    ph = PasswordHasher(
        time_cost=3,           # 迭代次数
        memory_cost=65536,     # 64MB
        parallelism=4,         # 并行度
        type=Algorithm.ID      # Argon2id（推荐）
    )
    return ph.hash(password)

def verify_password(password, hash_value):
    ph = PasswordHasher()
    try:
        # hash 中包含了参数信息，验证时自动使用
        ph.verify(hash_value, password)

        # 如果参数已更新，检查是否需要重新哈希
        if ph.check_needs_rehash(hash_value):
            # 密码安全但参数已过期，需要重新哈希
            return "NEEDS_REHASH"
        return True
    except Exception:
        return False
```

**Node.js - 正确的 Argon2：**
```javascript
const argon2 = require('argon2');

async function hashPassword(password) {
    const hash = await argon2.hash(password, {
        type: argon2.argon2id,  // Argon2id
        memoryCost: 65536,      // 64MB
        timeCost: 3,            // 迭代次数
        parallelism: 4,         // 并行度
        hashLength: 32,         // 输出长度（字节）
        saltLength: 16          // 盐长度（自动生成）
    });
    return hash;
}

async function verifyPassword(password, hash) {
    try {
        const match = await argon2.verify(hash, password, {
            // 可选：指定验证参数，但通常从 hash 中读取
        });
        return match;
    } catch (err) {
        return false;
    }
}
```

**PHP - 正确的 Argon2：**
```php
<?php
function hashPassword($password) {
    $options = [
        'memory_cost' => 65536,  // 64MB
        'time_cost'   => 3,      // 迭代次数
        'threads'     => 4       // 并行度
    ];
    return password_hash($password, PASSWORD_ARGON2ID, $options);
}

function verifyPassword($password, $hash) {
    if (!password_verify($password, $hash)) {
        return false;
    }

    // 检查参数是否需要更新
    $options = [
        'memory_cost' => 65536,
        'time_cost'   => 3,
        'threads'     => 4
    ];

    if (password_needs_rehash($hash, PASSWORD_ARGON2ID, $options)) {
        // 参数已过时，需要在用户下次登录时重新哈希
        return "NEEDS_REHASH";
    }

    return true;
}
?>
```

### 快速定位核心操作（L1: 关键词扫描）

**Argon2 库识别：**
```
Java:
  de.mkammerer:argon2-jvm
  com.lambdaworks:scrypt
  Argon2Factory

Python:
  argon2-cffi
  from argon2 import PasswordHasher
  pip install argon2-cffi

Node.js:
  argon2
  npm install argon2

PHP:
  password_hash(..., PASSWORD_ARGON2ID)
  php-argon2

Go:
  golang.org/x/crypto/argon2

Rust:
  argon2 crate
  pwhash crate
```

**参数关键词：**
- `memory_cost`, `memoryCost`, `memory_size`
- `time_cost`, `timeCost`, `iterations`
- `parallelism`, `threads`
- `Argon2id`, `Argon2i`, `Argon2d`
- `salt`, `saltLength`

**危险模式：**
```
// 参数过低
memory_cost < 32768  (< 32MB)
time_cost < 2
parallelism < 2

// 使用弱类型
Argon2i 而不是 Argon2id

// 未实现参数更新
密码存储后，参数有了新建议但代码未更新

// 验证时参数变化
哈希时 memory_cost=65536，验证时 memory_cost=32768
```

### 快速定位保护机制（L2: 跳读）

**正确的参数配置：**
```
推荐值（2024）：
- memory_cost: >= 64MB (65536 KB)
- time_cost: >= 3
- parallelism: >= 4
- type: Argon2id（不是 Argon2i）
```

**参数更新机制：**
```python
# Python 示例
def should_rehash(password_hash):
    current_options = {
        'memory_cost': 65536,
        'time_cost': 3,
        'parallelism': 4
    }
    return argon2.PasswordHasher().check_needs_rehash(
        password_hash,
        type=argon2.Algorithm.ID,
        **current_options
    )
```

**内存清理：**
```java
// Java 示例：验证后清除密码
finally {
    argon2.wipePassword(password);
}
```

**审计技巧（L3: 逐行读）：**
- 查找所有 Argon2 初始化和参数设置
- 检查 memory_cost 是否 >= 32768
- 检查 time_cost 是否 >= 2
- 确认使用的是 Argon2id 而非 Argon2i
- 验证 salt 长度 >= 16 字节
- 检查是否实现了参数更新机制

**跨模块保护（L4: 跨模块追踪）：**
- 密码存储是否统一使用相同的 Argon2 配置
- 是否有中央配置文件定义参数
- 是否实现了 "check_needs_rehash" 逻辑在登录时

## Classify

### 确认为漏洞

- 使用了 Argon2 但参数设置过低（memory < 32MB, time < 2）
- 使用 Argon2i 而非 Argon2id
- salt 长度 < 16 字节或未生成随机 salt
- 未实现参数更新机制，导致参数过期
- 验证时参数与存储时参数不一致
- 密码未被清除出内存

### 误报场景

- 参数设置符合现代标准（memory >= 64MB, time >= 3, parallelism >= 4）
- 使用 Argon2id 且 salt 长度正确
- 实现了 check_needs_rehash 机制
- 密码在使用后被显式清除
- 应用运行在高约束环境（移动设备）但参数已相应调整

### 代码异味

- 应用中存在多个不同的 Argon2 参数配置
- 参数配置硬编码在代码中，难以更新
- 验证逻辑中参数可被用户控制
- 没有日志记录密码哈希操作或参数变更

## Low risk

### 降级为低风险的情况

- **足够的参数**：memory >= 64MB, time >= 3, parallelism >= 4
- **使用 Argon2id**：显式使用 Argon2id（不是 i 或 d）
- **足够的 salt**：salt 长度 >= 16 字节，使用加密随机数生成器
- **参数更新机制**：实现了 check_needs_rehash，定期重新哈希过期密码
- **内存清理**：验证后清除密码变量
- **配置可维护**：参数存储在配置文件或环境变量，便于更新

### 需要额外评估的因素

- 应用是否会频繁验证密码（高频调用可能需要降低参数）
- 是否有监视机制检测异常高频的密码验证（暴力破解）
- 参数上次更新是在何时
- 是否定期审查 NIST 或密码学社区的最新建议
- 迁移机制是否完善（从旧参数迁移到新参数）
