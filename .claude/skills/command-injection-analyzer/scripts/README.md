# Command Injection Sink Detector

A tree-sitter-based static code analysis tool for detecting command injection vulnerabilities across multiple programming languages. This tool identifies dangerous sinks where user input could lead to arbitrary command execution.

## Overview

The Command Injection Sink Detector scans source code to identify potential command injection vulnerabilities by detecting dangerous function calls and methods that execute system commands. It supports PHP, Python, Java, JavaScript, Go, and Rust.

### What are Command Injection Sinks?

Command injection sinks are functions, methods, or operators that execute system commands with potentially untrusted input. Examples include:
- **PHP**: `system()`, `exec()`, `shell_exec()`, `passthru()`, backticks
- **Python**: `os.system()`, `subprocess.run()`, `subprocess.Popen()`
- **Java**: `Runtime.exec()`, `ProcessBuilder.start()`
- **JavaScript**: `child_process.exec()`, `child_process.spawn()`
- **Go**: `os/exec.Command()`
- **Rust**: `std::process::Command`

## Features

- **Multi-language Support**: PHP, Python, Java, JavaScript, Go, Rust
- **Regex-based Detection**: Fast pattern matching for sink identification
- **Tree-Sitter Ready**: Extensible architecture for tree-sitter-based queries
- **Multiple Output Formats**: JSON, CSV, HTML reports
- **Context-Aware**: Shows code context around detected sinks
- **Configurable**: Easy to add new sinks or languages via YAML configuration

## Project Structure

```
command_injection_sink_detector/
├── README.md                    # This file
├── cli.py                       # Command-line interface with scanning logic
├── scan.sh                      # Convenience shell script for running
├── config/
│   └── languages.yaml          # Language and sink configuration
├── core/
│   ├── __init__.py
│   └── parser_manager.py       # Parser management (tree-sitter ready)
├── languages/                   # Per-language tree-sitter queries (ready for future use)
│   ├── php/queries/sinks.scm
│   ├── python/queries/sinks.scm
│   ├── java/queries/sinks.scm
│   ├── javascript/queries/sinks.scm
│   ├── go/queries/sinks.scm
│   └── rust/queries/sinks.scm
├── reports/
│   ├── __init__.py
│   └── json_reporter.py        # JSON/CSV/HTML report generation
├── requirements.txt            # Python dependencies
└── tests/
    ├── __init__.py
    ├── fixtures/               # Test code samples
    │   ├── php/cmd_calls.php
    │   ├── python/cmd_calls.py
    │   ├── java/CommandInjection.java
    │   ├── javascript/cmd_calls.js
    │   ├── go/cmd_calls.go
    │   └── rust/cmd_calls.rs
    └── test_scanner.py         # Unit tests
```

## Installation

### Requirements

- Python 3.7+
- PyYAML

### Setup

```bash
# Install dependencies
pip install pyyaml

# Optional: For tree-sitter support
pip install tree-sitter
```

## Usage

### Scan a Directory

```bash
python cli.py --path /path/to/code --languages php,python --output report.json
```

### Scan a Single File

```bash
python cli.py --path /path/to/file.php --output report.json
```

### Scan with Verbose Output

```bash
python cli.py --path /app --verbose --output report.html
```

### Available Options

- `--path` (required): Path to file or directory to scan
- `--languages`: Comma-separated list of languages (php, python, java, javascript, go, rust)
- `--output`, `-o`: Output file path (default: sink_report.json)
- `--verbose`, `-v`: Enable verbose output

### Output Formats

The tool supports multiple output formats based on file extension:

- **JSON** (`*.json`): Structured report with metadata and detailed sink information
- **CSV** (`*.csv`): Spreadsheet-friendly format with sink details
- **HTML** (`*.html`): Human-readable HTML report with summaries

## Configuration

### Adding New Sinks

Edit `config/languages.yaml` to add new sinks:

```yaml
languages:
  php:
    enabled: true
    file_patterns:
      - "*.php"
    sinks:
      - name: "my_function"
        category: "custom_category"
        type: "function_call"
        vulnerable_params: [0]
```

### Sink Configuration Fields

- `name`: Function/method name to detect
- `category`: Classification category for the sink
- `type`: `function_call`, `method_call`, or `operator`
- `class_names`: (Optional) Class names for method calls
- `vulnerable_params`: List of parameter indices that are vulnerable (0-indexed)

## Supported Sinks

