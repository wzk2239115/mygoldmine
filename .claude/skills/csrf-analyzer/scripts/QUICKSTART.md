# CSRF Sink Detector - Quick Start Guide

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Verify installation
python3 cli.py --help
```

## Quick Usage

### Scan a project
```bash
# Scan all languages
python3 cli.py /path/to/project

# Scan specific languages only
python3 cli.py --lang python java /path/to/project

# Save report to file
python3 cli.py --output report.json /path/to/project

# SARIF format
python3 cli.py --format sarif --output report.sarif /path/to/project

# Verbose output
python3 cli.py --verbose /path/to/project
```

### Using the bash script
```bash
# Default behavior
./scan.sh /path/to/project

# Verbose mode
VERBOSE=true ./scan.sh /path/to/project
```

### Run tests
```bash
python3 -m unittest tests.test_scanner -v
```

## What It Detects

The detector identifies **state-changing endpoints** that may need CSRF protection:

- **PHP**: `Route::post()`, `$_POST`, `REQUEST_METHOD === 'POST'`
- **Python**: `@app.route(..., methods=['POST'])`, `@csrf_exempt`
- **Java**: `@PostMapping`, `@PutMapping`, `@DeleteMapping`, `@RequestMapping(method=POST)`, `csrf().disable()`
- **JavaScript**: `app.post()`, `router.post()`, `app.put()`, `app.delete()`

## Output

### JSON Output (Default)
```json
{
  "timestamp": "2025-11-30T03:16:46.868649",
  "version": "1.0",
  "tool": "CSRF Sink Detector",
  "summary": {
    "total_sinks": 28,
    "by_type": {
      "POST_ROUTE": 17,
      "CSRF_EXEMPT": 3,
      "POST_ENDPOINT": 8
    },
    "by_file": {
      "app.py": 5,
      "controller.java": 8
    }
  },
  "sinks": [...]
}
```

### SARIF Output
SARIF 2.1.0 standard format compatible with:
- GitHub Advanced Security
- GitLab SAST
- VS Code
- Security scanning tools

## Common Workflows

### 1. Initial audit setup
```bash
# Generate baseline report
./scan.sh /path/to/project
# Review csrf_sink_report_*.json
```

### 2. CI/CD integration
```bash
# In your CI pipeline
python3 /path/to/csrf_sink_detector/cli.py \
    --format json \
    --output csrf_sinks.json \
    .

# Check report
if [ -f csrf_sinks.json ]; then
    # Process report...
fi
```

### 3. Python API usage
```python
from core.scanner import CSRFSinkScanner
from reports.json_reporter import JSONReporter

scanner = CSRFSinkScanner()
sinks = scanner.scan_directory('.')

reporter = JSONReporter()
reporter.save_report(sinks, 'csrf_report.json')
```

## Understanding Results

Each sink entry contains:
- **file**: Source code file path
- **line**: Line number
- **column**: Column number
- **type**: Sink type (POST_ROUTE, POST_ENDPOINT, CSRF_EXEMPT, etc.)
- **sink**: Human-readable description
- **code**: The actual code line

Example:
```json
{
  "file": "app.py",
  "line": 10,
  "column": 5,
  "type": "POST_ROUTE",
  "sink": "POST endpoint",
  "code": "@app.route('/update', methods=['POST'])"
}
```

## Next Steps

1. **Analyze results**: Review the generated report
2. **Investigate each sink**: Check if CSRF protection is implemented
3. **Document findings**: Compare endpoints with CSRF protection list
4. **Fix vulnerabilities**: Implement missing CSRF protections

## Troubleshooting

### No sinks found
- Verify the project path exists
- Check if project uses one of the supported languages
- Run with `--verbose` to see scan progress

### Python import errors
- Ensure all dependencies are installed: `pip install -r requirements.txt`
- Check Python version (requires Python 3.6+)

### File encoding issues
- Files are processed with UTF-8 encoding
- Non-UTF-8 files are skipped gracefully

## Support

For more information:
- See `README.md` for detailed documentation
- See `IMPLEMENTATION_SUMMARY.md` for technical details
- Review test fixtures for detection examples
