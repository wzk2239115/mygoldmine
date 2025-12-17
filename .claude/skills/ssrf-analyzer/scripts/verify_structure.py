#!/usr/bin/env python3
"""Verify SSRF Sink Detector project structure."""

import os
from pathlib import Path

REQUIRED_FILES = {
    # Core files
    '__init__.py': 'Package initialization',
    'cli.py': 'Command-line interface',
    'requirements.txt': 'Python dependencies',
    'README.md': 'Project documentation',

    # Configuration
    'config/languages.yaml': 'Language configuration',

    # Core modules
    'core/__init__.py': 'Core package init',
    'core/scanner.py': 'Main scanning engine',
    'core/parser_manager.py': 'Parser management',

    # Language queries
    'languages/php/queries/sinks.scm': 'PHP sink queries',
    'languages/python/queries/sinks.scm': 'Python sink queries',
    'languages/java/queries/sinks.scm': 'Java sink queries',
    'languages/javascript/queries/sinks.scm': 'JavaScript sink queries',

    # Reporters
    'reports/__init__.py': 'Reports package init',
    'reports/json_reporter.py': 'JSON report generator',
    'reports/sarif_reporter.py': 'SARIF report generator',

    # Tests
    'tests/__init__.py': 'Tests package init',
    'tests/test_scanner.py': 'Unit tests',
    'tests/fixtures/php/http_calls.php': 'PHP test fixtures',
    'tests/fixtures/python/http_calls.py': 'Python test fixtures',
}

def verify_structure():
    """Verify project structure and files."""
    project_root = Path(__file__).parent
    missing_files = []

    print("🔍 Verifying SSRF Sink Detector Project Structure...\n")

    for file_path, description in REQUIRED_FILES.items():
        full_path = project_root / file_path
        if full_path.exists():
            file_size = full_path.stat().st_size
            print(f"✅ {file_path:<50} ({file_size:>6} bytes) - {description}")
        else:
            print(f"❌ {file_path:<50} MISSING - {description}")
            missing_files.append(file_path)

    print(f"\n{'='*80}")

    if missing_files:
        print(f"❌ Verification FAILED: {len(missing_files)} file(s) missing:")
        for f in missing_files:
            print(f"   - {f}")
        return False
    else:
        print("✅ Verification PASSED: All required files present!")
        total_size = sum((project_root / f).stat().st_size
                        for f in REQUIRED_FILES.keys()
                        if (project_root / f).exists())
        print(f"   Total project size: {total_size:,} bytes")
        return True

if __name__ == '__main__':
    import sys
    success = verify_structure()
    sys.exit(0 if success else 1)
