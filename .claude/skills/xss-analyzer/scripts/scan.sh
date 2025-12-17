#!/bin/bash

# XSS Sink Detector Scan Script

if [ $# -eq 0 ]; then
    echo "Usage: bash scan.sh <path> [options]"
    echo ""
    echo "Examples:"
    echo "  bash scan.sh ~/project                    # scan directory in text format"
    echo "  bash scan.sh ~/project --output json      # output in JSON format"
    echo "  bash scan.sh file.js                      # scan single file"
    echo ""
    exit 1
fi

# Get the xss directory (parent of scripts directory)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
XSS_DIR="$(dirname "$SCRIPT_DIR")"

# Run Python CLI from the xss directory
cd "$XSS_DIR" || exit 1
python -m scripts.cli "$@"
