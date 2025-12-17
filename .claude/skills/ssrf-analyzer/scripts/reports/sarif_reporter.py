"""SARIF (Static Analysis Results Format) report generation for SSRF findings."""

import json
import uuid
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime


class SARIFReporter:
    """Generates SARIF format reports for SSRF findings."""

    SARIF_VERSION = "2.1.0"

    @staticmethod
    def generate(
        findings: List[Dict],
        output_path: Optional[str] = None,
        tool_name: str = "SSRF Sink Detector"
    ) -> str:
        """
        Generate SARIF format report from findings.

        Args:
            findings: List of detected sink findings
            output_path: Optional path to write report to file
            tool_name: Name of the analysis tool

        Returns:
            SARIF JSON string
        """
        sarif_report = {
            "version": SARIFReporter.SARIF_VERSION,
            "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
            "runs": [
                {
                    "tool": {
                        "driver": {
                            "name": tool_name,
                            "version": "1.0.0",
                            "informationUri": "https://github.com/security/ssrf-detector",
                            "rules": SARIFReporter._generate_rules()
                        }
                    },
                    "results": [
                        SARIFReporter._convert_finding_to_sarif(finding)
                        for finding in findings
                    ]
                }
            ]
        }

        json_str = json.dumps(sarif_report, indent=2, ensure_ascii=False)

        if output_path:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(json_str)

        return json_str

    @staticmethod
    def _convert_finding_to_sarif(finding: Dict) -> Dict:
        """Convert a single finding to SARIF result format."""
        severity_map = {
            'high': 'error',
            'medium': 'warning',
            'low': 'note'
        }

        sarif_level = severity_map.get(finding.get('severity', 'medium'), 'warning')

        result = {
            "ruleId": f"ssrf-{finding.get('language', 'unknown')}-{finding.get('sink_name', 'unknown')}",
            "level": sarif_level,
            "message": {
                "text": f"Potential SSRF vulnerability: {finding.get('sink_name', 'Unknown sink')} at line {finding.get('start_line', '?')}"
            },
            "locations": [
                {
                    "physicalLocation": {
                        "address": {
                            "relativeUri": finding.get('file', ''),
                            "offsetFromStart": 0
                        },
                        "region": {
                            "startLine": finding.get('start_line', 1),
                            "startColumn": finding.get('start_col', 0) + 1,
                            "endLine": finding.get('end_line', 1),
                            "endColumn": finding.get('end_col', 0) + 1,
                            "snippet": {
                                "text": finding.get('code_snippet', '')
                            }
                        }
                    }
                }
            ],
            "properties": {
                "language": finding.get('language', 'unknown'),
                "sink_name": finding.get('sink_name', 'unknown')
            }
        }

        return result

    @staticmethod
    def _generate_rules() -> List[Dict]:
        """Generate SARIF rule definitions."""
        return [
            {
                "id": "ssrf-generic",
                "name": "SSRF Vulnerability",
                "shortDescription": {
                    "text": "Server-Side Request Forgery (SSRF) vulnerability"
                },
                "fullDescription": {
                    "text": "A Server-Side Request Forgery (SSRF) vulnerability occurs when an application fetches remote resources without properly validating user-supplied URLs. This can allow attackers to make unauthorized requests to internal systems or services."
                },
                "defaultConfiguration": {
                    "level": "warning"
                },
                "helpUri": "https://owasp.org/www-community/attacks/Server-Side_Request_Forgery"
            }
        ]
