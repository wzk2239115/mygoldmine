#!/usr/bin/env python3
"""
CLI entry point for JWT sink detector.

Usage:
    python cli.py --lang python --output json /path/to/code
    python cli.py --output sarif /path/to/code
    python cli.py --output report.json /path/to/code
"""

import argparse
import sys
import os
from pathlib import Path

from core.scanner import JWTSinkScanner
from reports.json_reporter import JSONReporter
from reports.sarif_reporter import SARIFReporter


def setup_argument_parser():
    """Set up command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Detect JWT authentication operations in source code"
    )

    parser.add_argument(
        "path",
        help="Path to file or directory to scan"
    )

    parser.add_argument(
        "--lang", "--language",
        dest="language",
        help="Specific language to scan (python, php, javascript, java). If not specified, all supported languages are scanned."
    )

    parser.add_argument(
        "--output", "-o",
        dest="output",
        default="json",
        help="Output format: json, sarif, or file path (default: json). Use 'json' or 'sarif' to print to stdout, or provide a file path to save."
    )

    parser.add_argument(
        "--config",
        dest="config",
        help="Path to languages.yaml configuration file"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )

    return parser


def validate_arguments(args):
    """Validate command-line arguments."""
    if not os.path.exists(args.path):
        print(f"Error: Path does not exist: {args.path}", file=sys.stderr)
        sys.exit(1)

    if args.language:
        valid_languages = {"python", "php", "javascript", "java"}
        if args.language.lower() not in valid_languages:
            print(
                f"Error: Invalid language '{args.language}'. "
                f"Supported: {', '.join(valid_languages)}",
                file=sys.stderr
            )
            sys.exit(1)

    if args.config and not os.path.exists(args.config):
        print(f"Error: Config file not found: {args.config}", file=sys.stderr)
        sys.exit(1)


def determine_output_format(output_str):
    """Determine output format and file path."""
    output_lower = output_str.lower()

    if output_lower in ("json", "sarif"):
        return output_lower, None
    else:
        # It's a file path
        ext = Path(output_str).suffix.lower()
        if ext == ".json":
            return "json", output_str
        elif ext == ".sarif":
            return "sarif", output_str
        else:
            # Default to JSON if extension is unknown
            return "json", output_str


def main():
    """Main CLI entry point."""
    parser = setup_argument_parser()
    args = parser.parse_args()

    validate_arguments(args)

    output_format, output_file = determine_output_format(args.output)

    if args.verbose:
        print(f"[*] Scanning: {args.path}")
        print(f"[*] Output format: {output_format}")
        if output_file:
            print(f"[*] Output file: {output_file}")

    try:
        # Initialize scanner
        scanner = JWTSinkScanner(config_path=args.config)

        # Scan path
        scan_path = args.path
        if os.path.isfile(scan_path):
            findings = scanner.scan_file(scan_path)
        else:
            findings = scanner.scan_directory(scan_path)

        if args.verbose:
            summary = scanner.get_summary()
            print(f"\n[+] Scan complete!")
            print(f"[+] Total findings: {summary['total_findings']}")
            for lang, count in summary['by_language'].items():
                print(f"    - {lang}: {count}")

        # Generate and output report
        if output_format == "json":
            reporter = JSONReporter(output_file)
            reporter.add_findings(findings)

            if output_file:
                output_path = reporter.write_report()
                if args.verbose:
                    print(f"[+] Report written to: {output_path}")
                else:
                    print(f"Report written to: {output_path}")
            else:
                print(reporter.get_json_string())

        elif output_format == "sarif":
            reporter = SARIFReporter(output_file)
            reporter.add_findings(findings)

            if output_file:
                output_path = reporter.write_report()
                if args.verbose:
                    print(f"[+] Report written to: {output_path}")
                else:
                    print(f"Report written to: {output_path}")
            else:
                print(reporter.get_sarif_string())

        # Exit with error code if findings detected
        if len(findings) > 0:
            sys.exit(1)
        else:
            sys.exit(0)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(2)


if __name__ == "__main__":
    main()
