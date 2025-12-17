# Python API对象暴露 - IDOR审计

## 漏洞成因
API接口通过JSON请求/响应中的`id`/`user_id`等字段直接查询并返回对象数据，未校验请求者是否有权访问该资源。

## Details

### 代码示例
```python
@app.route('/api/user/<int:user_id>')
def get_user(user_id):
    user = User.query.get(user_id)  # 直接通过ID查询
    return jsonify(user.to_dict())  # 未验证session['user_id'] == user_id

@app.route('/api/order', methods=['POST'])
def get_order():
    order_id = request.json.get('order_id')
    order = Order.query.filter_by(id=order_id).first()
    return jsonify(order.serialize())  # 未检查order.user_id
```

### 快速定位核心操作 (L2:跳读)
- 搜索路由装饰器：`@app.route`、`@bp.route`、`@api.route`
- 关注URL参数提取：`<int:id>`、`request.args.get('id')`、`request.json.get('xxx_id')`
- 定位ORM查询：`query.get()`、`filter_by(id=)`、`find_one({'_id':})`
- 追踪响应序列化：`jsonify()`、`to_dict()`、`.serialize()`

### 快速定位保护机制 (L1:关键词扫描 → L3:逐行读)
- **L1扫描权限关键词**：`@login_required`、`@permission_required`、`check_ownership`、`verify_access`
- **L1扫描条件判断**：`if current_user.id ==`、`if obj.owner_id ==`
- **L3逐行检查**：装饰器内部实现是否仅验证登录而未验证资源归属
- **L3查询链检查**：`filter_by(id=x, user_id=current_user.id)` 是否同时包含ID和归属条件
- **L4跨模块追踪**：自定义装饰器/中间件的实现逻辑，查看是否有硬编码跳过检查的角色

## Classify

### 确认为漏洞
- 查询条件仅基于用户可控ID，无任何归属校验
- 装饰器仅验证登录态，未验证资源所有权
- 条件分支存在但可绕过（如仅校验特定角色）

### 误报
- 查询中已包含`user_id=current_user.id`的复合条件
- 返回前有明确的`if obj.owner != current_user: abort(403)`
- 资源本身为公开数据（如公开文章、公开用户基础信息）

### 代码异味
- 仅在业务逻辑层做校验但数据层可直接调用
- 权限检查分散在多个if分支，逻辑不清晰
- 使用软删除但未在查询中过滤`deleted=False`

## Low risk

- 接口返回的是统计数据或脱敏信息（如用户昵称、头像）
- ID映射的是非敏感配置项（如公开的分类、标签）
- 系统为内部工具，攻击者无法接触到真实ID
- 已有rate limiting且ID空间大（如UUID），枚举成本极高
- 仅暴露对象存在性而非详细数据（如返回`{"exists": true}`）