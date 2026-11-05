---
name: supply-chain-diff-audit
description: |
  审查单次 git 提交的 diff，判断是否引入供应链投毒、后门、凭据外泄、
  构建脚本劫持、CI 权限滥用或二进制夹带。用于持续监控仓库更新。
---

# Supply-chain diff audit

目标：回答一个问题——**这次更新是否让仓库更危险，变化是否解释得通。**

## 输入

- `project`
- `sha`
- `parent`
- `diff` 或 diff 文件
- `static_report`（可选，`scripts/watch` 的规则命中）
- `repo_path`（只读）

## 原则

1. **只根据 diff 和仓库上下文判断**，不执行仓库代码，不联网。
2. 先看“这次提交声称做什么”，再看“实际改了什么”；两者不一致是强信号。
3. 区分合法更新和投毒：
   - 合法：锁文件与 `package.json`/`pyproject.toml` 同步、版本号单调、来源是官方 registry。
   - 可疑：锁文件指向新域名/HTTP/git/file、安装脚本新增下载执行、CI 权限突然扩大。
4. 不把“用了 `subprocess`/`eval`”本身当漏洞；要看输入是否可控、是否新增。
5. 没有证据就写 `inconclusive`，不要编造 CVE 或利用链。

## 高信号

- 安装/构建入口新增 `curl|sh`、`wget|sh`、`eval`、base64 解码、`chmod +x`
- `setup.py` / `package.json` / lockfile 新增非官方源、`file:`、`git+http`
- GitHub Actions 新增 `pull_request_target`、`write-all`、secret 直接进入 shell
- 新增二进制、`.node`、`.so`、`.wasm`、可执行位文件
- 新增读取 `~/.ssh`、云凭据、`GITHUB_TOKEN`、`NPM_TOKEN` 并外联
- 大量删除、历史重写、作者身份突变、提交信息与内容不符
- 依赖包名与知名包极其相似（typosquatting）

## 输出

写 `llm-audit.json`：

```json
{
  "sha": "...",
  "verdict": "malicious | suspicious | benign | inconclusive",
  "confidence": "high | medium | low",
  "summary": "一句话结论",
  "findings": [
    {
      "severity": "critical | high | medium | low",
      "path": "...",
      "line": 0,
      "evidence": "diff 中的原文片段",
      "why": "为什么这构成风险",
      "benign_explanation": "如果可能是正常变更，给出解释"
    }
  ],
  "recommended_action": "block | review | monitor | ignore"
}
```

## 判定

- `malicious`：有直接后门/外泄/下载执行证据，且无合理解释。
- `suspicious`：高信号但存在合法解释，需要人工或动态验证。
- `benign`：变化与提交意图一致，来源可解释。
- `inconclusive`：diff 被截断或上下文不足。

绝不把静态命中直接写成“已确认漏洞”；确认需要完整源码路径、动态验证或隔离环境中捕获的随机标记。
