#!/usr/bin/env python3
"""
CLI entry point for insecure deserialization sink detector.

Usage:
    python cli.py --lang php /path/to/code
    python cli.py --lang python --output json report.json /path/to/code
    python cli.py --output sarif report.sarif /path/to/code
"""

import argparse
import os
import sys
from pathlib import Path

from core.scanner import Scanner
from reports.json_reporter import JSONReporter, SARIFReporter, PlainTextReporter


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Detect insecure deserialization sinks in source code',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Scan a directory for PHP vulnerabilities
  python cli.py --lang php /path/to/code

  # Scan with JSON output
  python cli.py --lang python --output json report.json /path/to/code

  # Scan with SARIF output (all languages)
  python cli.py --output sarif report.sarif /path/to/code

  # Auto-detect language
  python cli.py /path/to/code
        """
    )

    parser.add_argument(
        'path',
        help='File or directory to scan'
    )

    parser.add_argument(
        '--lang',
        '--language',
        dest='language',
        help='Programming language (php, python, java, javascript, typescript, c, cpp, go, rust)',
        choices=['php', 'python', 'java', 'javascript', 'typescript', 'c', 'cpp', 'go', 'rust'],
        default=None
    )

    parser.add_argument(
        '--output',
        '-o',
        dest='output_format',
        help='Output format (json, sarif, text)',
        choices=['json', 'sarif', 'text'],
        default='text'
    )

    parser.add_argument(
        '--report',
        '-r',
        dest='report_file',
        help='Output report file path',
        default=None
    )

    parser.add_argument(
        '--recursive',
        '-R',
        action='store_true',
        help='Recursively scan directories',
        default=True
    )

    parser.add_argument(
        '--verbose',
        '-v',
        action='store_true',
        help='Verbose output'
    )

    args = parser.parse_args()

    # Validate path
    if not os.path.exists(args.path):
        print(f"Error: Path not found: {args.path}", file=sys.stderr)
        sys.exit(1)

    # Initialize scanner
    scanner = Scanner()

    if args.verbose:
        print(f"[*] Scanning: {args.path}")
        if args.language:
            print(f"[*] Language: {args.language}")

    # Perform scan
    try:
        if os.path.isfile(args.path):
            sinks = scanner.scan_file(args.path, language=args.language)
        else:
            sinks = scanner.scan_directory(
                args.path,
                language=args.language,
                recursive=args.recursive
            )
    except Exception as e:
        print(f"Error scanning path: {e}", file=sys.stderr)
        sys.exit(1)

    # Generate report
    if args.output_format == 'json':
        report = JSONReporter.generate(sinks, output_file=args.report_file)
    elif args.output_format == 'sarif':
        report = SARIFReporter.generate(sinks, output_file=args.report_file)
    else:  # text format (default)
        report = PlainTextReporter.generate(sinks, output_file=args.report_file, base_dir=args.path)

    # Output results
    if args.report_file:
        print(f"[+] Report saved to: {args.report_file}", file=sys.stderr)
    else:
        print(report)

    if args.verbose:
        print(f"[*] Found {len(sinks)} sink(s)", file=sys.stderr)

    # Exit with appropriate code
    sys.exit(0 if len(sinks) == 0 else 1)


if __name__ == '__main__':
    main()
