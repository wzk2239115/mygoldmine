# PHP 框架上传存储设计漏洞

## Details

### 漏洞成因
现代 PHP 框架（Laravel、Symfony、CodeIgniter、ThinkPHP 等）提供高级抽象来处理文件上传与存储，如 Laravel `Storage`、Symfony `Filesystem`、Flysystem。然而若未合理配置存储磁盘、访问策略、随机命名和目录权限，或将用户上传的文件直接存放在 `public/`、`web/` 目录下，攻击者可枚举、访问或覆盖文件，甚至执行脚本。常见风险包括共享磁盘未隔离、多租户混用、使用 `Storage::url` 返回永久公开链接等。

### 代码示例

**易受攻击的代码：**
```php
// Laravel 控制器
public function store(Request $request) {
    $path = $request->file('avatar')->storeAs('avatars', $request->file('avatar')->getClientOriginalName(), 'public');
    // 使用原始文件名，且存储在 public disk，可被直接访问
    return Storage::url($path);
}
```

**另一个不安全示例（Symfony）：**
```php
public function upload(Request $request, SluggerInterface $slugger): Response
{
    $file = $request->files->get('file');
    $directory = $this->getParameter('kernel.project_dir') . '/public/uploads';
    $file->move($directory, $file->getClientOriginalName()); // 未随机命名
    return new JsonResponse(['url' => '/uploads/' . $file->getClientOriginalName()]);
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- Laravel：`Storage::put`, `store`, `storeAs`, `disk`, `public_path`
- Symfony：`$request->files`, `UploadedFile::move`, `Filesystem`, `public/`
- Flysystem 配置：`filesystems.php`, `adapters`, `visibility`
- URL 生成：`Storage::url`, `asset`, `generateUrl`

**定位步骤：**
1. 检查存储磁盘配置，确认 `public` 或 `local` 是否直接暴露。
2. 搜索 `storeAs`、`move` 等函数，确认是否使用随机文件名。
3. 跳读（L2）看是否存在目录隔离、权限设置、访问鉴权。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **随机命名**：使用 `hashName`, `uniqid`, `Str::uuid`.
- **私有磁盘**：Laravel 使用 `private` disk + `Storage::temporaryUrl`，Symfony 使用守护进程返回。
- **访问控制**：通过控制器或中间件验证权限后再返回文件，避免直接 public URL。
- **配置隔离**：按租户/用户创建子目录，限制跨租户访问。
- **权限设置**：使用 `.htaccess`、Nginx 限制执行，设置文件权限。

**定位技巧：**
- 检查是否对不同环境（dev/prod）启用了相同防护。
- 查看对象存储驱动（S3、OSS）是否使用私有桶与签名 URL。
- 评估删除/过期策略，防止敏感文件长期存在。

#### 审计等级标注

| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 私有磁盘 + 随机命名 + 签名访问 | **L0（快速跳过）** | 风险低 |
| 使用 public disk 但文件仅静态资源 | **L2（跳读）** | 检查是否存在脚本上传 |
| public 目录 + 原始文件名 + 无鉴权 | **L3（逐行读）** | 高风险 |
| 多租户共享目录 + 无隔离 | **L4（跨模块追踪）** | 需全面审计 |

## Classify

### 研判标准

#### 确认漏洞
需满足以下条件：
1. 存储策略允许未经授权的访问、枚举或覆盖文件。
2. 上传文件在 `public` 目录可直接执行或下载。
3. 缺乏随机命名、目录隔离或访问控制，导致敏感文件泄露或 RCE。

#### 误报
以下情况可视为误报：
1. 上传仅限公开资源，且文件经过审核、不可执行。
2. 存储在私有磁盘，通过控制器或签名 URL 鉴权访问。
3. 存储后立即进行病毒扫描与权限调整（如 `chmod 0640`）。

#### 代码异味
需记录的风险：
1. 同时提供 public/private 磁盘但逻辑混乱，易误用。
2. 使用 `Storage::url` 返回永久可访问链接，无过期机制。
3. 没有日志记录，无法追踪文件访问/覆盖。
4. 多租户共享目录，没有隔离策略。

## Low risk

### 低风险评级场景

#### 1. 内部业务场景
- **场景：** 文件仅供内部系统访问，路由有严格鉴权。
- **风险评估：** 攻击面有限，但需防内部滥用。

#### 2. 短期签名 URL
- **场景：** 使用 `temporaryUrl`、`temporarySignedRoute` 生成短期访问链接。
- **风险评估：** 风险较低，需确保存储策略安全。

#### 3. 加密存储 + 清理
- **场景：** 上传文件加密后存储，并定期清理无用文件。
- **风险评估：** 降低敏感信息泄露影响。

#### 4. 审计日志
- **场景：** 启用存储访问日志、异常告警和操作审计。
- **风险评估：** 有助于快速发现问题，需配合防护。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 内部访问控制 | 攻击面有限 | 中 |
| 签名 URL + 随机命名 | 技术防护完善 | 低 |
| 加密存储/定期清理 | 降低泄露影响 | 中 |
| 审计告警 | 提升感知能力 | 高（持续优化）|

