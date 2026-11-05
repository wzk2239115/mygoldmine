# mygoldmine 第一轮流程检查（2026-10-30）

项目实际位置：Spark 23 `/home/wzk/mygoldmine`，本机没有同名仓库。

## 理解

框架通过本地源码画像与 Jev 召回，驱动 security-orchestrator 及扫描技能，生成原始 stream-json、可读日志与 JSON/Markdown 报告。后续环境构建、自动复现与人工分诊是独立阶段。网页从 runs 发现正在执行与历史任务，提供运行视图、结构化轨迹和原始日志。

格式完整只代表产物具备所需字段，不代表漏洞成立；复现、误报审查与信任边界判断仍需独立完成。

## 本轮修改

- 修复检查日志写到 `run-meta.json/report-quality.log` 的错误，改为运行目录内的 `report-quality.log`。
- 新任务在写最终元数据之前执行强制格式检查；不合格报告退出 2，保留 timeout/signal/provider 原有错误码。
- JSON 解析、顶层类型、findings/vulnerabilities 数组与条目类型错误会产出诊断，不再当成零漏洞。
- 显式空数组合法。冲突的双 findings 集合不合法。
- 标题必须显式提供，不能借 description/type 补位；空白、数字、布尔值不再充当必填文本。
- 空白证据、空字典等不再通过；兼容现有字符串、路径对象与代码证据。
- Python 与网页质量检查保持一致，加入中文/英文交叉对照测试。
- 运行中的增量报告标为 DRAFT，避免把报告存在等同于最终检查或漏洞验证通过。
- API smoke 使用统计一致性检查，去掉依赖历史 finding 数量和固定项目个案的断言。
- 快速 CI 纳入新的报告回归与网页契约测试。

## 验证

- Python 快速 CI：99 passed, 2 skipped（SkillOpt 未安装的可选适配测试）。
- 网页 Node 测试：8 passed。
- Ruff、Shell 语法、版本库与数据集校验通过。
- Node 22.23.2 下网页 build、API smoke 与 Chromium system test 通过。
- system test 首次遇到页面/测试版本不同步，重新构建后复测通过。
- 没有提交或清理仓库既有的未提交改动。

## 历史轨迹与样本

原备份：`backups/runs-pre-deepseek-20261030T085419Z.tar.zst`，归档列表可读，1446 个条目；SHA256 记录在本目录 `trajectory-backup.sha256`。原 runs 保留，没有删除。
本轮源码修改前后分别保存在 `source-before.tar.gz`、`ui-before.tar.gz`、`LiveRunDrawer.jsx` 与 `source-after.tar.gz`。哈希与质量基线一并保存。

## 当前测试用例

目标已导入 `targets/deepseek-harness`，commit `22ddee3792402c3e70ec5f86a63c3e3e895a2f60`。
现有新一轮运行 `runs/deepseek-harness/20261030T085517Z` 已在本轮核查前启动，预算 3600 秒；保留运行，没有启动重复任务。
该轮采用 mine-only，跳过环境构建与自动验证；当前可见内容为源码审计过程及草稿，不能称为漏洞已复现。
运行中的 Bash 已加载旧版收尾函数；新的强制退出规则适用于之后启动的任务。本轮可用下列命令单独检查最终报告，实时检查快照保存在 `report-quality-live.json`。

```bash
cd /home/wzk/mygoldmine
python3 scripts/mine/check_report.py \
  --report runs/deepseek-harness/20261030T085517Z/audit-report.json \
  --fail-missing --fail-language
PATH=/tmp/mygoldmine-format-venv/bin:$PATH bash scripts/ci/fast.sh
cd ui
PATH=/home/wzk/miniconda3/bin:$PATH npm run build
/home/wzk/miniconda3/bin/node scripts/api-smoke.mjs
/home/wzk/miniconda3/bin/node scripts/system-test.mjs
```

观察台：Spark 23 本地 `http://127.0.0.1:8787/`；Mac 已建立同端口 SSH 转发，点击 DeepSeek Harness 实时任务卡。

下一轮按失败样本补回归、修正产生问题的阶段，再重跑该目标；不直接改写旧报告填充虚构证据。
