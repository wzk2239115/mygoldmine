"""
JSON Reporter: Generates JSON format reports for findings
"""
import json
from typing import List, Dict
from datetime import datetime


class JSONReporter:
    """Generate JSON format reports"""

    def __init__(self):
        """Initialize JSON reporter"""
        self.findings = []

    def add_findings(self, findings: List) -> None:
        """Add findings to report"""
        self.findings = findings

    def generate(self) -> str:
        """Generate JSON report"""
        lines = []
        lines.append('tool: mass_assignment_sink_detector')
        lines.append('version: 1.0.0')
        lines.append(f'timestamp: {datetime.now().isoformat()}')
        lines.append(f'total_findings: {len(self.findings)}')
        lines.append('')

        for i, finding in enumerate(self.findings, 1):
            code = finding.get_truncated_code(150)
            lines.append(f'{i}. {finding.file}:{finding.line}:{finding.column} | type: {finding.type} | severity: {finding.severity} | code: {code} | message: {finding.message}')

        return '\n'.join(lines)

    def save(self, output_path: str) -> None:
        """Save JSON report to file"""
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(self.generate())
        print(f"JSON report saved to: {output_path}")
