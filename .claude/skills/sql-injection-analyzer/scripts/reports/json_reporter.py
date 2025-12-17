"""JSON reporter for SQL injection sink detection results."""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime


class JSONReporter:
    """Generates JSON reports of detected SQL injection sinks."""

    def __init__(self, pretty_print: bool = True, include_context: bool = True):
        """Initialize reporter."""
        self.pretty_print = pretty_print
        self.include_context = include_context

    def generate_report(
        self,
        sinks: List[Dict[str, Any]],
        source_path: str = None,
        languages: List[str] = None,
    ) -> Dict[str, Any]:
        """Generate comprehensive report."""
        report = {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "tool": "SQL Injection Sink Detector",
                "version": "1.0.0",
                "source_path": source_path,
                "languages_scanned": languages or [],
            },
            "summary": self._generate_summary(sinks),
            "sinks": self._filter_and_format_sinks(sinks),
        }
        return report

    def _generate_summary(self, sinks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate summary statistics."""
        summary = {
            "total_sinks": len(sinks),
            "by_category": {},
            "by_file": {},
            "by_sink_type": {},
        }

        for sink in sinks:
            # Count by category
            category = sink.get('sink_category', 'unknown')
            summary['by_category'][category] = summary['by_category'].get(category, 0) + 1

            # Count by file
            file = sink.get('file', 'unknown')
            if file not in summary['by_file']:
                summary['by_file'][file] = 0
            summary['by_file'][file] += 1

            # Count by sink type
            sink_type = sink.get('sink_type', 'unknown')
            summary['by_sink_type'][sink_type] = summary['by_sink_type'].get(sink_type, 0) + 1

        return summary

    def _filter_and_format_sinks(self, sinks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter and format sink information."""
        formatted = []
        for sink in sinks:
            formatted_sink = {
                "file": sink.get('file'),
                "line": sink.get('line'),
                "column": sink.get('column'),
                "sink_type": sink.get('sink_type'),
                "sink_category": sink.get('sink_category'),
                "function_name": sink.get('function_name'),
                "parameters": sink.get('parameters', []),
                "vulnerable_params": sink.get('vulnerable_params', []),
            }

            if self.include_context:
                formatted_sink['context'] = sink.get('context', '')

            formatted.append(formatted_sink)

        # Sort by file and line
        formatted.sort(key=lambda x: (x['file'], x['line']))
        return formatted

    def write_json(self, report: Dict[str, Any], output_path: str, pretty: bool = None):
        """Write report to JSON file."""
        if pretty is None:
            pretty = self.pretty_print

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            if pretty:
                json.dump(report, f, indent=2, ensure_ascii=False)
            else:
                json.dump(report, f, ensure_ascii=False)

    def write_csv(self, sinks: List[Dict[str, Any]], output_path: str):
        """Write report to CSV file."""
        import csv

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        fieldnames = [
            'file',
            'line',
            'column',
            'sink_type',
            'sink_category',
            'function_name',
            'parameters',
            'vulnerable_params',
        ]

        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for sink in sinks:
                row = {field: str(sink.get(field, '')) for field in fieldnames}
                writer.writerow(row)

    def write_html(self, report: Dict[str, Any], output_path: str):
        """Write report to HTML file."""
        html_content = self._generate_html(report)
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)

    def _generate_html(self, report: Dict[str, Any]) -> str:
        """Generate HTML report content."""
        metadata = report.get('metadata', {})
        summary = report.get('summary', {})
        sinks = report.get('sinks', [])

        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>SQL Injection Sink Detection Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .metadata {{ background: #f5f5f5; padding: 10px; border-radius: 5px; margin-bottom: 20px; }}
        .summary {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin-bottom: 20px; }}
        .stat-box {{ background: #e8f4f8; padding: 15px; border-left: 4px solid #0288d1; }}
        table {{ border-collapse: collapse; width: 100%; margin-top: 20px; }}
        th {{ background: #0288d1; color: white; padding: 10px; text-align: left; }}
        td {{ border: 1px solid #ddd; padding: 10px; }}
        tr:nth-child(even) {{ background: #f9f9f9; }}
        .category {{ display: inline-block; background: #fff3cd; padding: 3px 8px; border-radius: 3px; font-size: 0.9em; }}
        .context {{ font-family: 'Courier New', monospace; font-size: 0.85em; background: #f5f5f5; padding: 5px; border-radius: 3px; max-height: 100px; overflow-y: auto; }}
    </style>
</head>
<body>
    <h1>SQL Injection Sink Detection Report</h1>

    <div class="metadata">
        <p><strong>Tool:</strong> {metadata.get('tool', 'Unknown')}</p>
        <p><strong>Timestamp:</strong> {metadata.get('timestamp', 'N/A')}</p>
        <p><strong>Source Path:</strong> {metadata.get('source_path', 'N/A')}</p>
        <p><strong>Languages Scanned:</strong> {', '.join(metadata.get('languages_scanned', []))}</p>
    </div>

    <h2>Summary</h2>
    <div class="summary">
        <div class="stat-box">
            <strong>Total Sinks Detected:</strong> {summary.get('total_sinks', 0)}
        </div>
        <div class="stat-box">
            <strong>Unique Files:</strong> {len(summary.get('by_file', {}))}
        </div>
    </div>

    <h3>Sinks by Category</h3>
    <div class="summary">
        {''.join(f'<div class="stat-box"><strong>{cat}:</strong> {count}</div>' for cat, count in summary.get('by_category', {}).items())}
    </div>

    <h2>Detected Sinks</h2>
    <table>
        <tr>
            <th>File</th>
            <th>Line</th>
            <th>Type</th>
            <th>Category</th>
            <th>Parameters</th>
        </tr>
        {''.join(f'''
        <tr>
            <td><strong>{sink.get('file', 'N/A')}</strong>:{sink.get('column', 'N/A')}</td>
            <td>{sink.get('line', 'N/A')}</td>
            <td><code>{sink.get('sink_type', 'N/A')}</code></td>
            <td><span class="category">{sink.get('sink_category', 'N/A')}</span></td>
            <td><code>{', '.join(sink.get('parameters', []))}</code></td>
        </tr>
        ''' for sink in sinks)}
    </table>

    <hr>
    <p style="font-size: 0.9em; color: #666;">
        <strong>⚠️ Disclaimer:</strong> This report is a pre-filter screening tool. All detected sinks require
        manual verification to confirm whether they actually receive user input and whether proper
        parameterization/sanitization is in place.
    </p>
</body>
</html>"""
        return html
