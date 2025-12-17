# TypeScript 路径遍历与文件包含漏洞

## Details

### 漏洞成因
TypeScript 编写的后端（NestJS、Express、Next.js API、Serverless 函数等）最终编译为 JavaScript，但在开发阶段常使用类型定义、装饰器、依赖注入。若在服务中直接将用户输入赋值给 `path.join`、`fs.readFileSync`、`require`、`import()` 等 API，且未进行 `path.resolve`、`path.normalize` 与根目录校验，攻击者可利用目录穿越读取源码、配置、凭证。SSR/模板渲染（Next.js `getServerSideProps`、Nest Handlebars）或动态模块加载（`DynamicModule`, `require`）也可能造成本地/远程文件包含。TypeScript 项目常使用装饰器隐藏真实调用链，审计需关注依赖注入和管道。

### 代码示例

**易受攻击的代码（NestJS 下载接口）：**
```typescript
@Get('download')
download(@Query('file') file: string, @Res() res: Response) {
  const filePath = join(__dirname, '..', 'uploads', file); // file=../../../../etc/passwd
  res.sendFile(filePath); // 未做 resolve + 校验
}
```

**动态模块加载（LFI）：**
```typescript
@Get('plugin/:name')
async loadPlugin(@Param('name') name: string) {
  const modulePath = join(__dirname, 'plugins', name);
  const plugin = await import(modulePath); // 可导入任意模块
  return plugin.run();
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- `fs.readFileSync`, `fs.promises.readFile`, `createReadStream`, `res.sendFile`
- `path.join`, `path.resolve`, `path.normalize`, 模板字面量
- `import()`, `require`, `DynamicModule`, `Loader`, `ModuleRef.get`
- `serveStatic`, `express.static`, `next export`, `fastify-static`
- `unzipper`, `adm-zip`, `multer` 与文件写入逻辑

**定位步骤：**
1. 搜索上述 API，查找与 `@Query`, `@Param`, `req.body`, `dto.field` 等输入共现的代码。
2. 分析拦截器/管道内对文件路径的处理，注意自动装配字段。
3. 跳读（L2）确认是否进行了 `resolve` + `relative` 校验或白名单映射。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **路径规范化：** `path.resolve`, `path.normalize`
- **前缀校验：** `resolved.startsWith(baseDir)` 或 `path.relative(baseDir, resolved)` 判断
- **白名单枚举：** `enum`、配置文件映射固定模板/插件
- **禁用远程协议：** 对 `axios`、`fetch` 拉取资源进行域名限制
- **上传处理：** 使用 `multer` 自定义存储时校验目标路径

**定位技巧：**
- 确认 TypeScript 编译产物中的路径操作与源代码一致（避免通过装饰器注入动态字符串）。
- 检查守卫/拦截器是否可能绕过校验逻辑。
- 对 Serverless 函数，确认每次执行前的全局状态是否复用旧路径。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 固定枚举或配置映射 | **L0（快速跳过）** | 用户无法控制物理路径 |
| `resolve` + `relative` 校验 | **L2（跳读）** | 检查异常分支 |
| 直接拼接用户输入路径 | **L3（逐行读）** | 高风险 |
| 动态模块导入/SSR 自定义模板 | **L4（跨模块追踪）** | 需追踪依赖注入链 |

## Classify

### 研判标准

#### 确认漏洞
判定漏洞需同时满足：
1. **路径/模块可被用户控制。**
2. **缺乏标准化、白名单、前缀校验。**
3. **访问或执行了敏感文件/模块。**

#### 误报
可视为误报的情况：
1. **使用 `enum`/配置映射将逻辑名称转换为固定路径。**
2. **`path.resolve` + `path.relative` 并拒绝离开根目录。**
3. **访问目录仅包含公开资源，部署无敏感文件。**

#### 代码异味
需记录的隐患：
1. **仅做字符串替换 `../`。**
2. **校验后继续使用未净化的原始路径。**
3. **依赖拦截器/守卫做限制，但存在绕过路径。**
4. **ModuleRef 动态加载外部模块未隔离执行上下文。**

## Low risk

### 低风险评级场景

#### 1. 内部控制台功能
- **场景：** 操作仅供内部人员使用。
- **风险评估：** 攻击面小，但需防内鬼。

#### 2. 只读公开目录
- **场景：** 服务仅暴露公共静态资源。
- **风险评估：** 危害有限，但目录结构可能泄露。

#### 3. 无状态 Serverless 环境
- **场景：** 每次执行在临时沙箱，文件系统只读。
- **风险评估：** 限制影响范围，但仍需修复。

#### 4. 外部安全监控
- **场景：** 结合 API 网关/日志监控检测异常路径。
- **风险评估：** 具备侦测能力，但不替代修复。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 内部专用接口 | 攻击面小 | 中 |
| `resolve` + `relative` 防护 | 技术封堵遍历 | 低 |
| Serverless 沙箱 | 限制危害 | 中 |
| 网关/监控告警 | 可及时发现 | 高（继续推进修复）|

