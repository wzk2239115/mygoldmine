#!/usr/bin/env python3
"""CLI entry point for SSRF Sink Detector."""

import argparse
import sys
from pathlib import Path
from core.scanner import Scanner
from reports.json_reporter import JSONReporter
from reports.sarif_reporter import SARIFReporter


def get_config_path() -> str:
    """Get path to languages.yaml configuration file."""
    current_dir = Path(__file__).parent
    config_path = current_dir / 'config' / 'languages.yaml'
    return str(config_path)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='SSRF Sink Detector - Static analysis tool for Server-Side Request Forgery vulnerabilities',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cli.py --lang php /path/to/code
  python cli.py --lang python --output json /path/to/code
  python cli.py --all --output sarif /path/to/code
  python cli.py --lang javascript --output both --json-out report.json --sarif-out report.sarif /path/to/code
        """
    )

    parser.add_argument(
        'path',
        help='Path to file or directory to scan'
    )
    parser.add_argument(
        '--lang',
        choices=['php', 'python', 'java', 'javascript', 'typescript', 'c', 'cpp', 'go', 'rust'],
        help='Programming language to scan (default: auto-detect by file extension)'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Scan all supported languages'
    )
    parser.add_argument(
        '--output',
        choices=['json', 'sarif', 'both', 'text'],
        default='text',
        help='Output format (default: text)'
    )
    parser.add_argument(
        '--json-out',
        metavar='FILE',
        help='Output file for JSON report'
    )
    parser.add_argument(
        '--sarif-out',
        metavar='FILE',
        help='Output file for SARIF report'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )

    args = parser.parse_args()

    # Validate path
    path = Path(args.path)
    if not path.exists():
        print(f"Error: Path not found: {args.path}", file=sys.stderr)
        return 1

    # Initialize scanner
    config_path = get_config_path()
    if not Path(config_path).exists():
        print(f"Error: Configuration file not found: {config_path}", file=sys.stderr)
        return 1

    scanner = Scanner(config_path)

    # Perform scan
    if args.verbose:
        print(f"Scanning: {path}", file=sys.stderr)
        if args.lang:
            print(f"Language: {args.lang}", file=sys.stderr)

    try:
        if path.is_file():
            findings = scanner.scan_file(str(path))
        else:
            findings = scanner.scan_directory(str(path))
    except Exception as e:
        print(f"Error during scan: {e}", file=sys.stderr)
        return 1

    # Display results
    if args.output == 'text':
        if not findings:
            print("No SSRF sinks detected.")
        else:
            print_text_report(findings)
    elif args.output in ('json', 'both'):
        json_output = args.json_out or 'report.json'
        json_report = JSONReporter.generate(findings, json_output)
        if args.output == 'json':
            print(json_report)
        else:
            print(f"JSON report written to: {json_output}", file=sys.stderr)

    if args.output in ('sarif', 'both'):
        sarif_output = args.sarif_out or 'report.sarif'
        sarif_report = SARIFReporter.generate(findings, sarif_output)
        if args.output == 'sarif':
            print(sarif_report)
        else:
            print(f"SARIF report written to: {sarif_output}", file=sys.stderr)

    return 0


def print_text_report(findings):
    """Print findings in human-readable text format."""
    print(f"\n{'=' * 80}")
    print(f"SSRF Sink Detection Results")
    print(f"{'=' * 80}")
    print(f"Total findings: {len(findings)}\n")

    for idx, finding in enumerate(findings, 1):
        print(f"{idx}. {finding.get('sink_name', 'Unknown')}")
        print(f"   File: {finding.get('file', 'Unknown')}")
        print(f"   Line: {finding.get('start_line', '?')}:{finding.get('start_col', '?')}")
        print(f"   Language: {finding.get('language', 'Unknown')}")
        print(f"   Severity: {finding.get('severity', 'Unknown').upper()}")
        print(f"   Code: {finding.get('code_snippet', 'N/A')}")
        print()

    # Summary
    by_severity = {}
    by_language = {}
    for finding in findings:
        severity = finding.get('severity', 'unknown')
        language = finding.get('language', 'unknown')
        by_severity[severity] = by_severity.get(severity, 0) + 1
        by_language[language] = by_language.get(language, 0) + 1

    print(f"{'=' * 80}")
    print("Summary by Severity:")
    for severity, count in sorted(by_severity.items()):
        print(f"  {severity.upper()}: {count}")

    print("\nSummary by Language:")
    for language, count in sorted(by_language.items()):
        print(f"  {language}: {count}")
    print(f"{'=' * 80}\n")


if __name__ == '__main__':
    sys.exit(main())
