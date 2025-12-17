# Python JWT 签名绕过漏洞

## 漏洞成因
使用 PyJWT、python-jose 等库时禁用或跳过签名验证，导致任意伪造的令牌被接受。核心问题是验证过程中主动设置 `verify=False`、`options={"verify_signature": False}` 或完全跳过验证逻辑。

---

## Details

### 代码示例

**PyJWT 库典型漏洞模式：**

```python
import jwt

# 危险：显式禁用签名验证
payload = jwt.decode(token, options={"verify_signature": False})

# 危险：旧版本 PyJWT 使用 verify 参数
payload = jwt.decode(token, SECRET_KEY, verify=False)

# 危险：不提供密钥且禁用验证
payload = jwt.decode(token, algorithms=["HS256"], options={"verify_signature": False})
```

**python-jose 库典型漏洞模式：**

```python
from jose import jwt

# 危险：跳过签名验证
payload = jwt.decode(token, "", options={"verify_signature": False})

# 危险：捕获异常后仍使用未验证的 payload
try:
    payload = jwt.decode(token, SECRET_KEY)
except:
    payload = jwt.get_unverified_claims(token)  # 直接使用未验证数据
```

### 快速定位核心操作（审计等级：L1-L2）

**L1 关键词扫描：**
- 搜索 `jwt.decode`、`jwt.get_unverified`
- 搜索 `verify_signature`、`verify=False`
- 搜索 `options=` 配合 decode

**L2 跳读技巧：**
- 定位所有 JWT 解码点，检查是否传入 `options` 参数
- 追踪 `options` 字典构造位置，确认 `verify_signature` 键值
- 查看 try-except 块内是否在异常后降级使用未验证数据

### 快速定位保护机制（审计等级：L2-L3）

**L2 跳读技巧：**
- 检查 `jwt.decode` 第二参数是否为有效密钥（非空、非 None）
- 确认 `algorithms` 参数明确指定且不包含 "none"
- 检查是否存在统一认证装饰器/中间件集中处理验证

**L3 逐行读技巧：**
- 追踪密钥来源：环境变量、配置文件、密钥管理系统
- 验证 options 参数默认值，确保无默认禁用验证的配置
- 检查条件分支：生产/开发环境是否有不同验证逻辑

---

## Classify

**漏洞判定条件：**
- `verify_signature` 显式设为 `False` 且在生产代码路径中
- 使用 `get_unverified_claims/get_unverified_headers` 且直接信任其返回值进行鉴权
- 异常捕获后降级使用未验证的 payload 进行身份判断

**误报识别：**
- 仅在测试代码/测试环境配置中禁用验证
- 禁用验证后仅用于日志记录、调试输出，未用于鉴权决策
- 先获取未验证 claims 但后续仍完整验证（如仅为提取 `kid` 选择密钥）

**代码异味：**
- 条件化验证（如 `if DEBUG: verify=False`）即使当前生产环境为 True
- 使用空字符串/None 作为密钥但未禁用验证（会抛异常但设计不当）
- 混用多个验证库导致验证逻辑分散

---

## Low risk

**低风险场景：**
1. **内部系统令牌**：JWT 仅用于内部微服务间通信，且网络边界已完全隔离，攻击者无法触达
2. **非鉴权用途**：JWT 仅用于传递非敏感配置信息，未用于身份验证或权限判断
3. **已有二次验证**：禁用 JWT 验证后，存在其他强鉴权机制（如数据库会话校验、额外签名检查）
4. **只读公开数据**：JWT 声明的资源本身为公开只读数据，即使伪造也无安全影响

**注意**：即使标记低风险，仍应建议修复以遵循安全最佳实践。