### PHP
- `system()`, `exec()`, `shell_exec()`, `passthru()`
- `proc_open()`, `popen()`
- Backtick operator (`` ` ``)

### Python
- `os.system()`, `os.popen()`, `os.execvp()`, `os.execv()`
- `subprocess.run()`, `subprocess.call()`, `subprocess.Popen()`
- `subprocess.check_call()`, `subprocess.check_output()`
- `commands.getstatusoutput()`, `commands.getoutput()` (deprecated)

### Java
- `Runtime.exec()`
- `ProcessBuilder.start()`, `ProcessBuilder.command()`

### JavaScript/TypeScript
- `child_process.exec()`, `child_process.execFile()`
- `child_process.spawn()`
- `child_process.execSync()`, `child_process.spawnSync()`
- `child_process.execFileSync()`

### Go
- `os/exec.Command()`
- `(*exec.Cmd).Run()`, `(*exec.Cmd).Output()`
- `(*exec.Cmd).CombinedOutput()`

### Rust
- `std::process::Command::new()`
- `.arg()`, `.args()`, `.output()`, `.status()`

## Example Report Output

### JSON Report Structure

```json
{
  "metadata": {
    "tool": "Command Injection Sink Detector",
    "timestamp": "2025-11-30T10:30:00.000000",
    "source_path": "/app",
    "languages_scanned": ["php", "python"],
    "total_sinks": 15
  },
  "sinks": [
    {
      "file": "/app/handler.php",
      "line": 42,
      "column": 5,
      "sink_type": "system",
      "sink_category": "direct_execution",
      "function_name": "system",
      "parameters": ["$_GET['cmd']"],
      "vulnerable_params": [0],
      "context": "system($_GET['cmd']);"
    }
  ],
  "summary": {
    "total": 15,
    "by_category": {
      "direct_execution": 8,
      "subprocess": 5,
      "process_control": 2
    },
    "by_file": {
      "/app/handler.php": 10,
      "/app/utils.php": 5
    }
  }
}
```

## Testing

Run the test suite to verify sink detection:

```bash
python -m pytest tests/test_scanner.py -v
```

Or using unittest:

```bash
python -m unittest tests.test_scanner -v
```

### Test Coverage

The test suite includes fixtures for each supported language and validates:
- Sink detection accuracy
- File pattern matching
- Report generation
- Language configuration loading
- Sink configuration validation

## Architecture

### Parser Manager

The `ParserManager` class handles:
- Loading language configuration from YAML
- Providing sink configurations for each language
- Managing tree-sitter parser instances (when available)
- Tracking enabled languages and file patterns

### Sink Detector

The detector uses regex-based pattern matching (with tree-sitter queries ready for future enhancement):
- Identifies function calls: `function_name(...)`
- Detects method calls: `->method_name(...)`, `.method_name(...)`
- Recognizes operators: backticks, etc.

### Reporter

The reporter generates findings in multiple formats:
- Detailed sink information (file, line, column, parameters)
- Context-aware output showing surrounding code
- Summary statistics grouped by category and file
- Support for JSON, CSV, and HTML output

## Limitations

- **Regex-based**: Uses regex patterns rather than full AST analysis (tree-sitter ready for upgrade)
- **No Flow Analysis**: Does not track data flow or taint analysis
- **Parameter Matching**: Relies on parameter position, not sophisticated argument analysis
- **Pattern Matching**: May have false positives/negatives with complex code patterns

## Future Enhancements

- [ ] Full tree-sitter integration for AST-based analysis
- [ ] Data flow analysis for better accuracy
- [ ] SARIF format support for CI/CD integration
- [ ] Configuration of detection rules per organization
- [ ] Plugin system for custom sink definitions
- [ ] Integration with SAST platforms

## Integration with AI Tools

This detector is designed to be used by AI tools to:

1. **Identify Dangerous Sinks**: Locate potential command injection vulnerabilities
2. **Understand Code Context**: Get surrounding code for better analysis
3. **Generate Reports**: Produce structured reports for further processing
4. **Integration**: Use JSON output for programmatic access to findings

### Example: Using with AI Tools

```python
import json
import subprocess

# Run detector
result = subprocess.run(
    ['python', 'cli.py', '--path', '/app', '--output', 'sinks.json'],
    capture_output=True
)

# Parse results
with open('sinks.json', 'r') as f:
    report = json.load(f)

# Process sinks with AI
for sink in report['sinks']:
    print(f"Check {sink['file']}:{sink['line']} - {sink['sink_type']}")
    print(f"Context: {sink['context']}")
```

## Contributing

To add support for a new language:

1. Add language configuration to `config/languages.yaml`
2. Create tree-sitter query file at `languages/{lang}/queries/sinks.scm`
3. Add test fixtures in `tests/fixtures/{lang}/`
4. Update `cli.py` file extension mapping
5. Add unit tests to `tests/test_scanner.py`

## License

See LICENSE file in the parent command_injection directory.

## References

- [OWASP Command Injection](https://owasp.org/www-community/attacks/Command_Injection)
- [Tree-sitter](https://tree-sitter.github.io)
- [CWE-78: Improper Neutralization of Special Elements used in an OS Command](https://cwe.mitre.org/data/definitions/78.html)
