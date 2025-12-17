#!/bin/bash

# SSRF Sink Detector - Scan Script
# A wrapper script to scan directories for SSRF sinks

# ===== GLOBAL CONFIGURATION =====
# Set max length of code snippet (0 = unlimited, recommended: 100-200)
MAX_SNIPPET_LENGTH=200
# =================================

# Parse options
SUMMARY_ONLY=false
LIMIT=0
HELP=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --summary)
            SUMMARY_ONLY=true
            shift
            ;;
        --limit)
            LIMIT="$2"
            shift 2
            ;;
        --help|-h)
            HELP=true
            shift
            ;;
        *)
            if [ -z "$TARGET_DIR" ]; then
                TARGET_DIR="$1"
            fi
            shift
            ;;
    esac
done

# Show help if requested
if [ "$HELP" = true ]; then
    echo "SSRF Sink Detector - Scan Script"
    echo ""
    echo "Usage: bash scan.sh [options] [path]"
    echo ""
    echo "Options:"
    echo "  --summary          Show summary only (count by language/severity)"
    echo "  --limit N          Limit output to first N results (0 = unlimited)"
    echo "  --help, -h         Show this help message"
    echo ""
    echo "Examples:"
    echo "  bash scan.sh /path/to/code"
    echo "  bash scan.sh --limit 50 /path/to/code"
    echo "  bash scan.sh --summary /path/to/code"
    exit 0
fi

# Default to current directory if not specified
TARGET_DIR="${TARGET_DIR:-.}"
# Resolve to absolute path for consistency
TARGET_DIR="$(cd "$TARGET_DIR" 2>/dev/null && pwd)" || TARGET_DIR="${TARGET_DIR:-.}"

echo "======================================"
echo "SSRF Sink Detector"
echo "======================================"
echo "Scanning directory: $TARGET_DIR"
[ "$SUMMARY_ONLY" = true ] && echo "Mode: Summary only"
[ "$LIMIT" -gt 0 ] && echo "Limit: $LIMIT results"
echo "======================================"

# Check if cli.py exists in current script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ ! -f "$SCRIPT_DIR/cli.py" ]; then
    echo "Error: cli.py not found in script directory: $SCRIPT_DIR"
    exit 1
fi

# Create temporary output file with absolute path and .json extension
TMP_OUTPUT=$(mktemp).json
export TMP_OUTPUT  # Make it available to Python
export TARGET_DIR  # Make it available to Python for relative path conversion
export SCRIPT_DIR
export SUMMARY_ONLY
export LIMIT
export MAX_SNIPPET_LENGTH

# Run the Python CLI to generate JSON report
cd "$SCRIPT_DIR" || exit 1
python3 cli.py --output json "$TARGET_DIR" > "$TMP_OUTPUT" 2>&1
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
    summary_only = os.environ.get('SUMMARY_ONLY', 'false').lower() == 'true'
    limit = int(os.environ.get('LIMIT', '0'))
    max_snippet_length = int(os.environ.get('MAX_SNIPPET_LENGTH', '150'))

    if not tmp_file:
        print("Error: TMP_OUTPUT environment variable not set", file=sys.stderr)
        sys.exit(1)

    with open(tmp_file, 'r') as f:
        content = f.read()

    # Find and extract JSON starting from first '{'
    json_start = content.find('{')
    if json_start == -1:
        print("Error: No JSON data found in output", file=sys.stderr)
        sys.exit(1)

    json_content = content[json_start:]
    data = json.loads(json_content)

    findings = data.get('findings', [])

    if not findings:
        print('No SSRF sinks found.')
        sys.exit(0)

    # Display summary if requested
    if summary_only:
        by_severity = {}
        by_language = {}
        for finding in findings:
            severity = finding.get('severity', 'unknown')
            language = finding.get('language', 'unknown')
            by_severity[severity] = by_severity.get(severity, 0) + 1
            by_language[language] = by_language.get(language, 0) + 1

        print(f'Found {len(findings)} potential SSRF sinks')
        print("")
        print("By Severity:")
        for severity in sorted(by_severity.keys()):
            count = by_severity[severity]
            print(f"  {severity.upper()}: {count}")
        print("")
        print("By Language:")
        for language in sorted(by_language.keys()):
            count = by_language[language]
            print(f"  {language}: {count}")
        sys.exit(0)

    # Apply limit if specified
    total_findings = len(findings)
    if limit > 0 and len(findings) > limit:
        findings = findings[:limit]
        print(f'Found {total_findings} potential SSRF sinks (showing first {limit}):')
    else:
        print(f'Found {len(findings)} potential SSRF sinks:')
    print("")

    # Group findings by file
    findings_by_file = {}
    for finding in findings:
        file_path = finding.get('file', 'unknown')
        try:
            rel_path = os.path.relpath(file_path, target_dir)
        except ValueError:
            rel_path = file_path

        if rel_path not in findings_by_file:
            findings_by_file[rel_path] = []
        findings_by_file[rel_path].append(finding)

    # Print findings grouped by file
    for rel_path in sorted(findings_by_file.keys()):
        print(f'File: {rel_path}')
        for finding in findings_by_file[rel_path]:
            line_num = finding.get('start_line', 0)
            column_num = finding.get('start_col', 0)
            sink_name = finding.get('sink_name', 'unknown')
            language = finding.get('language', 'unknown')
            severity = finding.get('severity', 'unknown')
            code_snippet = finding.get('code_snippet', '').replace('\n', '\\n').replace('"', '\"')

            # Skip if code_snippet is empty
            if not code_snippet or code_snippet.strip() == '':
                continue

            # Truncate snippet if it exceeds max length
            if max_snippet_length > 0 and len(code_snippet) > max_snippet_length:
                code_snippet = code_snippet[:max_snippet_length] + '...'

            print(f'  Line {line_num}:{column_num} | {sink_name} ({language}, {severity}) | {code_snippet}')

    # Show note if results were limited
    if limit > 0 and total_findings > limit:
        print("")
        print(f"Note: Showing {limit} of {total_findings} results. Use --limit to see more.")

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
