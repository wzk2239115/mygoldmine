---
name: model-loading-analyzer
description: 专业的审计工作流程，通过静态代码分析识别和验证模型加载链路中的不可信代码执行漏洞；重点关注 HuggingFace transformers / vLLM / SGLang / verl 等推理框架在加载模型配置、tokenizer、自定义模型类时是否信任模型仓库内的远程代码，包括 trust_remote_code=True、config.json 的 auto_map、get_class_from_dynamic_module、动态 import 与 torch.load 权重反序列化；覆盖用户可控 model 参数、CLI --model、环境变量和本地配置等 source，给出可核实的代码位置与误报排除规则。
---

# 模型加载信任边界分析器

分析 AI 推理/训练项目在“模型 ID 或模型目录 → 配置/tokenizer/权重 → 动态模块/反序列化”这条链路上，是否把不可信仓库内容当成可执行代码。适用缺口：G01（模型加载信任边界）、G02 的 HuggingFace 加载链、G14 的 eval + 反序列化组合。

## 适用场景

- 项目使用 `transformers`、`vllm`、`sglang`、`verl`、`peft`、`accelerate` 或自研权重加载器。
- 代码中出现 `from_pretrained`、`AutoConfig`、`AutoModel`、`AutoTokenizer`、`get_class_from_dynamic_module`、`torch.load`。
- 存在用户可控的 `model` / `model_path` / `tokenizer_path` / `--model` / `LORA_PATH` 等输入。
- 项目提供模型下载、模型热更新、LoRA 加载、权重合并等端点。

**Early exit**：项目完全不加载外部模型（无 `from_pretrained`、无 `torch.load`、无动态 import），或模型路径在编译期硬编码且 `trust_remote_code` 恒为 `False`，可缩减为只检查 `torch.load(weights_only=False)`。

## Source / Sink

| 类别 | 具体位置 |
|------|----------|
| Source | HTTP 请求 `model` 字段、CLI `--model`、`--tokenizer`、`--load-format`、环境变量 `HF_HOME` / `TRUST_REMOTE_CODE`、`config.json` 中的 `auto_map` / `architectures`、LoRA/权重上传接口 |
| Sink | `AutoConfig.from_pretrained(..., trust_remote_code=True)`、`AutoModel*.from_pretrained`、`AutoTokenizer.from_pretrained`、`get_class_from_dynamic_module`、`transformers.dynamic_module_utils`、`importlib.import_module`、`torch.load(..., weights_only=False)`、`torch.jit.load`、`numpy.load(..., allow_pickle=True)` |
| 安全对照 | `trust_remote_code=False`、`safetensors.torch.load_file`、`torch.load(..., weights_only=True)`、固定 `revision` 到受信 commit |

## 检测步骤

1. **定位加载入口**：搜索 `from_pretrained`、`get_config`、`get_tokenizer`、`load_model`、`load_weights`、`model_merger`，记录模型 ID/目录来自哪里。
2. **回溯模型来源**：模型 ID 是否来自请求体、查询参数、上传文件、环境变量或仓库内配置；是否能由低权限用户指定任意 HuggingFace repo 或本地路径。
3. **检查远程代码开关**：`trust_remote_code` 的默认值、显式赋值、是否被 `kwargs` 覆盖；注意 `trust_remote_code |= kwargs.get(...)` 这类合并写法。
4. **检查配置驱动的动态模块**：`config.json` 的 `auto_map` 是否被读取；`architectures` / `model_type` 是否映射到 `get_class_from_dynamic_module` 或 `importlib.import_module`。
5. **检查版本固定**：`revision` / `code_revision` 是否为空或 `main`；是否校验模型仓库 owner/commit；是否只允许本地受信目录或白名单。
6. **检查权重反序列化**：`torch.load` 的 `weights_only` 是否为 `True`；旧版本默认 `False` 时按危险处理；`safetensors` 不报。
7. **串联判定**：只有“不可信模型源 + 远程代码/危险反序列化”同时成立时才给 High；仅有 sink 但模型源固定受信时降级为 Info/Medium。

## 判定矩阵

| 条件 | 结论 |
|------|------|
| 用户可控模型 ID + `trust_remote_code=True` | High：可执行模型仓库内任意 Python 代码 |
| 用户可控模型 ID + `auto_map` 且 `trust_remote_code` 由请求/配置开启 | High |
| 用户可控模型 ID + `torch.load(weights_only=False)` | High（pickle 反序列化 RCE） |
| `torch.load` 未显式传 `weights_only` 且模型文件可被外部替换 | Medium：取决于 torch 版本默认值，需人工确认 |
| 模型 ID 固定为官方仓库但 `revision` 未固定 | Low：供应链/仓库劫持风险 |
| `trust_remote_code=False` 或 `weights_only=True` | 不报告；若仍加载自定义配置类，仅在报告中说明 |

## 真实代码位置（已核对，2026-10-27）

