# Python JWT Claim Ignored

## 漏洞成因
解码JWT时通过options参数主动禁用exp/aud/iss等声明校验，或使用verify=False，导致过期令牌、未授权audience、伪造issuer的token均可通过验证。

---

## Details

### 代码示例

**PyJWT库典型漏洞模式：**

```python
import jwt

# 漏洞1：完全禁用验证
payload = jwt.decode(token, SECRET_KEY, verify=False)

# 漏洞2：显式禁用exp校验
payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'], 
                     options={'verify_exp': False})

# 漏洞3：禁用多个声明校验
payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'],
                     options={
                         'verify_exp': False,
                         'verify_aud': False,
                         'verify_iss': False
                     })

# 漏洞4：仅校验签名不校验声明
payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'],
                     options={'verify_signature': True, 'verify_exp': False})
```

**python-jose库漏洞模式：**

```python
from jose import jwt

# 禁用exp校验
payload = jwt.decode(token, SECRET_KEY, options={'verify_exp': False})
```

### 快速定位核心操作技巧 **[L1-L2]**

**L1关键词扫描：**
- 搜索 `jwt.decode` 调用点
- 定位 `verify=False` 或 `options=` 参数
- 检索 `verify_exp`、`verify_aud`、`verify_iss` 关键字

**L2跳读确认：**
- 检查decode()第三个参数（algorithms）是否存在
- 检查options字典中verify_*键值是否为False
- 确认是否存在`verify=False`全局禁用

### 快速定位保护机制技巧 **[L2-L3]**

**L2跳读检查：**
- 查找`jwt.decode`调用时options参数是否缺省（缺省则默认开启所有验证）
- 确认是否传入`audience=`、`issuer=`参数进行显式校验

**L3逐行验证：**
- 检查decode后是否有手动校验exp逻辑（`if payload['exp'] < time.time()`）
- 确认是否在业务层二次校验aud/iss（`if payload.get('aud') != EXPECTED_AUD`）
- 验证是否使用装饰器或中间件统一处理JWT校验

**保护性代码特征：**
```python
# 正确示例：默认启用所有验证
payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])

# 显式声明校验
payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'],
                     audience='myapp', issuer='auth-service')
```

---

## Classify

### 漏洞判定标准
1. **明确禁用校验**：options中任何`verify_*=False`或全局`verify=False`直接定性为漏洞
2. **场景区分**：如果token用于身份认证/授权决策且缺失校验，属于高危漏洞
3. **上下文关联**：若decode后立即进行业务层手动校验（如检查exp时间戳），可降级为代码异味

### 误报识别
1. **非认证场景**：仅用于解析公开数据（如公开API响应）而非权限验证
2. **测试代码**：位于test/目录或被`@pytest.mark`装饰的测试函数中
3. **Decode-only场景**：明确注释说明仅解析payload不做验证（需结合后续有严格验证逻辑）

### 代码异味特征
1. **部分禁用**：仅禁用aud/iss但保留exp校验，且业务确实不需要audience/issuer验证
2. **双重验证**：禁用库级校验但实现了等效的业务层校验（冗余但安全）

---

## Low Risk

### 低风险评级条件
1. **非核心身份场景**：token仅用于前端展示数据、日志追踪等非授权决策
2. **内网隔离环境**：仅在完全可信的内部服务间传递，且攻击者无法接触token生成/传输链路
3. **短生命周期+严格上下文**：exp禁用但token有效期极短（<1分钟）且结合其他强验证机制（如IP白名单、TLS双向认证）
4. **显式业务需求**：架构设计明确要求支持过期token重放（如幂等性保障），且有完善的业务层防护
5. **Legacy兼容**：为兼容旧系统临时禁用校验，且已规划修复roadmap并有compensating controls

### 注意事项
即使满足低风险条件，仍需在审计报告中标注为"待改进项"，避免未来场景变化导致风险升级。