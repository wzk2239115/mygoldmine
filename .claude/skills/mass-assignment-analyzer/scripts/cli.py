#!/usr/bin/env python3
"""
CLI: Command-line interface for mass assignment sink detector
Usage: python cli.py --lang python --output json /path/to/code
"""
import argparse
import os
import sys
from pathlib import Path

from core.scanner import Scanner
from reports.json_reporter import JSONReporter
from reports.sarif_reporter import SARIFReporter


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description='Mass Assignment Sink Detector - Detect mass assignment vulnerabilities',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Scan Python files
  python cli.py --lang python --output json /path/to/code

  # Scan all supported languages in directory
  python cli.py --output sarif /path/to/code

  # Save report to file
  python cli.py --lang php --output json --report output.json /path/to/code
        '''
    )

    parser.add_argument(
        'target',
        help='Target file or directory to scan'
    )

    parser.add_argument(
        '--lang', '-l',
        help='Programming language (php, python, java, javascript). Auto-detect if not specified',
        default=None
    )

    parser.add_argument(
        '--output', '-o',
        choices=['json', 'sarif'],
        default='json',
        help='Output format (default: json)'
    )

    parser.add_argument(
        '--report', '-r',
        help='Output file path for report (default: stdout)',
        default=None
    )

    parser.add_argument(
        '--config', '-c',
        help='Config file path',
        default=None
    )

    args = parser.parse_args()

    # Validate target
    if not os.path.exists(args.target):
        print(f"Error: Target '{args.target}' does not exist")
        sys.exit(1)

    try:
        # Initialize scanner
        scanner = Scanner(args.config)

        # Check language support
        if args.lang and not scanner.parser_manager.supports_language(args.lang):
            print(f"Error: Language '{args.lang}' is not supported")
            print(f"Supported languages: {', '.join(scanner.parser_manager.get_supported_languages())}")
            sys.exit(1)

        # Scan target
        print(f"Scanning {args.target}...")

        if os.path.isfile(args.target):
            findings = scanner.scan_file(args.target)
        else:
            findings = scanner.scan_directory(args.target)

        # Generate report
        if args.output == 'json':
            reporter = JSONReporter()
        else:  # sarif
            reporter = SARIFReporter()

        reporter.add_findings(findings)
        report_content = reporter.generate()

        # Output report
        if args.report:
            reporter.save(args.report)
        else:
            print("\n" + "="*60)
            print(f"Findings: {len(findings)}")
            print("="*60)
            print(report_content)

        return 0 if len(findings) == 0 else 1

    except KeyboardInterrupt:
        print("\nScanning interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    sys.exit(main())
