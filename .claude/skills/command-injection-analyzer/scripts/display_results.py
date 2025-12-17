#!/usr/bin/env python3
"""Display command injection detection results."""

import json
import sys
import os
import time
from pathlib import Path
from collections import defaultdict

def display_results(json_file):
    """Display results from JSON report - grouped by file with relative paths."""
    # Wait for file to be written
    for i in range(10):
        if os.path.getsize(json_file) > 0:
            break
        time.sleep(0.1)

    try:
        with open(json_file) as f:
            data = json.load(f)

        sinks = data['sinks']
        source_path = data['metadata'].get('source_path', '')

        # Print header
        print(f"\n{'='*120}")
        print(f"Command Injection Sinks Found: {len(sinks)}")
        print(f"{'='*120}\n")

        if sinks:
            # Group sinks by file
            sinks_by_file = defaultdict(list)
            for sink in sinks:
                sinks_by_file[sink['file']].append(sink)

            # Convert source_path to absolute path for comparison
            source_abs = os.path.abspath(source_path) if source_path else None

            # Sort files by name
            for file_path in sorted(sinks_by_file.keys()):
                file_sinks = sinks_by_file[file_path]

                # Convert to relative path based on source_path
                try:
                    if source_abs:
                        rel_path = os.path.relpath(file_path, source_abs)
                    else:
                        rel_path = file_path
                except ValueError:
                    # On Windows, relpath may fail if paths are on different drives
                    rel_path = file_path

                # Print file header
                print(f"\n📄 {rel_path}  ({len(file_sinks)} sinks)")
                print(f"   {'-'*110}")

                # Print column headers
                print(f"   {'Line:Col':<10} {'Function':<20} {'Category':<20} {'Parameters':<55}")
                print(f"   {'-'*10} {'-'*20} {'-'*20} {'-'*55}")

                # Print sinks for this file
                for sink in file_sinks:
                    line_col = f"{sink['line']}:{sink['column']}"
                    func = sink['sink_type']
                    category = sink['sink_category']

                    # Get parameters
                    params = ', '.join(sink['parameters'][:2]) if sink['parameters'] else ''
                    if len(params) > 55:
                        params = params[:52] + '...'

                    print(f"   {line_col:<10} {func:<20} {category:<20} {params:<55}")

        print(f"\n{'='*120}")
        print(f"Summary:")
        print(f"  Total Sinks: {data['metadata']['total_sinks']}")

        by_category = data['summary']['by_category']
        if by_category:
            print(f"  By Category:")
            for cat, count in sorted(by_category.items()):
                print(f"    - {cat}: {count}")

        by_file = data['summary']['by_file']
        if by_file:
            print(f"  By File:")
            for file, count in sorted(by_file.items(), key=lambda x: -x[1]):
                try:
                    if source_abs:
                        rel_path = os.path.relpath(file, source_abs)
                    else:
                        rel_path = file
                except ValueError:
                    rel_path = file
                print(f"    - {rel_path}: {count} sinks")

        print(f"{'='*120}\n")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: display_results.py <json_file>", file=sys.stderr)
        sys.exit(1)

    display_results(sys.argv[1])
