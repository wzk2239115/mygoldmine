---
name: bug-report
description: 漏洞报告模板技能：定义标准化的漏洞报告格式，供其他安全分析技能加载使用。
---

## 概述

提供标准化的漏洞报告格式，确保所有安全分析技能输出一致的漏洞文档。

## 文件命名规则

**路径**：`.workspace/findings/BUG-{vuln_type}-{file}-L{line}-{source}-{sink}.md`

**命名组成**：
- `{vuln_type}`：漏洞类型简写
- `{file}`：源文件名（不含路径和扩展名）
- `L{line}`：漏洞代码行号
- `{source}`：污点源函数/参数名
- `{sink}`：危险函数名（Sink 点）

**命名示例**：
```
BUG-sqli-userController-L42-req.body.id-query.md
BUG-xss-homeHandler-L78-req.query.name-res.send.md
BUG-cmdi-fileService-L156-filename-exec.md
BUG-ssrf-apiProxy-L89-req.body.url-fetch.md
```

## 漏洞类型简写

| 漏洞类型 | 简写 |
|----------|------|
| SQL 注入 | `sqli` |
| 命令注入 | `cmdi` |
| 代码注入 | `codei` |
| XSS 跨站脚本 | `xss` |
| SSRF 服务端请求伪造 | `ssrf` |
| XXE XML 外部实体 | `xxe` |
| 路径遍历/文件包含 | `path` |
| 文件上传 | `upload` |
| 开放重定向 | `redirect` |
| CSRF 跨站请求伪造 | `csrf` |
| IDOR 越权访问 | `idor` |
| LDAP 注入 | `ldapi` |
| 敏感信息泄露 | `info` |
| 认证缺陷 | `auth` |
| HTTP 头注入 | `httpi` |
| XPath 注入 | `xpathi` |

## 报告模板

```markdown
# BUG-{vuln_type}-{file}-L{line}-{source}-{sink}

## 基本信息
- **漏洞类型**：{vuln_type_full_name}
- **风险等级**：{severity: 高/中/低}
- **源文件**：{file_path}:{line_number}
- **Source**：{source}（污点源）
- **Sink**：{sink}（危险函数）
- **路由路径**：{route_path}
- **HTTP 方法**：{method}

## 漏洞描述
{detailed_description}

## 漏洞代码
```{language}
// {file_path} L{start_line}-L{end_line}
{line_number}: {vulnerable_code_line}
{line_number}: {vulnerable_code_line}
...
```

## 数据流
```
{source} -> ... -> {sink}
```

**污点传播路径**：
1. `{source}` - {description}
2. `{intermediate}` - {description}
3. `{sink}` - {description}

## 攻击向量
- **入口点**：{entry_point}
- **污点数据**：{taint_source}
- **触发条件**：{trigger_condition}
- **攻击示例**：
```
{attack_payload_example}
```

## 修复建议
{fix_recommendation}

### 修复代码示例
```{language}
// {file_path} L{line_number} 修复后
{fix_code_example}
```

## 参考资料
- {reference_links}
```

## 风险等级定义

| 等级 | 定义 | 示例 |
|------|------|------|
| 高 | 可直接导致数据泄露、系统控制、权限提升 | SQL 注入、命令注入、认证绕过 |
| 中 | 需要特定条件或用户交互才能利用 | XSS、CSRF、信息泄露 |
| 低 | 影响有限，难以直接利用 | 低危配置问题、信息披露 |

## 使用说明

其他安全分析技能（如 `code-security-analyzer`）应加载此技能获取报告格式，确保输出一致性。

**加载方式**：在分析技能中声明依赖 `bug-report` 技能，按照本模板生成漏洞报告。
