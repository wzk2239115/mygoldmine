#!/bin/bash

# Mass Assignment Sink Detector - Bash wrapper script
# Usage: bash scan.sh /path/to/code [options]
# Examples:
#   bash scan.sh ~/WebGoat
#   bash scan.sh ~/WebGoat --lang python
#   bash scan.sh ~/WebGoat --output sarif
#   bash scan.sh ~/WebGoat --report output.json

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Check if target path is provided
if [ -z "$1" ]; then
    echo "Usage: bash scan.sh <target_path> [options]"
    echo ""
    echo "Arguments:"
    echo "  target_path   Target file or directory to scan"
    echo ""
    echo "Options:"
    echo "  --lang LANG         Programming language (php, python, java, javascript, c, go, rust)"
    echo "  --output FORMAT     Output format: json or sarif (default: json)"
    echo "  --report FILE       Save report to file (default: stdout)"
    echo "  --config FILE       Config file path"
    echo ""
    echo "Examples:"
    echo "  bash scan.sh ~/WebGoat"
    echo "  bash scan.sh ~/WebGoat --lang python"
    echo "  bash scan.sh ~/WebGoat --output sarif"
    echo "  bash scan.sh ~/WebGoat --report findings.json"
    exit 1
fi

# Get the target path (expand ~ if present)
TARGET="${1/#\~/$HOME}"

# Run the Python CLI with all arguments
cd "$SCRIPT_DIR"
python3 cli.py "$TARGET" "${@:2}"
