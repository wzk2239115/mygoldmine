# PHP Symfony 批量赋值漏洞

## Details

### 漏洞成因
Symfony 框架通过 Form 组件、Serializer、API Platform 等机制，将请求数据映射到实体或 DTO。若表单未使用 `->add()` 白名单字段，或 Serializer 未配置 `groups`, `denormalizationContext`, `ignoreAttributes` 等限制，攻击者可提交额外字段覆盖敏感属性（如 `roles`, `enabled`, `isAdmin`, `tenant`, `status`）。Doctrine ORM 的 `EntityManager::persist` 与 `flush` 若直接使用反序列化结果，也会造成批量赋值漏洞。

### 代码示例

**易受攻击的代码：**
```php
// Controller
public function update(Request $request, User $user, EntityManagerInterface $em): Response
{
    $data = json_decode($request->getContent(), true);
    // Serializer 未限制字段，JSON 可包含 roles => ["ROLE_ADMIN"]
    $this->serializer->denormalize($data, User::class, null, ['object_to_populate' => $user]);
    $em->flush();
    return $this->json($user);
}
```

**另一个不安全示例（Form 组件）：**
```php
class UserType extends AbstractType
{
    public function buildForm(FormBuilderInterface $builder, array $options)
    {
        $builder->add('email')->add('password')->add('roles'); // roles 不应可写
    }
}

public function create(Request $request, EntityManagerInterface $em): Response
{
    $user = new User();
    $form = $this->createForm(UserType::class, $user);
    $form->handleRequest($request); // roles 可由用户提交
    if ($form->isSubmitted() && $form->isValid()) {
        $em->persist($user);
        $em->flush();
    }
    return $this->redirectToRoute('user_list');
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- Serializer：`denormalize`, `deserialize`, `ObjectNormalizer`
- FormType：`$builder->add`, `configureOptions`, `allow_extra_fields`
- API Platform：`normalizationContext`, `denormalizationContext`
- Doctrine 更新：`persist`, `flush`, `merge`

**定位步骤：**
1. 搜索控制器/Service 中的 Serializer 调用，检查上下文配置。
2. 查看 FormType 是否添加了敏感字段或允许额外字段。
3. 跳读（L2）确认实体是否包含 `roles`, `isAdmin`, `tenant` 等属性。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **FormType 白名单：** 仅添加允许字段，移除敏感字段。
- **Serializer Groups：** `denormalizationContext` 限制可写字段。
- **`ignoreAttributes`/`allow_extra_fields`：** 拒绝额外字段。
- **安全检查：** 使用 `Voter`/`Security` 权限校验。
- **DTO 分离：** 输入 DTO 不包含敏感字段。

**定位技巧：**
- 检查 Entity 是否实现 `UserInterface` 并包含角色字段。
- 查看 API Platform Resource 注解中的 `denormalizationContext` 是否包含敏感字段。
- 确认 `allow_extra_fields` 是否设置为 `false`。

#### 审计等级标注

| 场景 | 审计等级 | 说明 |
|------|----------|------|
| Serializer/Form 均使用白名单 | **L0（快速跳过）** | 风险低 |
| 部分白名单，但敏感字段通过其他路径保护 | **L2（跳读）** | 验证完整性 |
| 直接 `denormalize` 或 Form 允许敏感字段 | **L3（逐行读）** | 高风险 |
| API Platform 多资源共享实体 | **L4（跨模块追踪）** | 需检查所有上下文 |

## Classify

### 研判标准

#### 确认漏洞
需满足以下条件：
1. **Form/Serializer** 自动将请求映射到实体/DTO。
2. **未限制敏感字段** 或允许额外字段。
3. **产生越权或关键数据篡改**。

#### 误报
可视为误报的情况：
1. 使用 `denormalizationContext` 或 FormType 白名单限制字段。
2. 输入数据经过自定义 Handler 过滤。
3. 接口仅对内部受信系统开放且有签名验证。

#### 代码异味
需关注的风险：
1. 依赖 `ignoreAttributes` 黑名单，易遗漏。
2. Form `allow_extra_fields` 设置为 `true`。
3. DTO/实体共享，新增字段可能未更新安全配置。
4. 缺少审计记录，难以追踪敏感变更。

## Low risk

### 低风险评级场景

#### 1. 仅管理员访问
- **场景：** 接口仅对高级管理员开放。
- **风险评估：** 攻击面小，但需防账号泄露。

#### 2. DTO 手动映射
- **场景：** 输入 DTO 不包含敏感字段，由服务层手动赋值。
- **风险评估：** 风险较低，但需持续维护。

#### 3. 数据库约束/触发器
- **场景：** 敏感列由数据库限制不可修改。
- **风险评估：** 降低危害，但非根治。

#### 4. 审计与告警
- **场景：** 对角色/状态变更有日志与告警。
- **风险评估：** 有助于检测异常，但需修复根因。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 管理员专用接口 | 攻击面有限 | 中 |
| DTO 白名单 + 权限校验 | 技术防护完善 | 低 |
| 数据库约束 | 阻断敏感修改 | 中 |
| 审计告警 | 及时发现异常 | 高（持续改进）|

