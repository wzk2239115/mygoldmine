# Quick Start Guide - Insecure Deserialization Sink Detector

## Installation (30 seconds)

```bash
cd insecure_deserialization_sink_detector
pip install -r requirements.txt
```

## Basic Usage

### Scan a directory for all vulnerabilities
```bash
python cli.py /path/to/code
```

### Scan specific language
```bash
python cli.py --lang python /path/to/python/code
python cli.py --lang php /path/to/php/code
python cli.py --lang java /path/to/java/code
python cli.py --lang javascript /path/to/js/code
```

### Generate reports
```bash
# JSON report
python cli.py --output json --report findings.json /code

# SARIF report (for integration with other tools)
python cli.py --output sarif --report findings.sarif /code
```

### Verbose output
```bash
python cli.py --verbose /code
```

## What Gets Detected

### PHP
- `unserialize()` calls
- Magic methods: `__wakeup()`, `__destruct()`, `__unserialize()`

### Python
- `pickle.loads()` / `pickle.load()`
- `yaml.load()` / `yaml.unsafe_load()`
- `dill.loads()`, `cloudpickle.loads()`
- `marshal.loads()`
- `shelve` operations

### Java
- `ObjectInputStream.readObject()`
- Jackson `readValue()` with default typing
- XStream `fromXML()`
- SnakeYAML `load()`
- `Class.forName()`

### JavaScript
- `eval()` calls
- `new Function()` constructor
- `vm.runInContext()` / `vm.runInNewContext()`
- `setTimeout/setInterval` with string code

## Output Example

### JSON Output
```json
{
  "timestamp": "2024-01-15T10:30:00.123456",
  "summary": {
    "total_sinks": 5,
    "critical": 3,
    "high": 2
  },
  "sinks": [
    {
      "file": "app.php",
      "line": 42,
      "column": 10,
      "function": "unserialize",
      "context": "unserialize($_GET['data'])"
    }
  ]
}
```

## Running Tests

```bash
python -m unittest tests.test_scanner -v
```

## Integration with CI/CD

### GitHub Actions Example
```yaml
- name: Scan for deserialization vulnerabilities
  run: |
    python cli.py --lang python --output json --report findings.json src/
    python cli.py --lang php --output json --report php_findings.json src/
```

### Exit Codes
- `0`: No vulnerabilities found
- `1`: Vulnerabilities found

## Common Issues

### "No module named 'tree_sitter'"
This is a warning - the tool falls back to pattern-based detection which works fine for most cases. To fix:
```bash
pip install tree-sitter tree-sitter-languages
```

### No sinks found but code has deserialization
Check that the language is correctly specified or auto-detected. Verify file extensions match the language configuration.

### Too many false positives
This is expected - the tool detects patterns, not data flow. Review findings and prioritize based on:
1. Whether data is from user input
2. Whether any validation occurs
3. The specific function (some are more dangerous than others)

## Next Steps

1. Review the comprehensive [README.md](README.md) for detailed documentation
2. Check [test fixtures](tests/fixtures/) for examples of detected patterns
3. Run on your codebase and review findings
4. Integrate into your CI/CD pipeline

## Support

For detailed documentation, see:
- [README.md](README.md) - Full feature documentation
- [IMPLEMENTATION_SUMMARY.md](../IMPLEMENTATION_SUMMARY.md) - Technical details
- Test fixtures in `tests/fixtures/` - Example vulnerable code patterns
