#!/usr/bin/env python3
"""CLI interface for Command Injection sink detector."""

import argparse
import sys
import os
from pathlib import Path
from typing import List, Dict, Any
import re
import yaml

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from core.parser_manager import ParserManager
from reports.json_reporter import JSONReporter


class CommandInjectionSinkDetectorCLI:
    """CLI interface for Command Injection sink detector."""

    def __init__(self):
        """Initialize CLI."""
        self.parser_manager = ParserManager()
        self.reporter = JSONReporter(pretty_print=True, include_context=True)
        self.all_sinks = []

    def find_files(self, directory: str, patterns: List[str]) -> List[str]:
        """Find files matching patterns in directory."""
        directory = Path(directory)
        matched_files = []

        for pattern in patterns:
            # Convert glob pattern to regex
            regex_pattern = pattern.replace('.', r'\.').replace('*', '.*')
            regex = re.compile(f'^{regex_pattern}$')

            for file_path in directory.rglob('*'):
                if file_path.is_file() and regex.match(file_path.name):
                    matched_files.append(str(file_path))

        return sorted(set(matched_files))

    def scan_directory(
        self,
        directory: str,
        languages: List[str] = None,
        verbose: bool = False,
    ) -> List[Dict[str, Any]]:
        """Scan directory for command injection sinks."""
        all_sinks = []

        if languages is None:
            languages = self.parser_manager.get_enabled_languages()

        directory = Path(directory)
        if not directory.exists():
            print(f"Error: Directory {directory} does not exist", file=sys.stderr)
            return []

        for language in languages:
            if not self.parser_manager.is_language_enabled(language):
                if verbose:
                    print(f"Skipping disabled language: {language}")
                continue

            patterns = self.parser_manager.get_file_patterns(language)
            sink_config = self.parser_manager.get_sink_config(language)

            if not sink_config:
                if verbose:
                    print(f"No sink configuration for {language}")
                continue

            files = self.find_files(str(directory), patterns)

            if verbose:
                print(f"Found {len(files)} {language} files")

            for file_path in files:
                try:
                    sinks = self.scan_file(file_path, language, sink_config, verbose)
                    all_sinks.extend(sinks)
                except Exception as e:
                    if verbose:
                        print(f"Error scanning {file_path}: {e}")

        return all_sinks

    def scan_file(
        self,
        file_path: str,
        language: str,
        sink_config: List[Dict[str, Any]],
        verbose: bool = False,
    ) -> List[Dict[str, Any]]:
        """Scan a single file for command injection sinks."""
        sinks = []

        # Skip minified JavaScript libraries for JavaScript/TypeScript
        if language in ('javascript', 'typescript') and self._is_minified_library(file_path):
            if verbose:
                print(f"Skipping minified library: {file_path}")
            return []

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                source_code = f.read()

            # Use regex-based detection
            sinks = self._detect_sinks_regex(
                source_code,
                file_path,
                language,
                sink_config,
            )

            if verbose and sinks:
                print(f"Found {len(sinks)} sinks in {file_path}")

        except Exception as e:
            if verbose:
                print(f"Error reading {file_path}: {e}")

        return sinks

    def _detect_sinks_regex(
        self,
        source_code: str,
        file_path: str,
        language: str,
        sink_config: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Detect sinks using regex patterns."""
        sinks = []
        lines = source_code.split('\n')

        for sink in sink_config:
            sink_name = sink.get('name', '')
            category = sink.get('category', 'unknown')
            sink_type = sink.get('type', 'function_call')

            # Build regex pattern based on sink type
            if sink_type == 'function_call':
                # Match: function_name(...) or $obj->function_name(...)
                patterns = [
                    rf'\b{re.escape(sink_name)}\s*\(',  # function_name(
                    rf'\-\>{re.escape(sink_name)}\s*\(',  # ->method_name(
                    rf'\::{re.escape(sink_name)}\s*\(',  # ::static_method_name(
                ]
            elif sink_type == 'method_call':
                # Match method calls
                patterns = [
                    rf'\-\>{re.escape(sink_name)}\s*\(',  # ->method_name(
                    rf'\.{re.escape(sink_name)}\s*\(',  # .method_name(
                ]
            elif sink_type == 'operator':
                # Match operators like backticks or shell_exec
                patterns = [rf'`[^`]*{re.escape(sink_name)}[^`]*`']
            else:
                patterns = [rf'\b{re.escape(sink_name)}\s*\(']

            # Search for patterns in source code
            for line_num, line in enumerate(lines, 1):
                for pattern in patterns:
                    matches = list(re.finditer(pattern, line))
                    for match in matches:
                        column = match.start() + 1
                        context = self._get_context(lines, line_num - 1)

                        sink_obj = {
                            'file': file_path,
                            'line': line_num,
                            'column': column,
                            'sink_type': sink_name,
                            'sink_category': category,
                            'function_name': sink_name,
                            'parameters': self._extract_params_regex(line, match.start()),
                            'vulnerable_params': sink.get('vulnerable_params', [0]),
                            'context': context,
                        }
                        sinks.append(sink_obj)

        return sinks

    def _get_context(self, lines: List[str], line_num: int, context_lines: int = 1) -> str:
        """Get context around a line."""
        start = max(0, line_num - context_lines)
        end = min(len(lines), line_num + context_lines + 1)
        return '\n'.join(lines[start:end]).strip()

    def _extract_params_regex(self, line: str, start_pos: int) -> List[str]:
        """Extract parameters from a function call (simple regex-based)."""
        # Find the opening parenthesis
        paren_pos = line.find('(', start_pos)
        if paren_pos == -1:
            return []

        # Simple extraction: get content until matching closing paren
        depth = 0
        end_pos = paren_pos
        for i, char in enumerate(line[paren_pos:]):
            if char == '(':
                depth += 1
            elif char == ')':
                depth -= 1
                if depth == 0:
                    end_pos = paren_pos + i
                    break

        if depth == 0:
            params_str = line[paren_pos + 1:end_pos]
            # Split by comma, but be careful with nested structures
            params = self._split_params(params_str)
            return [p.strip() for p in params if p.strip()]

        return []

    def _split_params(self, params_str: str) -> List[str]:
        """Split parameters by comma, respecting nesting."""
        params = []
        current = []
        depth = 0

        for char in params_str:
            if char in ('(', '[', '{', '"', "'"):
                current.append(char)
                if char in ('"', "'"):
                    depth += 1
            elif char in (')', ']', '}'):
                current.append(char)
                if char in ('"', "'"):
                    depth -= 1
            elif char == ',' and depth == 0:
                params.append(''.join(current))
                current = []
            else:
                current.append(char)

        if current:
            params.append(''.join(current))

        return params

    def run(self, args):
        """Run the detector."""
        if args.path and os.path.isfile(args.path):
            # Single file scan
            language = self._detect_language(args.path)
            if language:
                sink_config = self.parser_manager.get_sink_config(language)
                sinks = self.scan_file(args.path, language, sink_config, args.verbose)
            else:
                print(f"Error: Could not determine language for {args.path}")
                return 1
        else:
            # Directory scan
            languages = args.languages.split(',') if args.languages else None
            sinks = self.scan_directory(args.path, languages, args.verbose)

        self.all_sinks = sinks

        if args.verbose:
            print(f"\nTotal sinks found: {len(sinks)}")

        # Generate report
        report = self.reporter.generate_report(
            sinks,
            source_path=args.path,
            languages=args.languages.split(',') if args.languages else None,
        )

        # Write output
        output_file = args.output or 'sink_report.json'
        try:
            if output_file.endswith('.json'):
                self.reporter.write_json(report, output_file)
            elif output_file.endswith('.csv'):
                self.reporter.write_csv(sinks, output_file)
            elif output_file.endswith('.html'):
                self.reporter.write_html(report, output_file)
        except Exception as e:
            print(f"Error writing report: {e}")
            return 1

        print(f"Report written to: {output_file}")
        print(f"Total sinks detected: {len(sinks)}")

        return 0

    def _is_minified_library(self, file_path: str) -> bool:
        """Check if file is a minified JavaScript library."""
        file_name = Path(file_path).name.lower()

        # Common minified library patterns
        minified_patterns = [
            '.min.js',
            '.min.ts',
            'jquery',
            'backbone',
            'bootstrap',
            'ace.js',
            'wysihtml5',
            'moment.js',
            'lodash',
            'underscore',
            'd3.js',
            'chart.js',
            'datatables',
            'select2',
            'jqueryui',
            'popper.js',
            'mode-',  # syntax highlight plugins (mode-java.js, mode-php.js, etc.)
            'require.js',  # AMD loader
            'text.js',  # RequireJS text plugin
            'modernizr',
            'polyglot',  # i18n library
        ]

        # Check if file matches minified patterns
        for pattern in minified_patterns:
            if pattern in file_name:
                return True

        return False

    def _detect_language(self, file_path: str) -> str:
        """Detect language from file extension."""
        ext_map = {
            '.php': 'php',
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.java': 'java',
            '.go': 'go',
            '.rs': 'rust',
        }
        ext = Path(file_path).suffix
        return ext_map.get(ext)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Command Injection Sink Detector - Detects potential command injection sinks',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Scan entire directory
  python cli.py --path /app --languages php,python

  # Scan single file
  python cli.py --path /app/handler.php --output report.json

  # Scan with verbose output
  python cli.py --path /app --verbose --output report.html
        """,
    )

    parser.add_argument(
        '--path',
        required=True,
        help='Path to file or directory to scan',
    )
    parser.add_argument(
        '--languages',
        help='Comma-separated list of languages to scan (php,python,java,javascript,go,rust)',
    )
    parser.add_argument(
        '--output',
        '-o',
        help='Output file path (default: sink_report.json)',
    )
    parser.add_argument(
        '--verbose',
        '-v',
        action='store_true',
        help='Enable verbose output',
    )

    args = parser.parse_args()

    cli = CommandInjectionSinkDetectorCLI()
    return cli.run(args)


if __name__ == '__main__':
    sys.exit(main())
