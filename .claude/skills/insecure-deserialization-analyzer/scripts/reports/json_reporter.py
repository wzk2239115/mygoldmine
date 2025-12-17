"""
Report generators for scan results.
"""

import json
import os
from typing import List
from datetime import datetime
from core.scanner import Sink


class JSONReporter:
    """JSON format reporter for scan results."""

    @staticmethod
    def generate(sinks: List[Sink], output_file: str = None) -> str:
        """
        Generate JSON report from detected sinks.

        Args:
            sinks: List of detected sinks
            output_file: Output file path (optional)

        Returns:
            JSON string
        """
        report = {
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'total_sinks': len(sinks),
                'critical': len([s for s in sinks if 'critical' in s.function.lower()]),
                'high': len([s for s in sinks if 'high' in s.function.lower()]),
                'medium': len([s for s in sinks if 'medium' in s.function.lower()]),
            },
            'sinks': [sink.to_dict() for sink in sinks]
        }

        json_str = json.dumps(report, indent=2)

        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(json_str)

        return json_str


class PlainTextReporter:
    """Plain text format reporter for scan results (compact)."""

    MAX_CONTEXT_LENGTH = 80  # Maximum length for context in plain text output

    @staticmethod
    def generate(sinks: List[Sink], output_file: str = None, base_dir: str = None) -> str:
        """
        Generate plain text report from detected sinks.

        Args:
            sinks: List of detected sinks
            output_file: Output file path (optional)
            base_dir: Base directory for relative path calculation

        Returns:
            Plain text string
        """
        lines = []

        for sink in sinks:
            file_path = sink.file_path

            # Convert to relative path if base_dir is provided
            if base_dir:
                try:
                    file_path = os.path.relpath(sink.file_path, base_dir)
                except ValueError:
                    # On Windows, relpath fails if paths are on different drives
                    file_path = sink.file_path

            # Truncate context to MAX_CONTEXT_LENGTH
            context = sink.context
            if len(context) > PlainTextReporter.MAX_CONTEXT_LENGTH:
                context = context[:PlainTextReporter.MAX_CONTEXT_LENGTH - 3] + '...'

            # Format: file:path,line: N,column: N,function:NAME,context: TEXT
            line = f"file:{file_path},line: {sink.line},column: {sink.column},function:{sink.function},context: {context}"
            lines.append(line)

        output = '\n'.join(lines)

        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(output)

        return output


class SARIFReporter:
    """SARIF format reporter for scan results."""

    @staticmethod
    def generate(sinks: List[Sink], output_file: str = None) -> str:
        """
        Generate SARIF report from detected sinks.

        Args:
            sinks: List of detected sinks
            output_file: Output file path (optional)

        Returns:
            SARIF JSON string
        """
        results = []

        for sink in sinks:
            result = {
                'ruleId': 'INSECURE_DESERIALIZATION',
                'message': {
                    'text': f"Insecure deserialization sink detected: {sink.function}"
                },
                'locations': [
                    {
                        'physicalLocation': {
                            'address': {
                                'relativePageIndex': 0,
                                'offsetFromStartOfParent': 0
                            },
                            'region': {
                                'startLine': sink.line,
                                'startColumn': sink.column,
                            },
                            'artifactLocation': {
                                'uri': sink.file_path,
                                'uriBaseId': '%SRCROOT%'
                            }
                        }
                    }
                ],
                'properties': {
                    'function': sink.function,
                    'context': sink._truncate_context(sink.context)
                }
            }
            results.append(result)

        sarif = {
            '$schema': 'https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json',
            'version': '2.1.0',
            'runs': [
                {
                    'tool': {
                        'driver': {
                            'name': 'insecure-deserialization-detector',
                            'version': '1.0.0',
                            'rules': [
                                {
                                    'id': 'INSECURE_DESERIALIZATION',
                                    'name': 'Insecure Deserialization',
                                    'shortDescription': {
                                        'text': 'Detects unsafe deserialization sinks'
                                    }
                                }
                            ]
                        }
                    },
                    'results': results
                }
            ]
        }

        sarif_str = json.dumps(sarif, indent=2)

        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(sarif_str)

        return sarif_str
