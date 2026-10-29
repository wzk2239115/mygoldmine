---
name: project-cartographer
description: 把源码项目、审计覆盖和漏洞证据转成可读的项目地图、覆盖树、攻击路径图和带 image2 插图的审计报告；结构图由数据生成，插图只做叙事层。
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
  project-map.svg
  coverage-tree.svg
  attack-<finding-id>.svg
  scene-<finding-id>.svg
  scene-<finding-id>.webp
  cover.webp
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

`root -> 源码顶层目录 -> 子目录 -> finding`

- 目录宽度表示文件数量
- finding 叶子按 severity 着色
- 证据路径来自 finding 的 `evidence/files/location`，不靠猜

### 审计覆盖树

`root -> 审计阶段 -> finding`

- 阶段来自报告 `coverage.stages`
- 没有 coverage 时使用默认阶段
- 灰色表示报告没有明确覆盖状态

### 攻击路径树

`goal -> entry -> auth/preconditions -> sink -> impact`

- 只为 Critical/High 生成
- 字段来自 finding 的 `preconditions/root_cause/impact/evidence`
- 这是解释图，不是新的漏洞结论

## 攻击场景插图

每个 Critical/High attack tree 会生成一份双栏场景：

```text
攻击者：构造输入 -> 满足前置条件 -> 触发 root cause
受害者：接收输入 -> 进入敏感路径 -> 到达 sink / 产生 impact
中间：信任边界
```

`scene-<finding-id>.svg` 是数据生成的准确步骤图；`scene-<finding-id>.webp` 是 image2 生成的叙事插图。两者都标注“AI 插图，非漏洞证据”。

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

`--all` 为每个 attack 生成插图；`--dry-run` 只写 prompt，不调用 API。插图 prompt 只使用去标识化的攻击类型和双方动作，不发送源码、端点、密钥或完整报告。

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
  --size 1536x1024 \
  --out docs/visuals/<project>-cover.webp \
  --json
```

API：

```text
base: https://api.360.cn/v1
POST /images/generations
```

凭据读取顺序：`IMAGE_API_KEY`、`OPENCODE_360_KEY`、`ANTHROPIC_AUTH_TOKEN`、`ANTHROPIC_API_KEY`、`GLM_API_KEY`、opencode 配置。不要打印或写入密钥。

缓存：按 `model + size + prompt` 哈希存到 `.cache/image2/`。重跑同 prompt 不重复扣费。

## 插图规则

- 只用于封面、章节页、case card 顶部、攻击场景叙事和氛围
- **不用于**架构图、攻击路径节点、覆盖树、代码/证据截图；攻击路径和双方步骤由 SVG 准确生成
- 提示词只使用去标识化攻击类型和双方动作；不得包含源码、端点、密钥、完整报告或可复制的利用细节
- 图里不要生成文字、代码、UI 截图、真实 logo
- 生成后写 WebP，单张控制在几百 KB
- 记录 prompt、model、尺寸、生成时间；在报告里标注“AI 插图，非漏洞证据”
- image2 不可用时回退到 SVG 封面，不阻塞报告

封面提示词骨架：

```text
editorial ink illustration of <project metaphor>, warm paper background,
vermilion accent, high contrast, subtle paper grain, no text, no logos,
no code, no screenshots, centered subject, generous clean space for title
```

## 报告结构

```text
1. 一页项目地图
2. 一页信任边界
3. 一页覆盖树
4. Top findings case cards
5. 证据附录
```

每张 case card：

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
- `render_diagrams.py` 可独立生成 SVG 和插图报告
- UI 的 Map 视图读取 `GET /api/visual/:project/:runId`
- 报告生成器可在 `audit-report.md` 后追加 `report-illustrated.md` 的链接

## 准确性要求

- 每个图节点都能追溯到源码路径、finding ID 或 coverage stage
- 不把 image2 生成的图当作证据
- 不为了好看编造不存在的服务、端点、调用链
- 树太大时折叠到包/模块层，避免一次渲染上千节点
