# TypeScript - 构造命令字符串注入

## Details

**审计等级：L3（逐行读）+ L4（跨模块追踪）**

### 代码示例
```typescript
import { exec } from 'child_process';
// 危险：直接拼接用户输入
exec(`git clone ${userInput}`, callback);
exec('ffmpeg -i ' + req.body.file, callback);
```

### 快速定位核心操作
- 关键函数：`exec()`、`execSync()`
- 导入路径：`child_process` 模块
- 特征模式：命令字符串中包含变量拼接（`${}`、`+`、模板字符串）
- 搜索策略：`exec.*\$\{` 或 `exec.*\+.*req\.|params\.|query\.`

### 快速定位保护机制
- ✓ 使用 `execFile()` 替代 `exec()`（参数数组化）
- ✓ 白名单校验：`allowedCommands.includes()` 或正则 `^[a-zA-Z0-9_-]+$`
- ✓ 使用专用库：`shell-quote`、`shell-escape` 转义
- ✗ 黑名单过滤：`replace(/[;&|]/g, '')` **不可靠**

## Classify

### 确认为漏洞
- 外部输入（`req.*`、`ctx.*`、环境变量）直接拼接到命令字符串
- 无任何过滤或仅有黑名单过滤
- 命令包含 shell 元字符操作空间（`;`、`|`、`&`、`$`、`` ` ``）

### 判定为误报
- 输入已通过严格白名单（枚举值或 `^[a-z0-9]+$`）
- 使用 `execFile()` 且参数以数组形式传递
- 输入源为常量、配置文件硬编码值

### 代码异味
- 黑名单过滤不完整（仅过滤部分特殊字符）
- 过滤逻辑与执行点距离过远（跨多个函数传递）
- 使用 `JSON.stringify()` 等非专业转义方法

## Low risk

- **受限执行环境**：Docker 容器 + 无特权模式 + 无敏感挂载
- **输入长度限制**：严格限制为 1-3 个字符（如文件扩展名 `.jpg`）
- **非关键功能**：测试环境专用接口 + 明确标注 dev-only
- **输入类型受限**：经过 TypeScript 严格类型校验且为枚举类型
- **后置沙箱**：命令执行在 VM2、isolated-vm 等沙箱中
- **用户隔离**：命令执行用户为低权限账户 + 无sudo权限 + 无敏感文件访问权