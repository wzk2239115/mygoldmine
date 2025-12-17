"""JSON reporter for CSRF sink detection results."""

import json
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime


class JSONReporter:
    """Reports CSRF sink detection results in JSON format."""

    def __init__(self, pretty_print: bool = True, include_context: bool = True):
        """Initialize JSON reporter."""
        self.pretty_print = pretty_print
        self.include_context = include_context

    def generate_report(self, sinks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate JSON report from sinks."""
        report = {
            'timestamp': datetime.now().isoformat(),
            'version': '1.0',
            'tool': 'CSRF Sink Detector',
            'summary': {
                'total_sinks': len(sinks),
                'by_type': self._count_by_type(sinks),
                'by_file': self._count_by_file(sinks),
            },
            'sinks': sinks,
        }

        return report

    def _count_by_type(self, sinks: List[Dict[str, Any]]) -> Dict[str, int]:
        """Count sinks by type."""
        counts = {}
        for sink in sinks:
            sink_type = sink.get('type', 'unknown')
            counts[sink_type] = counts.get(sink_type, 0) + 1
        return counts

    def _count_by_file(self, sinks: List[Dict[str, Any]]) -> Dict[str, int]:
        """Count sinks by file."""
        counts = {}
        for sink in sinks:
            file_path = sink.get('file', 'unknown')
            counts[file_path] = counts.get(file_path, 0) + 1
        return counts

    def save_report(self, sinks: List[Dict[str, Any]], output_file: str):
        """Save report to file."""
        report = self.generate_report(sinks)

        with open(output_file, 'w', encoding='utf-8') as f:
            if self.pretty_print:
                json.dump(report, f, indent=2, ensure_ascii=False)
            else:
                json.dump(report, f, ensure_ascii=False)

    def report_to_string(self, sinks: List[Dict[str, Any]]) -> str:
        """Convert report to JSON string."""
        report = self.generate_report(sinks)

        if self.pretty_print:
            return json.dumps(report, indent=2, ensure_ascii=False)
        else:
            return json.dumps(report, ensure_ascii=False)
