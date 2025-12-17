#!/bin/bash

# SQL Injection Sink Detector - Scan Script
# A wrapper script to scan directories for SQL injection sinks

echo "======================================"
echo "SQL Injection Sink Detector"
echo "======================================"

# Target directory (default: current directory)
TARGET_DIR="${1:-.}"
# Resolve to absolute path for consistency
TARGET_DIR="$(cd "$TARGET_DIR" 2>/dev/null && pwd)" || TARGET_DIR="${1:-.}"

echo "Scanning directory: $TARGET_DIR"
echo "======================================"

# Check if cli.py exists
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ ! -f "$SCRIPT_DIR/cli.py" ]; then
    echo "Error: cli.py not found in script directory"
    exit 1
fi

# Create temporary output file with absolute path and .json extension
TMP_OUTPUT=$(mktemp).json
export TMP_OUTPUT  # Make it available to Python
export TARGET_DIR  # Make it available to Python for relative path conversion

# Run the Python CLI
cd "$SCRIPT_DIR"
python3 cli.py --path "$TARGET_DIR" --output "$TMP_OUTPUT" >/dev/null 2>&1
CLI_EXIT_CODE=$?

# Check if scan was successful and format output
if [ $CLI_EXIT_CODE -eq 0 ] && [ -f "$TMP_OUTPUT" ] && [ -s "$TMP_OUTPUT" ]; then
    python3 << 'PYEOF'
import sys
import json
import os
from pathlib import Path

try:
    # Read JSON from temporary file using environment variable
    tmp_file = os.environ.get('TMP_OUTPUT')
    target_dir = os.environ.get('TARGET_DIR', '.')

    if not tmp_file:
        print("Error: TMP_OUTPUT environment variable not set", file=sys.stderr)
        sys.exit(1)

    with open(tmp_file, 'r') as f:
        data = json.load(f)

    sinks = data.get('sinks', [])

    if not sinks:
        print('No SQL injection sinks found.')
        sys.exit(0)

    print(f'Found {len(sinks)} potential SQL injection sinks:')
    print("")

    for sink in sinks:
        file_path = sink.get('file', 'unknown')
        line_num = sink.get('line', 0)
        column_num = sink.get('column', 0)
        sink_type = sink.get('sink_type', 'unknown')
        category = sink.get('category', 'unknown')
        context = sink.get('context', '').replace('\n', '\\n').replace('"', '\"')

        # Skip if context is empty
        if not context or context.strip() == '':
            continue

        # Convert to relative path if possible
        try:
            rel_path = os.path.relpath(file_path, target_dir)
        except ValueError:
            # On Windows, relpath fails if paths are on different drives
            rel_path = file_path

        print(f'file: {rel_path},line: {line_num},column: {column_num},sink_type: {sink_type},category: {category},context: "{context}"')

except json.JSONDecodeError as e:
    print(f'Error: Failed to parse scan results - {e}', file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f'Error: {e}', file=sys.stderr)
    sys.exit(1)
PYEOF
    FORMAT_EXIT_CODE=$?

    # Clean up
    rm -f "$TMP_OUTPUT"

    if [ $FORMAT_EXIT_CODE -eq 0 ]; then
        echo ""
        echo "Scan completed!"
    else
        exit 1
    fi
else
    echo ""
    echo "Scan failed or no output generated!"
    rm -f "$TMP_OUTPUT"
    exit 1
fi
