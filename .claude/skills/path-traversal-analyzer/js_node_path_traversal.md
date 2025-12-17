# JavaScript (Node.js) 路径遍历与文件包含漏洞

## Details

### 漏洞成因
Node.js 服务端常使用 `fs.readFile`, `fs.createReadStream`, `fs.promises.readFile`, `path.join`, `require`, `import()` 等 API 读取文件或加载模块。如果将来自 `req.query`, `req.params`, `req.body` 的输入直接拼接到路径，且未进行 `path.resolve` 与根目录校验，攻击者可利用 `../`, `%2e%2e%2f`, `..\\` 等技巧突破目录限制，读取源码、配置、凭证文件。若动态 `require` 用户提供的路径，或 SSR/模板引擎加载自定义模板，也可能导致 LFI/RFI。处理上传压缩包、文件导出等功能时缺乏校验，会引发覆盖写入或远程代码执行。

### 代码示例

**易受攻击的代码（Express 下载接口）：**
```javascript
app.get("/logs", (req, res) => {
  const name = req.query.name; // ../../../../etc/passwd
  const filePath = path.join(__dirname, "logs", name);
  res.sendFile(filePath); // 未验证 resolved 路径
});
```

**动态 require（LFI）：**
```javascript
app.get("/plugin/:id", (req, res) => {
  const plugin = req.params.id; // ../../../../tmp/shell
  const modulePath = path.join(__dirname, "plugins", plugin);
  const loaded = require(modulePath); // 可执行任意模块
  res.json(loaded.run());
});
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- 文件访问：`fs.readFile`, `fs.promises.readFile`, `fs.createReadStream`, `res.sendFile`
- 路径处理：`path.join`, `path.resolve`, `path.normalize`, 模板字符串 `${req...}`
- 模块加载：`require`, `import()`, `vm.runInThisContext`
- 静态服务：`express.static`, `serve-static`, `next-ssr`
- 解压/写入：`fs.writeFile`, `unzipper`, `adm-zip`, `tar`

**定位步骤：**
1. 搜索上述函数，寻找与 `req`/`ctx` 等输入结合的路径拼接。
2. 关注文件预览、日志导出、模板切换、插件执行、SSR 渲染等功能。
3. 跳读（L2）检查是否执行 `path.resolve` 与根目录校验。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **路径规范化：** `path.resolve`, `path.normalize`
- **根目录校验：** `resolved.startsWith(baseDir)` 或 `path.relative` 检查
- **白名单映射：** 映射 ID → 文件路径，拒绝任意输入
- **扩展名匹配：** 限制允许访问的文件类型
- **禁止远程协议：** 当使用 `axios`, `fetch` 拉取资源时限制协议域名

**定位技巧：**
- 确认 `resolve` 或 `relative` 的结果被验证并使用。
- 检查 `sendFile` 是否传入 `root` 并在 `options` 中使用 `dotfiles: "deny"`。
- 对 `require`/`import`，查验是否允许外部输入决定路径。
- 关注 `express.static` 是否暴露整个项目根目录。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| `express.static` 指向公开目录并限制 dotfiles | **L0（快速跳过）** | 基本安全 |
| `resolve` + `relative` 校验 | **L2（跳读）** | 检查异常分支 |
| 直接拼接用户输入路径 | **L3（逐行读）** | 高风险 |
| 动态 require/SSR 模板 | **L4（跨模块追踪）** | 需深入追踪执行链 |

## Classify

### 研判标准

#### 确认漏洞
判定漏洞需满足：
1. **用户输入控制路径或模块引用。**
2. **缺乏规范化和根目录校验或白名单。**
3. **能访问敏感文件、执行任意模块或覆盖写入。**

#### 误报
可视为误报的情况：
1. **路径值来自受控枚举/配置。**
2. **使用 `path.resolve` + `path.relative` 验证并拒绝越界。**
3. **访问目录仅包含公开资源，部署无敏感内容。**

#### 代码异味
需记录的隐患：
1. **只替换 `../` 字符串或简单正则过滤。**
2. **`path.join` 后未使用 `path.resolve` 导致 `..` 可绕过。**
3. **`require` 路径拼接但未隔离插件运行环境。**
4. **缺乏错误处理，隐藏异常访问。**

## Low risk

### 低风险评级场景

#### 1. 受控后台接口
- **场景：** 功能仅对内部账号开放。
- **风险评估：** 攻击面有限，但需防权限滥用。

#### 2. 只读公开目录
- **场景：** 静态资源目录无敏感数据。
- **风险评估：** 危害较小，但防止目录信息泄露。

#### 3. 容器/沙箱限制
- **场景：** Node 进程运行在权限受限容器，文件系统隔离。
- **风险评估：** 限制影响范围，但不能替代修复。

#### 4. 运行时防护
- **场景：** 使用安全代理、日志监控检测异常路径。
- **风险评估：** 有助于发现攻击，但不消除根因。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 内部接口 | 攻击面小 | 中 |
| `resolve` + `relative` 校验 | 技术封堵遍历 | 低 |
| 容器/沙箱隔离 | 限制危害 | 中 |
| 安全监控告警 | 可感知攻击 | 高（持续修复）|

