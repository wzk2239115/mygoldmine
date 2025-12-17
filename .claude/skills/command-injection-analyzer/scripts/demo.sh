#!/bin/bash
# Command Injection Sink Detector - Demo Script
# This script demonstrates the capabilities of the detector

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "Command Injection Sink Detector Demo"
echo "=========================================="
echo

# Ensure dependencies are installed
echo "[1/5] Installing dependencies..."
pip install -q -r requirements.txt
echo "✓ Dependencies installed"
echo

# Run tests
echo "[2/5] Running unit tests..."
python3 -m unittest tests.test_scanner -q
echo "✓ All tests passed"
echo

# Scan fixtures directory
echo "[3/5] Scanning test fixtures..."
python3 cli.py --path tests/fixtures --languages php,python,java,javascript,go,rust \
  --output demo_report.json --verbose 2>&1 | tail -5
echo "✓ Scanning complete"
echo

# Show results summary
echo "[4/5] Analysis Results:"
python3 << 'EOF'
import json
with open('demo_report.json', 'r') as f:
    report = json.load(f)

print(f"Total sinks detected: {report['metadata']['total_sinks']}")
print("\nSinks by category:")
for category, count in sorted(report['summary']['by_category'].items()):
    print(f"  {category}: {count}")

print("\nSinks by language:")
by_lang = {}
for sink in report['sinks']:
    file_path = sink['file']
    # Extract language from file extension
    lang = file_path.split('.')[-1]
    by_lang[lang] = by_lang.get(lang, 0) + 1

for lang, count in sorted(by_lang.items()):
    print(f"  {lang.upper()}: {count}")
EOF

echo

# Generate HTML report
echo "[5/5] Generating HTML report..."
python3 cli.py --path tests/fixtures --languages php,python \
  --output demo_report.html -q
echo "✓ HTML report generated: demo_report.html"
echo

echo "=========================================="
echo "Demo Complete!"
echo "=========================================="
echo
echo "Generated files:"
echo "  - demo_report.json: Detailed JSON report"
echo "  - demo_report.html: Human-readable HTML report"
echo
echo "Next steps:"
echo "  1. Review the JSON report: less demo_report.json"
echo "  2. Open HTML report in browser: open demo_report.html"
echo "  3. Run detector on your code: python3 cli.py --path /your/code"
echo
