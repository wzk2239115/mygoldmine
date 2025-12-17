#!/bin/bash

# Simple test version of scan.sh
echo "=== Simple Scan Test ==="

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="${1:-.}"

# Use a fixed temp file in /tmp
TMP_OUTPUT="/tmp/sink_scan_$$.json"
echo "Using temp file: $TMP_OUTPUT"

# Run CLI
cd "$SCRIPT_DIR"
python3 cli.py --path "$TARGET_DIR" --output "$TMP_OUTPUT"
CLI_EXIT_CODE=$?

echo "CLI exit code: $CLI_EXIT_CODE"
echo "File exists: $([ -f "$TMP_OUTPUT" ] && echo 'yes' || echo 'no')"
if [ -f "$TMP_OUTPUT" ]; then
    echo "File size: $(wc -c < "$TMP_OUTPUT")"
    echo "First 100 chars:"
    head -c 100 "$TMP_OUTPUT"
    echo ""
fi

# Clean up
rm -f "$TMP_OUTPUT"
echo "=== Test Complete ==="