"""JSON reporter for JWT sink findings."""

import json
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

from core.scanner import Finding


class JSONReporter:
    """Reporter for outputting findings in JSON format."""

    def __init__(self, output_file: Optional[str] = None):
        """
        Initialize the JSON reporter.

        Args:
            output_file: Optional file path to write JSON output
        """
        self.output_file = output_file
        self.findings = []

    def add_findings(self, findings: List[Finding]):
        """Add findings to the report."""
        self.findings.extend(findings)

    def generate_report(self) -> Dict:
        """Generate a JSON report structure."""
        return {
            "tool": "authentication_jwt_detector",
            "version": "1.0.0",
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_findings": len(self.findings),
                "by_language": self._count_by_language(),
                "by_severity": self._count_by_severity(),
            },
            "findings": [finding.to_dict() for finding in self.findings]
        }

    def _count_by_language(self) -> Dict[str, int]:
        """Count findings by language."""
        counts = {}
        for finding in self.findings:
            lang = finding.language
            counts[lang] = counts.get(lang, 0) + 1
        return counts

    def _count_by_severity(self) -> Dict[str, int]:
        """Count findings by severity."""
        counts = {}
        for finding in self.findings:
            sev = finding.severity
            counts[sev] = counts.get(sev, 0) + 1
        return counts

    def write_report(self, output_file: Optional[str] = None) -> str:
        """
        Write report to a JSON file.

        Args:
            output_file: File path to write to (uses self.output_file if not provided)

        Returns:
            Path to written file
        """
        file_path = output_file or self.output_file
        if not file_path:
            raise ValueError("No output file specified")

        report = self.generate_report()

        # Create parent directories if needed
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, 'w') as f:
            json.dump(report, f, indent=2)

        return file_path

    def get_json_string(self) -> str:
        """Get the report as a JSON string."""
        report = self.generate_report()
        return json.dumps(report, indent=2)
