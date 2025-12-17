#!/bin/bash

# Insecure Deserialization Sink Detector - Quick Start Guide
#
# This script demonstrates the basic usage of the scan tool

echo "=================================================="
echo "Insecure Deserialization Sink Detector"
echo "Quick Start Examples"
echo "=================================================="
echo ""

# Get the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Example 1: Show help
echo "1. View help information:"
echo "   bash scripts/scan.sh --help"
echo ""

# Example 2: Basic scan
echo "2. Scan test fixtures:"
echo "   bash scripts/scan.sh scripts/tests/fixtures/"
echo ""

# Example 3: Scan specific language
echo "3. Scan specific language (Python):"
echo "   bash scripts/scan.sh scripts/tests/fixtures/ --lang python"
echo ""

# Example 4: Save JSON report
echo "4. Save results to JSON file:"
echo "   bash scripts/scan.sh scripts/tests/fixtures/ --report findings.json"
echo ""

# Example 5: Save SARIF report
echo "5. Save results to SARIF file:"
echo "   bash scripts/scan.sh scripts/tests/fixtures/ --output sarif --report findings.sarif"
echo ""

# Example 6: Real usage with WebGoat
echo "6. Scan WebGoat (if available):"
echo "   bash scripts/scan.sh ~/WebGoat/ --lang python --report webgoat.json"
echo ""

# Example 7: Verbose output
echo "7. Verbose output for debugging:"
echo "   bash scripts/scan.sh scripts/tests/fixtures/ --verbose"
echo ""

echo "=================================================="
echo "To get started, try:"
echo "  bash scripts/scan.sh scripts/tests/fixtures/"
echo "=================================================="
