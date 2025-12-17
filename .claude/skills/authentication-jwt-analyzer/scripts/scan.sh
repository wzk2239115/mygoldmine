#!/bin/bash
#
# JWT Sink Detector - Scan script
# Detects JWT authentication operations in source code
#

# Don't exit on error - cli.py returns 1 when findings are detected


# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Get target directory (save original before expansion)
TARGET_ORIG="${1:-.}"
TARGET="${TARGET_ORIG}"

# Expand ~ manually if present, but keep track of original
if [[ "$TARGET" == "~"* ]]; then
    TARGET="${TARGET/#\~/$HOME}"
fi

DISPLAY_TARGET="$TARGET_ORIG"  # Save the original path for display

# Default output format
OUTPUT_FORMAT="${OUTPUT_FORMAT:-json}"
VERBOSE="${VERBOSE:-false}"

# Convert to absolute path if not already
if [ ! -d "$TARGET" ]; then
    echo "Error: Target directory '$TARGET' not found" >&2
    exit 1
fi

TARGET="$(cd "$TARGET" && pwd)"

# Create output directory if needed
OUTPUT_DIR="${SCRIPT_DIR}/reports"
mkdir -p "$OUTPUT_DIR"

# Generate output filename with timestamp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTPUT_FILE="${OUTPUT_DIR}/jwt_sink_report_${TIMESTAMP}.${OUTPUT_FORMAT}"

echo "JWT Sink Detector"
echo "================="
echo ""
echo "Target directory: $DISPLAY_TARGET"
echo "Output format: $OUTPUT_FORMAT"
echo ""

# Run the scanner with proper PYTHONPATH
export PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH"
if [ "$VERBOSE" = "true" ]; then
    python3 "$SCRIPT_DIR/cli.py" \
        --output "$OUTPUT_FILE" \
        --verbose \
        "$TARGET"
else
    python3 "$SCRIPT_DIR/cli.py" \
        --output "$OUTPUT_FILE" \
        "$TARGET"
fi

EXIT_CODE=$?

# cli.py returns 0 if no findings, 1 if findings detected, 2 for errors
# We treat both 0 and 1 as success
if [ $EXIT_CODE -eq 0 ] || [ $EXIT_CODE -eq 1 ]; then
    echo ""

    # Parse and display JSON report
    if [ "$OUTPUT_FORMAT" = "json" ]; then
        python3 << EOF
import json
import os
import sys
from pathlib import Path

output_file = "$OUTPUT_FILE"
target = "$TARGET"
display_target = "$DISPLAY_TARGET"
MAX_CODE_LENGTH = 100

try:
    with open(output_file, 'r') as f:
        data = json.load(f)

    summary = data.get('summary', {})
    total_sinks = summary.get('total_findings', 0)  # JWT uses total_findings
    by_type = summary.get('by_language', {})  # JWT uses by_language instead of by_type
    sinks = data.get('findings', [])  # JWT uses findings instead of sinks

    print("Scan completed successfully!")
    print(f"Total JWT sinks found: {total_sinks}")
    print()

    if by_type:
        print("By language:")
        for lang, count in by_type.items():
            print(f"  {lang}: {count}")
        print()

    if sinks:
        print("Matched content:")
        for sink in sinks:
            file_path = sink.get('file', '')
            line = sink.get('line', '')
            column = sink.get('column', '')
            code_snippet = sink.get('code_snippet', '')

            # Truncate code if too long
            if len(code_snippet) > MAX_CODE_LENGTH:
                code_snippet = code_snippet[:MAX_CODE_LENGTH] + "..."

            # Show relative path based on the absolute target
            try:
                rel_path = os.path.relpath(file_path, target)
                # If display_target is not absolute, prepend it
                if not os.path.isabs(display_target) and display_target != ".":
                    rel_path = os.path.join(display_target, rel_path)
            except ValueError:
                rel_path = file_path

            print(f"  {rel_path}:{line}:{column}")
            print(f"    {code_snippet}")
    else:
        print("No JWT sinks found")

except Exception as e:
    print(f"Error parsing report: {e}", file=sys.stderr)
    sys.exit(1)
EOF
    else
        echo "Scan completed successfully!"
        echo "Report saved to: $OUTPUT_FILE"
    fi
else
    echo "Scan failed with exit code $EXIT_CODE" >&2
    exit $EXIT_CODE
fi
