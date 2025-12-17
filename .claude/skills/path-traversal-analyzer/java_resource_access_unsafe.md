# Java 资源访问不安全 - 路径遍历审计

## Details

**核心问题**：使用 `Files.readAllBytes`、`ResourceUtils.getFile`、`new File()`、`FileInputStream` 等API直接读取用户可控路径，缺乏路径规范化和边界检查。

**代码模式识别**：
```java
// 典型漏洞模式
String fileName = request.getParameter("file");
byte[] content = Files.readAllBytes(Paths.get(fileName));  // 危险

File resource = ResourceUtils.getFile("classpath:" + userInput);  // 危险

FileInputStream fis = new FileInputStream(basePath + userPath);  // 危险
```

**快速定位核心操作（L1-L2）**：
- **关键API**：`Files.readAllBytes()`, `Files.newInputStream()`, `FileInputStream`, `FileReader`, `ResourceUtils.getFile()`, `ClassLoader.getResource()`, `ServletContext.getResource()`
- **数据流**：追踪 HTTP参数(`request.getParameter/getHeader`)、路径变量(`@PathVariable`)、请求体字段 → 文件操作API
- **典型位置**：文件下载接口、模板加载、配置读取、静态资源服务

**快速定位保护机制（L2-L3）**：
- **路径规范化**：`Path.normalize()`, `File.getCanonicalPath()`, `FilenameUtils.normalize()` 是否在文件操作前调用
- **白名单校验**：是否检查扩展名、文件名、路径前缀（注意：黑名单不可靠）
- **边界限制**：`Path.startsWith(allowedDir)` 或 `canonicalPath.startsWith(baseDir)` 检查
- **沙箱机制**：SecurityManager、自定义FilePermission检查

**审计等级标注**：
- **L1 关键词扫描**：搜索 `readAllBytes|FileInputStream|ResourceUtils|getResource` + `getParameter|@PathVariable`
- **L2 跳读**：确认数据流：用户输入 → 文件路径 → 读取操作，观察是否有中间校验
- **L3 逐行读**：分析路径拼接逻辑、normalize调用时机、startsWith校验的正确性（规范化后校验 vs 先校验再规范化）
- **L4 跨模块追踪**：文件路径从配置、数据库、缓存获取时，追踪初始来源是否用户可控

## Classify

**漏洞判定**：
1. **确认可控性**：路径/文件名的全部或部分来自用户输入（直接或间接）
2. **校验缺失或绕过**：无规范化、规范化时序错误（先校验后规范化）、白名单不严格（仅检查扩展名可被`file.txt.....`绕过Windows）、使用相对路径校验
3. **敏感性**：可读取到应用配置文件、源码、系统文件、其他用户数据

**误报排除**：
- 路径完全硬编码或从只读配置源（application.yml中的固定值）获取
- 用户输入经过严格白名单映射（如 `fileId → UUID → 文件系统路径`）
- 读取操作限制在明确的临时目录且目录隔离（如 `/tmp/{sessionId}/{uuid}.tmp`）

**代码异味**：
- 路径拼接使用字符串加法而非 `Paths.get()` 或 `Path.resolve()`
- 使用 `new File(userInput)` 而不检查 `getCanonicalPath()`
- 依赖扩展名黑名单（`.jsp`, `.class`）

## Low risk

**降级场景**：
1. **范围受限**：仅能访问公开静态资源目录（如 `public/static/`），且目录下无敏感文件
2. **内容无害**：读取的文件内容不返回给用户、不执行、仅用于非敏感业务逻辑（如日志统计）
3. **多重防护**：应用运行在容器中 + 文件系统权限严格限制 + SELinux/AppArmor强制访问控制
4. **二次依赖**：文件路径由管理员预先导入数据库，用户仅能选择ID，且导入过程已校验
5. **影响有限**：开发/测试环境且无生产数据、或读取失败不影响主业务流程

**注意**：即使低风险也应记录并建议修复，防御纵深原则。