---
name: vtr-scanner
description: 专业靶场扫描技能：具备主流语言/框架的靶场扫描能力，可以快速发现项目中的靶场类型。
---

# 概述与边界

- 聚焦靶场扫描：发现项目中的细分靶场类型，包括Benchmark靶场和CTF靶场。
- 不做：漏洞扫描、漏洞利用、漏洞利用链推导。

**重要：靶场中包含多种相同类型或不同类型的漏洞，每一个漏洞都需要独立分析，不能遗漏。**

# 靶场项目分类规则
## Benchmark靶场

**识别方法：**以基准/教材形式提供标准化漏洞集，通常包含官方文档或预置账号，案例固定且覆盖常见 CWE/CVE（如 WebGoat、DVWA、Juice Shop、bWAPP、Mutillidae 等）。

**识别步骤：**
1) 目录/文件特征：优先扫描 `challenges|ctf|labs|vulns|levels|missions|quests` 目录，关注文件名含 `flag|submit|score|judge|check` 的脚本/接口。
2) 题目信息提取：从题目 README/markdown、`config.(yml|json)`、题库元数据（title/difficulty/tags/category）、文件夹/文件名称提取题目名称与分类。

## CTF靶场

**识别方法：**以夺旗题库形式提供多题目/多关卡，存在 flag/score/submit 入口，关卡独立且可能包含自定义或混合漏洞。

**识别步骤：**
1) 目录/文件特征：优先扫描 `challenges|ctf|labs|vulns|levels|missions|quests` 目录，关注文件名含 `flag|solve|writeup|answer` 的题目代码/描述。
2) 题目信息提取：从题目 README/markdown、`config.(yml|json)`、题库元数据（title/difficulty/tags/category）、文件夹/文件名称提取题目名称与分类。

# 输出要求

1. 首先按照题目类型分类
2. 如果同一种题目类型题目数量超过3个时，题目信息按照题目编号或先后顺序输出到多个文件，每个文件中包含不超过3个题目信息

**产物输出路径规则为：**
    .workspace/tasks/{TASK_ID}/vtr-scanner-result-{category}-01.md
    .workspace/tasks/{TASK_ID}/vtr-scanner-result-{category}-02.md
    ...
    .workspace/tasks/{TASK_ID}/vtr-scanner-result-{category}-{NN}.md

**文档内容格式为：**
```markdown
名称：{题目名称}
类型：{题目类型}
文件或文件夹路径：{文件或文件夹路径}
行号：{行号} (可选， 若一个文件中包含多个题目，则需要注明行号)
```

**下游任务生成规则（总结输出）：**
- 每个md文件生成一个下游审计任务，根据题目类型选择技能。示例:
{
    "tasks": [
        {
            "artifact": ".workspace/tasks/{TASK_ID}/vtr-scanner-result-{category}-01.md",
            "skill": "sql-injection-analyzer"
        },
        {
            "artifact": ".workspace/tasks/{TASK_ID}/vtr-scanner-result-{category}-02.md",
            "skill": "xss-analyzer"
        },
        ...
    ],
    "warnings": [
        "**deep analysis of each task is required, never skip any task.**"
    ]
}
    
4. **允许的 Skill 列表（仅限以下技能）：**

| 技能 | 描述 |
|------|------|
| `command-injection-analyzer` | 分析命令注入漏洞。 |
| `code-injection-analyzer` | 分析代码注入漏洞。 |
| `csrf-analyzer` | 分析CSRF漏洞。 |
| `insecure-file-uploads-analyzer` | 分析文件上传漏洞。 |
| `http-header-injection-analyzer` | 分析HTTP头注入漏洞。 |
| `idor-analyzer` | 分析IDOR漏洞。 |
| `ldap-injection-analyzer` | 分析LDAP注入漏洞。 |
| `open-redirect-analyzer` | 分析开放重定向漏洞。 |
| `path-traversal-analyzer` | 分析路径遍历漏洞。 |
| `lfi-analyzer` | 分析本地文件包含漏洞。 |
| `rfi-analyzer` | 分析远程文件包含漏洞。 |
| `sql-injection-analyzer` | 分析SQL注入漏洞。 |
| `ssrf-analyzer` | 分析SSRF漏洞。 |
| `xxe-analyzer` | 分析XXE漏洞。 |
| `xss-analyzer` | 分析XSS漏洞。 |

**技能推荐约束（必须遵守）：**
- ⛔ **禁止推荐列表之外的任何技能**，列表外的技能与当前任务无关，推荐会导致任务失败
- ⚠️ 如果题目类型无法匹配到上述任何技能，应在 `warnings` 字段中说明原因，而非推荐不存在的技能
- ✅ 如果一个题目需要综合使用多个技能，skill 字段填写多个技能，以逗号分隔，如 `skill: "sql-injection-analyzer,xss-analyzer"`