# Python 路径遍历与文件包含漏洞

## Details

### 漏洞成因
Python Web 应用（Flask、Django、FastAPI 等）常通过 `open`、`os.path.join`、`send_file`、`send_from_directory`、`FileResponse` 等接口根据请求参数返回文件或加载模板。如果缺乏路径规范化和白名单控制，攻击者可利用 `../`、URL 编码、双写、Unicode 变体来穿越目录，读取敏感配置（如 `.env`、`settings.py`）、源码或系统文件。组件化框架还可能允许动态导入模块、执行模板（Jinja2 `Environment.get_template`）导致本地/远程包含。上传解压、备份恢复逻辑若未校验目标路径，也会造成覆盖写入。

### 代码示例

**易受攻击的代码（Django 下载接口）：**
```python
from django.http import FileResponse

def download(request):
    name = request.GET.get("name", "")
    path = f"/var/app/uploads/{name}"  # 未校验 ../
    try:
        return FileResponse(open(path, "rb"))
    except FileNotFoundError:
        return HttpResponseNotFound()
```

**Flask 静态代理（send_file）：**
```python
@app.route("/preview")
def preview():
    doc = request.args.get("doc")
    # doc=../../../../etc/passwd
    abs_path = os.path.join(app.config["DOC_ROOT"], doc)
    return send_file(abs_path)  # 未使用安全 join
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- `open`, `os.open`, `pathlib.Path.open`, `builtins.__import__`
- `os.path.join`, `os.path.abspath`, `os.path.normpath`, `Path.resolve`
- Flask/Django 响应：`send_file`, `send_from_directory`, `FileResponse`, `StaticFiles`
- 模板加载：`Environment.get_template`, `loader.get_source`, `importlib.import_module`
- 解压：`zipfile`, `tarfile`, `shutil.unpack_archive`

**定位步骤：**
1. 搜索上述 API，并查找与 `request.args`, `request.form`, `request.json`, `path_params` 等用户输入组合使用的逻辑。
2. 关注文件下载、报告导出、预览、插件加载、模板切换功能。
3. 跳读（L2）确认是否进行了 `os.path.normpath` + 根目录校验或白名单映射。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **路径标准化：** `os.path.normpath`, `os.path.realpath`, `Path.resolve(strict=True)`
- **根目录前缀校验：** `abs_path.startswith(base_dir)` 或使用 `os.path.commonpath`
- **白名单映射：** 定义允许访问的文件名/模板列表
- **扩展名/MIME 校验：** 防止加载脚本或敏感文件
- **禁止远程协议：** 对 `requests.get` 等远程拉取操作做协议限制

**定位技巧：**
- 确认 `normpath` 或 `resolve` 的结果被重新赋值并使用。
- 检查 `commonpath` 使用是否正确（需传列表，且比较目录而非文件名）。
- 对 `zipfile`, `tarfile` 使用 `extractall` 时，确认是否有成员路径校验。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 使用白名单映射或固定模板 | **L0（快速跳过）** | 用户无法自定义路径 |
| `normpath` + 根目录校验 | **L2（跳读）** | 检查是否覆盖符号链接/编码绕过 |
| 直接拼接请求参数为路径 | **L3（逐行读）** | 高风险，需要逐行分析 |
| 上传解压/动态导入模块 | **L4（跨模块追踪）** | 需跨文件追踪处理链路 |

## Classify

### 研判标准

#### 确认漏洞
判断为路径遍历/LFI/RFI 的条件：
1. **用户可控路径：** 输入直接或经简单处理后用于文件访问/模板加载。
2. **防护缺失：** 未做规范化前缀校验或白名单限制。
3. **敏感影响：** 能访问应用根目录外的文件、包含任意模板或远程资源。

#### 误报
判定为误报的情况：
1. **路径名由受控枚举/数据库字段映射。**
2. **标准化后验证前缀，且拒绝异常。**
3. **访问目录仅包含公开静态资源，无敏感内容。**

#### 代码异味
需记录的风险模式：
1. **仅用 `replace("../", "")` 等替换逻辑。**
2. **未处理符号链接或大小写问题。**
3. **依赖 Nginx/网关校验，缺乏后端保护。**

## Low risk

### 低风险评级场景

#### 1. 后台限定功能
- **场景：** 接口仅供内部管理员使用。
- **风险评估：** 攻击面有限，但需防会话泄露。

#### 2. 只读公开目录
- **场景：** 访问对象为公开文档，部署时无敏感文件。
- **风险评估：** 危害较小，但需防目录遍历泄露结构。

#### 3. 容器/虚拟化隔离
- **场景：** 应用运行在受限容器，访问根目录即沙箱。
- **风险评估：** 影响范围受限，但仍需修复代码。

#### 4. 外部监控
- **场景：** 集成安全代理、审计日志对异常路径告警。
- **风险评估：** 提供侦测手段，但无法完全阻挡。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 功能仅对内开放 | 攻击面小 | 中 |
| `normpath` + `commonpath` 校验 | 技术封堵遍历 | 低 |
| 沙箱/容器隔离 | 限制危害 | 中 |
| 安全监控告警 | 提升可见性 | 高（继续推进修复）|

