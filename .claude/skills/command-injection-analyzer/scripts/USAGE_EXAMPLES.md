# Command Injection Sink Detector - Usage Examples

## Quick Start (New Usage Pattern)

### Basic Scanning with Positional Argument

```bash
# Scan a directory - simplest form
bash scan.sh ~/WebGoat/

# Scan with output file
bash scan.sh ~/WebGoat/ --output findings.json

# Scan with verbose output
bash scan.sh ~/WebGoat/ --verbose

# Scan with language filtering
bash scan.sh ~/WebGoat/ --languages php,python

# Combine options
bash scan.sh ~/WebGoat/ --languages php,python --output report.html --verbose
```

## Advanced Usage

### Using the CLI Directly

```bash
# Traditional flag-based usage
python3 cli.py --path ~/WebGoat/ --languages php,python --output report.json

# Single file scanning
python3 cli.py --path /app/handler.php --output handler_report.json

# All languages with verbose output
python3 cli.py --path . --verbose

# Generate HTML report
python3 cli.py --path . --output report.html
```

## Output Format Variants

```bash
# JSON report (default)
bash scan.sh . --output report.json

# HTML report (for presentations)
bash scan.sh . --output report.html

# CSV report (for spreadsheets)
bash scan.sh . --output findings.csv
```

## Language Specific Scanning

```bash
# PHP only
bash scan.sh . --languages php

# Python only
bash scan.sh . --languages python

# Multiple languages
bash scan.sh . --languages php,python,java,javascript,go,rust

# All supported languages (default if not specified)
bash scan.sh .
```

## Real-World Examples

### Scan WebGoat Application
```bash
bash scan.sh ~/WebGoat/ --output webgoat_findings.html --verbose
```

### Scan Node.js Project
```bash
bash scan.sh ~/my-nodejs-app --languages javascript --output nodejs_report.json
```

### Scan PHP Web Application
```bash
bash scan.sh ~/wordpress --languages php --output wordpress_audit.html --verbose
```

### Scan Python Backend
```bash
bash scan.sh ~/django-app --languages python --output django_security_report.json
```

### CI/CD Integration
```bash
# In your CI/CD pipeline
bash scan.sh . --output security_report.json
if [ $? -ne 0 ]; then
    echo "Scanning failed!"
    exit 1
fi

# Check if critical sinks found
python3 -c "import json; data = json.load(open('security_report.json')); print(f'Found {len(data[\"sinks\"])} sinks')"
```

## Testing & Demo

```bash
# Run the demo
./demo.sh

# Run unit tests
python3 -m unittest tests.test_scanner -v

# Quick test with fixtures
bash scan.sh tests/fixtures --output test_report.json
```

## Help and Documentation

```bash
# Show help
bash scan.sh --help

# View comprehensive README
cat README.md

# View quick reference
python3 QUICKREF.py

# View implementation summary
cat IMPLEMENTATION_SUMMARY.md
```

## Tips & Tricks

### Process Large Codebases
```bash
# Scan with progress output
bash scan.sh /large/codebase --verbose --output detailed_report.json
```

### Generate Different Report Formats
```bash
# Generate all report formats
bash scan.sh . --output report.json
bash scan.sh . --output report.html
bash scan.sh . --output report.csv
```

### Combine with Other Tools
```bash
# Pipe output to jq for processing
bash scan.sh . --output report.json | jq '.summary'

# Count sinks by category
python3 << 'PYTHON'
import json
data = json.load(open('report.json'))
for cat, count in data['summary']['by_category'].items():
    print(f'{cat}: {count}')
PYTHON
```

### Integration with JSON Processing
```bash
# Extract critical findings
python3 << 'PYTHON'
import json
with open('report.json') as f:
    data = json.load(f)

for sink in data['sinks']:
    if 'exec' in sink['sink_type'].lower():
        print(f"{sink['file']}:{sink['line']} - {sink['sink_type']}")
PYTHON
```

## Troubleshooting

### Python Not Found
```bash
# Make sure Python 3 is installed
python3 --version

# Or use python instead
python cli.py --path .
```

### Dependencies Missing
```bash
# Manually install dependencies
pip3 install -r requirements.txt

# Or let the script auto-install
bash scan.sh .  # Will prompt to install if needed
```

### Permission Issues
```bash
# Make script executable
chmod +x scan.sh

# Run with bash explicitly
bash scan.sh .
```

## Summary

The updated `scan.sh` now supports intuitive positional arguments while maintaining backward compatibility with the traditional flag-based approach. Choose whichever is more convenient for your workflow!
