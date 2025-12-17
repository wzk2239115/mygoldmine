# 统一输出限制配置

## 概述

SSRF Sink Detector 现在提供了**统一的全局限制配置**，可以在一个位置统一控制所有扫描的输出大小。

## 全局配置点

在 `scan.sh` 文件的顶部有一个配置区域：

```bash
# ===== GLOBAL CONFIGURATION =====
# Set default output limit (0 = unlimited, use this to limit all scans)
DEFAULT_LIMIT=0
# =================================
```

### 如何使用

修改 `DEFAULT_LIMIT` 的值：

- `DEFAULT_LIMIT=0` - 不限制（默认，显示所有结果）
- `DEFAULT_LIMIT=50` - 所有扫描都限制在前 50 个结果
- `DEFAULT_LIMIT=100` - 所有扫描都限制在前 100 个结果

## 配置示例

### 示例 1：限制所有扫描为 50 个结果

编辑 `scan.sh` 第 8 行：

```bash
DEFAULT_LIMIT=50
```

现在所有扫描都会自动限制：

```bash
bash scan.sh ~/WebGoat/
# 自动限制在前 50 个结果
```

### 示例 2：限制所有扫描为 100 个结果

编辑 `scan.sh` 第 8 行：

```bash
DEFAULT_LIMIT=100
```

### 示例 3：恢复无限制

编辑 `scan.sh` 第 8 行：

```bash
DEFAULT_LIMIT=0
```

## 覆盖全局限制

即使设置了全局默认限制，你仍然可以通过命令行参数覆盖它：

```bash
# 全局设置为 50，但此次扫描显示 20 个结果
bash scan.sh --limit 20 ~/WebGoat/

# 全局设置为 50，但此次扫描显示所有结果
bash scan.sh --limit 0 ~/WebGoat/

# 使用摘要模式（覆盖任何限制，只显示统计）
bash scan.sh --summary ~/WebGoat/
```

## 完整配置位置

```
/home/wangzekai/TOP14/ssrf/scripts/scan.sh
    ↓
第 6-9 行：全局配置区域
    ↓
DEFAULT_LIMIT 变量
```

## 实际应用场景

### 场景 1：处理大型项目

如果经常扫描大型项目（如 WebGoat，267+ 结果），设置：

```bash
DEFAULT_LIMIT=50
```

这样默认只显示前 50 个，防止输出过长。

### 场景 2：开发环境

如果需要查看所有结果用于开发：

```bash
DEFAULT_LIMIT=0
```

### 场景 3：CI/CD 集成

如果在持续集成中使用，设置合理的限制防止日志过长：

```bash
DEFAULT_LIMIT=100
```

## 工作流程

```
用户运行 bash scan.sh ~/code/
    ↓
读取 DEFAULT_LIMIT 配置（第 8 行）
    ↓
如果指定 --limit 参数，则使用参数值（覆盖默认）
    ↓
如果指定 --summary，只显示统计
    ↓
否则使用 DEFAULT_LIMIT 显示结果
```

## 命令优先级

配置优先级从高到低：

1. **--summary flag** - 仅显示统计（最高优先）
2. **--limit N 参数** - 命令行指定的限制
3. **DEFAULT_LIMIT** - 全局默认限制（最低优先）

## 建议的设置

对于大多数使用场景，建议设置：

```bash
DEFAULT_LIMIT=50
```

这样可以：
- 防止输出过长
- 仍允许通过 `--limit 0` 查看所有结果
- 使用 `--summary` 获取快速概览
