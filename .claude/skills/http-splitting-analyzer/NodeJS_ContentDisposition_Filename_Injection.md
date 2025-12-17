# NodeJS Content-Disposition 文件名注入

## Details

**审计等级：L1（关键词扫描）/ L2（跳读）**

**危险函数特征：**
- `response.setHeader('Content-Disposition', value)` 直接设置
- `res.download(path, filename)` - filename 参数
- 文件名直接拼接进响应头

**快速定位核心操作：**
1. 搜索关键字：`Content-Disposition`、`filename=`、`download`
2. 追踪文件名来源：`req.query`、`req.body`、文件系统
3. 检查是否使用双引号
4. 查看是否过滤特殊字符

**快速定位保护机制：**
- 特殊字符过滤：`filename.replace(/[;,
]/g, '')`
- 双引号转义：`filename.replace(/"/g, '\"')`
- 白名单验证：`/^[a-zA-Z0-9\-_.]+$/.test(filename)`
- URL 编码：`encodeURIComponent(filename)`

**代码示例：**
```javascript
// 危险：用户文件名直接用于下载
app.get('/download', (req, res) => {
    const filename = req.query.file;
    res.setHeader('Content-Disposition',
        \`attachment; filename=\${filename}\`);  // 危险
});

// 危险：POST 文件名
app.post('/export', (req, res) => {
    const name = req.body.export_name;
    res.download(filepath, name);  // 危险
});

// 危险：路径参数
app.get('/file/:name', (req, res) => {
    const fname = req.params.name;
    res.setHeader('Content-Disposition',
        \`attachment; filename=\${fname}\`);  // 危险
});
```

## Classify

**漏洞（High）：**
- 用户文件名未验证
- 文件名包含特殊字符导致头分割
- 允许目录遍历

**误报：**
- 文件名系统生成
- 经过白名单验证
- 使用安全方法

**代码异味（Medium）：**
- 仅过滤部分字符
- 黑名单不完整
- 间接来源

## Low risk

**以下情况评为低风险：**
- 文件名硬编码
- 严格白名单验证
- RFC 合规编码
- 内部来源且已验证

## 审计专业技巧

### 1. 真实漏洞的特征模式

**模式A：双引号中的换行注入**
```javascript
// 真实漏洞：双引号允许换行
const filename = req.query.file;  // 用户输入："test.txt\r\nX-Injected: value"
res.setHeader('Content-Disposition', `attachment; filename="${filename}"`);
// 攻击者可以：注入新的响应头或改变 Content-Type
```

**关键点：** 即使使用双引号，如果不转义 CRLF 和双引号字符本身，仍然可以注入

**模式B：RFC 2183 标准的误用**
```javascript
// 看似安全但实际有缺陷：
const sanitized = filename.replace(/[;"']/g, '');
res.setHeader('Content-Disposition', `attachment; filename=${sanitized}`);
// 问题：未考虑 RFC 2231 编码中的特殊字符（分号在某些编码方案中有意义）
```

**模式C：编码层跳过检查**
```javascript
// 危险模式：检查原始值，传入编码值
if (!filename.includes('\r')) {
    const encoded = filename.split('').map(c => `%${c.charCodeAt(0).toString(16)}`).join('');
    res.setHeader('Content-Disposition', `attachment; filename=${encoded}`);
    // 如果浏览器端 URL 解码，漏洞重现
}
```

### 2. 真实漏洞 vs 误报的判断标准

| 标准 | 真实漏洞 | 误报 | 判断方法 |
|------|--------|------|---------|
| 用户输入来源 | request.*（query/body/params/headers） | 常量、随机数、系统生成 | 追踪数据流源头 |
| 过滤机制 | 无、或黑名单不完整 | 白名单、多层过滤 | 检查 replace/filter/match 函数 |
| CRLF 处理 | 未移除 \r\n | 已移除 | 搜索 /\\r\\n/ 或 normalize 操作 |
| 编码方式 | 明文设置 | RFC 2231 或 URL 编码 | 检查是否使用 encodeURIComponent |
| 上下文 | 公开接口无验证 | 后台管理/认证用户操作 | 查看路由是否有中间件保护 |

