# PHP - GET/REQUEST 参数直接查询未授权漏洞

## Details

**代码示例：**
```php
// 典型漏洞模式 - 直接拼接SQL（SQL注入+IDOR双重风险）
$user_id = $_GET['id'];
$sql = "SELECT * FROM users WHERE id = $user_id";
$result = mysqli_query($conn, $sql);

// 预编译绑定但未校验权限
$user_id = $_REQUEST['user_id'];
$stmt = $pdo->prepare("SELECT * FROM user_profile WHERE id = ?");
$stmt->execute([$user_id]);
$profile = $stmt->fetch();

// ORM查询无权限校验
$order_id = $_GET['order_id'];
$order = $db->query("orders")->where("id", $order_id)->first();

// 框架路由参数
// Laravel: $id = $request->input('user_id');
// ThinkPHP: $id = input('get.id'); 或 Request::param('id');
// CodeIgniter: $id = $this->input->get('user_id');
$user = User::find($id);  // 直接查询
```

**快速定位核心操作（L1-L2 关键词扫描/跳读）：**
- **参数提取识别**：
  - 超全局变量：`$_GET[`、`$_POST[`、`$_REQUEST[`、`$_COOKIE[`、`$_SERVER['HTTP_`
  - 框架封装：`input()`、`$request->input/get/post()`、`Request::param()`、`$this->input->`
  - 参数名特征：`id`、`user_id`、`uid`、`order_id`、`file_id`、`doc_id`等ID字段
- **数据库操作入口**：
  - 原生SQL：`query()`、`mysqli_query()`、`mysql_query()`、`prepare()->execute()`
  - ORM：`find()`、`where()->first()`、`get()`、`select()`、`table()->where()`
  - 框架DB：`DB::table()->where()`、`M('user')->where()`、`$this->db->get_where()`
- **定位技巧**：
  - 搜索`$_GET[` → 提取变量名 → 全局搜索该变量 → 追踪至SQL/ORM查询 → 验证中间无过滤

**快速定位保护机制（L3-L4 逐行读/跨模块追踪）：**
- **L3-同文件检查**：
  - **会话校验**：
    - `$_SESSION['user_id']`、`session('user_id')`、`Auth::id()`是否存在
    - `if (!isset($_SESSION['user_id'])) exit();` 仅验证登录但未校验所有权
  - **所有权判断**：
    - 查询前：`if ($user_id != $_SESSION['user_id']) die('forbidden');`
    - 查询后：`if ($result['owner_id'] != $_SESSION['user_id']) return;`
    - SQL条件：`WHERE id=? AND user_id=?` （检查占位符/条件字段数量）
  - **参数过滤**：
    - `intval()`、`filter_var()`仅过滤类型，不代表权限校验
    - `is_numeric()`、`ctype_digit()`只防注入，不防越权
- **L4-跨文件追踪**：
  - **公共函数封装**：
    - 追踪`getUserInfo($id)`、`getOrderDetail($id)`实现，检查是否注入session校验
    - 确认函数内部是否自动拼接`AND owner_id = {$_SESSION['uid']}`
  - **中间件/钩子**：
    - Laravel：检查路由是否有`->middleware('auth', 'can:view,user')`
    - ThinkPHP：查找`_before`钩子或行为绑定`'before_select' => 'checkOwner'`
    - 自定义：`require_once 'auth_check.php'`文件是否校验资源归属
  - **ORM模型层**：
    - 全局Scope：Laravel `protected static function boot() { static::addGlobalScope(...) }`
    - 模型事件：`Model::retrieved()`、`Model::find()`钩子是否过滤
  - **框架级安全**：
    - 检查ACL配置文件（如`auth.php`、`permission.php`）是否定义资源权限规则
    - 确认路由定义处是否绑定权限验证：`Route::get()->can('view')`

## Classify

**漏洞确认标准：**
- **可横向越权**：修改`?id=`参数值可访问任意用户/订单/文档，无需额外凭证
- **敏感数据泄露**：响应包含密码hash、手机号、邮箱、身份证、地址、余额等私密字段
- **零防护特征**：既无session比对、也无SQL条件约束、更无框架中间件拦截

**误报排除依据：**
- **公开资源设计**：
  - 查询的是公开文章、商品详情、分类列表等无需权限控制的数据
  - 业务逻辑本身允许用户互查（如社交平台的公开主页）
- **前置拦截有效**：
  - 入口统一鉴权：所有请求经`require 'auth.php'`过滤，已绑定用户可访问ID范围
  - Nginx/Apache配置层已限制访问，后端仅处理已授权请求
- **字段过滤充分**：
  - 查询后仅提取公开字段：`return ['nickname'=>$user['nickname'], 'avatar'=>$user['avatar']];`
  - SQL显式排除敏感列：`SELECT id,username FROM users` 不含phone/email
- **静态数据表**：
  - 查询配置表、字典表、常量表等无敏感信息的参考数据

**代码异味识别：**
- **防御不完整**：
  - 仅校验ID格式（`is_numeric($id)`）或正则匹配，未校验归属关系
  - 仅验证登录态（`if(!$_SESSION['uid'])`），未比对资源所有者
- **条件性保护**：
  - 仅在`$role != 'admin'`分支校验，管理员路径存在漏洞
  - `if($_GET['check']==1)`才验证权限，可通过删除参数绕过
- **客户端依赖**：
  - 前端JS过滤不显示他人ID，后端无二次验证
  - 通过`$_POST['is_owner']`判断权限，可客户端伪造
- **逻辑缺陷**：
  - 查询失败返回空数组而非抛异常，导致绕过后续权限校验
  - 使用`||`短路逻辑：`if($is_admin || checkOwner())`管理员未执行检查

## Low risk

**可降级为低风险的场景：**
- **数据脱敏充分**：
  - 手机号中间4位替换为`*`、邮箱仅显示首尾字符
  - 姓名仅显示姓氏+`**`、身份证号隐藏中间12位
  - 金额/余额字段返回`null`或固定值`-`，非真实数据
- **影响范围受限**：
  - 仅泄露用户等级、注册时间、头像URL、公开标签等低敏感度字段
  - 返回数组通过白名单键过滤（需代码确认严格执行）
- **外部控制层**：
  - 数据库配置视图权限或触发器自动过滤（MySQL `DEFINER`、PostgreSQL RLS）
  - WAF规则拦截异常ID枚举行为（需确认规则有效且不可绕过）
  - API网关统一鉴权，配置已覆盖全部敏感路由（需审查配置完整性）
- **间接利用门槛高**：
  - ID为UUID/hash且无序，需先通过其他漏洞获取有效ID列表
  - 接口限流严格（如10秒内仅允许3次访问），批量枚举成本极高
  - 需配合验证码或短信验证才能查看完整信息
- **业务场景限制**：
  - 内部CRM/ERP系统，用户间本可互查（需与业务确认设计意图）
  - 测试/预发布环境，不包含真实生产数据
  - 历史遗留接口已停用，日志显示近3个月无访问记录