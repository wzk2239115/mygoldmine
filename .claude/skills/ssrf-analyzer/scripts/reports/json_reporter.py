"""JSON report generation for SSRF sink detection results."""

import json
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime


class JSONReporter:
    """Generates JSON format reports for SSRF findings."""

    @staticmethod
    def generate(
        findings: List[Dict],
        output_path: Optional[str] = None,
        summary: Optional[Dict] = None
    ) -> str:
        """
        Generate JSON report from findings.

        Args:
            findings: List of detected sink findings
            output_path: Optional path to write report to file
            summary: Optional summary statistics

        Returns:
            JSON string
        """
        report = {
            'version': '1.0.0',
            'timestamp': datetime.now().isoformat(),
            'summary': summary or {
                'total_findings': len(findings),
                'by_severity': JSONReporter._count_by_severity(findings),
                'by_language': JSONReporter._count_by_language(findings)
            },
            'findings': findings
        }

        json_str = json.dumps(report, indent=2, ensure_ascii=False)

        if output_path:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(json_str)

        return json_str

    @staticmethod
    def _count_by_severity(findings: List[Dict]) -> Dict[str, int]:
        """Count findings by severity level."""
        counts = {'high': 0, 'medium': 0, 'low': 0}
        for finding in findings:
            severity = finding.get('severity', 'medium')
            if severity in counts:
                counts[severity] += 1
        return counts

    @staticmethod
    def _count_by_language(findings: List[Dict]) -> Dict[str, int]:
        """Count findings by programming language."""
        counts = {}
        for finding in findings:
            language = finding.get('language', 'unknown')
            counts[language] = counts.get(language, 0) + 1
        return counts
