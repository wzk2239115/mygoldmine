# 生成的视觉素材

这些是 `project-cartographer` 技能生成的 AI 插图，不是漏洞证据。

| 文件 | 用途 | 模型 | 说明 |
|---|---|---|---|
| `open-sandbox-cover.webp` | OpenSandbox 报告封面 | `openai/gpt-image-2` | 证据档案与纸面风格，无文字 |
| `open-sandbox-cover.json` | 生成元数据 | — | 提示词、尺寸和用量 |
| `open-sandbox-attack-execd-001.webp` | 远程代码执行攻击场景插图 | `openai/gpt-image-2` | 智能体场景导演设计分镜，左侧输入、右侧 execd 执行 |
| `open-sandbox-attack-execd-001.director.json` | 智能体分镜与提示词 | — | `attack-scene-director` 产物 |
| `open-sandbox-attack-cp-001.webp` | 认证绕过场景插图 | `openai/gpt-image-2` | 代理路径绕过 API 密钥，无文字 |

规则：

- 插图用于封面、章节页、案例卡片顶部和攻击场景叙事。
- 架构图、攻击路径、覆盖树、攻击者与受害者步骤一律由代码生成 SVG。
- 提示词不包含源码、密钥和完整报告。
- 生成图不冒充截图或漏洞证据。
