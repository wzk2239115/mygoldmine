# Python | Session验证码暴力破解漏洞

## 基本信息
- **难度等级：** ★★☆☆☆ (初级)
- **审计时间：** 15-25分钟

## 🚀 30秒快速清单
- [ ] 验证码是否存储在Session中？
- [ ] 是否设置了过期时间？
- [ ] 是否有尝试次数限制？
- [ ] 是否有速率限制？

## Details

### 漏洞成因
Django/Flask在Session中存储验证码，常见问题：缺乏过期时间、无尝试限制、无速率限制。

### 代码示例

```python
# 漏洞1：验证码无过期时间
from flask import session

@app.route('/request-captcha', methods=['POST'])
def request_captcha():
    captcha = str(random.randint(1000, 9999))
    session['captcha'] = captcha
    # 问题：无过期时间戳
    return jsonify({'status': 'ok'})

@app.route('/verify-captcha', methods=['POST'])
def verify_captcha():
    input_code = request.json.get('code')
    stored = session.get('captcha')
    # 问题：无时间检查，验证码永不过期
    if input_code == stored:
        return jsonify({'status': 'ok'})
    # 问题：无尝试限制
    return jsonify({'error': 'Invalid'})
```

```python
# 漏洞2：无请求限制
def request_captcha():
    # 问题：无请求限制，可无限请求新验证码
    captcha = str(random.randint(1000, 9999))
    session['captcha'] = captcha
    return jsonify({'status': 'ok'})
```

### 快速定位
- **生成**：`random.randint()`, `session['captcha'] = ...`
- **验证**：`session.get()`, `==` 比较, 缺少计数
- **存储**：Session无 `captcha_time` 时间戳

### 保护机制
- **过期时间**：时间戳检查，10分钟过期
- **尝试限制**：最多3次，超过自动失效
- **请求限制**：`flask-limiter`, 3次/小时
- **延迟**：验证失败有延迟
- **统一响应**：相同消息和延迟

---

## Classify

### 确认漏洞
1. Session无过期时间戳
2. 无尝试计数
3. 无请求限制
4. 验证码过短（4位数字）

### 误报排除
- ✗ 时间戳检查
- ✗ 尝试限制≤3
- ✗ 速率限制
- ✗ 6位字母数字

---

## Low Risk

1. **时间管理**：验证时检查过期
2. **尝试限制**：≤3次，超过删除
3. **请求限制**：3-5次/小时
4. **安全验证码**：≥6位字母数字

---

## 安全实现

```python
import redis
import random
import string
import time
from flask import Flask, request, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

app = Flask(__name__)
redis_client = redis.Redis(host='localhost', port=6379)
limiter = Limiter(app=app, key_func=get_remote_address)

class VerificationCodeService:
    CODE_LENGTH = 8
    VALIDITY_MINUTES = 10
    MAX_ATTEMPTS = 3
    MAX_REQUESTS_PER_HOUR = 3

    @staticmethod
    def generate_code():
        chars = string.ascii_uppercase + string.digits
        return ''.join(random.choices(chars, k=VerificationCodeService.CODE_LENGTH))

    @staticmethod
    def request_code(email):
        # 速率限制检查
        key = f"requests:{email}"
        count = redis_client.incr(key)
        if count == 1:
            redis_client.expire(key, 3600)
        if count > VerificationCodeService.MAX_REQUESTS_PER_HOUR:
            return False

        # 生成验证码
        code = VerificationCodeService.generate_code()
        ttl = VerificationCodeService.VALIDITY_MINUTES * 60

        redis_client.setex(f"captcha:{email}", ttl, code)
        redis_client.setex(f"attempts:{email}", ttl, "0")
        return True

    @staticmethod
    def verify_code(email, input_code):
        key = f"captcha:{email}"
        attempts_key = f"attempts:{email}"

        stored = redis_client.get(key)
        if not stored:
            return False

        attempts = int(redis_client.get(attempts_key) or 0)
        if attempts >= VerificationCodeService.MAX_ATTEMPTS:
            redis_client.delete(key)
            redis_client.delete(attempts_key)
            return False

        redis_client.incr(attempts_key)

        if input_code != stored.decode():
            # 延迟
            time.sleep(min(0.1 * (2 ** attempts), 5))
            return False

        # 成功，清理
        redis_client.delete(key)
        redis_client.delete(attempts_key)
        return True

@app.route('/request-code', methods=['POST'])
@limiter.limit("3 per hour")
def request_code():
    data = request.json
    if VerificationCodeService.request_code(data.get('email')):
        pass
    # 统一响应
    return jsonify({'message': 'Code sent if email exists'})

@app.route('/verify-code', methods=['POST'])
def verify_code():
    data = request.json
    if VerificationCodeService.verify_code(data.get('email'), data.get('code')):
        return jsonify({'status': 'ok'})
    return jsonify({'error': 'Invalid'}), 400
```

## 修复优先级

1. **当天**：添加时间戳检查
2. **3天**：尝试限制+速率限制
3. **1周**：延迟机制+统一响应
