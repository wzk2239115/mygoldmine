# TypeScript｜Angular bypassSecurityTrust 系列误用 XSS

## 基本信息

- **难度等级：** ★★★★☆ (中高级)
- **审计时间：** 25-40分钟（单个漏洞点）
- **先决知识：** Angular 框架、DomSanitizer、SecurityContext、信任 API、RxJS
- **复杂度评估：**
  - 简单场景（单个 bypassSecurityTrust 调用）：20-25分钟
  - 复杂场景（多个组件、动态内容、跨文件）：40-60分钟

## 🚀 30秒快速清单

- [ ] 代码是否使用了 `bypassSecurityTrustHtml()`、`bypassSecurityTrustUrl()` 等信任 API？
- [ ] 这些 API 处理的数据是否来自用户输入或不可信数据源？
- [ ] 在调用信任 API 前是否经过了 DOMPurify 或其他净化库的处理？
- [ ] 是否仅对特定的 SecurityContext（HTML、URL、Attribute）使用了信任 API？
- [ ] 是否存在多个组件使用信任 API 且管理混乱的情况？

**判断：** 如果第 1-2 个问题打勾且第 3 个未打勾，需要进行 L3+ 深度分析

## Details

### 漏洞成因
Angular 默认启用 DomSanitizer 对 HTML、URL、样式进行安全处理。但若开发者调用 `bypassSecurityTrustHtml`、`bypassSecurityTrustStyle`、`bypassSecurityTrustUrl` 等方法直接信任用户输入，就会绕过 Angular 的自动转义，导致 XSS。

### 代码示例

**易受攻击的代码：**
```typescript
@Component({ selector: 'app-preview', template: '<div [innerHTML]="trusted"></div>' })
export class PreviewComponent {
  trusted: SafeHtml;
  constructor(private sanitizer: DomSanitizer) {
    const html = localStorage.getItem('preview');
    this.trusted = this.sanitizer.bypassSecurityTrustHtml(html || '');
  }
}
```

**安全示例：**
```typescript
@Component({ selector: 'app-preview', template: '<div [innerText]="content"></div>' })
export class PreviewComponent {
  content = (localStorage.getItem('preview') || '').slice(0, 500);
  // 若必须渲染富文本，使用可信后端过滤或 DOMPurify
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `DomSanitizer`, `bypassSecurityTrustHtml`, `bypassSecurityTrustUrl`, `bypassSecurityTrustStyle`, `[innerHTML]`, `[style]`, `[src]`。

**定位步骤：**
1. 搜索 `bypassSecurityTrust` 方法调用；
2. 跳读（L2）确认传入的数据是否来自用户或第三方；
3. 检查组件模板是否直接绑定 `[innerHTML]`。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- 使用 Angular DomSanitizer 默认转义；
- 后端提供净化后的白名单 HTML；
- 使用 `innerText`、`textContent` 等安全绑定；
- 引入 DOMPurify 并严格限制标签属性。

**定位技巧：**
- 逐行读（L3）确认 bypass 仅用于可信常量；
- 跨模块追踪（L4）同一服务是否返回含脚本的富文本。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 未使用 bypass，依赖默认转义 | **L0（快速跳过）** | 风险低 |
| 少数组件 bypass 且来源受控 | **L2（跳读）** | 核实来源 |
| 广泛使用 bypass 信任用户输入 | **L3（逐行读）** | 高风险 |
| 数据来自多模块富文本 | **L4（跨模块追踪）** | 需完整链路分析 |

## Classify

### 研判标准

#### 确认漏洞
1. 通过 bypassSecurityTrust 信任用户/第三方输入；
2. 缺乏净化或白名单控制；
3. 可注入脚本执行。

#### 误报
1. bypass 仅用于硬编码常量或 SVG 图标；
2. 数据来源于可信后端，已严格净化；
3. 组件仅在内部受控环境渲染且不可被攻击者操控。

#### 代码异味
1. 在服务层统一返回 `SafeHtml` 而未说明净化机制；
2. bypass 与 `[innerHTML]` 同时出现但缺少注释；
3. 依赖前端正则过滤脚本标签。

## Low risk

### 低风险评级场景

#### 1. 内容仅由管理员编辑
- 攻击面小，可暂列低风险。

#### 2. 页面仅面向内网
- 仍建议改造，但影响有限。

#### 3. 计划接入统一净化/白名单服务
- 有清晰时间表，可暂降级并跟踪。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 管理员受控 | 攻击面小 | 中 |
| 内网使用 | 影响有限 | 低 |
| 改造计划明确 | 可暂缓 | 低 |
