# 安全配置绕过秘笈

## 默认凭证和配置

### 默认密码
```
常见默认凭证：
admin / admin
admin / password
root / root
root / toor
test / test
guest / guest

检查清单：
1. 数据库管理工具（MySQL, PostgreSQL, MongoDB）
2. Web应用管理面板
3. 设备管理界面（路由器、防火墙）
4. 云服务控制台
```

### 调试界面暴露
```
常见调试端口和路径：
8008, 9000, 5000, 3000（开发服务器）

路径：
/debug/
/admin/
/console/
/__pycache__/
/dev/
/test/
```

## HTTP头和安全配置缺失

### 缺少安全头
```
X-Frame-Options: DENY          # 防Clickjacking
X-Content-Type-Options: nosniff # 防MIME猜测
Strict-Transport-Security      # HTTPS强制
Content-Security-Policy        # 防XSS
X-XSS-Protection              # IE XSS保护

缺失这些头的应用容易被攻击
```

### HTTPS配置不当
```
- HTTP降级到HTTPS时未加密
- 混合内容（HTTPS页面加载HTTP资源）
- 证书验证不当
- 过期或自签名证书被信任

攻击：中间人可拦截通信
```

## CORS配置漏洞

### 过于宽松的CORS
```
Access-Control-Allow-Origin: *
Access-Control-Allow-Credentials: true

# 允许任何源进行跨域请求，包括Cookie

漏洞：任何网站都能以用户身份发起请求
```

### 动态CORS头验证
```
应用接受请求的Origin值直接作为CORS头返回：

请求：Origin: https://attacker.com
响应：Access-Control-Allow-Origin: https://attacker.com

# 攻击者网站可跨域访问
```

## 服务器配置暴露

### 目录列表启用
```
服务器配置启用目录浏览：
Apache: Options Indexes
Nginx: autoindex on

访问/uploads/、/downloads/等目录
看到所有文件列表
```

### Git和版本控制暴露
```
.git目录未被保护：
/.git/config  # 获取仓库信息
/.git/logs/HEAD  # 查看提交历史

可恢复整个源代码
```

### 备份文件暴露
```
常见备份：
/index.php~
/index.php.bak
/index.php.old
/index.php.swp
/web.config.backup

通过这些文件获取源代码或配置
```

## 错误处理和信息泄露

### Stack trace泄露
```
生产环境中显示详细错误信息：
- 服务器路径
- 数据库查询
- 代码行号
- 库版本

帮助攻击者了解系统
```

### 信息枚举
```
错误消息泄露敏感信息：
"User not found"  # 用户枚举
"Invalid password"  # 密码提示
"Database connection failed"  # 基础设施信息
```

## 默认应用和路由暴露

### 默认应用文件
```
/phpmyadmin/  # MySQL管理
/wp-admin/  # WordPress后台
/admin/  # 通用后台
/api/  # API根目录
/swagger/  # API文档
/graphql/  # GraphQL端点
```

### 源代码管理系统暴露
```
/.git/
/.hg/
/.svn/
Dockerfile  # 容器配置
docker-compose.yml  # 服务配置
requirements.txt  # Python依赖（可获知版本）
package.json  # Node.js依赖
```

## 权限配置错误

### 文件权限不当
```
配置文件权限过于宽松：
chmod 644 /etc/mysql/my.cnf  # 密码暴露

数据库备份可读：
-rw-r--r-- backup.sql  # 所有人可读

日志文件过于详细且可读
```

### Web服务器权限
```
上传目录可执行：
/uploads有execute权限

临时目录可写且web可访问：
/tmp/web可通过URL访问
```

## 快速定位和利用

**关键词识别**：
- 默认端口运行（3000, 5000, 8080等）
- 公开的git目录
- 目录列表启用
- Stack trace显示
- 调试模式启用

**信息收集工具**：
```bash
# 检查常见路径
curl https://target.com/.git/config
curl https://target.com/phpmyadmin
curl https://target.com/debug/

# 检查安全头
curl -I https://target.com

# 获取git历史
git clone https://target.com/.git
git log
git show
```

**测试优先级**：
1. 检查默认凭证（数据库、管理面板）
2. 枚举常见路径（/admin, /debug等）
3. 查找版本控制暴露
4. 检查安全头
5. 尝试目录遍历

## ReDoS (正则表达式拒绝服务) - CWE-1333

### 漏洞原理
ReDoS（Regular Expression Denial of Service）是一种通过构造特定的输入字符串，使正则表达式引擎陷入**灾难性回溯（Catastrophic Backtracking）**，导致CPU资源耗尽、响应时间极长的拒绝服务攻击。

