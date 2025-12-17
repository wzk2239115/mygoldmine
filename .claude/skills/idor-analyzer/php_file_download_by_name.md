# PHP - 文件下载/包含未授权漏洞

## Details

**代码示例：**
```php
// 典型漏洞模式 - 通过GET参数直接下载
if (isset($_GET['file'])) {
    $filename = $_GET['file'];  // 直接获取文件名
    $filepath = '/uploads/' . $filename;  // 路径拼接
    header('Content-Type: application/octet-stream');
    readfile($filepath);  // 无权限校验直接输出
}

// 通过ID查询后下载
$fileId = $_GET['id'];
$sql = "SELECT * FROM files WHERE id = " . $fileId;  // 未检查所有权
$file = mysqli_fetch_assoc(mysqli_query($conn, $sql));
header('Content-Disposition: attachment; filename=' . $file['name']);
readfile($file['path']);

// 文件包含场景
$page = $_GET['page'];
include('pages/' . $page . '.php');  // 直接包含无验证

// 常见变体
$docId = $_REQUEST['doc_id'];  // $_REQUEST混用
$doc = $pdo->query("SELECT path FROM documents WHERE id=$docId")->fetch();
file_get_contents($doc['path']);  // 读取后处理

// Laravel隐蔽模式
Route::get('/download/{id}', function($id) {
    $file = File::find($id);  // Eloquent直接查询
    return response()->download(storage_path($file->path));  // 未检查user_id
});

// Symfony Controller
public function downloadAction(Request $request) {
    $filename = $request->query->get('filename');  // 从query获取
    $path = $this->getParameter('upload_dir') . '/' . $filename;
    return new BinaryFileResponse($path);  // 无ACL检查
}
```

**快速定位核心操作（L1-L2 关键词扫描/跳读）：**
- **L1参数获取**：`$_GET`、`$_POST`、`$_REQUEST`、`$_FILES`、`$request->query->get()`、`$request->input()`
- **L1文件操作**：`readfile()`、`file_get_contents()`、`fopen()`、`fread()`、`include()`、`require()`、`include_once()`
- **L1框架下载**：`response()->download()`、`BinaryFileResponse`、`StreamedResponse`、`header('Content-Disposition')`
- **L2数据查询**：
  - 原生SQL：`mysqli_query()`、`mysql_query()`、`$pdo->query()`、`$pdo->prepare()`
  - ORM：`Model::find()`、`Model::where('id', $id)->first()`、`$em->find()`（Doctrine）
  - 关注表：files、documents、attachments、uploads、media
- **L2路径构造**：字符串拼接（`.`连接符）、`sprintf()`、路径常量（`UPLOAD_DIR`）与变量组合

**快速定位保护机制（L3-L4 逐行读/跨模块追踪）：**
- **L3同层校验**：
  - **会话检查**：
    - `$_SESSION['user_id']`、`session('user_id')`（Laravel）
    - `Auth::check()`、`Auth::id()`、`$this->getUser()`（Symfony）
  - **所有权验证**：
    - 条件判断：`if ($file['user_id'] != $_SESSION['user_id']) exit('Forbidden')`
    - SQL条件：`WHERE id=? AND user_id=?`（检查占位符数量）
    - ORM过滤：`->where('user_id', Auth::id())`
  - **路径校验**：
    - `basename()`去目录、`realpath()`规范化、`strpos()`检查前缀
    - 白名单：`in_array($filename, $allowedFiles)`
- **L3中间件/钩子**：
  - Laravel：`Route::middleware(['auth', 'can:download,file'])`、`Gate::allows('download', $file)`
  - Symfony：`@Security`注解、`$this->denyAccessUnlessGranted('DOWNLOAD', $file)`
  - 全局中间件：`app/Http/Middleware/`、`EventSubscriber`
- **L4跨模块追踪**：
  - **Service封装**：
    - 追踪`FileService::getFile($id, $userId)`方法签名，确认是否强制传递userId
    - 检查`canUserAccessFile()`类似方法是否在文件操作前调用
  - **Repository层**：
    - 自定义查询：`findByIdAndUser($id, $userId)`、`findOneBy(['id' => $id, 'owner' => $user])`
    - QueryBuilder：`->andWhere('f.userId = :uid')->setParameter('uid', $currentUserId)`
  - **ACL框架**：
    - Symfony ACL：`$aclProvider->findAcl(ObjectIdentity::fromDomainObject($file))`
    - 自定义ACL：数据库acl表、`hasPermission()`全局函数
  - **钩子触发**：
    - Doctrine事件：`@HasLifecycleCallbacks`、`@PostLoad`加载时过滤
    - Eloquent事件：`Model::retrieved()`监听器注入权限逻辑

## Classify

**漏洞判定标准：**
- 文件名/ID参数直接来自`$_GET`/`$_POST`，可通过修改参数访问任意文件
- 数据库查询或文件系统操作未关联当前会话用户标识
- 能够下载其他用户的私密文档或遍历获取系统敏感文件

**误报常见场景：**
- **公共资源**：下载的是产品手册、通知附件等设计允许全员访问的文件
- **前置验证**：中间件/Filter已验证token合法性，且token签发时已限制可访问的fileId集合
- **查询约束**：SQL语句强制`WHERE user_id = {当前用户}`，ORM查询已绑定会话关联
- **文件映射**：参数经过哈希映射表转换，攻击者无法推测真实路径或ID对应关系
- **ACL框架托底**：Symfony Security Voters或Laravel Gates已统一拦截（需确认配置覆盖性）

**代码异味识别：**
- **防御不足**：仅检查文件是否存在（`file_exists()`）但未验证所有权
- **路径修复遗漏**：修复了路径遍历（`../`过滤）但未加所有权检查
- **条件保护缺陷**：仅在普通用户角色校验（`if (!isAdmin()) checkOwner()`），管理员跳过检查存在风险
- **软删除混淆**：WHERE条件包含`deleted=0`但遗漏`AND user_id={uid}`
- **前端信任**：依赖JS禁用下载按钮，后端未二次验证
- **类型混淆**：使用`==`弱类型比较（`$file['user_id'] == $_GET['fake_admin']`可被字符串绕过）

## Low risk

**可降级为低风险的场景：**
- **文件脱敏处理**：下载前已水印标记、内容加密或仅返回预览图，非原始敏感文件
- **影响范围受限**：
  - 仅泄露文件元数据（名称、大小、MD5），无法获取实际内容
  - 文件ID为UUID或随机哈希，不可枚举且无业务价值
  - 临时文件（缓存、日志片段）不含用户隐私
- **业务逻辑防护**：
  - 下载消耗积分/需二次验证（短信码），攻击成本高且留痕
  - 文件访问记录完整审计日志，异常行为可追溯和告警
- **外部控制机制**：
  - 存储在OSS/S3且配置了细粒度ACL策略，后端仅签发临时URL且验证身份
  - Web服务器层（Nginx/Apache）已配置`X-Accel-Redirect`/`X-Sendfile`并限制路径范围
  - CDN层已启用鉴权URL（时效签名），后端无直接下载逻辑
- **数据价值低**：
  - 测试环境无真实用户数据
  - 文件为公开数据集副本、系统默认模板，即使越权获取也无危害
  - 已过期的历史归档文件，当前无业务价值
- **补偿控制**：
  - WAF规则拦截文件名枚举、高频下载行为
  - 数据库触发器记录所有文件访问并实时比对user_id（需确认实现）
  - 仅内网访问且网络隔离完善（需业务场景确认）
