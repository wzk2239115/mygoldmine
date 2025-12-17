#!/usr/bin/env python3
"""Quick reference and examples for the Command Injection Sink Detector."""

EXAMPLES = """
# Command Injection Sink Detector - Quick Reference

## Basic Usage

# Scan a directory for PHP vulnerabilities
python cli.py --path /var/www --languages php

# Scan a single Python file
python cli.py --path app.py --output report.json

# Scan all supported languages
python cli.py --path /app --languages php,python,java,javascript,go,rust

## Using the Shell Script

# Scan with convenience script
./scan.sh --path /app --output report.html --verbose

## Output Formats

# JSON report (default)
python cli.py --path /app --output report.json

# HTML report
python cli.py --path /app --output report.html

# CSV report
python cli.py --path /app --output report.csv

## Common Patterns

# Scan entire project
python cli.py --path . --verbose

# Scan with specific language
python cli.py --path src --languages python

# Run tests
python -m unittest tests.test_scanner -v

# Generate HTML for stakeholders
python cli.py --path /app --output findings.html --languages php,python,java

## Sink Categories by Language

### PHP
- Direct execution: system(), exec(), shell_exec(), passthru()
- Process control: proc_open(), popen()
- Shell operators: backtick operator

### Python
- OS module: os.system(), os.popen(), os.execv()
- Subprocess: run(), call(), Popen(), check_call(), check_output()
- Deprecated: commands module functions

### Java
- Runtime: Runtime.exec()
- ProcessBuilder: start(), command()

### JavaScript/TypeScript
- Child process: exec(), execFile(), spawn()
- Sync variants: execSync(), execFileSync(), spawnSync()

### Go
- os/exec: Command(), Run(), Output(), CombinedOutput()

### Rust
- std::process::Command: new(), arg(), args(), output(), status()

## Configuration

Edit config/languages.yaml to:
- Add new sink functions
- Enable/disable languages
- Modify file patterns
- Adjust sink categories

Example sink configuration:
```yaml
- name: "my_command_function"
  category: "custom"
  type: "function_call"
  vulnerable_params: [0, 1]
```

## Integration with CI/CD

# GitHub Actions example
- name: Check for command injection
  run: |
    pip install -r requirements.txt
    python cli.py --path . --languages php,python --output ci_report.json
    python check_report.py ci_report.json  # Custom validation script

## Interpreting Results

Each sink report includes:
- **file**: Source file path
- **line**: Line number
- **column**: Column number
- **sink_type**: Function/method name
- **sink_category**: Category of vulnerability
- **parameters**: Function parameters (extracted)
- **vulnerable_params**: Parameter indices prone to injection
- **context**: Surrounding code for reference

## Limitations

- Regex-based detection (not AST analysis)
- No taint/data flow analysis
- Parameter matching based on position
- May produce false positives/negatives

## Future Work

- Tree-sitter AST analysis
- Taint analysis
- Flow-sensitive detection
- SARIF output format
- CI/CD platform integrations
"""

if __name__ == '__main__':
    print(EXAMPLES)
