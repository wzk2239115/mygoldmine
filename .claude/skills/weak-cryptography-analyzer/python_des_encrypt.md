# Python DES 加密弱密码学审计

## Details

### 代码示例
```python
# pycryptodome/pycrypto 库使用 DES
from Crypto.Cipher import DES
key = b'8bytekey'
cipher = DES.new(key, DES.MODE_ECB)
encrypted = cipher.encrypt(b'datadata')

# pyDes 库使用 DES
import pyDes
des = pyDes.des('DESCRYPT', pyDes.ECB)
encrypted = des.encrypt('message!')

# 三重 DES (仍属弱加密)
from Crypto.Cipher import DES3
cipher = DES3.new(key, DES3.MODE_CBC, iv)
```

### 快速定位核心操作技巧
- **L1: 关键词扫描** - `import` 语句搜索: `from Crypto.Cipher import DES`、`import pyDes`、`import DES`
- **L1: 关键词扫描** - 类实例化: `DES.new()`、`pyDes.des()`、`DES3.new()`
- **L2: 跳读** - 加密模式识别: `MODE_ECB`（最弱）、`MODE_CBC`、`MODE_CFB`
- **L2: 跳读** - 密钥变量追踪: 定位 `key` 参数来源（硬编码/配置/动态生成）
- **L3: 逐行读** - 数据流分析: 确认加密目标（敏感数据/会话令牌/API 签名）

### 快速定位保护机制技巧
- **L1: 关键词扫描** - 加密算法升级标识: `AES`、`ChaCha20`、`Fernet` 是否并存
- **L2: 跳读** - 配置文件检查: 搜索 `algorithm`、`cipher`、`encryption_method` 配置项
- **L3: 逐行读** - 降级逻辑判断: 是否存在 `try-except` 回退到 DES 的兼容代码
- **L3: 逐行读** - 临时方案标记: 注释中的 `TODO`、`FIXME`、`legacy`、`deprecated`
- **L4: 跨模块追踪** - 加密抽象层: 检查是否通过工厂模式/配置化封装可切换算法

## Classify

### 确认为漏洞
- DES 加密敏感数据（密码、令牌、身份凭证、支付信息）且无额外防护层
- 密钥长度 56 位且硬编码或可预测
- MODE_ECB 模式加密结构化数据（存在明文模式泄露风险）
- 对外暴露加密接口（API/RPC）直接使用 DES

### 判定为误报
- 仅用于单元测试、示例代码、注释掉的历史代码
- 加密非敏感数据且业务逻辑已废弃（无调用链）
- 外层已有 TLS/IPsec 等传输加密且 DES 仅作混淆

### 识别为代码异味
- 使用 DES 但加密目标为低敏感度数据（日志脱敏、缓存 Key 生成）
- 存在现代加密算法并行使用，DES 仅用于向后兼容
- 密钥通过 KMS/HSM 管理但算法本身为 DES

## Low risk

### 低风险评级条件
- **数据敏感度低**: 加密对象为公开数据、已脱敏数据或短期有效缓存
- **攻击成本高**: 密文不对外暴露，仅限内网或受信环境传输
- **已有补偿控制**: 多层加密（外层 AES + 内层 DES）、频繁密钥轮换（< 24h）
- **遗留兼容性**: 对接第三方系统强制要求 DES，且已记录风险并计划迁移
- **攻击时间窗口短**: 加密数据生命周期极短（< 5 分钟）且单次使用后失效