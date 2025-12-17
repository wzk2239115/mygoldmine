#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="${1:-.}"
echo "Scanning: $TARGET_DIR"
cd "$SCRIPT_DIR"
python3 cli.py --lang all "$TARGET_DIR"
