# Insecure Deserialization Sink Detector

A tree-sitter based tool for detecting insecure deserialization sinks across multiple programming languages.

## Overview

This tool uses tree-sitter parsing and pattern matching to detect dangerous deserialization operations that could lead to remote code execution (RCE) vulnerabilities. It supports:

- **PHP**: `unserialize()`, `__wakeup()`, `__destruct()`, `__unserialize()`
- **Python**: `pickle.loads()`, `pickle.load()`, `yaml.load()`, `yaml.unsafe_load()`, `dill.loads()`, etc.
- **Java**: `ObjectInputStream.readObject()`, Jackson `readValue()`, XStream `fromXML()`, SnakeYAML `load()`
- **JavaScript/TypeScript**: `vm.runInContext()`, `eval()`, `Function` constructor, etc.

## Project Structure

```
insecure_deserialization_sink_detector/
├── README.md                    # This file
├── config/
│   └── languages.yaml          # Language configuration
├── core/
│   ├── __init__.py
│   ├── scanner.py              # Main scanning engine
│   └── parser_manager.py       # Tree-sitter parser management
├── languages/                   # Language-specific implementations
│   ├── php/queries/
│   ├── python/queries/
│   ├── java/queries/
│   └── javascript/queries/
├── reports/
│   ├── __init__.py
│   └── json_reporter.py        # JSON and SARIF reporters
├── tests/
│   ├── fixtures/               # Test samples
│   └── test_scanner.py         # Automated tests
└── cli.py                       # Command-line interface
```

## Installation

### Requirements

- Python 3.7+
- PyYAML: `pip install pyyaml`
- tree-sitter: `pip install tree-sitter tree-sitter-languages`

### Quick Setup

```bash
# Install dependencies
pip install pyyaml tree-sitter tree-sitter-languages

# Make CLI executable
chmod +x cli.py
```

## Usage

### Basic Usage

```bash
# Scan a directory (auto-detect language)
python cli.py /path/to/code

# Scan with specific language
python cli.py --lang php /path/to/code

# Save to JSON report
python cli.py --output json --report report.json /path/to/code

# Save to SARIF format
python cli.py --output sarif --report report.sarif /path/to/code
```

### Command-line Options

```
positional arguments:
  path                  File or directory to scan

optional arguments:
  -h, --help            Show help message
  --lang LANGUAGE       Programming language (php, python, java, javascript)
  --output FORMAT       Output format (json, sarif) [default: json]
  --report FILE         Output report file path
  --recursive           Recursively scan directories [default: True]
  --verbose             Verbose output
```

### Examples

```bash
# Scan PHP code in current directory
python cli.py --lang php .

# Scan Python files with verbose output
python cli.py --lang python --verbose /myproject

# Generate SARIF report for Java code
python cli.py --lang java --output sarif --report findings.sarif /src

# Scan all supported languages recursively
python cli.py --recursive /codebase
```

## Detected Sinks

### PHP Deserialization

- `unserialize()` - PHP object deserialization
- `__wakeup()` - Magic method called on unserialization
- `__destruct()` - Magic method called on destruction
- `__unserialize()` - Alternative serialization handler (PHP 7.0+)

**Example Vulnerability:**
```php
// VULNERABLE
$data = unserialize($_GET['user']);

class User {
    public function __wakeup() {
        // Arbitrary code can be executed here
        system($this->command);
    }
}
```

### Python Deserialization

- `pickle.loads()`, `pickle.load()` - Python native serialization
- `yaml.load()`, `yaml.unsafe_load()` - YAML parsing without safe loader
- `dill.loads()` - Extended pickle serialization
- `cloudpickle.loads()` - Cloud pickle serialization
- `marshal.loads()` - Python internal serialization
- `shelve` operations - Shelf database using pickle

**Example Vulnerability:**
```python
# VULNERABLE
import pickle
data = pickle.loads(user_input)  # Can execute arbitrary code

# VULNERABLE
import yaml
config = yaml.load(user_input)  # Without Loader=yaml.SafeLoader
```

### Java Deserialization

- `ObjectInputStream.readObject()` - Java native deserialization
- `ObjectInputStream.readUnshared()` - Variant of readObject
- Jackson `ObjectMapper.readValue()` - JSON deserialization with type info
- XStream `fromXML()` - XML deserialization
- SnakeYAML `Yaml.load()` - YAML deserialization

**Example Vulnerability:**
```java
// VULNERABLE
ObjectInputStream ois = new ObjectInputStream(input);
Object obj = ois.readObject();  // Can instantiate arbitrary classes

// VULNERABLE
ObjectMapper mapper = new ObjectMapper();
mapper.enableDefaultTyping();  // Enables polymorphic type handling
Object obj = mapper.readValue(json, Object.class);
```

### JavaScript Deserialization

