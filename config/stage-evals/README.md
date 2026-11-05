# 阶段技能的独立评估套件

本目录仅放维护者编写并审查的评估命令。智能体只能提交候选，不能通过 MCP 设置评估套件、发布技能或改变验收门槛。

实际配置命名为 `<stage>.json`，例如 `environment.json`。结构示例：

```json
{
  "stage": "environment",
  "metrics": {"capability_checks_passed": "higher", "elapsed_seconds": "lower"},
  "cases": [
    {"id": "verl-arm64-cpu", "project": "verl", "argv": ["python3", "path/to/reviewed_environment_benchmark.py"]}
  ]
}
```

示例不是可运行的默认评估器。评估命令必须在同一固定任务、源码版本、平台、模型与隔离条件下实际执行该阶段，并执行独立验收。评估器向环境变量 `STAGE_EVAL_OUTPUT` 指定的文件写 JSON，至少有布尔字段 `valid` 和配置的数值指标。`elapsed_seconds` 由控制器实测，不信任命令自报耗时。两次运行通过 `STAGE_SKILL_BASELINE` 读取固定的现行版本指针；候选运行额外设置 `STAGE_SKILL_OVERRIDE`，仅替换候选对应阶段与层级，其他技能保持一致。每组用例必须使用独立输出目录，不能复用上一组的交付物来充当本次结果。

指标应覆盖所声明的改进目标与不能退化的能力。环境至少验收源码版本、必要工具和规定的 CPU 检查；审计覆盖率、误报率必须由有独立标签的任务和验证结果计算，不能以候选条数、报告篇幅或智能体自评分代替。场景设计检查来源绑定、产物完整性与表达准确性；验证与审核检查已知样例的判断及证据来源；经验学习检查适用范围、来源和保留用例的结果。

每个用例默认重复 3 次，交替执行两组以减小缓存与顺序偏差；可配置 `repetitions` 为 3—10。默认要求所有用例的独立验收均通过、所有指标不退化且至少一项严格改善。通用技能还需要两个不同的其他仓库作为保留验证项目，提炼来源仓库不计入。没有套件、标签或充分证据时保留候选，不发布。

命令：

```bash
python3 scripts/stages/skill_bank.py evaluate --candidate <候选编号> --suite config/stage-evals/environment.json
python3 scripts/stages/skill_bank.py publish --evaluation <通过的评估编号>
python3 scripts/stages/skill_bank.py rollback --publication <发布记录文件名，去掉 .json>
```

评估日志、结果、候选正文及发布记录在 `rsi/stage-skills/`，不进入代码提交。评估命令是可信执行边界，不应让候选内容自行定义命令或结果判定。

当前仓库没有配置任何阶段评估套件。第 08 阶段产生的 SkillOpt 候选会保留，并在 `rsi/stage-learning-evaluation.json` 或 `skill_bank.py advance` 的记录中显示 `missing_evaluation_suite`；没有可信套件时不会自动发布。测试中的临时评估命令只验证接线，不代表阶段能力已经提高。
