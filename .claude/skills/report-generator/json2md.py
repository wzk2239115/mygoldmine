#!/usr/bin/env python3
"""
JSON 报告转 Markdown 报告脚本
将 audit-report.json 转换为 audit-report.md
"""

import json
import sys
from datetime import datetime
from pathlib import Path


def load_json_report(json_path: str) -> dict:
    """加载 JSON 报告"""
    with open(json_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def format_severity_badge(severity: str) -> str:
    """格式化严重程度标签"""
    badges = {
        'critical': '🔴 Critical',
        'high': '🟠 High',
        'medium': '🟡 Medium',
        'low': '🟢 Low'
    }
    return badges.get(severity.lower(), severity)


def generate_metadata_section(report: dict) -> str:
    """生成报告元信息章节"""
    metadata = report.get('metadata', {})
    generated_at = report.get('generated_at', datetime.now().isoformat())

    return f"""## 报告元信息

| 项目 | 值 |
|------|-----|
| **项目名称** | {metadata.get('project_name', 'N/A')} |
| **项目路径** | {metadata.get('project_root', 'N/A')} |
| **扫描范围** | {metadata.get('scan_scope', 'N/A')} |
| **扫描文件数** | {metadata.get('total_files_scanned', 0)} |
| **扫描代码行数** | {metadata.get('total_lines_scanned', 0)} |
| **报告生成时间** | {generated_at} |
| **报告版本** | {report.get('report_version', '1.0')} |
"""


def generate_executive_summary(report: dict) -> str:
    """生成执行摘要章节"""
    risk = report.get('risk_assessment', {})
    summary = report.get('summary', {})
    by_severity = summary.get('by_severity', {})

    risk_level = risk.get('overall_risk_level', 'Low')
    risk_score = risk.get('risk_score', 0.0)
    risk_factors = risk.get('risk_factors', [])

    total = summary.get('total_vulnerabilities', 0)
    critical = by_severity.get('critical', 0)
    high = by_severity.get('high', 0)
    medium = by_severity.get('medium', 0)
    low = by_severity.get('low', 0)

    factors_text = '\n'.join([f"- {f}" for f in risk_factors]) if risk_factors else '- 无重大风险因素'

    return f"""## 执行摘要

### 风险评估

| 指标 | 值 |
|------|-----|
| **整体风险级别** | {format_severity_badge(risk_level)} |
| **风险分数** | {risk_score:.1f} / 10.0 |

### 漏洞统计

| 严重程度 | 数量 |
|----------|------|
| 🔴 Critical | {critical} |
| 🟠 High | {high} |
| 🟡 Medium | {medium} |
| 🟢 Low | {low} |
| **总计** | **{total}** |

### 主要风险因素

{factors_text}
"""


def generate_vulnerability_detail(vuln: dict, index: int) -> str:
    """生成单个漏洞的详细信息"""
    location = vuln.get('location', {})

    return f"""### {vuln.get('id', f'VULN-{index:03d}')} - {vuln.get('type', 'Unknown')}

**基本信息**

| 项目 | 值 |
|------|-----|
| **漏洞类型** | {vuln.get('type', 'N/A')} |
| **严重程度** | {format_severity_badge(vuln.get('severity', 'low'))} |
| **CVSS 分数** | {vuln.get('cvss_score', 'N/A')} |
| **CWE ID** | {vuln.get('cwe_id', 'N/A')} |
| **扫描器** | {vuln.get('scanner', 'N/A')} |
| **文件位置** | `{location.get('file', 'N/A')}:{location.get('line', 0)}` |

**问题描述**

{vuln.get('description', '无描述')}

**利用方式**

{vuln.get('exploit', '无利用信息')}

**修复建议**

{vuln.get('remediation', '无修复建议')}

**修复代码示例**

```
{vuln.get('fixed_code', '// 无修复代码示例')}
```

---
"""


def generate_vulnerability_table_row(vuln: dict) -> str:
    """生成漏洞表格行"""
    location = vuln.get('location', {})
    return f"| {vuln.get('id', 'N/A')} | {vuln.get('type', 'N/A')} | `{location.get('file', 'N/A')}:{location.get('line', 0)}` | {vuln.get('description', 'N/A')[:50]}... |"


def generate_vulnerabilities_section(report: dict) -> str:
    """生成漏洞详情章节"""
    vulnerabilities = report.get('vulnerabilities', [])

    if not vulnerabilities:
        return """## 漏洞详情

未发现漏洞。
"""

    # 按严重程度分组
    critical_vulns = [v for v in vulnerabilities if v.get('severity', '').lower() == 'critical']
    high_vulns = [v for v in vulnerabilities if v.get('severity', '').lower() == 'high']
    medium_vulns = [v for v in vulnerabilities if v.get('severity', '').lower() == 'medium']
    low_vulns = [v for v in vulnerabilities if v.get('severity', '').lower() == 'low']

    sections = []

    # Critical 漏洞 - 详细展示
    if critical_vulns:
        sections.append("## 🔴 Critical 级别漏洞（必须立即修复）\n")
        for i, vuln in enumerate(critical_vulns, 1):
            sections.append(generate_vulnerability_detail(vuln, i))

    # High 漏洞 - 详细展示
    if high_vulns:
        sections.append("## 🟠 High 级别漏洞（需要紧急处理）\n")
        for i, vuln in enumerate(high_vulns, 1):
            sections.append(generate_vulnerability_detail(vuln, i))

    # Medium 漏洞 - 表格展示
    if medium_vulns:
        sections.append("## 🟡 Medium 级别漏洞（计划修复）\n")
        sections.append("| ID | 类型 | 位置 | 描述 |")
        sections.append("|-----|------|------|------|")
        for vuln in medium_vulns:
            sections.append(generate_vulnerability_table_row(vuln))
        sections.append("")

    # Low 漏洞 - 表格展示
    if low_vulns:
        sections.append("## 🟢 Low 级别漏洞（后续修复）\n")
        sections.append("| ID | 类型 | 位置 | 描述 |")
        sections.append("|-----|------|------|------|")
        for vuln in low_vulns:
            sections.append(generate_vulnerability_table_row(vuln))
        sections.append("")

    return '\n'.join(sections)


def generate_scanner_results_section(report: dict) -> str:
    """生成扫描器执行详情章节"""
    scanner_results = report.get('scanner_results', {})

    if not scanner_results:
        return """## 扫描器执行详情

无扫描器执行记录。
"""

    rows = []
    for scanner, result in scanner_results.items():
        status = '✅ 完成' if result.get('status') == 'completed' else '❌ 失败'
        duration = result.get('duration_ms', 0)
        vulns = result.get('vulnerabilities_found', 0)
        rows.append(f"| {scanner} | {status} | {duration}ms | {vulns} |")

    return f"""## 扫描器执行详情

| 扫描器 | 状态 | 耗时 | 发现漏洞数 |
|--------|------|------|-----------|
{chr(10).join(rows)}
"""


def generate_priority_recommendations(report: dict) -> str:
    """生成修复优先级建议章节"""
    vulnerabilities = report.get('vulnerabilities', [])

    critical_vulns = [v for v in vulnerabilities if v.get('severity', '').lower() == 'critical']
    high_vulns = [v for v in vulnerabilities if v.get('severity', '').lower() == 'high']
    medium_vulns = [v for v in vulnerabilities if v.get('severity', '').lower() == 'medium']
    low_vulns = [v for v in vulnerabilities if v.get('severity', '').lower() == 'low']

    immediate = []
    short_term = []
    mid_term = []

    for v in critical_vulns:
        immediate.append(f"- [ ] {v.get('id', 'N/A')}: {v.get('type', 'N/A')} - `{v.get('location', {}).get('file', 'N/A')}`")

    for v in high_vulns:
        short_term.append(f"- [ ] {v.get('id', 'N/A')}: {v.get('type', 'N/A')} - `{v.get('location', {}).get('file', 'N/A')}`")

    for v in medium_vulns + low_vulns:
        mid_term.append(f"- [ ] {v.get('id', 'N/A')}: {v.get('type', 'N/A')} - `{v.get('location', {}).get('file', 'N/A')}`")

    immediate_text = '\n'.join(immediate) if immediate else '- 无'
    short_term_text = '\n'.join(short_term) if short_term else '- 无'
    mid_term_text = '\n'.join(mid_term) if mid_term else '- 无'

    return f"""## 修复优先级建议

### 🚨 立即行动（24 小时内）

{immediate_text}

### ⚠️ 短期（1 周内）

{short_term_text}

### 📋 中期（1 个月内）

{mid_term_text}
"""


def generate_markdown_report(report: dict) -> str:
    """生成完整的 Markdown 报告"""
    sections = [
        "# 代码安全审计报告\n",
        generate_metadata_section(report),
        generate_executive_summary(report),
        generate_vulnerabilities_section(report),
        generate_priority_recommendations(report),
        generate_scanner_results_section(report),
        """## 附录

### 严重程度定义

| 级别 | 定义 |
|------|------|
| 🔴 Critical | 可直接导致数据泄露、系统控制、权限提升，需立即修复 |
| 🟠 High | 高危漏洞，可能导致严重安全问题，需紧急处理 |
| 🟡 Medium | 中危漏洞，需要特定条件才能利用，计划修复 |
| 🟢 Low | 低危漏洞，影响有限，后续修复 |

### 参考资料

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [CWE/SANS Top 25](https://cwe.mitre.org/top25/)
- [CVSS 评分标准](https://www.first.org/cvss/)

---

*此报告由自动化安全扫描工具生成*
"""
    ]

    return '\n'.join(sections)


def main():
    if len(sys.argv) < 2:
        print("Usage: python json2md.py <input.json> [output.md]")
        print("  input.json  - JSON 报告文件路径")
        print("  output.md   - Markdown 输出路径 (可选，默认替换 .json 为 .md)")
        sys.exit(1)

    json_path = sys.argv[1]

    if len(sys.argv) >= 3:
        md_path = sys.argv[2]
    else:
        md_path = str(Path(json_path).with_suffix('.md'))

    # 加载 JSON 报告
    print(f"读取 JSON 报告: {json_path}")
    report = load_json_report(json_path)

    # 生成 Markdown
    print("生成 Markdown 报告...")
    markdown_content = generate_markdown_report(report)

    # 写入文件
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(markdown_content)

    print(f"Markdown 报告已生成: {md_path}")

    # 输出统计
    summary = report.get('summary', {})
    by_severity = summary.get('by_severity', {})
    print(f"\n漏洞统计:")
    print(f"  - Critical: {by_severity.get('critical', 0)}")
    print(f"  - High: {by_severity.get('high', 0)}")
    print(f"  - Medium: {by_severity.get('medium', 0)}")
    print(f"  - Low: {by_severity.get('low', 0)}")
    print(f"  - 总计: {summary.get('total_vulnerabilities', 0)}")


if __name__ == '__main__':
    main()
