# TypeScript SSR/BFF 上传防护漏洞

## Details

### 漏洞成因
使用 TypeScript 编写的 SSR 框架（Next.js、Nuxt with TS、Remix）、BFF 层或 Serverless API 往往在同一进程内完成页面渲染与文件上传。如果将上传文件直接保存到服务端可访问目录、在 SSR 渲染中引用用户上传资源、或将文件路径嵌入模板执行（例如 `getServerSideProps` 返回未经筛选的文件 URL），攻击者可通过上传恶意脚本实现反射型 XSS、HTML 注入、RCE 或读取敏感数据。

### 代码示例

**易受攻击的代码：**
```typescript
// Next.js API 路由
export const config = { api: { bodyParser: false } };

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  const form = new formidable.IncomingForm({ uploadDir: "public/uploads", keepExtensions: true });
  form.parse(req, (_err, _fields, files) => {
    const file = files.file as formidable.File;
    res.json({ imageUrl: `/uploads/${file.originalFilename}` }); // 未随机命名/鉴权
  });
}
```

```typescript
// getServerSideProps 注入用户上传内容
export const getServerSideProps: GetServerSideProps = async ({ query }) => {
  return { props: { imageUrl: query.imageUrl } }; // 客户端可传入任意 URL，配合上传导致 XSS
};
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- Next.js 上传：`formidable`, `busboy`, `multer`, `api: { bodyParser: false }`
- SSR 渲染：`getServerSideProps`, `getInitialProps`, `server-side fetch`
- 模板注入：`dangerouslySetInnerHTML`, 直接输出 `props.imageUrl`
- 静态目录：`public/`, `static`, `AppRouter`, `pages/api/upload`

**定位步骤：**
1. 搜索上传 API 与 SSR 函数之间的关联，确认是否存在交叉引用。
2. 检查是否将用户上传的文件放在 `public/` 并在 SSR 页面中引用。
3. 跳读（L2）确认是否有鉴权、随机命名、内容过滤。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **随机命名与隔离目录：** 上传文件保存在不可执行目录，返回签名 URL。
- **SSR 输出净化：** 使用 `escape-html`, `Content-Security-Policy`, 仅允许可信域名。
- **访问控制：** SSR/BFF 层访问上传文件需鉴权或签名。
- **内容扫描：** 上传后触发安全扫描或人工审核。
- **Serverless 隔离：** 上传处理在独立函数/服务中执行。

**定位技巧：**
- 检查 `next.config.js` 是否设置 headers 禁止脚本执行。
- 审查 `Image` 组件或自定义标签是否限制外部域名。
- 确认 Serverless 运行环境权限最小化。

#### 审计等级标注

| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 上传隔离 + 签名 URL + SSR 输出净化 | **L0（快速跳过）** | 风险低 |
| 部分防护但仍引用 public 文件 | **L2（跳读）** | 检查潜在 XSS |
| 上传文件直接暴露在 SSR 页面 | **L3（逐行读）** | 高风险 |
| SSR/BFF 与对象存储交叉信任 | **L4（跨模块追踪）** | 需审计全链路 |

## Classify

### 研判标准

#### 确认漏洞
需满足：
1. 上传文件保存在可公开访问或 SSR 引用的目录。
2. SSR/BFF 输出未净化用户控制的数据，或模板执行用户生成内容。
3. 攻击者可通过上传/引用触发 XSS、RCE 或访问敏感文件。

#### 误报
以下情况可视为误报：
1. 上传文件存储在私有位置，SSR 页面仅使用经过验证的签名 URL。
2. 页面输出经过严格净化，CSP 限制外部脚本。
3. 上传内容需人工审核或仅供内部使用。

#### 代码异味
需记录的风险：
1. 使用 `dangerouslySetInnerHTML` 输出用户内容。
2. public 目录与上传目录混用，缺乏隔离。
3. 缺少日志，无法追踪 SSR 输出异常。
4. Serverless 函数使用过高权限 IAM 角色。

## Low risk

### 低风险评级场景

#### 1. 可信内部系统
- **场景：** SSR/BFF 仅服务内部用户，访问受控。
- **风险评估：** 攻击面有限，但需防内部滥用。

#### 2. 签名 URL + 输出净化
- **场景：** 上传文件通过短期签名访问，SSR 页面统一净化。
- **风险评估：** 风险较低，需确保存储策略安全。

#### 3. 内容审核
- **场景：** 上传内容经自动扫描与人工复核后才展示。
- **风险评估：** 降低恶意内容风险。

#### 4. 安全监控
- **场景：** 结合监控发现异常 URL、脚本注入、访问模式。
- **风险评估：** 有助于快速响应，需与防护结合。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 内部系统 | 攻击面有限 | 中 |
| 签名 URL + 净化 | 技术防护完善 | 低 |
| 审核流程 | 减少恶意内容 | 中 |
| 监控告警 | 提升感知能力 | 高（持续优化）|

