#!/bin/bash

echo "=== Debug Scan Script ==="

# Create temp file
TMP_OUTPUT=$(mktemp)
echo "Temp file: $TMP_OUTPUT"

# Run CLI
echo "Running CLI..."
python3 cli.py --path /home/wangzekai/sqli-labs/ --output "$TMP_OUTPUT" > /dev/null 2>&1
CLI_EXIT_CODE=$?

echo "CLI exit code: $CLI_EXIT_CODE"
echo "Temp file exists: $([ -f "$TMP_OUTPUT" ] && echo 'yes' || echo 'no')"
if [ -f "$TMP_OUTPUT" ]; then
    echo "Temp file size: $(wc -c < "$TMP_OUTPUT")"
    echo "First 200 chars:"
    head -c 200 "$TMP_OUTPUT"
    echo ""
fi

# Clean up
rm -f "$TMP_OUTPUT"
echo "=== Debug Complete ==="