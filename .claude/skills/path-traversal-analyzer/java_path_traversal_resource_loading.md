# Java 路径遍历与文件包含漏洞

## Details

### 漏洞成因
在基于 Java 的 Web 应用中，常见于通过 `File`, `Files`, `Paths`, `ServletContext.getResource`, `ResourceUtils.getFile` 等 API 根据请求参数读取文件。当开发者缺乏白名单映射或路径规范化，攻击者可利用 `..`、URL 编码、绝对路径、UNC 路径等方式突破根目录限制，读取 `WEB-INF`、配置文件或系统敏感文件。若框架允许动态 include JSP/Velocity/FreeMarker 模板，或自定义类加载插件，也可能演化为本地/远程文件包含。上传解压、备份还原等功能若未验证目标路径，亦会造成覆盖写入风险。

### 代码示例

**易受攻击的代码（日志下载接口）：**
```java
@GetMapping("/logs")
public ResponseEntity<Resource> downloadLog(@RequestParam String name) throws IOException {
    Path path = Paths.get("/var/app/logs/" + name); // 未过滤 ../
    Resource resource = new UrlResource(path.toUri());
    if (!resource.exists()) {
        throw new FileNotFoundException();
    }
    return ResponseEntity.ok()
            .contentType(MediaType.TEXT_PLAIN)
            .body(resource);
}
```

**JSP 动态包含（LFI）：**
```jsp
<%
String page = request.getParameter("page"); // 允许 page=../../../../etc/passwd
RequestDispatcher dispatcher = request.getRequestDispatcher("/WEB-INF/views/" + page + ".jsp");
dispatcher.include(request, response);
%>
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- 文件访问类：`FileInputStream`, `Files.readAllBytes`, `ResourceUtils.getFile`, `ResourceLoader.getResource`
- 路径组合：`Paths.get`, `Paths.resolve`, `ServletContext.getRealPath`, `String.format("/...%s", param)`
- 模板包含：`include`, `forward`, `RequestDispatcher`, `TemplateLoader`, `ClasspathResource`
- 上传解压：`ZipInputStream`, `JarFile`, `FileSystem`, `Files.copy`

**定位步骤：**
1. 搜索上述 API 与用户输入（`@RequestParam`, `getParameter`, JSON/表单字段）同处的代码段。
2. 重点关注服务端渲染返回文件、导出、预览、模板渲染、插件加载功能。
3. 跳读（L2）确认是否存在路径过滤或白名单逻辑。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **路径标准化：** `path.normalize()`, `path.toRealPath()`, `FilenameUtils.normalize`
- **根目录校验：** 使用 `path.startsWith(baseDir)` 限制访问范围
- **白名单映射：** 通过枚举将逻辑名称映射到物理文件
- **文件类型校验：** 限制扩展名、MIME、内容签名
- **远程 URL 拒绝：** 禁止 `http://`、`ftp://` 等协议

**定位技巧：**
- 验证 `normalize` 后是否重新赋值，否则仍引用未净化路径。
- 检查 `path.startsWith` 时是否使用绝对路径并考虑符号链接。
- 对上传解压，确认每个解压项的 `getCanonicalPath` 前缀校验。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 使用白名单映射或固定模板 | **L0（快速跳过）** | 用户无法控制物理路径 |
| `normalize` + 前缀校验 | **L2（跳读）** | 需确认校验正确性 |
| 直接拼接请求参数为路径 | **L3（逐行读）** | 高风险，必须追踪数据流 |
| 包含上传解压/模板动态 include | **L4（跨模块追踪）** | 需分析多层调用链 |

## Classify

### 研判标准

#### 确认漏洞
同时满足以下条件判定为漏洞：
1. **路径可控：** 用户输入影响文件系统访问或模板 include。
2. **缺乏防护：** 未做标准化/前缀校验或白名单限制。
3. **敏感影响：** 可读取/写入敏感文件、包含任意 JSP/模板或执行远程资源。

#### 误报
可判定为误报的情况：
1. **路径来自严格枚举或数据库受控字段。**
2. **使用 `Path path = base.resolve(userInput).normalize();` 且验证 `path.startsWith(base)`。**
3. **访问目录仅含测试数据且部署时不包含敏感内容。**

#### 代码异味
需记录为风险但暂不构成漏洞：
1. **仅删除字符串中的 `..`**，可被编码绕过。
2. **校验后未使用标准化结果**，如 `path.normalize();` 但继续使用原路径。
3. **依赖前端校验或权限控制**，缺乏后端验证。

## Low risk

### 低风险评级场景

#### 1. 后台管理员限定
- **场景：** 功能仅对高可信后台用户开放。
- **风险评估：** 外部攻击面小，但需防内鬼或会话劫持。

#### 2. 只读非敏感目录
- **场景：** 只允许访问公开资源目录（如公开文档）。
- **风险评估：** 即使遍历影响有限，但仍需防止目录结构泄露。

#### 3. 沙箱/容器隔离
- **场景：** 服务运行于容器，根文件系统隔离。
- **风险评估：** 限制破坏面，但敏感配置仍可能泄露。

#### 4. 外部防护
- **场景：** 配置 WAF/ISP 日志告警监控访问模式。
- **风险评估：** 可降低攻击成功率，仍应修复代码。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 管理员限定操作 | 攻击面有限 | 中 |
| 正确 normalize + 前缀校验 | 技术封堵遍历 | 低 |
| 容器/沙箱隔离 | 限制影响面 | 中 |
| WAF/日志监控 | 有侦测能力 | 高（继续推进修复）|

