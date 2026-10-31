# 系统语言

系统语言只有一个来源：`config/system.json`。

```json
{
  "language": "zh"
}
```

支持 `zh`（简体中文）和 `en`（English）。也可以用环境变量临时覆盖：

```bash
MYGOLDMINE_LANG=en python3 scripts/redteam/agent.py ...
```

## UI 设置

看板左下角齿轮打开设置，里面有语言选择器（中文 / English）。切换后会：

1. 写入 `config/system.json`；
2. 更新导航、详情页标签和按钮文案；
3. 后续启动的 agent 读取同一份配置。

也可以直接改配置或命令行：

```bash
python3 scripts/config/language.py --set en
python3 scripts/config/language.py --json
python3 scripts/config/language.py --prompt
```

## 提示词注入

所有会生成面向人文本的入口都会把 `scripts/config/language.py --prompt` 拼进提示词：

- `scripts/mine/entrypoint.sh`（审计主编排）
- `scripts/env/build_env_agent.sh`（环境构建）
- `scripts/redteam/build_lab.py`（lab builder）
- `scripts/redteam/judge.py`（judge）
- `scripts/redteam/agent.py`（红队 thought 字段）
- `scripts/watch/watch.py`（diff-auditor）
- `.claude/skills/project-cartographer/scripts/render_attack_scenes_agentic.py`（攻击场景导演）

规则只约束面向人的标题、摘要、影响和修复建议；代码、路径、命令、标识符、CVE 编号和原始证据不改写。英文原始标题保留在 `title_en`。
