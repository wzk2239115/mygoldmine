# 临时指令

正常运行，按 `TODOLIST.md` 与 `.agent/tasks.json` 的优先级执行。

运行中人工追加的指令写在这里，下一轮优先处理。当前无额外指令。

## 补充约束

- 先完成 Phase 1（T01-T05），再进入 Docker（T06-T10），最后并行编排（T11-T15）。
- 不确定的漏洞编号宁可标 `unverified`，不要编造。
- 不允许在实现阶段启动真实 6h 挖矿；T10/T12 只做 dry-run 或 sleep 假目标。
- 每轮结束前必须提交本任务改动；不得把 `targets/`、`runs/`、`logs/` 提交。

## 工具降级

- 若 `web-search-prime` 返回 429，改用以下方式取证，不要卡住：
  - GitHub Advisory：`https://api.github.com/advisories?ecosystem=pip&affects=vllm`
  - NVD API：`https://services.nvd.nist.gov/rest/json/cves/2.0?keywordSearch=vllm`
  - 目标仓库的 `git log --grep=security`、`SECURITY.md`、release notes、已合并的安全 PR。
- 所有外部请求都要带超时（`curl --max-time 20`），失败记录后继续，不要重试到死。
