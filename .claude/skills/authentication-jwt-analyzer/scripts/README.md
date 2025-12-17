# JWT Authentication Sink Detector

A tree-sitter based static code analysis tool for detecting JWT authentication operations (decode, verify, sign) across multiple programming languages.

## Overview

This tool uses tree-sitter AST parsing to identify JWT-related security-sensitive operations in source code. It's useful for:

- Security audits and code reviews
- Finding potential JWT misconfigurations
- Identifying areas where JWT verification might be skipped
- Compliance and security assessment

## Supported Languages

- **Python** - PyJWT, jwt.io library patterns
- **PHP** - Firebase/JWT and similar patterns
- **JavaScript/TypeScript** - jsonwebtoken, node-jose patterns
- **Java** - JJWT, Spring Security JWT patterns

## Installation

### Prerequisites

- Python 3.7+
- tree-sitter Python bindings

### Setup

```bash
# Install dependencies
pip install tree-sitter pyyaml

# Install language parsers (one or more as needed)
pip install tree-sitter-python tree-sitter-php tree-sitter-javascript tree-sitter-java
```

## Quick Start

### Scan a single file

```bash
python cli.py /path/to/file.py --output json
```

### Scan a directory

```bash
python cli.py /path/to/project --output json
```

### Save report to file

```bash
python cli.py /path/to/project --output report.json
```

### Generate SARIF report

```bash
python cli.py /path/to/project --output report.sarif
```

### Verbose output

```bash
python cli.py /path/to/project --verbose
```

## Command-line Options

```
positional arguments:
  path                  Path to file or directory to scan

optional arguments:
  -h, --help            Show help message
  --lang LANGUAGE       Specific language to scan (python, php, javascript, java)
  --output OUTPUT, -o OUTPUT
                        Output format: json, sarif, or file path (default: json)
  --config CONFIG       Path to languages.yaml configuration file
  --verbose, -v         Enable verbose output
```

## Output Formats

### JSON Format

```json
{
  "tool": "authentication_jwt_detector",
  "version": "1.0.0",
  "timestamp": "2024-11-30T10:30:00",
  "summary": {
    "total_findings": 5,
    "by_language": {
      "python": 3,
      "javascript": 2
    },
    "by_severity": {
      "HIGH": 5
    }
  },
  "findings": [
    {
      "file": "auth.py",
      "line": 42,
      "column": 8,
      "function_name": "jwt.decode",
      "code_snippet": "payload = jwt.decode(token, key, algorithms=['HS256'])",
      "severity": "HIGH",
      "language": "python",
      "message": "JWT authentication operation detected: call"
    }
  ]
}
```

### SARIF Format

SARIF (Static Analysis Results Format) compliant output for integration with security tools and dashboards.

## Architecture

### Core Components

#### `parser_manager.py`
- Manages tree-sitter parser instances
- Loads and caches language configurations
- Handles dynamic language module loading

#### `scanner.py`
- Main scanning engine
- Executes tree-sitter queries on parsed code
- Extracts code snippets and metadata
- Aggregates findings

#### Language Query Files (`.scm`)
Tree-sitter S-expression format queries for detecting JWT operations:

- `python/queries/jwt_sinks.scm` - Detects jwt.decode(), PyJWT patterns
- `php/queries/jwt_sinks.scm` - Detects Firebase\JWT\JWT patterns
- `javascript/queries/jwt_verify.scm` - Detects jsonwebtoken patterns
- `java/queries/jwt_verify.scm` - Detects JJWT patterns

#### Reporters
- `json_reporter.py` - Generates JSON reports
- `sarif_reporter.py` - Generates SARIF-format reports

### Directory Structure

