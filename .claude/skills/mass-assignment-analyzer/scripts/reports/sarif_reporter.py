"""
SARIF Reporter: Generates SARIF format reports for findings
SARIF: Static Analysis Results Interchange Format
"""
import json
from typing import List, Dict
from datetime import datetime


class SARIFReporter:
    """Generate SARIF format reports (Static Analysis Results Interchange Format)"""

    SARIF_VERSION = "2.1.0"

    def __init__(self):
        """Initialize SARIF reporter"""
        self.findings = []

    def add_findings(self, findings: List) -> None:
        """Add findings to report"""
        self.findings = findings

    def generate(self) -> str:
        """Generate SARIF report"""
        results = []

        for i, finding in enumerate(self.findings):
            result = {
                "ruleId": "MASS_ASSIGNMENT",
                "message": {
                    "text": finding.message
                },
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {
                                "uri": finding.file
                            },
                            "region": {
                                "startLine": finding.line,
                                "startColumn": finding.column,
                                "snippet": {
                                    "text": finding.code
                                }
                            }
                        }
                    }
                ],
                "level": self._get_sarif_level(finding.severity),
                "kind": "notApplicable"
            }
            results.append(result)

        sarif_report = {
            "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
            "version": self.SARIF_VERSION,
            "runs": [
                {
                    "tool": {
                        "driver": {
                            "name": "mass_assignment_sink_detector",
                            "version": "1.0.0",
                            "informationUri": "https://github.com/yourusername/mass_assignment_sink_detector",
                            "rules": [
                                {
                                    "id": "MASS_ASSIGNMENT",
                                    "shortDescription": {
                                        "text": "Mass Assignment Vulnerability"
                                    },
                                    "fullDescription": {
                                        "text": "Detects potential mass assignment vulnerabilities where user input is directly assigned to model attributes without validation"
                                    },
                                    "defaultConfiguration": {
                                        "level": "warning"
                                    },
                                    "help": {
                                        "text": "Mass assignment vulnerabilities occur when an application blindly assigns all user input to model properties. This can lead to privilege escalation and other security issues."
                                    }
                                }
                            ]
                        }
                    },
                    "results": results,
                    "invocations": [
                        {
                            "executionSuccessful": True,
                            "endTimeUtc": datetime.utcnow().isoformat() + "Z"
                        }
                    ]
                }
            ]
        }

        return json.dumps(sarif_report, indent=2, ensure_ascii=False)

    @staticmethod
    def _get_sarif_level(severity: str) -> str:
        """Convert severity to SARIF level"""
        severity_map = {
            'CRITICAL': 'error',
            'HIGH': 'warning',
            'MEDIUM': 'warning',
            'LOW': 'note',
            'INFO': 'none'
        }
        return severity_map.get(severity, 'warning')

    def save(self, output_path: str) -> None:
        """Save SARIF report to file"""
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(self.generate())
        print(f"SARIF report saved to: {output_path}")
