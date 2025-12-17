# Insecure Deserialization Sink Detector - Scan Script

This script provides an easy-to-use interface for scanning code repositories for insecure deserialization vulnerabilities.

## Quick Start

```bash
# Basic usage - scan a directory
bash scan.sh /path/to/your/code

# Scan specific language
bash scan.sh /path/to/code --lang python

# Save results to JSON file
bash scan.sh /path/to/code --output json --report findings.json

# Save results to SARIF format
bash scan.sh /path/to/code --output sarif --report findings.sarif

# Get help
bash scan.sh --help
```

## Usage

```
bash scan.sh <target_directory> [options]
```

### Options

- `--lang LANGUAGE` - Specify language to scan (php, python, java, javascript)
- `--output FORMAT` - Output format (json or sarif) [default: json]
- `--report FILE` - Save report to file
- `--verbose` - Show detailed output
- `--help` - Show help message

## Examples

```bash
# Scan Python files in WebGoat
bash scan.sh ~/WebGoat/ --lang python

# Scan all code and save to JSON report
bash scan.sh /myproject --output json --report report.json

# Scan with verbose output
bash scan.sh /code --verbose

# Scan Java and save as SARIF
bash scan.sh /src --lang java --output sarif --report findings.sarif
```

## Detected Vulnerabilities

### PHP
- `unserialize()` - Direct object deserialization
- `__wakeup()`, `__destruct()`, `__unserialize()` - Magic methods
- `json_decode()`, `simplexml_load_string()` - Related functions

### Python
- `pickle.loads()`, `pickle.load()` - Pickle serialization
- `yaml.load()`, `yaml.unsafe_load()`, `yaml.full_load()` - YAML parsing
- `dill.loads()`, `cloudpickle.loads()` - Extended serialization
- `marshal.loads()` - Internal serialization
- `shelve` operations - Database serialization

### Java
- `ObjectInputStream.readObject()`, `readUnshared()`
- Jackson `ObjectMapper.readValue()`
- XStream `fromXML()`
- SnakeYAML `Yaml.load()`
- `Class.forName()`

### JavaScript
- `eval()` - Direct code evaluation
- `new Function()` - Dynamic function creation
- `vm.runInContext()`, `vm.runInNewContext()`
- `setTimeout/setInterval` with string code
- `require()` / dynamic `import()`

## Output Formats

### JSON
Standard JSON format with statistics and all findings:
```json
{
  "timestamp": "2025-11-30T10:00:00",
  "summary": {
    "total_sinks": 15,
    "critical": 3,
    "high": 2
  },
  "sinks": [...]
}
```

### SARIF
OASIS SARIF format for integration with other security tools.

## Exit Codes

- `0` - No vulnerabilities found
- `1` - Vulnerabilities found

## Requirements

- Bash 4.0+
- Python 3
- insecure_deserialization_sink_detector module

## Setup

The scan.sh script expects the detector module to be in the `scripts/` directory.
