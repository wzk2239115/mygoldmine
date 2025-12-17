# PHP_Protocol_Field_Conversion

**漏洞类型**: 协议字段解包转换，网络协议解析中的类型转换

**PHP**

PHP 中二进制协议解析通过 `unpack()`, `ord()`, 位运算等方式提取字段。网络字节序（大端法）与主机字节序转换、有符号/无符号字段混淆、字段长度/偏移量的边界检查不足等问题常导致缓冲区越界、内存泄露或逻辑错误。特别是在用户输入的网络包解析中，类型转换不当可导致严重漏洞。

---

## Details

### 代码示例与核心操作定位

**危险模式1：协议长度字段直接用于内存分配**
```php
function parseHttpPacket($packet_data) {
    $header = unpack('N', substr($packet_data, 0, 4));  // 读取大端整数
    $content_length = (int)$header[1];  // 无范围检查

    $content = substr($packet_data, 4, $content_length);  // 可能超出缓冲区
    return $content;
}

// 攻击：构造恶意包，content_length 为巨大值
parseHttpPacket(pack('N', 999999999) . 'payload');  // 内存溢出
```

**危险模式2：有符号/无符号字段混淆**
```php
function parseTcpOptions($packet) {
    $offset = 0;
    $option_length = ord($packet[$offset]);  // 字节为 0-255 无符号

    if ($option_length < 0) {  // 永远不可能为真！
        return error();
    }

    $option_data = substr($packet, $offset + 1, $option_length);
    return $option_data;
}

// 攻击：option_length > 127 时判断失败
parseTcpOptions("\xFF" . "payload");  // ord 返回 255，判断失败
```

**危险模式3：多字段组合未完整验证**
```php
function parseMessageFrame($data) {
    // 解包：版本(1字节) + 标志(1字节) + 长度(2字节) + 数据
    $header = unpack('C2flags/nlen', $data);

    $frame_length = $header['len'];  // unpack 返回有符号短整数
    $offset = 4;  // 头部长度

    // 检查：offset + 实际长度 vs 缓冲区长度
    if ($offset + $frame_length > strlen($data)) {
        return error();
    }

    // 但 $frame_length 可能为负数！
    if ($frame_length < 0) {
        // 负数导致 substr 从后往前读取
        $payload = substr($data, $offset, $frame_length);
        return $payload;
    }

    return substr($data, $offset, $frame_length);
}

// 攻击：构造 len 为 0x8000（有符号为 -32768）
parseMessageFrame(pack('C2ndata', 1, 1, 0x8000));
```

**危险模式4：协议偏移量字段直接用于索引**
```php
function extractField($packet) {
    // 协议格式: 计数(1字节) + [偏移量(2字节) + 长度(2字节)] * N + 数据
    $count = ord($packet[0]);

    for ($i = 0; $i < $count; $i++) {
        $offset_pos = 1 + $i * 4;
        $offset = unpack('n', substr($packet, $offset_pos, 2))[1];
        $length = unpack('n', substr($packet, $offset_pos + 2, 2))[1];

        // 无验证直接使用偏移量和长度
        $field = substr($packet, $offset, $length);
        processField($field);
    }
}

// 攻击：构造包含超出范围的 offset 和 length
```

**危险模式5：网络字节序转换错误**
```php
function parseIpHeader($packet) {
    // IP 头：版本(4bit) + IHL(4bit) + ToS(1字节) + 总长(2字节)
    $header = unpack('C', $packet[0]);
    $version = ($header[1] >> 4) & 0x0F;
    $ihl = ($header[1] & 0x0F) * 4;  // IHL 单位为 32 位字，乘以 4

    $total_length = unpack('n', substr($packet, 2, 2))[1];  // 大端 16 位

    // 检查包是否完整
    if ($ihl > $total_length) {
        return error();
    }

    $payload = substr($packet, $ihl, $total_length - $ihl);
    return $payload;
}

// 攻击：构造 ihl 或 total_length 导致整数溢出或越界
```

**危险模式6：协议字段用于循环计数**
```php
function parseRecords($data) {
    $record_count = unpack('N', substr($data, 0, 4))[1];  // 无上限检查

    for ($i = 0; $i < $record_count; $i++) {  // DoS 风险
        $record = unpack('nlen', substr($data, 4 + $i * 6, 2));
        echo $record['len'];
    }

    return true;
}

// 攻击：传入 record_count = 0xFFFFFFFF，导致无限循环
parseRecords(pack('N', 0xFFFFFFFF));
```

**危险模式7：字节序转换后直接用于权限判断**
```php
function validateMessageAuth($message) {
    // 消息格式: 权限位(1字节) + 用户ID(4字节) + 数据
    $perms_byte = ord($message[0]);
    $user_id = unpack('N', substr($message, 1, 4))[1];

    // 权限位解析：第 0-2 位为权限等级
    $permission_level = $perms_byte & 0x07;

    if ($permission_level >= 5) {
        // 权限等级检查依赖于字节转换
        grantAdminAccess();  // 可能被绕过
    }

    return $permission_level;
}

// 攻击：构造恶意权限字节
validateMessageAuth("\x07" . pack('N', 12345) . 'data');
```

