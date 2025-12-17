"""SARIF reporter for JWT sink findings."""

import json
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
from urllib.parse import urljoin
import os

from core.scanner import Finding


class SARIFReporter:
    """Reporter for outputting findings in SARIF (Static Analysis Results Format)."""

    def __init__(self, output_file: Optional[str] = None, base_uri: Optional[str] = None):
        """
        Initialize the SARIF reporter.

        Args:
            output_file: Optional file path to write SARIF output
            base_uri: Base URI for file references
        """
        self.output_file = output_file
        self.base_uri = base_uri or f"file://{os.getcwd()}/"
        self.findings = []

    def add_findings(self, findings: List[Finding]):
        """Add findings to the report."""
        self.findings.extend(findings)

    def _get_file_uri(self, file_path: str) -> str:
        """Convert file path to URI."""
        abs_path = os.path.abspath(file_path)
        if self.base_uri.startswith("file://"):
            return f"file://{abs_path}"
        return urljoin(self.base_uri, file_path)

    def _create_location(self, finding: Finding) -> Dict:
        """Create a SARIF location object."""
        return {
            "physicalLocation": {
                "address": {
                    "relativeUri": finding.file,
                    "uri": self._get_file_uri(finding.file)
                },
                "region": {
                    "startLine": finding.line,
                    "startColumn": finding.column + 1
                }
            }
        }

    def _create_result(self, finding: Finding) -> Dict:
        """Create a SARIF result object."""
        severity_map = {
            "CRITICAL": "error",
            "HIGH": "warning",
            "MEDIUM": "note",
            "LOW": "note"
        }

        return {
            "ruleId": "JWT-SINK",
            "message": {
                "text": finding.message or f"JWT sink detected: {finding.function_name}"
            },
            "locations": [self._create_location(finding)],
            "level": severity_map.get(finding.severity, "warning"),
            "partialFingerprints": {
                "functionName": finding.function_name,
                "file": finding.file
            }
        }

    def generate_report(self) -> Dict:
        """Generate a SARIF report structure."""
        results = [self._create_result(finding) for finding in self.findings]

        return {
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {
                        "driver": {
                            "name": "authentication_jwt_detector",
                            "version": "1.0.0",
                            "informationUri": "https://github.com/anthropics/authentication_jwt_detector",
                            "rules": [
                                {
                                    "id": "JWT-SINK",
                                    "name": "JWTAuthenticationSink",
                                    "shortDescription": {
                                        "text": "Detects JWT authentication operations"
                                    },
                                    "fullDescription": {
                                        "text": "This rule detects operations that handle JWT tokens, such as decode, verify, and sign operations."
                                    },
                                    "defaultConfiguration": {
                                        "level": "warning"
                                    }
                                }
                            ]
                        }
                    },
                    "results": results,
                    "properties": {
                        "scanDate": datetime.now().isoformat(),
                        "totalFindings": len(self.findings),
                        "byLanguage": self._count_by_language(),
                        "bySeverity": self._count_by_severity()
                    }
                }
            ]
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
        Write report to a SARIF file.

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

    def get_sarif_string(self) -> str:
        """Get the report as a SARIF JSON string."""
        report = self.generate_report()
        return json.dumps(report, indent=2)
