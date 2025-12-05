---
allowed-tools: Bash, Read, Write, Edit, Grep, Glob, AskUserQuestion, TodoWrite
description: Analyze errors, stack traces, and find root causes
argument-hint: [--file <log-path>] | <error-description>
---


# 调试分析

> 分析错误日志、堆栈跟踪，定位问题根因

## 任务

帮助分析和调试程序错误，找出根本原因并提供修复建议。

## 输入方式

1. **粘贴错误信息**：直接粘贴错误日志或堆栈跟踪
2. **指定日志文件**：提供日志文件路径
3. **描述问题现象**：描述遇到的问题

## 执行步骤

### 1. 收集错误信息

- 完整的错误消息
- 堆栈跟踪（Stack Trace）
- 相关日志上下文
- 触发条件和复现步骤

### 2. 分析错误类型

| 类型 | 特征 | 常见原因 |
|------|------|----------|
| SyntaxError | 语法错误 | 拼写、缺少符号 |
| TypeError | 类型错误 | 类型不匹配、None 访问 |
| ImportError | 导入错误 | 模块不存在、循环导入 |
| KeyError/IndexError | 访问错误 | 键/索引不存在 |
| ConnectionError | 连接错误 | 网络、数据库连接 |
| TimeoutError | 超时错误 | 请求超时、死锁 |
| PermissionError | 权限错误 | 文件/资源权限 |

### 3. 定位问题

- 解析堆栈跟踪，找到出错位置
- 读取相关代码文件
- 分析上下文和数据流
- 检查相关配置

### 4. 根因分析

使用 5 Why 分析法：
1. 直接原因是什么？
2. 为什么会发生？
3. 根本原因是什么？
4. 如何预防？

### 5. 提供解决方案

输出格式：

```markdown
## 错误摘要
[一句话描述问题]

## 根本原因
[详细解释为什么会发生]

## 问题位置
- 文件: `path/to/file.py`
- 行号: 123
- 函数: `function_name()`

## 修复方案

### 方案 1（推荐）
[具体修复代码或步骤]

### 方案 2（备选）
[备选方案]

## 预防措施
- [如何避免类似问题]

## 相关资源
- [相关文档或链接]
```

## 常用调试命令

```bash
# Python 调试
python -m pdb script.py
pytest --pdb  # 测试失败时进入调试

# Node.js 调试
node --inspect script.js
npm run test -- --inspect-brk

# 日志分析
tail -f /var/log/app.log | grep ERROR
journalctl -u service-name -f
```

## 示例

```
/debug
[粘贴错误堆栈]

/debug --file logs/error.log

/debug 程序启动后 30 秒自动退出
```


------

**最后更新**: 2025-11-30 16:10:35
**维护者**: Documentation Team
**版本**: 1.0.0