| 项目 / commit | 位置 | 关键代码 | 用途 |
|---------------|------|----------|------|
| vLLM `20bf65ad3338` | `vllm/transformers_utils/config.py:344-353` | `HFConfigParser.parse(..., trust_remote_code, ...)`；`trust_remote_code \|= kwargs.get("trust_remote_code", False)` | 配置解析入口，开关可被 kwargs 合并打开 |
| vLLM `20bf65ad3338` | `vllm/transformers_utils/config.py:418-447` | `config_class.from_pretrained(..., trust_remote_code=trust_remote_code, ...)`、`AutoConfig.from_pretrained(...)` | 远程配置类/动态模块加载 sink |
| vLLM `20bf65ad3338` | `vllm/model_executor/models/nemotron_vl.py:174-177` | `AutoModel.from_config(config.vision_config, trust_remote_code=self.model_config.trust_remote_code)` | 模型执行期继续传播远程代码开关 |
| SGLang `3a62cdfb3d0b` | `python/sglang/srt/utils/hf_transformers/tokenizer.py:89-117` | `if tok_cls is None and kwargs.get("trust_remote_code"):` → `auto_map.get("AutoTokenizer")` → `get_class_from_dynamic_module(...)` | tokenizer 的 auto_map 动态模块链 |
| SGLang `3a62cdfb3d0b` | `python/sglang/srt/utils/hf_transformers/tokenizer.py:470-478` | `def get_tokenizer(..., trust_remote_code: bool = False, ...)` | tokenizer 加载入口默认值审计点 |
| SGLang `3a62cdfb3d0b` | `python/sglang/srt/utils/hf_transformers/config.py:220-232` | `AutoConfig.from_pretrained(model, trust_remote_code=trust_remote_code, revision=revision, ...)` | 配置加载 sink |
| verl `174888fcf4b6` | `verl/model_merger/fsdp_model_merger.py:108-112` | `torch.load(..., map_location="cpu", weights_only=False)` | 分片合并时的权重反序列化 |
| verl `174888fcf4b6` | `verl/model_merger/fsdp_model_merger.py:174` | `state_dict = torch.load(model_path, ..., weights_only=False)` | 多 rank 权重加载 |

复核命令：

```bash
targets/vllm $ grep -n "trust_remote_code" vllm/transformers_utils/config.py | sed -n '1,8p'
targets/sglang $ grep -n "auto_map\|get_class_from_dynamic_module" python/sglang/srt/utils/hf_transformers/tokenizer.py
targets/verl $ grep -n "weights_only" verl/model_merger/fsdp_model_merger.py
```

## 误报排除

- `from_pretrained` 未开启 `trust_remote_code` 且模型仓库为官方硬编码：不报。
- `torch.load(..., weights_only=True)`、`safetensors.torch.load_file`、`safetensors.torch.load_model`：不报。
- 只加载本地目录且该目录由 root/安装包提供、普通用户不可写：降级为 Info。
- `revision` / `code_revision` 固定到受信 commit，且仓库 owner 受控：降级。
- 仅出现 `architectures` 字段但没有 `auto_map` / 动态 import：不单独报告，保留为上下文。
- 与 `insecure-deserialization-analyzer` 重叠时，本 skill 只报告“模型/权重加载链”，普通 `pickle.loads` 交给后者。

## 输出格式

```json
{
  "skill": "model-loading-analyzer",
  "findings": [
    {
      "rule": "ML-REMOTE-CODE",
      "severity": "high",
      "confidence": "high",
      "file": "vllm/transformers_utils/config.py",
      "line": 445,
      "source": "request model id",
      "sink": "AutoConfig.from_pretrained(trust_remote_code=True)",
      "evidence": "trust_remote_code=trust_remote_code",
      "why": "模型 ID 可由请求指定，远程配置类会被执行",
      "fix": "默认 trust_remote_code=False；固定 revision；只允许受信仓库/本地目录白名单"
    }
  ]
}
```

Markdown 报告按 `severity` 排序，每条包含：Source、Sink、可达路径、影响、修复建议、误报排除说明。

## 快速扫描

```bash
python3 .claude/skills/model-loading-analyzer/quick-scan.py targets/vllm targets/sglang
python3 .claude/skills/model-loading-analyzer/quick-scan.py --self-test
```

`quick-scan.py` 只使用 Python 标准库（`ast` + `re`），不依赖 tree-sitter；输出 JSON，退出码 0 表示扫描完成，2 表示参数/IO 错误。规则数据位于 `patterns/transformers.json`。

## 修复建议

- 默认 `trust_remote_code=False`，仅对白名单仓库显式开启。
- 固定 `revision` / `code_revision`，并在下载后校验 commit。
- 禁止把请求里的 `model` 直接拼成本地路径；使用模型注册表。
- 权重统一转为 `safetensors`；必须用 `torch.load` 时强制 `weights_only=True`。
- 对 `auto_map` / `architectures` 做允许列表校验，不直接进入 `get_class_from_dynamic_module`。
