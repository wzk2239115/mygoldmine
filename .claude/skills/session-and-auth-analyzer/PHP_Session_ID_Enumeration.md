# PHP_Session_ID_Enumeration

**漏洞类型**: PHP 原生 Session 或自定义会话管理中，会话ID可被系统枚举或预测，导致攻击者可尝试使用不同的会话ID访问他人账户

---

## Details

### 代码示例

**易受攻击的代码模式**:
```php
// 示例1: PHP 原生会话ID生成不安全
session_start();
$sessionId = session_id();
// 默认 ID 可能可被枚举

// 示例2: 自定义会话ID，长度过短
function generateSessionId() {
    return substr(md5(time()), 0, 8);  // 仅 8 字符
}

// 示例3: 会话ID来自用户输入
if (isset($_COOKIE['PHPSESSID'])) {
    session_id($_COOKIE['PHPSESSID']);  // 接受用户提供的 ID
}
session_start();

// 示例4: 数据库会话存储未限制访问
// SELECT * FROM sessions WHERE id = <user_input>
// 可通过遍历所有会话 ID 获取其他用户数据

// 示例5: URL 中暴露会话ID
header("Location: /dashboard.php?PHPSESSID=" . session_id());

// 示例6: 会话 ID 在日志中可见
error_log("Session: " . session_id());
```

### 快速定位核心操作 **[L1-L2]**

**L1 关键词扫描**:
- 会话 ID: `session_id()`, `PHPSESSID`, `_SESSION`, `$_COOKIE['session']`
- ID 生成: 自定义 `generateSessionId()`, `md5()` 生成的 ID
- 长度检查: `substr()` 限制长度的 ID
- 会话访问: `session_id(...)`, `$_COOKIE` 中的会话 ID
- 存储位置: 数据库会话表

**L2 跳读定位**:
- 会话初始化: `session_start()`, `session_id()` 调用
- ID 生成逻辑: 自定义函数的实现
- 访问控制: 会话数据的权限检查
- 会话文件存储: `/tmp/` 目录权限

### 快速定位保护机制 **[L2-L4]**

**L2 跳读检测**:
- 安全 ID 生成: `bin2hex(random_bytes())`, 密码学安全的随机
- 会话文件权限: `0600` 权限检查
- 数据库访问控制: WHERE 语句中的权限检查

**L3 逐行分析**:
- ID 生成:
  - 是否使用 `random_bytes()` 生成
  - ID 长度是否 >= 32 字符
  - 是否避免使用时间戳
  - 编码方式是否保留完整熵值
- 数据库访问:
  - SELECT 语句是否验证 `WHERE user_id = current_user`
  - 是否允许用户通过 session_id 直接查询
  - 是否有行级安全策略

**L4 跨模块追踪**:
- 追踪会话初始化的所有入口
- 检查是否有自定义的 session handler
- 验证所有会话访问的权限检查
- 审查日志中是否记录会话 ID

---

## Classify

### 漏洞判定标准

**确认为漏洞**:
- 会话 ID 长度 < 16 字符或熵值明显不足
- 会话 ID 由时间戳或计数器组成
- 可通过遍历 ID 访问其他用户会话
- URL 中暴露会话 ID

**误报判定**:
- 会话 ID 由密码学安全的随机数生成，长度足够
- PHP 原生会话使用默认的安全配置
- 数据库存储时有权限检查

**代码异味**:
- 会话 ID 生成长度在 8-15 字符之间
- URL 中有 PHPSESSID 或自定义会话参数

---

## Low risk

### 低风险场景

**权限检查**:
- 虽然会话 ID 可被枚举，但数据库查询有权限检查

**监控**:
- 实时检测会话 ID 枚举尝试
