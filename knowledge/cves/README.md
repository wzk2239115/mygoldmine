# CVE / 公开漏洞卡片

来源：`research/disclosed-vulns.json`（38 条）与后续公开公告。

## 卡片格式

```markdown
---
project: vllm
cve: CVE-2026-XXXX
cwe: CWE-502
component: vllm/...
fixed_in: 0.x.y
source: https://...
verified: true
---

## 根因
...

## 触发条件
...

## 检测思路
- 入口：
- sink：
- 关键文件/行：
- 默认配置是否可达：

## 误报/边界
...

## 验证
...
```

## 使用

- `infra-analyst` 在分析对应项目时按需读取卡片，不要一次加载全部。
- `knowledge-scribe` 在新 CVE 披露或确认新根因后补卡片。
- 编号不确定时标 `verified: false`，不要编造。
