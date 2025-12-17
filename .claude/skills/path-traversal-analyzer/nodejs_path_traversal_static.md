# Node.js 静态文件服务路径穿越漏洞

**漏洞成因**：在 Express/Koa/Nest 等框架实现文件下载、静态资源访问时，使用 `fs.readFile` / `fs.createReadStream` / `res.sendFile` 直接拼接请求参数，未进行路径规范化和根目录校验，攻击者利用 `../` 序列可突破限制访问系统敏感文件。

---

## Details

### 代码示例

**典型易受攻击模式（Express）**：

```javascript
app.get('/download', (req, res) => {
    const filename = req.query.file; // ../../../../etc/passwd
    const filePath = path.join(__dirname, 'public', filename);
    // 危险：path.join 不阻止 ../ 向上穿越
    res.sendFile(filePath);
});
```

```javascript
// Koa 静态资源处理
router.get('/static/:path', async (ctx) => {
    const userPath = ctx.params.path; // ../../config/db.json
    const targetFile = `./assets/${userPath}`;
    // 危险：字符串拼接 + 未规范化
    ctx.body = fs.readFileSync(targetFile);
});
```

```javascript
// 文件流传输
app.get('/logs', (req, res) => {
    const logName = req.query.name;
    const stream = fs.createReadStream('./logs/' + logName);
    // 危险：直接拼接用户输入
    stream.pipe(res);
});
```

```javascript
// Nest.js 静态文件服务
@Get('files/:filename')
downloadFile(@Param('filename') filename: string, @Res() res: Response) {
    const filePath = path.join(process.cwd(), 'uploads', filename);
    // 危险：未验证 resolved 路径边界
    return res.sendFile(filePath);
}
```

### 快速定位核心操作技巧（L1-L2）

**关键函数调用链**（L1: 关键词扫描）：
- 文件读取：`fs.readFile`, `fs.readFileSync`, `fs.promises.readFile`
- 文件流：`fs.createReadStream`, `fs.openSync`
- 响应发送：`res.sendFile`, `res.download`, `ctx.attachment`
- 路径处理：`path.join`, `path.normalize`, 模板字符串 `${...}`
- 静态中间件：`express.static`, `koa-static`, `serve-static`

**核心操作识别**（L2: 跳读）：
1. 搜索文件操作函数，回溯路径参数来源
2. 检查路径是否包含 `req.query`, `req.params`, `req.body`, `ctx.request` 等用户输入
3. 关注文件下载、日志查看、图片预览、导出报表等业务功能
4. 确认是否直接拼接或仅使用 `path.join`（不阻止 `../`）

**特征模式**：
- `path.join(baseDir, req.query.file)` 直接传入文件操作
- `'./public/' + req.params.path` 字符串拼接用户输入
- `sendFile(path.join(__dirname, userInput))` 无边界验证
- `express.static(process.cwd())` 暴露项目根目录

### 快速定位保护机制技巧（L2-L3）

**有效防护特征**（L2: 跳读）：
- **规范化 + 边界检查**：`path.resolve` 后验证 `startsWith(baseDir)`
- **相对路径校验**：`path.relative(baseDir, resolvedPath)` 检查是否包含 `..`
- **白名单映射**：`fileMap[id]` 硬编码路径，拒绝直接文件名输入
- **扩展名限制**：`path.extname(file) === '.pdf'` 且无路径分隔符
- **sendFile 选项**：`res.sendFile(file, {root: baseDir, dotfiles: 'deny'})`

**审计要点**（L3: 逐行读）：
1. **规范化时机**：必须 `path.resolve` 后再检查边界，顺序不可颠倒
2. **Join 陷阱**：`path.join` 不阻止 `../`，需配合 `resolve` 和 `startsWith`
3. **Normalize 不足**：`path.normalize` 仅标准化格式，不验证边界
4. **空路径处理**：空字符串可能被解析为当前目录 `.`
5. **编码绕过**：检查是否解码后验证（`decodeURIComponent` 后再 `resolve`）
6. **符号链接**：`fs.realpath` 可解析符号链接真实路径

**正确防护示例识别**：
```javascript
// 正确：resolve + startsWith
const safeFile = path.resolve(baseDir, userInput);
if (!safeFile.startsWith(baseDir)) {
    throw new Error('Invalid path');
}
```