```
authentication_jwt_detector/
├── config/
│   └── languages.yaml           # Language configuration
├── core/
│   ├── parser_manager.py        # Parser instance management
│   └── scanner.py               # Core scanning engine
├── languages/
│   ├── python/queries/jwt_sinks.scm
│   ├── php/queries/jwt_sinks.scm
│   ├── javascript/queries/jwt_verify.scm
│   └── java/queries/jwt_verify.scm
├── reports/
│   ├── json_reporter.py         # JSON report generation
│   └── sarif_reporter.py        # SARIF report generation
├── tests/
│   ├── fixtures/                # Test code samples
│   └── test_scanner.py          # Unit tests
├── cli.py                       # Command-line interface
└── README.md
```

## Understanding JWT Sink Detection

A **JWT sink** is any operation that handles, decodes, or verifies JWT tokens. The scanner detects:

### Decode Operations
```python
# Python
jwt.decode(token, secret)
PyJWT().decode(token, secret)

# JavaScript
jwt.verify(token, secret)
jsonwebtoken.verify(token, key, options)

# PHP
JWT::decode($token, $key)
Firebase\JWT\JWT::decode($token, $key)

# Java
Jwts.parser().setSigningKey(key).parseClaimsJws(token)
```

### Verification Operations
```python
token.verify(secret)
jwt.verify(token, key)

# PHP
$verifier->verify($token)

# JavaScript
jwt.verify(token, secret)

# Java
parser.parseClaimsJws(token)
```

### Sign Operations
```python
jwt.encode(payload, secret)

# JavaScript
jwt.sign(payload, secret)

# Java
Jwts.builder().setSubject(...).signWith(key).compact()
```

## Configuration

Edit `config/languages.yaml` to:

- Add new languages
- Modify file extensions
- Change tree-sitter module names
- Adjust scanner behavior

```yaml
languages:
  python:
    extensions: ['.py']
    tree_sitter_module: "tree_sitter_python"
    query_file: "jwt_sinks.scm"
    priority: 1
```

## Writing Custom Queries

Extend detection by modifying or creating query files in `languages/*/queries/`:

```scheme
;; Detect custom JWT pattern
(call
  function: (attribute
    object: (identifier) @jwt_lib
    attribute: (identifier) @method)
  arguments: (arguments) @args
  (#match? @method "^(decode|verify)$")
) @jwt_sink
```

## Running Tests

```bash
cd authentication_jwt_detector
python -m pytest tests/test_scanner.py -v

# Or use unittest
python -m unittest tests.test_scanner -v
```

## Integration

### CI/CD Integration

```yaml
# GitHub Actions example
- name: Run JWT detector
  run: python cli.py . --output report.sarif

- name: Upload to security dashboard
  uses: github/codeql-action/upload-sarif@v2
  with:
    sarif_file: report.sarif
```

## Limitations

- Tree-sitter queries match syntactic patterns, not semantic analysis
- False positives possible if JWT libraries use non-standard patterns
- Large files may take time to parse
- Requires tree-sitter language parsers to be installed

## Troubleshooting

### Parser not found error
```
ImportError: Failed to load tree-sitter language tree_sitter_python
```
Solution: Install the language parser
```bash
pip install tree-sitter-python
```

### No findings reported
- Ensure language parser is installed
- Check that query file exists
- Verify file extensions match configuration
- Use `--verbose` flag for debugging

### Performance issues
- Large directories may take time to process
- Non-code files should be filtered out
- Consider scanning specific subdirectories

## Future Enhancements

- [ ] Semantic analysis for better accuracy
- [ ] Support for more languages (Go, Rust, C#)
- [ ] IDE plugin integration
- [ ] Machine learning-based pattern recognition
- [ ] Integration with OWASP dependency checker
- [ ] Performance optimizations with parallel scanning

## References

- [Tree-sitter Documentation](https://tree-sitter.github.io)
- [SARIF Standard](https://sarifweb.azurewebsites.net/)
- [JWT Best Practices](https://tools.ietf.org/html/rfc7519)

## License

This tool is provided as-is for security research and code analysis purposes.

## Contributing

Contributions welcome! Areas for improvement:

- Additional language support
- Enhanced query patterns
- Better false positive filtering
- Performance optimizations
- Documentation improvements
