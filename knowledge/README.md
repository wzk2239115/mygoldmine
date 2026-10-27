# Goldmine Knowledge Base

这里积累“怎么审”的知识，而不是“用什么规则扫”。目标是让 Claude Code / LLM 每次审计都从已有经验出发，
而不是从零读代码。

## 目录

```
knowledge/
  project-types/     项目类型威胁模型（agent-harness / inference-engine / training-framework / model-serving）
  projects/          具体项目的入口、信任边界、已知模式、验证配方
  cves/              公开漏洞卡片（根因、触发条件、检测思路、误报）
  cases/             每次审计的 confirmed/rejected 案例
  playbooks/         通用审阅方法（证据优先、可达性、验证）
  false-positives/   误报模式与排除条件
```

> 在挖掘容器内，知识库挂载在 `$MYGOLDMINE_HOME/knowledge`（默认 `/opt/mygoldmine/knowledge`）；
> 在宿主机仓库根目录下就是 `knowledge/`。

## 使用方式

1. `project-profiler` 先产出轻量画像（类型、入口、信任边界、推荐 track）。
2. `infra-analyst` 读取对应 `project-types/` + `projects/` 知识卡，按信任边界并行分析。
3. `hypothesis-critic` 去重、挑战证据、标注 reachability/confidence。
4. `verify-agent` 用环境镜像做最小验证。
5. `knowledge-scribe` 把 confirmed/rejected 写回 `cases/`，必要时更新 `projects/` 与 `false-positives/`。

## 写作规则

- 只写可复用的事实：入口、配置开关、危险 sink、已验证的触发链、排除条件。
- 每条结论尽量带 `file:line` 或命令；没有证据的写成“假设”。
- CVE/编号不确定时标 `unverified`，不要编造。
- 不写可直接武器化的 exploit；只写 benign 验证思路。
- 每个 case 必须区分：`confirmed` / `rejected` / `inconclusive` / `blocked`。
- 发现新事实后更新 `projects/<project>.md`，不要只留在聊天记录里。

## 渐进加载

agent 不应一次读完整个 `knowledge/`。按需加载：

```text
project-profiler 输出 project_types
  → 读 knowledge/project-types/<type>.md
  → 读 knowledge/projects/<project>.md
  → 按 boundary 读 knowledge/playbooks/<topic>.md
  → 需要时读 knowledge/cves/<project>/<cve>.md
```

## Case 模板

```markdown
# <project> / <finding-id> / <date>

- verdict: confirmed|rejected|inconclusive|blocked
- severity: critical|high|medium|low
- reachability: default|opt-in|dev-only|requires-config|unknown
- files: path:line
- root cause: ...
- trigger: ...
- evidence: ...
- verification: command / harness / report
- false-positive notes: ...
```

## 与代码扫描器的关系

`scripts/experimental/infra_surface_index.py` 只作为“目录/入口索引”的可选辅助，默认不参与流程。
它输出的只是线索，不是 finding；真正的判断由 `infra-analyst` 和 `hypothesis-critic` 完成。
