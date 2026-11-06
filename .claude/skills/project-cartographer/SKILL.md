---
name: project-cartographer
description: 把源码项目、审计覆盖和漏洞证据转成可读的项目地图、覆盖树、攻击路径图和带 image2 插图的审计报告；所有插图由文生图模型生成；代码仅整理文字、表格和已有模型图片。
---

# Project Cartographer

用于把“一个项目 + 一份 audit-report”变成更容易理解、可追溯的视觉报告。

## 输入

- `project`：`runs/<project>` 名称
- `run-dir`：某次审计目录；省略时取最新成功报告
- 源码目录：优先从 `catalog/manifest.json` 的 `path` 读取，否则 `targets/<project>`
- `audit-report.json`：findings、coverage、severity、evidence
- 可选：`docs/visuals/<slug>-cover.webp` 或 `--cover`

## 输出

```text
<run-dir>/visual/visual-model.json
<run-dir>/visual-rendered/
  scene-<finding-id>.webp
  report-illustrated.md
```

## 快速使用

```bash
python3 .claude/skills/project-cartographer/scripts/build_visual_model.py \
  --project aud-048-opensandbox \
  --run-dir runs/aud-048-opensandbox/20261028T080748Z

python3 .claude/skills/project-cartographer/scripts/render_diagrams.py \
  --model runs/aud-048-opensandbox/20261028T080748Z/visual/visual-model.json \
  --out-dir runs/aud-048-opensandbox/20261028T080748Z/visual-rendered
```

## 三种树

### 项目结构树

`root -> 源码顶层目录 -> 子目录 -> 候选问题`

- 目录结构与文件数量作为文字数据，不绘制结构图
- 候选问题严重度保留为文字字段
- 证据路径来自候选问题的 `evidence/files/location`，不靠猜

### 审计覆盖树

`root -> 审计阶段 -> 候选问题`

- 阶段来自报告 `coverage.stages`
- 没有覆盖信息时使用默认阶段
- 未明确覆盖的范围标为未知，不用颜色图代替记录

### 攻击路径树

`目标 -> 入口 -> 认证/前置条件 -> 危险操作 -> 影响`

- 只为 Critical/High 生成
- 字段来自候选问题的 `preconditions/root_cause/impact/evidence`
- 这是绘图模型的解释输入，不是新的漏洞结论

## 攻击场景插图

每个选定候选使用统一模板 references/technical-explainer-prompt.md 生成横向技术原理图，呈现 3–5 个真实技术实体、信任边界、正常数据流和连续利用路径：

```text
攻击者：构造输入 -> 满足前置条件 -> 触发根因
受害者：接收输入 -> 进入敏感路径 -> 到达危险操作 / 产生影响
中间：信任边界
```

场景图片必须由 image2 文生图模型生成，并标注“AI 插图，非漏洞证据”。攻击步骤用文字和表格说明，不编写 SVG。

```bash
python3 .claude/skills/project-cartographer/scripts/render_diagrams.py \
  --model runs/aud-048-opensandbox/20261028T080748Z/visual/visual-model.json \
  --out-dir runs/aud-048-opensandbox/20261028T080748Z/visual-rendered

python3 .claude/skills/project-cartographer/scripts/render_attack_images.py \
  --model runs/aud-048-opensandbox/20261028T080748Z/visual/visual-model.json \
  --max 3

# 重新渲染报告以把插图写进 report-illustrated.md
python3 .claude/skills/project-cartographer/scripts/render_diagrams.py \
  --model runs/aud-048-opensandbox/20261028T080748Z/visual/visual-model.json \
  --out-dir runs/aud-048-opensandbox/20261028T080748Z/visual-rendered
```

`--all` 为每条攻击路径生成插图；`--dry-run` 只写绘图提示词，不调用 API。绘图提示词只使用去标识化的攻击类型和双方动作，不发送源码、端点、密钥或完整报告。

## 智能体辅助场景设计（推荐）

`attack-scene-director` 智能体会先读候选问题、验证报告和证据源码，提炼技术实体、正常数据流、信任边界和缺失检查，再写绘图提示词、调用 image2，并检查结果、按需修正。

```bash
python3 .claude/skills/project-cartographer/scripts/render_attack_scenes_agentic.py \
  --model runs/aud-048-opensandbox/20261028T080748Z/visual/visual-model.json \
  --max 3 --max-attempts 2
```