```javascript
// 正确：relative + 检查 ..
const relative = path.relative(baseDir, path.resolve(baseDir, userInput));
if (relative.startsWith('..') || path.isAbsolute(relative)) {
    return res.status(403).send('Forbidden');
}
```

**L4 跨模块追踪场景**：
- 路径参数通过中间件处理后存入 `req.locals` / `ctx.state`，业务层直接使用
- 封装的文件服务工具类（`FileService.download(filename)`），需追踪内部实现
- 配置文件指定根目录，需确认配置来源是否受控
- 自定义静态服务中间件，需完整审计路径处理逻辑

**审计等级标注**：
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| `express.static(publicDir, {dotfiles: 'deny'})` 限定公开目录 | **L0（快速跳过）** | 框架自带安全机制 |
| `path.resolve` + `startsWith` 完整校验 | **L2（跳读）** | 检查校验时机和异常处理 |
| `path.join` + 用户输入但无边界验证 | **L3（逐行读）** | 高风险，需确认影响范围 |
| 动态路径处理或跨模块传递 | **L4（跨模块追踪）** | 需追踪完整调用链 |

---

## Classify

**漏洞判定条件**（同时满足）：
1. 用户可控路径参数传递到文件系统操作
2. 缺乏 `path.resolve` + 边界验证（`startsWith` / `relative`）
3. 可访问到敏感文件（源码、配置、凭证、用户数据）

**误报场景**：
- 路径参数来自硬编码映射表（如 `idMap[req.query.id] -> '/fixed/path/file.pdf'`）
- 使用 `path.resolve` 并正确验证最终路径在根目录内，且无逻辑漏洞
- `express.static` / `koa-static` 指向不含敏感文件的专用公开目录，且配置 `dotfiles: 'deny'`
- 路径参数仅用于日志记录或数据库查询，未传入文件系统操作
- 部署环境已通过 chroot 或容器文件系统完全隔离

**代码异味**（潜在风险）：
- 仅使用 `path.normalize` 而无边界检查（规范化不等于安全）
- 使用正则替换 `../` 或 `..\\`（可被编码、大小写、重复绕过）
- `path.resolve` 在边界检查之后执行（时序错误）
- 自定义路径过滤逻辑复杂但未经充分测试
- 错误处理不当，异常路径访问时泄露完整文件路径到响应
- `sendFile` 使用 `root` 选项但未配合 `dotfiles: 'deny'`

---

## Low risk

**降低风险评级的情况**：

1. **访问范围受限**：
   - 可遍历目录仅包含公开静态资源（CSS/JS/图片），无敏感文件
   - 部署时已确认目标目录不包含源码、配置、密钥等敏感内容
   - 文件读取后仅返回元数据（文件大小、修改时间），不返回文件内容

2. **输入约束有效**：
   - 路径参数有严格正则校验（如 `^[a-zA-Z0-9_-]+\.(pdf|jpg)$`）禁止 `/`, `\`, `.`
   - 业务逻辑仅支持文件名（不含路径分隔符），虽不完美但大幅降低风险
   - 使用数字 ID 映射，虽映射表拼接用户输入但可选值极有限

3. **权限与隔离**：
   - Node 进程以低权限用户运行，无法访问敏感系统文件（需验证部署配置）
   - 应用运行在容器内，敏感文件在不同挂载点或已移除
   - SELinux / AppArmor 策略限制文件系统访问范围

4. **访问控制**：
   - 功能仅对已认证且权限受限的内部用户开放
   - 多层访问控制（身份验证 + 授权检查）虽不能替代修复但降低攻击面

5. **监控与响应**：
   - 文件访问日志记录异常路径（包含 `..`）并实时告警
   - WAF 或安全代理拦截常见遍历 Payload
   - 行为分析检测异常文件访问模式

**风险降级条件总结**：
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 公开目录无敏感文件 | 危害有限 | 中（仍需修复）|
| 严格输入正则校验 | 攻击难度高 | 中 |
| `resolve` + `startsWith` 验证 | 技术封堵有效 | 低 |
| 容器/权限隔离 | 限制影响范围 | 中 |
| 认证 + 授权保护 | 攻击面小 | 高（仍是漏洞）|
| 安全监控告警 | 可感知攻击 | 高（持续修复）|

**注意**：低风险不等于无风险，路径穿越仍属于安全缺陷，应优先从代码层面修复，不应仅依赖外围防护措施。
