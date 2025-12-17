# Context 长度限制 - 实现说明

## 功能简介

已为不安全反序列化 Sink 检测工具实现了 **Context 长度限制**功能。所有输出报告中的 `context` 字段现在都被限制在 **100 字符**以内。

## 实现细节

### 修改位置

1. **core/scanner.py** - Sink 类
   - 添加 `MAX_CONTEXT_LENGTH = 100` 常量
   - 添加 `_truncate_context()` 方法来截断长文本
   - 在 `to_dict()` 方法中应用截断

2. **reports/json_reporter.py** - SARIF 报告生成
   - 在生成 SARIF 报告时也应用 context 截断

### 截断规则

- 若 context 超过 100 字符，则截断至 97 字符并在末尾添加 `...`
- 若 context 不超过 100 字符，则保持原样

示例：
```
原始:  config = yaml.load(some_very_long_configuration_data_that_exceeds_one_hundred_characters_and_should_be_truncated)
截断后: config = yaml.load(some_very_long_configuration_data_that_exceeds_one_hundred_characters_and_shou...
长度:  100
```

## 应用范围

- ✅ JSON 报告 (`--output json`)
- ✅ SARIF 报告 (`--output sarif`)
- ✅ 命令行直接输出
- ✅ 文件输出报告

## 测试结果

### 测试 1: 短 Context（不截断）
```
完整 | 长度: 88 | new ObjectMapper().readValue(result.getResponse().getContentAsString(), Object[].class);
完整 | 长度: 96 | nodes = new ObjectMapper().readValue(result.getResponse().getContentAsString(), Object[].class);
```

### 测试 2: 长 Context（截断）
```
截断 | 长度: 100 | result = pickle.loads(very_long_serialized_data_from_user_input_that_should_definitely_be_truncat...
截断 | 长度: 100 | config = yaml.load(some_very_long_configuration_data_that_exceeds_one_hundred_characters_and_shou...
```

### 测试 3: WebGoat 实际扫描
```
总 Sinks: 14
完整 Context: 14
截断 Context: 0
最长 Context: 96 字符
所有长度 <= 100: ✓ True
```

## 使用示例

### 生成带有长度限制的 JSON 报告

```bash
bash scripts/scan.sh ~/WebGoat/ --lang java --report findings.json
```

报告中所有 `context` 字段的长度都将被限制在 100 字符以内。

### 查看截断的 Context

```bash
python3 << 'EOF'
import json
with open('findings.json', 'r') as f:
    data = json.load(f)

for sink in data['sinks']:
    ctx = sink['context']
    is_truncated = "[截断]" if ctx.endswith('...') else "[完整]"
    print(f"{is_truncated} {len(ctx):3d} | {ctx}")
EOF
```

## 配置

可通过修改 `core/scanner.py` 中的 `MAX_CONTEXT_LENGTH` 常量来改变限制长度：

```python
class Sink:
    MAX_CONTEXT_LENGTH = 100  # 修改此值
```

## 优势

1. **输出简洁**: Context 字段长度统一，提高报告可读性
2. **一致性**: 所有输出格式（JSON、SARIF、CLI）都应用相同限制
3. **易于处理**: 固定的最大长度便于数据处理和显示
4. **保留关键信息**: 前 97 个字符通常包含足够的信息来识别问题

## 向后兼容性

- ✅ 现有脚本无需修改
- ✅ 自动应用于所有现存报告
- ✅ 不影响 sink 检测逻辑

## 状态

✅ **已实现并测试完毕**

所有报告格式都已应用 context 长度限制。

---

实现日期: 2025年11月30日
