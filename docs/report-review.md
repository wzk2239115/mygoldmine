# 已有审计报告预审（5 个仓库）

- 时间：2026-10-27
- 方法：5 个并行 review agent，各自用 jq 提取 findings/severity/证据/重复项，不重跑扫描。
- 说明：这是**报告质量预审**，不是漏洞验证；结论仍需 verify-agent 逐条确认。

## 总览

| 项目 | Findings | 严重度 | 质量 | 建议优先验证 |
|---|---:|---|---:|---|
| codex | 51 | Critical 2 / High 18 / Medium 26 / Low 5 | 3/5 | F-01, F-02, F-32 |
| deepseek-harness | 92 | High 9 / Medium 36 / Low 47 | 3.5/5 | VULN-005, VULN-003, VULN-004 |
| sglang | 342 | Critical 21 / High 102 / Medium 116 / Low 77 / Info 25 | 3/5 | VULN-002, VULN-004, VULN-008 |
| verl | 96 | High 16 / Medium 52 / Low 23 / Info 5 | 3.5/5 | FIND-001, AC-001, AC-002 |
| vllm | 20 | Critical 1 / High 8 / Medium 6 / Low 4 / Info 1 | 3/5 | F-01, F-04, F-05 |

## codex

- 优先：F-01（默认认证为空 + 非回环监听）、F-02/F-25（app-server 无方法级授权）、F-32（includeToken 泄露 OAuth token）、F-06（Python 审批默认 accept）、F-33（headers helper 经 sh -c）。
- 问题：F-36 与 F-01 重复；F-25 覆盖 F-02；F-05/F-33 与 F-04 重叠；F-42/F-35、F-34/F-45 重叠。F-08/11/20/21/28/30/38/47/50/32 证据偏薄。
- 完整性：JSON finding 缺 verification/status；F-01 与 F-36 定级矛盾；无 CVSS/复测；未构建镜像。

## deepseek-harness

- 优先：VULN-005（.env → Git 配置 RCE，有验证产物）、VULN-003（`/api/file` 任意宿主读）、VULN-004（默认上传全量会话）、VULN-001（工作区外读取，001/002 同根因）、VULN-006（无界循环 DoS）。
- 问题：001/002 同 `locateFile`；012/017 同为工具明文落盘；008/061 同为无签名/MAC；038/039 与 006 重叠；021、084/085、090 证据薄。
- 完整性：JSON `title` 92/92 为 null（MD 有标题）；CVE 全部 unverified；MD 正文与附录重复。

## sglang

- 优先：VULN-002（`/server_info` 明文 api_key）、VULN-006（无密钥 fail-open，43 个管理端点匿名）、VULN-004（`update_weights_from_disk` → `torch.load(weights_only=False)`）、VULN-008（未认证 `POST /workers`）。
- 重复：语义簇严重——server_info 17 条、torch.load 18 条、flush_cache 13 条、/workers 5 条；`source_id` 复用混乱。
- 问题：49 条 evidence 为空（含 VULN-001/007/025）；VULN-025 标题/描述不一致；CVSS 全 null；162/185 依赖未 vendored 外部 crate。
- 结论：342 条不能直接当 342 个漏洞，先按语义簇去重。

## verl

- 优先：AC-001/ROUTE-01/WEB-01（同一未认证通配反代）、FIND-001（训练进程 exec 模型生成代码）、AC-002/ROUTE-02（worker 无 api_key）、CI-01（exec_module 任意文件）、ML-01（硬编码 trust_remote_code=True）。
- 重复：AC-001=ROUTE-01=WEB-01、AC-002=WEB-03 属同源；DEP-01/02 供应链卫生评 high 偏高；ROUTE-02 标 unverified。
- 自动验证复核：CI-01 confirmed 合理；AC-001/CI-02/DEP-01 inconclusive 合理；AC-002 的 rejected 不合理（“缺失 api_key”按模式未命中导致假阴性）。

## vllm

- 优先：F-01（条件 RCE，需多个开关）、F-02（/invocations 绕过 api-key）、F-04（默认媒体 SSRF）、F-05（重定向绕过 allowlist）、F-09（LoRA 路径无白名单）。
- 重复：F-03/04/05/13 同属 SSRF 链；F-06/07/08 同属未授权运维面；F-20 是聚合 info。
- 完整性：summary unified_findings=22 与 20 不符；chains 缺 title/finding_ids；F-01 证据仅 2 处且 critical 偏高；F-07 降级未同步标题。

## 建议的验证顺序

1. vllm：F-01, F-04, F-05（环境需 `--mode auto` 先构建；F-01 可能需要 dev/RL 配置）
2. verl：FIND-001, AC-001, AC-002（已有 `mygoldmine/env:verl-test`，partial）
3. codex：F-01, F-02, F-32（需构建 rust+node 环境）
4. deepseek-harness：VULN-005, VULN-003, VULN-004（需构建 node 环境）
5. sglang：先按语义簇去重，再验证 VULN-002/VULN-004/VULN-008