### 3. 常见误报场景

**误报 1：数据库查询结果**
```javascript
// 审计员看到用户可控，但实际安全
app.get('/download/:id', (req, res) => {
    const file = db.getFile(req.params.id);  // 参数虽来自 URL，但从数据库查询
    if (!file || file.owner !== req.user.id) return res.sendStatus(403);
    res.setHeader('Content-Disposition', `attachment; filename="${file.name}"`);
    // file.name 是上传时的原始名称，但只有文件所有者可访问
});
// 判断：通过 ID 查询限制了访问，且转义了双引号则安全
```

**误报 2：Express 内置方法的安全实现**
```javascript
// Express 的 res.download() 在某些版本中做了基础处理
res.download(path, filename);
// Express 会自动对 filename 做基础处理（版本依赖）
// 判断：需检查 Express 版本文档，某些版本确实安全
```

**误报 3：既有的安全转义被误读**
```javascript
// 审计员可能错过的转义方式
const filename = sanitizeFilename(req.query.file);  // npm 包

res.setHeader('Content-Disposition', `attachment; filename="${filename}"`);
// 判断：需要检查 sanitizeFilename 函数的实现，如果使用专业包通常安全
```

### 4. 高级审计技巧

**技巧 A：追踪变量重新赋值**
```javascript
let filename = req.query.file;  // 可控
filename = sanitizeFilename(filename);  // 过滤
res.setHeader('Content-Disposition', `attachment; filename="${filename}"`);

// 但如果代码是这样：
let filename = req.query.file;
let output = filename;  // 变量复制
filename = sanitizeFilename(filename);
res.setHeader('Content-Disposition', `attachment; filename="${output}"`);  // 用旧变量
// ⚠️ 这是真实漏洞，需要仔细追踪赋值链
```

**技巧 B：检查多个路径的文件名来源**
```javascript
// 关键检查点：
app.get('/download', (req, res) => {
    // 检查点 1: 文件名参数
    let filename = req.query.file;

    // 检查点 2: 路径拼接
    const filepath = path.join('/uploads', filename);  // 可能目录遍历

    // 检查点 3: 响应头设置
    res.setHeader('Content-Disposition', `attachment; filename="${filename}"`);
});
// 需要检查所有三个点，不能只看第三个点
```

**技巧 C：识别"假过滤"**
```javascript
// 假过滤 1：只过滤常见字符但遗漏 CRLF
const sanitized = filename.replace(/[<>"|]/g, '');  // 忽略了 \r\n
// 检查：grep -n '\\r\\n' 文件，或看是否使用 normalize

// 假过滤 2：过滤后再次拼接
const cleaned = filename.replace(/"/g, '\\\"');  // 转义
const result = `filename="${cleaned}"`;  // 再次拼接
// 问题：如果后续还有其他处理可能再次注入

// 假过滤 3：依赖客户端验证
// 前端检查后再发送，但如果攻击者直接调用 API 则无效
```

**技巧 D：RFC 2231 编码识别**
```javascript
// 安全实现应该考虑：
const filename = req.query.file;
const encoded = Buffer.from(filename, 'utf8').toString('ascii');
// 或使用标准库
const rfc2231encoded = `UTF-8''${encodeURIComponent(filename)}`;
res.setHeader('Content-Disposition',
    `attachment; filename*=${rfc2231encoded}`);
// 这是正确的做法，应该标记为低风险
```

### 5. 审计检查清单

- [ ] 用户输入是否直接使用（request.query/body/params）？
- [ ] 是否移除了 \r\n 字符？
- [ ] 是否转义了双引号或使用编码？
- [ ] 是否使用白名单验证（而非黑名单）？
- [ ] 文件名来源是否经过数据库查询限制？
- [ ] 是否使用了标准的安全库（sanitize-filename 等）？
- [ ] 响应头设置前是否有其他修改变量的地方？
- [ ] RFC 2231 编码是否正确应用？
- [ ] 是否检查了所有可能的代码分支？
