# Python Flask 文件检索 IDOR 漏洞审计

## Details

### 代码示例

```python
@app.route('/download/<filename>')
def download_file(filename):
    return send_file(f'uploads/{filename}')

@app.route('/file/<file_id>')
def get_file(file_id):
    file_path = db.query(File).filter_by(id=file_id).first().path
    return send_from_directory('storage', file_path)

@app.route('/report/<int:report_id>')
def view_report(report_id):
    report = Report.query.get(report_id)
    return send_file(report.file_path)
```

### 快速定位核心操作（L2-L3）

**路由参数提取：**（L1）关键词 `<filename>`、`<file_id>`、`<path:filepath>` 等路由变量，`request.args.get`、`request.form.get`

**文件操作函数：**（L1）`send_file()`、`send_from_directory()`、`open()`、`read()`、`FileResponse()`

**路径拼接：**（L2）f-string、`os.path.join()`、字符串拼接 `+`，跟踪变量是否直接来自用户输入

**数据库查询：**（L3）`.get(id)`、`.filter_by(id=...)`、`.filter(Model.id==...)`，关注查询条件是否仅依赖用户可控ID

### 快速定位保护机制（L3-L4）

**所有权验证：**（L3）查找 `current_user`、`session.get('user_id')`、`g.user`，检查是否与文件所有者比对

**权限装饰器：**（L2）`@login_required`、`@permission_required`、自定义装饰器，判断是否有业务层权限检查

**ORM关联查询：**（L4）`.filter(File.user_id == current_user.id)`、关系属性过滤，跨表追踪所有权链条

**白名单过滤：**（L3）路径白名单、文件类型校验、`secure_filename()` 使用，判断是否仅处理路径遍历而忽略授权

**中间件/钩子：**（L4）`@before_request`、自定义中间件，跨模块追踪全局鉴权逻辑

## Classify

### 确认为漏洞
- 用户可控参数直接用于文件路径构造或数据库查询，且无任何所有权比对
- 仅验证文件存在性或路径合法性，未验证当前用户是否有权访问该资源
- 权限检查仅确认登录态，未验证资源级别授权（如user_id匹配）

### 判定为误报
- 文件属于公开资源（如公共文档库、静态资源CDN）
- 存在有效的跨表关联查询，确保只返回当前用户有权访问的记录
- 路由参数为加密token或不可预测的UUID，且token与用户绑定验证

### 归类为代码异味
- 存在权限检查但逻辑复杂、分散在多处难以追踪
- 依赖前端参数校验或客户端逻辑限制（后端未强制）
- 使用软删除或状态标记，但未在文件访问时复查状态

## Low Risk

- 文件仅包含非敏感信息（如公开的缩略图、通用模板）
- 泄露信息已在其他公开接口可获取（如用户头像、公开文档）
- 文件名或ID为不可预测的长随机串（128位以上），且无枚举接口
- 资源访问有严格的速率限制和监控告警
- 文件访问记录被完整记录，可追溯且有异常检测机制