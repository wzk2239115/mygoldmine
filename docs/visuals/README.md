# Generated Visual Assets

这些是 `project-cartographer` skill 生成的 AI 插图，不是漏洞证据。

| 文件 | 用途 | 模型 | 说明 |
|---|---|---|---|
| `open-sandbox-cover.webp` | OpenSandbox 报告封面 | `openai/gpt-image-2` | 证据档案/纸面风格，无文字 |
| `open-sandbox-cover.json` | 生成元数据 | — | prompt、尺寸、usage |
| `open-sandbox-attack-execd-001.webp` | RCE 攻击场景插图 | `openai/gpt-image-2` | agentic scene director 设计分镜，左侧输入、右侧 execd 执行 |
| `open-sandbox-attack-execd-001.director.json` | agent 分镜/提示词 | — | attack-scene-director 产物 |
| `open-sandbox-attack-cp-001.webp` | 认证绕过场景插图 | `openai/gpt-image-2` | 代理路径绕过 API key，无文字 |

规则：

- 插图用于封面、章节页、case card 顶部和攻击场景叙事。
- 架构图、攻击路径、覆盖树、攻击者/受害者步骤一律由代码生成 SVG。
- prompt 不包含源码、密钥、完整报告。
- 生成图不冒充截图或漏洞证据。
