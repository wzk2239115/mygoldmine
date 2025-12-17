"""SARIF reporter for CSRF sink detection results."""

import json
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime
import os


class SARIFReporter:
    """Reports CSRF sink detection results in SARIF format."""

    def __init__(self, tool_name: str = "CSRF Sink Detector"):
        """Initialize SARIF reporter."""
        self.tool_name = tool_name

    def generate_report(self, sinks: List[Dict[str, Any]], base_path: str = None) -> Dict[str, Any]:
        """Generate SARIF report from sinks."""
        results = []

        for sink in sinks:
            result = self._sink_to_sarif_result(sink, base_path)
            results.append(result)

        report = {
            'version': '2.1.0',
            '$schema': 'https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json',
            'runs': [
                {
                    'tool': {
                        'driver': {
                            'name': self.tool_name,
                            'version': '1.0',
                            'informationUri': 'https://github.com/yourusername/csrf-sink-detector',
                        }
                    },
                    'results': results,
                }
            ]
        }

        return report

    def _sink_to_sarif_result(self, sink: Dict[str, Any], base_path: str = None) -> Dict[str, Any]:
        """Convert a sink to a SARIF result."""
        file_path = sink.get('file', '')

        # Make path relative if base_path is provided
        if base_path and file_path.startswith(base_path):
            file_path = os.path.relpath(file_path, base_path)

        result = {
            'message': {
                'text': f"{sink.get('sink', 'CSRF Sink')} detected"
            },
            'locations': [
                {
                    'physicalLocation': {
                        'artifactLocation': {
                            'uri': file_path,
                        },
                        'region': {
                            'startLine': sink.get('line', 1),
                            'startColumn': sink.get('column', 1),
                        }
                    }
                }
            ],
            'properties': {
                'sink_type': sink.get('type', 'unknown'),
                'code': sink.get('code', ''),
            }
        }

        return result

    def save_report(self, sinks: List[Dict[str, Any]], output_file: str, base_path: str = None):
        """Save report to file."""
        report = self.generate_report(sinks, base_path)

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

    def report_to_string(self, sinks: List[Dict[str, Any]], base_path: str = None) -> str:
        """Convert report to SARIF string."""
        report = self.generate_report(sinks, base_path)
        return json.dumps(report, indent=2, ensure_ascii=False)
