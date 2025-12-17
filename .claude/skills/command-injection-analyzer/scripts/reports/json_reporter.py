"""JSON reporter for command injection sink detection results."""

import json
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime


class JSONReporter:
    """Reporter for generating JSON reports."""

    def __init__(self, pretty_print: bool = True, include_context: bool = True):
        """Initialize JSON reporter."""
        self.pretty_print = pretty_print
        self.include_context = include_context

    def generate_report(
        self,
        sinks: List[Dict[str, Any]],
        source_path: str = None,
        languages: List[str] = None,
    ) -> Dict[str, Any]:
        """Generate a report from detected sinks."""
        report = {
            'metadata': {
                'tool': 'Command Injection Sink Detector',
                'timestamp': datetime.utcnow().isoformat(),
                'source_path': source_path,
                'languages_scanned': languages or [],
                'total_sinks': len(sinks),
            },
            'sinks': sinks,
            'summary': self._generate_summary(sinks),
        }
        return report

    def _generate_summary(self, sinks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate a summary of the findings."""
        summary = {
            'total': len(sinks),
            'by_category': {},
            'by_file': {},
        }

        for sink in sinks:
            category = sink.get('sink_category', 'unknown')
            file_path = sink.get('file', 'unknown')

            # Count by category
            if category not in summary['by_category']:
                summary['by_category'][category] = 0
            summary['by_category'][category] += 1

            # Count by file
            if file_path not in summary['by_file']:
                summary['by_file'][file_path] = 0
            summary['by_file'][file_path] += 1

        return summary

    def write_json(self, report: Dict[str, Any], output_file: str) -> None:
        """Write report to JSON file."""
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            if self.pretty_print:
                json.dump(report, f, indent=2, ensure_ascii=False)
            else:
                json.dump(report, f, ensure_ascii=False)

    def write_csv(self, sinks: List[Dict[str, Any]], output_file: str) -> None:
        """Write sinks to CSV file."""
        import csv

        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if not sinks:
            return

        # Get all unique keys
        keys = set()
        for sink in sinks:
            keys.update(sink.keys())
        keys = sorted(list(keys))

        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            for sink in sinks:
                writer.writerow({k: sink.get(k, '') for k in keys})

    def write_html(self, report: Dict[str, Any], output_file: str) -> None:
        """Write report to HTML file."""
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        sinks = report.get('sinks', [])
        metadata = report.get('metadata', {})
        summary = report.get('summary', {})

        html_content = self._generate_html(metadata, summary, sinks)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

    def _generate_html(
        self,
        metadata: Dict[str, Any],
        summary: Dict[str, Any],
        sinks: List[Dict[str, Any]],
    ) -> str:
        """Generate HTML content for the report."""
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Command Injection Sink Detection Report</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        .header {{
            background-color: #333;
            color: white;
            padding: 20px;
            border-radius: 5px;
            margin-bottom: 20px;
        }}
        .metadata {{
            background-color: white;
            padding: 15px;
            margin-bottom: 20px;
            border-radius: 5px;
            border-left: 4px solid #4CAF50;
        }}
        .summary {{
            background-color: white;
            padding: 15px;
            margin-bottom: 20px;
            border-radius: 5px;
        }}
        .summary h2 {{
            margin-top: 0;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            background-color: white;
            border-radius: 5px;
            overflow: hidden;
        }}
        th {{
            background-color: #4CAF50;
            color: white;
            padding: 12px;
            text-align: left;
        }}
        td {{
            padding: 12px;
            border-bottom: 1px solid #ddd;
        }}
        tr:hover {{
            background-color: #f5f5f5;
        }}
        .category {{
            display: inline-block;
            background-color: #e3f2fd;
            color: #1976d2;
            padding: 5px 10px;
            border-radius: 3px;
            font-size: 12px;
        }}
        .file {{
            word-break: break-all;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Command Injection Sink Detection Report</h1>
        <p>Generated: {metadata.get('timestamp', 'N/A')}</p>
    </div>

    <div class="metadata">
        <h2>Scan Information</h2>
        <p><strong>Tool:</strong> {metadata.get('tool', 'N/A')}</p>
        <p><strong>Source Path:</strong> {metadata.get('source_path', 'N/A')}</p>
        <p><strong>Languages Scanned:</strong> {', '.join(metadata.get('languages_scanned', []))}</p>
    </div>

    <div class="summary">
        <h2>Summary</h2>
        <p><strong>Total Sinks Found:</strong> {summary.get('total', 0)}</p>
        <h3>By Category</h3>
        <ul>
"""

        for category, count in summary.get('by_category', {}).items():
            html += f"            <li>{category}: {count}</li>\n"

        html += """
        </ul>
    </div>

    <h2>Detected Sinks</h2>
    <table>
        <thead>
            <tr>
                <th>File</th>
                <th>Line</th>
                <th>Column</th>
                <th>Function</th>
                <th>Category</th>
                <th>Parameters</th>
            </tr>
        </thead>
        <tbody>
"""

        for sink in sinks:
            file_path = sink.get('file', 'N/A')
            line = sink.get('line', 'N/A')
            column = sink.get('column', 'N/A')
            function = sink.get('function_name', 'N/A')
            category = sink.get('sink_category', 'N/A')
            params = ', '.join(sink.get('parameters', []))

            html += f"""
            <tr>
                <td class="file">{file_path}</td>
                <td>{line}</td>
                <td>{column}</td>
                <td>{function}</td>
                <td><span class="category">{category}</span></td>
                <td>{params}</td>
            </tr>
"""

        html += """
        </tbody>
    </table>
</body>
</html>
"""

        return html