产物：

```text
visual/agentic/<finding>/task.json
visual/agentic/<finding>/agent.log
visual/prompts/scene-<finding>.txt
visual-rendered/scene-<finding>.director.json
visual-rendered/scene-<finding>.webp
```

`scene.director.json` 是智能体自己写的分镜和绘图提示词，不是固定模板。需要指定 Claude 模型时用 `--claude-model` 或 `VISUAL_AGENT_MODEL`。

## image2 插图

360 平台已确认存在：

```text
openai/gpt-image-2
openai/gpt-image-2.5-sunburst
microsoft/mai-image-2.6
qwen/qwen-image-3.0
bytedance/doubao-seedream-5.0-pro
```

默认：

```bash
python3 .claude/skills/project-cartographer/scripts/image2.py \
  --model openai/gpt-image-2 \
  --prompt-file prompts/cover.txt \
  --size 1536x864 \
  --out docs/visuals/<project>-cover.webp \
  --json
```

API：

```text
base: https://api.360.cn/v1
POST /images/generations
```

凭据读取顺序：`IMAGE_API_KEY`、`OPENCODE_360_KEY`、`ANTHROPIC_AUTH_TOKEN`、`ANTHROPIC_API_KEY`、`GLM_API_KEY`、opencode 配置。不要打印或写入密钥。

缓存：按模型、尺寸和绘图提示词的哈希存到 `.cache/image2/`。使用相同提示词重新运行时不重复扣费。

## 插图规则

- 用于解释核心漏洞机制，不用于故事插画和氛围装饰
- 所有报告图片必须由文生图模型生成，禁止 SVG、Canvas、Pillow 或其他代码绘图；项目结构、覆盖和攻击步骤可保留文字、表格，不用代码补画。
- 提示词只使用去标识化攻击类型和双方动作；不得包含源码、端点、密钥、完整报告或可复制的利用细节
- 允许少量准确技术标签；禁止长段正文、伪代码、界面截图、真实标志
- 生成后写 WebP，单张控制在几百 KB
- 记录提示词、模型、尺寸、生成时间；在报告里标注“AI 插图，非漏洞证据”
- 文生图模型不可用时记录缺图及失败原因，交付已有文字，不用代码绘图替代。

统一技术原理图模板：

```text
读取 references/technical-explainer-prompt.md 并结合去敏机制摘要。
technical-explainer-v1：1536×864，16:9，浅色背景、深灰组件、蓝色正常流、连续红色利用路径。
图片完全由文生图模型生成；矢量仅指视觉风格，禁止代码绘制 SVG。
```

## 报告结构

```text
1. 一页项目地图
2. 一页信任边界
3. 一页覆盖树
4. 重点候选问题案例卡片
5. 证据附录
```

每张案例卡片：

```text
[封面/插图] [severity] [finding id]
一句话结论
攻击路径图
前置条件
证据位置
验证状态：static / source-confirmed / runtime / blocked
修复建议
```

## 与流水线集成

- `mine_one_docker.sh` 在容器退出且存在 `audit-report.json` 时自动生成 `visual-model.json`
- `VISUAL_RENDER=1` 整理图文报告；`VISUAL_IMAGES=1` 生成插图；`VISUAL_AGENTIC=1` 优先使用场景设计智能体，失败可恢复为 `render_attack_images.py`
- `render_diagrams.py` 仅整理文字和已有模型图片，不生成任何图片
- UI 的地图视图读取 `GET /api/visual/:project/:runId`
- 报告生成器可在 `audit-report.md` 后追加 `report-illustrated.md` 的链接

## 准确性要求

- 每个图节点都能追溯到源码路径、候选问题 ID 或覆盖阶段
- 不把 image2 生成的图当作证据
- 不为了好看编造不存在的服务、端点、调用链
- 树太大时折叠到包/模块层，避免一次渲染上千节点

## 必须遵守：图片来源

所有新图片必须来自 image2 对文生图模型的真实请求或其已验证缓存。禁止手写 SVG、调用代码绘图库生成图片，禁止将 SVG 转成 PNG/WebP 后冒充模型图片。绘图失败保留真实失败，结构和覆盖信息用文字或表格呈现。兼容入口 render_diagrams.py 现在只整理报告，不再绘图。
