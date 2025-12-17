# PHP 文件上传审批绕过漏洞

**漏洞成因**：文件上传审批流程中，权限检查与操作执行分离，导致在审批前即可完成上传、访问或后续操作，绕过审批约束。典型表现为"先传后审"架构中，已上传文件在审批拒绝后仍可访问，或审批流程可被跳过直接进入后续环节。

---

## Details

**核心代码特征**：
```php
// 典型漏洞模式
function uploadFile() {
    $file = $_FILES['file'];
    $path = '/uploads/' . uniqid() . '_' . $file['name'];
    move_uploaded_file($file['tmp_name'], $path);  // 先执行上传
    
    createApprovalTask($path, $userId);  // 后创建审批
    return ['url' => $path, 'status' => 'pending'];  // 返回可访问路径
}

function approveFile($taskId) {
    $task = getTask($taskId);
    // 审批拒绝时未删除已上传文件
    updateTaskStatus($taskId, 'rejected');
}
```

**审计定位技巧**：

**L2 - 跳读（快速定位核心操作）**：
- 搜索上传函数：`move_uploaded_file|file_put_contents|copy|rename|Storage::put`
- 关注审批入口：`approve|review|audit|check` + `upload|file|attachment`
- 追踪路径：上传后返回的 `url|path|file_id` 是否包含可猜测的位置

**L3 - 逐行读（定位时序缺陷）**：
1. **确认操作顺序**：检查是否"权限验证 → 审批创建 → 文件上传 → 返回路径"
2. **查找关键分支**：`if (approved)` 是在上传前还是上传后
3. **检查回滚机制**：审批拒绝时是否调用 `unlink|delete|Storage::delete`

**L4 - 跨模块追踪（保护机制）**：
- **访问控制**：上传目录是否配置 `.htaccess` 禁止直接访问或需要鉴权
- **文件下载中转**：是否通过 `download.php?id=xxx` 验证审批状态后再输出文件
- **临时隔离**：待审批文件存储在受保护的临时目录（如 `/private/pending/`）
- **数据库关联**：文件记录表是否有 `approved` 字段，查询时强制 `WHERE approved = 1`

**危险信号**（直接判定高风险）：
- 上传完成即返回 `/uploads/xxx.pdf` 等直接可访问的公开路径
- 审批表与文件表无关联，或关联后不校验状态
- 文件名使用 `user_id_timestamp.ext` 等可枚举模式
- 控制器中有 `uploadTemp` 和 `confirmUpload` 两个接口但可单独调用

---

## Classify

### ✅ 确认漏洞
- **先传后审无防护**：`move_uploaded_file` 在审批流程创建之前，且目标目录可公开访问
- **路径可预测**：返回的文件 URL 包含明文路径或简单递增 ID，无 token 保护
- **审批与访问解耦**：文件下载接口不检查 `approval_status` 字段
- **拒绝后无清理**：审批拒绝仅更新状态，不执行 `unlink()` 删除文件
- **流程可跳过**：存在 `/upload` 和 `/uploadWithApproval` 两个入口，前者无限制

### ⚠️ 代码异味
- **软删除无物理删除**：审批拒绝设置 `deleted_at` 但文件仍在磁盘
- **异步审批**：上传成功后加入队列等待审批，期间文件已可访问
- **前端隐藏**：依赖前端不显示"未审批"文件，但后端接口无校验
- **混合权限**：部分文件类型需要审批，部分不需要，规则分散

### ✗ 误报
- **临时目录隔离**：待审批文件存储在 Web 根目录外（如 `/var/private/`）
- **下载鉴权严密**：所有文件访问必须通过 `fileProxy.php` 并验证 `is_approved = 1`
- **随机 token 保护**：文件路径包含 64 位随机 token，且与审批状态绑定
- **Web 服务器防护**：Nginx 配置 `/uploads/pending/` 返回 403

---

## Low Risk

以下场景可评为低风险（但仍需记录）：

1. **仅内部使用**：上传功能限管理员，且审批流程用于内部备案而非安全控制
2. **非敏感文件**：仅允许上传头像、公开资料等无机密性要求的内容
3. **短期窗口**：审批在 5 分钟内自动完成，且文件路径随机不可枚举
4. **访问日志监控**：所有待审批文件的访问会触发告警并人工介入
5. **业务自愈**：定时任务每小时清理超过 24 小时的未审批文件

**风险升级条件**（低风险→高风险）：
- 允许上传脚本文件（.php/.jsp）且目录可执行
- 涉及财务凭证、合同文档等敏感材料
- 存在历史记录显示用户绕过审批访问他人文件
- 文件路径可遍历（`id=1,2,3...`）且无权限隔离
