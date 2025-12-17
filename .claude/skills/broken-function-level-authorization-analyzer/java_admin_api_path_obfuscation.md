# Java｜管理员 API 仅依赖路径混淆

## Details

### 漏洞成因
部分 Java 后端仅通过将管理员接口放在特殊路径（如 `/hidden-admin`、`/internal`）或前端隐藏菜单来限制访问，而未在后端实现真实的权限校验。攻击者可以直接构造请求访问这些路径，从而绕过权限限制，执行敏感操作（导出数据、调整配置、删除账号）。

### 代码示例

**易受攻击示例：**
```java
@RestController
@RequestMapping("/internal/maintenance")
public class MaintenanceController {

    @PostMapping("/rebuild-index")
    public void rebuildIndex() {
        searchService.rebuild(); // 无权限检测
    }
}
```

**安全示例：**
```java
@RestController
@RequestMapping("/internal/maintenance")
public class MaintenanceController {

    @PreAuthorize("hasAuthority('maintenance:rebuild')")
    @PostMapping("/rebuild-index")
    public void rebuildIndex() {
        searchService.rebuild();
    }
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `internal`, `admin`, `maintenance`, `hidden`, `@RequestMapping`, `rebuild`, `export`, `config`。

**定位步骤：**
1. 搜索路径包含 `/admin`, `/internal`, `/hidden` 等关键词的 Controller；
2. 跳读（L2）确认是否缺少权限注解或校验逻辑；
3. 查看这些接口是否在文档或前端隐藏。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- 后端方法级权限注解；
- API Gateway 引入 RBAC；
- IP 白名单或 VPN 访问限制（仍需细粒度权限）；
- 访问日志与异常告警。

**定位技巧：**
- 逐行读（L3）敏感操作是否包含二次验证（口令、签名）；
- 跨模块追踪（L4）链路（移动端、第三方）是否能直接访问这些路径。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 接口带完整权限校验 | **L0（快速跳过）** | 安全性高 |
| 仅依赖前端隐藏或路径命名 | **L3（逐行读）** | 高风险 |
| 配合网关但仍无后端校验 | **L3（逐行读）** | 潜在绕过 |
| 多系统共享相同隐藏路径 | **L4（跨模块追踪）** | 必须全链路验证 |

## Classify

### 研判标准

#### 确认漏洞
1. 接口缺乏后端权限校验；
2. 普通用户直接访问即可成功；
3. 操作影响敏感数据或系统配置。

#### 误报
1. 接口虽然路径隐藏，但后端仍执行权限认证；
2. 接口仅部署在隔离网络，外部无法访问且有额外认证；
3. 接口只供自动化工具使用，并有强认证机制。

#### 代码异味
1. 把权限控制完全交给前端路由；
2. 使用自定义 header 校验但未验证其来源；
3. 缺少访问日志，无法追踪异常调用。

## Low risk

### 低风险评级场景

#### 1. 接口为只读状态检查
- **场景：** 返回运行信息，无敏感数据；
- **评估：** 可标低风险。

#### 2. 部署在隔离网络且有额外安全控制
- **场景：** 仅内部堡垒机访问；
- **评估：** 攻击面小，但仍需提醒。

#### 3. 计划引入统一权限网关
- **场景：** 即将上线 RBAC/ABAC；
- **评估：** 可暂降级，跟踪改造。

#### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 只读接口 | 影响有限 | 低 |
| 隔离网络 | 攻击面低 | 中 |
| 改造计划明确 | 可暂缓 | 低 |
