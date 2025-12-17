# 暴力破解绕过秘笈

## 速率限制绕过

### IP轮换绕过
```
原始防御：同一IP请求过多直接封禁

绕过方式：
1. 使用代理池更换IP
2. 使用VPN或Tor轮换IP
3. 利用Cloudflare等CDN的多IP回源

示例：
for ip in proxy_list:
    response = requests.get(url, proxies={'http': ip})
```

### X-Forwarded-For伪造
```
服务器仅看X-Forwarded-For而不验证：

正常: GET /login
返回: 暴力破解IP限制

使用代理头：
GET /login
X-Forwarded-For: 192.168.1.1
# 服务器认为来自192.168.1.1，速率限制重置
```

### User-Agent轮换
```
某些防御基于User-Agent计数

绕过：轮换User-Agent
User-Agent: Mozilla/5.0 (第1次)
User-Agent: Chrome/90.0 (第2次)
# 每个User-Agent有独立的限制配额
```

## 时间延迟利用

### 指数退避绕过
```
防御：请求失败后指数延迟

缺陷：如果没有最大延迟时间限制
1. 第1次失败：等待1秒
2. 第2次失败：等待2秒
3. 第3次失败：等待4秒
...
# 只要有足够时间，仍可破解（可在数周内破解所有密码）
```

### 限制时间绕过
```
防御：15分钟内超过5次失败，锁定账户

绕过：
1. 尝试5次，等待15分钟
2. 重复（多天/周内破解）

或利用时钟漂移：
- 快进系统时间
- 某些系统不验证时间顺序
```

## 账户枚举和检测回避

### 通过响应时间差异
```
登录失败响应时间：50ms
登录成功响应时间：200ms（因为做了额外验证或密钥派生）

攻击：
1. 测试所有可能的用户名
2. 记录响应时间
3. 长响应时间 = 用户存在
4. 再进行密码暴破
```

### 批量请求隐藏
```
防御：检测暴力破解IP

隐藏方式：
1. 分散在多个IP（代理轮换）
2. 分散在多个账户名
3. 在正常流量中混入攻击请求
4. 使用有效用户名和常见密码（与真实用户行为相似）
```

## 并发请求优化

### 多线程/并发加速
```python
import concurrent.futures

passwords = load_common_passwords()
with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
    futures = [executor.submit(try_login, pwd) for pwd in passwords]
    for future in concurrent.futures.as_completed(futures):
        if future.result():
            print("Found password!")
            break
```

### 管道化请求
```
HTTP Keep-Alive或HTTP/2多路复用：
发送100个请求，无需等待响应，再读取所有响应
# 绕过某些速率限制（基于请求完成时间而非发送时间）
```

## 登录页面逻辑漏洞

### 多步骤验证分离
```
防御：统一的登录页面有速率限制

缺陷：如果拆分成多个步骤：
1. /api/check-username （无速率限制）
2. /api/check-password （有速率限制但弱）

绕过：
- 分别调用两个API
- 先枚举用户，再破解密码
```

### 弱密码字典
```
常见弱密码（按概率排序）：
123456
password
admin
letmein
...

优化：
1. 先尝试最常见的密码
2. 跳过明显的强密码尝试
3. 结合社工获取的信息（生日、昵称等）
```

## Token和Session预测

### Session ID可预测
```
Session ID格式：timestamp + user_id + hash

攻击：
1. 获取多个有效session
2. 分析模式
3. 生成预测的session
4. 无需密码即可冒充用户
```

### 忘记密码链接可枚举
```
链接格式：/reset?token=abc123

token是：
- 时间戳 (可计算)
- 用户ID (可枚举)
- 弱hash (可破解)

攻击：
1. 为目标用户生成重置链接
2. 伪造token
3. 重置目标密码
```

## 快速定位和利用

**关键词识别**：
- 无速率限制或限制弱
- 无IP白名单/黑名单
- 枚举用户名可行
- Session/Token可预测
- 多步骤验证无整体保护

**测试优先级**：
1. 直接暴力破解（检查速率限制）
2. IP轮换（X-Forwarded-For等）
3. 时间延迟策略分析
4. 用户名枚举
5. 并发请求优化

## 防御检查清单

- ✓ 实施渐进式延迟（1秒、2秒、4秒等）
- ✓ 临时账户锁定（N次失败后锁X分钟）
- ✓ 验证所有来源IP（信任链）
- ✓ 关键操作要求验证码
- ✓ 实施CAPTCHA或其他挑战响应
- ✓ 监控异常登录模式
- ✓ 使用强默认密码策略
- ✓ 定期审计失败登录日志
- ✓ 使用多因素认证(MFA)