**危险模式8：Unpack 返回值类型混淆**
```php
function parseHeader($header_bytes) {
    // unpack 返回关联数组或数字索引数组
    $data = unpack('C3version/nport', $header_bytes);

    // $data['version1'] 为整数，但类型转换可能出错
    $v_major = (int)$data['version1'];
    $port = (int)$data['port'];  // 无符号短整数

    if ($port < 1024) {
        // 特权端口检查可能失败
        return error();
    }

    return [$v_major, $port];
}

// 攻击：利用浮点转换导致端口检查失败
```

### 快速定位核心操作 **[L1-L2]**

**关键词扫描 [L1]**:
- `unpack()` 调用：`unpack('N...', $data)`, `unpack('C...', $data)`
- `ord()` 使用：`ord($packet[0])`, `ord($data[$index])`
- 位运算操作：`>> 4`, `& 0xFF`, `<< 2`, `| $mask`
- 字节提取：`substr($data, $offset, $length)`
- 网络字节序：`'N'` (大端 32 位), `'n'` (大端 16 位), `'V'` (小端)
- 字段作为数组索引或长度：`substr(..., $offset, $field_length)`
- 协议字段用于循环或内存分配
- 权限/权限位检查：`if ($level >`，`$permission & 0x01`

**快速定位保护机制 [L2-L3]**:
- 是否对协议字段进行范围验证：`if ($length > MAX_LENGTH || $length < 0)`
- 是否检查缓冲区边界：`if ($offset + $length > strlen($data))`
- 是否处理有符号/无符号问题：`$value & 0xFF`, `$value & 0xFFFF`
- 是否验证多字段组合：`if ($offset >= 0 && $length >= 0 && $offset + $length <= $max)`
- 是否使用包验证库（如 `unserialize` 替代方案或专用库）
- 是否对循环计数进行上限检查：`if ($count > MAX_RECORDS)`
- 是否预先验证包头长度：在解包前检查最小长度

---

## Classify

**研判为真漏洞的特征：**

1. **协议字段直接用于内存操作，无范围检查**：如 `substr($data, $offset, $length)` 其中 `$offset` 或 `$length` 来自不可信的协议字段

2. **有符号/无符号混淆导致边界绕过**：如 `ord()` 返回 0-255 无符号值，但用于有符号比较

3. **多字段组合未完整验证**：偏移量 + 长度的组合未验证是否超出缓冲区范围

4. **协议字段用于循环条件无上限**：`for ($i = 0; $i < unpack(...)[1]; $i++)` 无迭代限制

5. **网络字节序转换错误**：大端/小端转换错误或转换后未进行范围验证

6. **协议字段用于权限/权限位判断**：权限位直接来自网络包而无额外验证

**误报/代码异味的特征：**

- 协议字段解包后立即进行范围验证：`$len = unpack('N', $data)[1]; if ($len > MAX_SIZE || $len < 0) { error(); }`
- 协议规范已明确限制字段范围（字段类型本身安全）
- 使用专门的二进制解析库处理协议（如 protobuf、msgpack）
- 字段仅用于校验码、版本号等非关键操作
- 缓冲区边界预先验证：`if (strlen($data) < MIN_HEADER_SIZE) { error(); }`
- 使用已验证的协议解析框架

---

## Low risk

**以下场景可评为低风险：**

1. **完整的协议字段验证**
   - 解包后立即范围检查：`$len = unpack('N', $data)[1]; if ($len > 65536 || $len <= 0) { throw new Exception(); }`
   - 多字段组合完整验证：`if ($offset >= 0 && $length >= 0 && $offset + $length <= strlen($data))`
   - 有符号/无符号处理：使用位掩码处理 `$value & 0xFF`, `$value & 0xFFFF`

2. **协议规范的内置限制**
   - 字段类型本身限制范围（如 unsigned short 最多 65535）
   - 协议规范明确规定字段限制（如最大包长 8192 字节）
   - 类型声明已包含安全范围

3. **使用安全的解析库**
   - Protocol Buffers/protobuf 库自动处理类型转换和范围验证
   - msgpack 或其他已验证的二进制序列化库
   - 框架内置的协议解析函数

4. **非关键字段解析**
   - 字段仅用于版本号、校验码、类型识别等元数据
   - 字段不直接影响内存分配、缓冲区操作或权限决策
   - 转换结果仅用于日志或显示

5. **预验证包长度**
   - 解包前已验证最小包长度：`if (strlen($data) < 8) { return error(); }`
   - 已预先限制可读取范围：`$limited_data = substr($data, 0, MAX_PACKET_SIZE)`
   - 使用 try-catch 捕获 unpack 异常

6. **循环计数的上限检查**
   - 循环前验证计数范围：`if ($count > 1000) { return error(); }`
   - 使用预定义常量作为上限
   - 循环内部有超时或中断机制

7. **已验证的数据来源**
   - 协议字段来自已验证的内部系统或受控的本地文件
   - 数据已通过完整性检查（如 HMAC、签名验证）
   - 数据来自信任的服务端点