### 危险的正则表达式模式
```regex
(a+)+$          # 嵌套量词 - 危险！
(a*)*$          # 嵌套量词 - 危险！
(a|a)*$         # 重复交替 - 危险！
(a|ab)*$        # 重叠交替 - 危险！
.*?a.*?a.*?a    # 多个非贪婪量词 - 危险！
```

### 攻击示例
```javascript
// 危险的正则表达式
const regex = /^(a+)+$/;

// 攻击输入：大量'a'后跟一个'b'
const attackString = 'a'.repeat(30) + 'b';

// 匹配时间：指数级增长
// 30个a: ~1ms
// 40个a: 可能超过1秒
// 50个a: 可能超过1分钟

regex.test(attackString);  // CPU占用100%，响应极慢
```

### PHP中的PCRE回溯限制
```php
// 危险的正则表达式
$pattern = '/(a+)+$/';

// 攻击输入
$input = str_repeat('a', 1000000) . 'b';

// PHP的pcre.backtrack_limit默认值为1000000
// 当回溯次数超过限制时，preg_match返回false
// 但在此之前，CPU已经被大量消耗

preg_match($pattern, $input);  // 可能导致超时或资源耗尽
```

### 实际Web应用场景
```python
# 危险：用户输入直接用于正则匹配
import re

def validate_email(email):
    # 这个正则表达式存在ReDoS风险
    pattern = r'^([a-zA-Z0-9]+\.)*[a-zA-Z0-9]+@([a-zA-Z0-9]+\.)*[a-zA-Z0-9]+$'
    return re.match(pattern, email)

# 攻击者输入
attack_email = 'a' * 10000 + '@' + 'b' * 10000
validate_email(attack_email)  # CPU占用极高，响应极慢
```

### 快速定位技巧
1. **搜索正则表达式使用**
   ```bash
   # PHP
   grep -r "preg_match\|preg_replace\|preg_split" .
   
   # Python
   grep -r "re.match\|re.search\|re.findall" .
   
   # JavaScript
   grep -r "\.match\|\.test\|new RegExp" .
   ```

2. **检查危险模式**
   - 嵌套量词：`(a+)+`, `(a*)*`, `(a?)+`
   - 重复交替：`(a|a)*`, `(a|ab)*`
   - 多个非贪婪：`.*?.*?.*?`

3. **检查用户输入**
   - 用户输入是否直接用于正则匹配
   - 是否有长度限制
   - 是否有超时机制

### 防护措施
```php
// 1. 设置回溯限制
ini_set('pcre.backtrack_limit', 10000);

// 2. 使用内置函数（更安全）
filter_var($email, FILTER_VALIDATE_EMAIL);

// 3. 限制输入长度
if (strlen($input) > 100) {
    return false;
}

// 4. 检查preg_match返回值
if (preg_match($pattern, $input) === false) {
    // 回溯限制被触发
    error_log('ReDoS detected: backtrack limit exceeded');
}
```

```python
# Python: 使用超时机制
import signal

def timeout_handler(signum, frame):
    raise TimeoutError("Regex matching timeout")

signal.signal(signal.SIGALRM, timeout_handler)
signal.alarm(1)  # 1秒超时

try:
    result = re.match(pattern, input)
finally:
    signal.alarm(0)
```

### 安全的正则表达式替代方案
```regex
# 危险: (a+)+
# 安全: a+  (等价但无回溯问题)

# 危险: (a|a)*
# 安全: a*  (等价但无回溯问题)

# 危险: .*?a.*?a.*?a
# 安全: [^a]*a[^a]*a[^a]*a  (使用否定字符类)
```

### 审计要点
1. **输入来源**：用户输入 → 正则匹配
2. **正则复杂度**：是否存在危险模式（嵌套量词、重复交替）
3. **防护措施**：是否有超时、限制、白名单
4. **影响范围**：是否影响核心功能、是否可能导致服务不可用

## 防御检查清单

- ✓ 更改所有默认凭证
- ✓ 禁用调试模式在生产环境
- ✓ 隐藏服务器信息和版本号
- ✓ 设置所有安全HTTP头
- ✓ 配置正确的CORS策略
- ✓ 禁用目录列表
- ✓ 保护敏感文件（.git, .env等）
- ✓ 实施正确的文件和目录权限
- ✓ 错误处理：不显示Stack trace
- ✓ 定期审计配置和权限
- ✓ 扫描暴露的敏感文件
- ✓ **配置正则表达式复杂度限制（防止ReDoS）**
- ✓ **设置正则匹配超时机制**
- ✓ **限制用户输入长度**
- ✓ **使用内置验证函数替代复杂正则**
