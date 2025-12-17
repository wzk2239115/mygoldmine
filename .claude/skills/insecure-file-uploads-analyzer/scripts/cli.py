#!/usr/bin/env python3
"""Command-line interface for insecure upload sink detector"""
import sys
import argparse
import json
import os
from pathlib import Path
from core.scanner import SinkDetector, Sink
from reports import JSONReporter, SARIFReporter

def create_demo_sinks(file_path):
    """Create demo sinks for testing"""
    # Demo sinks for testing purposes
    sinks = []

    # Skip certain files that are known to have false positives
    skip_patterns = ['jquery', 'modernizr', 'bootstrap', '.min.js', 'libs/', 'plugin']
    if any(skip in file_path.lower() for skip in skip_patterns):
        return sinks

    # Try to find actual vulnerabilities in PHP/Python files
    try:
        with open(file_path, 'r', errors='ignore') as f:
            content = f.read()
            lines = content.split('\n')

            # PHP patterns - more specific to avoid false positives
            php_patterns = [
                ('move_uploaded_file', 'file_write'),
                ('file_put_contents', 'file_write'),
                ('require_once', 'file_include'),
                ('require', 'file_include'),
                ('include_once', 'file_include'),
                ('include', 'file_include'),
                ('unserialize', 'unsafe_deserialize'),
            ]

            # Python patterns - more specific
            python_patterns = [
                ('shutil.move', 'file_operation'),
                ('os.path.join', 'path_operation'),
                ('pickle.load', 'unsafe_deserialize'),
            ]

            patterns = php_patterns if file_path.endswith('.php') else python_patterns

            for i, line in enumerate(lines):
                # Skip comments and minified code
                stripped = line.strip()
                if stripped.startswith('//') or stripped.startswith('#'):
                    continue

                for pattern, sink_type in patterns:
                    if pattern in line:
                        sinks.append(Sink(
                            line=i + 1,
                            column=line.find(pattern),
                            sink_type=sink_type,
                            function_name=pattern.replace('(', '').strip(),
                            file_path=file_path,
                            code_snippet=line.strip()[:100]
                        ))
    except:
        pass

    return sinks

def scan_files(path, language=None, recursive=True):
    """Scan files for sinks"""
    sinks = []

    path_obj = Path(path)
    if path_obj.is_file():
        sinks.extend(create_demo_sinks(str(path_obj)))
    elif path_obj.is_dir():
        pattern = '**/*' if recursive else '*'
        for file_path in path_obj.glob(pattern):
            if file_path.is_file():
                # Filter by language if specified
                if language:
                    ext_map = {
                        'php': ['.php', '.php5'],
                        'python': ['.py'],
                        'java': ['.java'],
                        'javascript': ['.js', '.jsx', '.ts', '.tsx']
                    }
                    if language in ext_map and file_path.suffix not in ext_map[language]:
                        continue

                sinks.extend(create_demo_sinks(str(file_path)))

    return sinks

def main():
    parser = argparse.ArgumentParser(description='Insecure Upload Sink Detector')
    parser.add_argument('path', help='Path to file or directory to scan')
    parser.add_argument('--lang', '--language', help='Programming language (php, python, java, javascript)')
    parser.add_argument('--all', action='store_true', help='Scan all languages')
    parser.add_argument('-o', '--output', choices=['text', 'json', 'sarif'], default='text', help='Output format')
    parser.add_argument('-r', '--report', help='Save report to file')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    parser.add_argument('--no-recursive', action='store_true', help='Non-recursive scan')

    args = parser.parse_args()

    # Determine language
    language = args.lang if args.lang else None

    # Scan files
    sinks = scan_files(args.path, language=language, recursive=not args.no_recursive)

    # Generate report
    if args.output == 'json':
        reporter = JSONReporter()
        reporter.add_sinks(sinks)
        report = reporter.generate_report(args.report)
        if not args.report:
            print(report)
        elif args.verbose:
            print(f"Report saved to: {args.report}")

    elif args.output == 'sarif':
        reporter = SARIFReporter()
        reporter.add_sinks(sinks)
        report = reporter.generate_report(args.report)
        if not args.report:
            print(report)
        elif args.verbose:
            print(f"Report saved to: {args.report}")

    else:  # text output
        if sinks:
            print(f"Found {len(sinks)} potential file upload sinks:\n")

            # Get the base path for relative path calculation
            base_path = Path(args.path).resolve()
            if base_path.is_file():
                base_path = base_path.parent

            by_file = {}
            for sink in sinks:
                if sink.file_path not in by_file:
                    by_file[sink.file_path] = []
                by_file[sink.file_path].append(sink)

            for file_path in sorted(by_file.keys()):
                # Convert absolute path to relative path
                try:
                    rel_path = Path(file_path).relative_to(base_path)
                    display_path = str(rel_path)
                except ValueError:
                    # If relative path calculation fails, use original path
                    display_path = file_path
                
                print(f"File: {display_path}")
                for sink in by_file[file_path]:
                    print(f"  Line {sink.line}:{sink.column} | {sink.sink_type:20s} | {sink.function_name:25s} | {sink.code_snippet}")
                print()
        else:
            print("No file upload sinks found.")

if __name__ == '__main__':
    main()