- `vm.runInContext()`, `vm.runInNewContext()` - Execute arbitrary code in context
- `eval()` - Execute arbitrary JavaScript
- `Function()` constructor - Create functions from strings
- `setTimeout()/setInterval()` with string code - Deferred code execution

**Example Vulnerability:**
```javascript
// VULNERABLE
const vm = require('vm');
vm.runInContext(userCode, sandbox);  // Sandbox can be escaped

// VULNERABLE
eval(userInput);  // Executes arbitrary code

// VULNERABLE
const fn = new Function('a', 'b', userCode)();
```

## Output Formats

### JSON Format

```json
{
  "timestamp": "2024-01-15T10:30:00.123456",
  "summary": {
    "total_sinks": 5,
    "critical": 3,
    "high": 2,
    "medium": 0
  },
  "sinks": [
    {
      "file": "/path/to/file.php",
      "line": 42,
      "column": 10,
      "function": "unserialize",
      "context": "unserialize($_GET['data'])"
    }
  ]
}
```

### SARIF Format

SARIF (Static Analysis Results Interchange Format) compatible output for integration with other security tools:

```json
{
  "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
  "version": "2.1.0",
  "runs": [{
    "tool": {
      "driver": {
        "name": "insecure-deserialization-detector",
        "version": "1.0.0"
      }
    },
    "results": [...]
  }]
}
```

## Testing

Run the automated test suite:

```bash
python -m pytest tests/test_scanner.py -v

# Or using unittest
python -m unittest tests.test_scanner -v
```

### Test Coverage

- Sink detection for all languages
- File and directory scanning
- Language auto-detection
- Report generation (JSON and SARIF)
- ParserManager initialization

## Implementation Details

### Scanner Engine

The scanner uses a hybrid approach:

1. **Tree-sitter Parsing**: For supported languages, uses tree-sitter queries to identify sink patterns
2. **Pattern Matching**: Fallback regex-based pattern matching when tree-sitter is unavailable
3. **Context Extraction**: Captures the code context around detected sinks

### Tree-sitter Queries

Query files (`.scm`) define pattern matches for each language:

```scheme
; Example query for detecting function calls
(function_call_expression
  function: (name) @function
  arguments: (arguments) @args
  (#eq? @function "unserialize")
)
```

### Parser Management

The `ParserManager` handles:
- Loading language configuration from YAML
- Initializing tree-sitter parsers for each language
- Managing parser instances across the application
- Auto-detecting file language from extension

## Security Considerations

### Limitations

1. **False Positives**: The tool may flag safe usage patterns (e.g., deserialization of trusted data)
2. **False Negatives**: Dynamic code patterns may not be detected
3. **Context Analysis**: The tool doesn't perform deep taint analysis or control flow analysis
4. **Library Detection**: May not detect deserialization through custom wrappers

### Safe Patterns

These patterns are generally safe but may still be flagged:

- Deserializing data from trusted sources only
- Using language-specific safe deserialization functions:
  - Python: `yaml.safe_load()`, restricted Unpickler
  - Java: Custom deserialization filters, whitelist validation
  - PHP: Custom validation before `unserialize()`

## Contributing

To add support for a new language:

1. Create a directory under `languages/YOUR_LANG/queries/`
2. Write tree-sitter query file: `deserialization_sinks.scm`
3. Update `config/languages.yaml` with language configuration
4. Add test fixtures under `tests/fixtures/YOUR_LANG/`
5. Update test suite in `test_scanner.py`

## References

### OWASP & CWE

- [CWE-502: Deserialization of Untrusted Data](https://cwe.mitre.org/data/definitions/502.html)
- [OWASP: Deserialization of untrusted data](https://owasp.org/www-community/Deserialization_of_untrusted_data)

### Language-Specific Resources

- **PHP**: [PHP unserialize() Manual](https://www.php.net/manual/en/function.unserialize.php)
- **Python**: [Python pickle — Object Serialization](https://docs.python.org/3/library/pickle.html)
- **Java**: [ObjectInputStream JavaDoc](https://docs.oracle.com/javase/8/docs/api/java/io/ObjectInputStream.html)
- **JavaScript**: [Node.js VM Documentation](https://nodejs.org/api/vm.html)

### Exploitation Techniques

- [PHP Object Injection](https://owasp.org/www-community/vulnerabilities/PHP_Object_Injection)
- [Pickle: Should you use it?](https://docs.python.org/3/library/pickle.html#data-stream-format-version-3-9)
- [Java Deserialization Gadgets](https://github.com/frohoff/ysoserial)
- [Node.js Code Injection](https://cheatsheetseries.owasp.org/cheatsheets/Nodejs_Security_Cheat_Sheet.html)

## License

MIT License - See LICENSE file for details

## Author

Security Research Team
