---
allowed-tools: Bash, Read, Write, Edit, Grep, Glob, AskUserQuestion, TodoWrite
description: Execute perf-analysis command
argument-hint: 
---


# 性能分析

> 分析代码性能瓶颈，提供优化建议

## 任务

分析代码或系统的性能问题，识别瓶颈并提供优化方案。

## 分析范围

### 1. 代码级性能

- 算法复杂度（时间/空间）
- 循环和迭代效率
- 内存使用和泄漏
- I/O 操作效率
- 数据库查询优化

### 2. 系统级性能

- CPU 使用率
- 内存占用
- 磁盘 I/O
- 网络延迟
- 并发/并行处理

## 执行步骤

### 1. 收集性能数据

**Python**:
```python
# 使用 cProfile
python -m cProfile -s cumtime script.py

# 使用 memory_profiler
python -m memory_profiler script.py

# 使用 line_profiler
kernprof -l -v script.py
```

**Node.js**:
```bash
# 内置性能分析
node --prof script.js
node --prof-process isolate-*.log

# 使用 clinic
clinic doctor -- node script.js
```

**通用**:
```bash
# 时间测量
time command

# 系统资源监控
top / htop
vmstat 1
iostat -x 1
```

### 2. 分析结果

| 指标 | 正常范围 | 需要关注 |
|------|----------|----------|
| CPU 使用率 | < 70% | > 80% |
| 内存使用率 | < 70% | > 85% |
| 响应时间 | < 200ms | > 500ms |
| 数据库查询 | < 100ms | > 500ms |

### 3. 识别瓶颈

常见瓶颈类型：
- **N+1 查询问题**
- **未使用索引**
- **内存泄漏**
- **同步阻塞**
- **过度序列化**
- **重复计算**

### 4. 提供优化建议

输出格式：

```markdown
## 性能摘要
- 总执行时间: X.XXs
- 内存峰值: XXX MB
- 主要瓶颈: [描述]

## 热点分析
| 函数/模块 | 耗时 | 占比 | 调用次数 |
|-----------|------|------|----------|
| func_a | 1.2s | 40% | 1000 |
| func_b | 0.8s | 27% | 500 |

## 优化建议

### 🔴 高优先级
1. [具体优化建议]
   - 当前问题: ...
   - 优化方案: ...
   - 预期收益: ...

### 🟡 中优先级
1. [具体优化建议]

### 🟢 低优先级
1. [具体优化建议]

## 优化代码示例
[提供具体的优化代码]
```

## 常见优化技巧

### 数据库
- 添加索引
- 使用 JOIN 替代多次查询
- 批量操作替代循环
- 使用缓存

### 算法
- 使用合适的数据结构
- 避免嵌套循环
- 使用缓存/记忆化
- 并行处理

### I/O
- 异步操作
- 批量读写
- 使用缓冲
- 压缩传输

## 示例

```
/perf-analysis 分析 src/api/handler.py 的性能

/perf-analysis 数据库查询太慢，分析 SQL 性能

/perf-analysis 内存使用持续增长，排查泄漏
```

------

**最后更新**: 2025-11-30 16:10:35
**维护者**: Documentation Team
**版本**: 1.0.0

