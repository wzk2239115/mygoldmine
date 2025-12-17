#!/usr/bin/env python3
"""CLI interface for CSRF sink detector."""

import argparse
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from core.scanner import CSRFSinkScanner
from reports.json_reporter import JSONReporter
from reports.sarif_reporter import SARIFReporter


class CSRFDetectorCLI:
    """CLI interface for CSRF sink detector."""

    def __init__(self):
        """Initialize CLI."""
        self.scanner = CSRFSinkScanner()
        self.json_reporter = JSONReporter(pretty_print=True, include_context=True)
        self.sarif_reporter = SARIFReporter()
        self.all_sinks = []

    def scan_directory(
        self,
        directory: str,
        languages: list = None,
        verbose: bool = False,
    ):
        """Scan directory for CSRF sinks."""
        sinks = self.scanner.scan_directory(directory, languages, verbose)
        self.all_sinks.extend(sinks)
        return sinks

    def scan_file(self, filepath: str, language: str = None):
        """Scan single file for CSRF sinks."""
        sinks = self.scanner.scan_file(filepath, language)
        self.all_sinks.extend(sinks)
        return sinks

    def output_results(
        self,
        sinks: list,
        output_file: str = None,
        output_format: str = 'json',
        verbose: bool = False,
    ):
        """Output results in specified format."""
        if not sinks:
            print("No CSRF sinks detected.")
            return

        if verbose:
            print(f"\nFound {len(sinks)} CSRF sinks:")
            for sink in sinks:
                print(f"  {sink['file']}:{sink['line']} - {sink['type']}")

        if output_format == 'json':
            output_str = self.json_reporter.report_to_string(sinks)
            if output_file:
                self.json_reporter.save_report(sinks, output_file)
                print(f"JSON report saved to {output_file}")
            else:
                print(output_str)

        elif output_format == 'sarif':
            base_path = os.getcwd()
            output_str = self.sarif_reporter.report_to_string(sinks, base_path)
            if output_file:
                self.sarif_reporter.save_report(sinks, output_file, base_path)
                print(f"SARIF report saved to {output_file}")
            else:
                print(output_str)

    def run(self):
        """Run CLI."""
        parser = argparse.ArgumentParser(
            description='CSRF sink detector - identifies state-changing endpoints'
        )

        parser.add_argument(
            'target',
            help='Target directory or file to scan'
        )

        parser.add_argument(
            '--lang',
            nargs='+',
            default=None,
            choices=['php', 'python', 'java', 'javascript', 'typescript'],
            help='Languages to scan (default: all enabled)'
        )

        parser.add_argument(
            '--output',
            '-o',
            default=None,
            help='Output file path'
        )

        parser.add_argument(
            '--format',
            '-f',
            default='json',
            choices=['json', 'sarif'],
            help='Output format (default: json)'
        )

        parser.add_argument(
            '--verbose',
            '-v',
            action='store_true',
            help='Verbose output'
        )

        args = parser.parse_args()

        # Check if target exists
        if not os.path.exists(args.target):
            print(f"Error: Target '{args.target}' not found", file=sys.stderr)
            return 1

        # Scan target
        if os.path.isdir(args.target):
            if args.verbose:
                print(f"Scanning directory: {args.target}")
            sinks = self.scan_directory(args.target, args.lang, args.verbose)
        else:
            if args.verbose:
                print(f"Scanning file: {args.target}")
            sinks = self.scan_file(args.target, args.lang[0] if args.lang else None)

        # Output results
        self.output_results(sinks, args.output, args.format, args.verbose)

        return 0


def main():
    """Main entry point."""
    cli = CSRFDetectorCLI()
    return cli.run()


if __name__ == '__main__':
    sys.exit(main())
