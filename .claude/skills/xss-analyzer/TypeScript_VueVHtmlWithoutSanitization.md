# TypeScript｜Vue v-html 未净化导致 XSS

## 基本信息

- **难度等级：** ★★★☆☆ (中级)
- **审计时间：** 15-35分钟（单个漏洞点）
- **先决知识：** Vue 模板语法、v-html 指令、HTML 编码、DOMPurify 使用
- **复杂度评估：**
  - 简单场景（单个 v-html）：15-20分钟
  - 复杂场景（多个组件、跨文件数据流）：35-50分钟

## 🚀 30秒快速清单

- [ ] 模板中是否使用了 `v-html` 指令？
- [ ] `v-html` 绑定的值是否来自用户输入或第三方 API 响应？
- [ ] 在绑定前是否经过 DOMPurify 或其他可信净化库处理？
- [ ] 如果使用了净化库，是否有明确的白名单配置（ALLOWED_TAGS、ALLOWED_ATTR）？
- [ ] 是否存在多个 v-html 使用点且净化逻辑不一致的情况？

**判断：** 如果第 1-2 个问题打勾且第 3 个未打勾，需要进行 L3+ 深度分析

## Details

### 漏洞成因
在 Vue 项目中，Mustache 语法 (`{{ }}`) 默认转义。但 `v-html` 指令会将绑定值作为原始 HTML 插入 DOM。若绑定的字符串来自用户输入或第三方接口且未净化，即可触发 XSS。Vue 组件库（Element Plus、Ant Design Vue 等）某些插槽也可能直接渲染 HTML，需要注意来源。

### 代码示例

**易受攻击的代码：**
```vue
<template>
  <div v-html="comment"></div>
</template>

<script lang="ts">
export default defineComponent({
  props: { comment: String },
});
</script>
```

**安全示例：**
```vue
<template>
  <div v-html="sanitized"></div>
</template>

<script lang="ts">
import DOMPurify from 'dompurify';

export default defineComponent({
  props: { comment: String },
  computed: {
    sanitized(): string {
      return DOMPurify.sanitize(this.comment ?? '', { ALLOWED_TAGS: ['b', 'i', 'p'] });
    },
  },
});
</script>
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `v-html`, `v-bind:innerHTML`, `innerHTML`, `v-dangerously-set-inner-html`, `render: (h)`。

**定位步骤：**
1. 搜索模板中的 `v-html` 或函数式组件返回的 `domProps.innerHTML`；
2. 跳读（L2）确认绑定值来源；
3. 检查是否对富文本字段做了白名单过滤。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- DOMPurify、sanitize-html、xss 库；
- 服务端富文本过滤；
- 限定允许标签/属性；
- CSP + iframe sandbox 等额外防护。

**定位技巧：**
- 逐行读（L3）computed/filters，确保净化逻辑覆盖所有路径；
- 跨模块追踪（L4）富文本从后台到前端的流转。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 未使用 `v-html` 或已统一净化 | **L0（快速跳过）** | 风险低 |
| 少量 `v-html` 绑定受控来源 | **L2（跳读）** | 核实来源 |
| 大量 `v-html` 直接绑定用户输入 | **L3（逐行读）** | 高风险 |
| 多链路富文本展示 | **L4（跨模块追踪）** | 需完整分析 |

## Classify

### 研判标准

#### 确认漏洞
1. `v-html` 绑定用户可控内容；
2. 缺乏净化或限制；
3. 能插入脚本触发 XSS。

#### 误报
1. 绑定常量或经过后端严格净化；
2. 仅内部管理使用且不可被攻击者控制；
3. 绑定内容经 DOMPurify 等库处理。

#### 代码异味
1. 自定义“净化”仅删除 `<script>`；
2. 将 `v-html` 用于属性或事件上下文；
3. 滥用 `v-html` 渲染 Markdown 输出但未经过安全转换。

## Low risk

### 低风险评级场景

#### 1. 富文本仅来源于受控后台
- 攻击面小，可暂列低风险。

#### 2. 页面部署在内网或受限环境
- 仍建议净化，但优先级较低。

#### 3. 计划引入统一富文本渲染组件
- 有明确时间表，可暂降级并跟踪。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 受控来源 | 攻击面小 | 中 |
| 内网环境 | 影响有限 | 低 |
| 改造计划明确 | 可暂缓 | 低 |
