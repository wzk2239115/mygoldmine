# Authentication JWT Detector - Implementation Summary

## Project Overview

The `authentication_jwt_detector` is a comprehensive tree-sitter based static analysis tool designed to detect JWT (JSON Web Token) authentication operations across multiple programming languages.

## Core Features

1. **Multi-language Support**: Python, PHP, JavaScript/TypeScript, Java
2. **AST-based Detection**: Uses tree-sitter for accurate syntax-aware pattern matching
3. **Multiple Report Formats**: JSON and SARIF output formats
4. **Extensible Architecture**: Easy to add new languages and custom patterns
5. **Command-line Interface**: Simple yet powerful CLI for integration into CI/CD pipelines

## Project Structure

```
authentication_jwt_detector/
├── config/
│   └── languages.yaml                    # Language configuration & patterns
│
├── core/
│   ├── __init__.py
│   ├── parser_manager.py                 # Parser instance management
│   └── scanner.py                        # Core scanning engine
│
├── languages/
│   ├── __init__.py
│   ├── python/queries/jwt_sinks.scm      # Python JWT patterns
│   ├── php/queries/jwt_sinks.scm         # PHP JWT patterns
│   ├── javascript/queries/jwt_verify.scm # JS/TS JWT patterns
│   └── java/queries/jwt_verify.scm       # Java JWT patterns
│
├── reports/
│   ├── __init__.py
│   ├── json_reporter.py                  # JSON report generation
│   └── sarif_reporter.py                 # SARIF report generation
│
├── tests/
│   ├── __init__.py
│   ├── test_scanner.py                   # Unit tests
│   └── fixtures/
│       ├── python/jwt_fixtures.py        # Python test samples
│       └── php/jwt_calls.php             # PHP test samples
│
├── cli.py                                # Command-line interface
├── requirements.txt                      # Python dependencies
└── README.md                             # Full documentation
```

## Key Components

### 1. Parser Manager (`core/parser_manager.py`)

**Responsibilities:**
- Load language configuration from YAML
- Dynamically instantiate tree-sitter parsers
- Manage parser lifecycle and caching
- Validate language support

**Key Methods:**
- `get_parser(language)` - Get or create parser for language
- `get_extensions(language)` - Get file extensions
- `get_supported_languages()` - List supported languages
- `is_supported(language)` - Check language support

### 2. JWT Sink Scanner (`core/scanner.py`)

**Responsibilities:**
- Execute tree-sitter queries on parsed code
- Extract code snippets and metadata
- Manage findings collection
- Generate summary statistics

**Key Classes:**
- `Finding` - Data class representing a JWT sink finding
- `JWTSinkScanner` - Main scanner engine

**Key Methods:**
- `scan_file(file_path)` - Scan single file
- `scan_directory(directory)` - Recursively scan directory
- `get_findings()` - Retrieve all findings
- `get_summary()` - Get aggregated statistics

### 3. Tree-sitter Query Files

**Purpose:** Define patterns for detecting JWT operations using tree-sitter S-expressions

**Examples:**

Python (`python/queries/jwt_sinks.scm`):
```scheme
(call
  function: (attribute
    object: (identifier) @object
    attribute: (identifier) @method)
  arguments: (arguments) @args
  (#match? @method "^(decode|verify)$")
) @jwt_sink
```

JavaScript (`javascript/queries/jwt_verify.scm`):
```scheme
(call
  callee: (member_expression
    object: (identifier) @object
    property: (identifier) @method)
  arguments: (arguments) @args
  (#match? @method "^(verify|decode|sign)$")
) @jwt_sink
```

### 4. Reporters

#### JSONReporter (`reports/json_reporter.py`)
- Generates findings in JSON format
- Includes summary statistics
- Supports file output or stdout

#### SARIFReporter (`reports/sarif_reporter.py`)
- Generates SARIF 2.1.0 compliant output
- Includes tool metadata and rules
- Suitable for integration with security dashboards

### 5. CLI Interface (`cli.py`)

**Features:**
- File and directory scanning
- Multiple output formats
- Verbose logging
- Configuration file support

**Usage Examples:**
```bash
# Scan directory, output JSON to stdout
python cli.py /path/to/project

# Save to file
python cli.py /path/to/project --output findings.json

# Generate SARIF report
python cli.py /path/to/project --output findings.sarif

# Verbose mode with specific language
python cli.py /path/to/project --lang python --verbose
```

## Detected Patterns

### Python Patterns
- `jwt.decode(token, secret)`
- `PyJWT().decode(token, secret)`
- `token.verify(secret)`
- Custom JWT handler patterns

### PHP Patterns
- `JWT::decode($token, $key)`
- `Firebase\JWT\JWT::decode()`
- `$jwt->decode()`
- `decode_token()` functions

### JavaScript/TypeScript Patterns
- `jwt.verify(token, secret)`
- `jsonwebtoken.verify(token, key)`
- `token.decode()`
- `verifyJWT()` functions

### Java Patterns
- `Jwts.parser().setSigningKey().parseClaimsJws()`
- `JWTVerifier.verify()`
- `Jwts.parserBuilder().build().parseClaimsJws()`

## Configuration File Format

`config/languages.yaml`:
```yaml
languages:
  python:
    extensions: ['.py']
    tree_sitter_module: "tree_sitter_python"
    query_file: "jwt_sinks.scm"
    priority: 1

scanner:
  max_file_size_mb: 10
  parallel_processing: true
  timeout_seconds: 30
```

## Testing

**Test Suite:** `tests/test_scanner.py`

**Test Coverage:**
- Parser manager initialization
- Language detection
- File scanning
- Code snippet extraction
- Finding data structures
- Report generation

**Fixtures:**
- `tests/fixtures/python/jwt_fixtures.py` - Various JWT patterns in Python
- `tests/fixtures/php/jwt_calls.php` - JWT usage in PHP

**Running Tests:**
```bash
python -m unittest tests.test_scanner -v
```

## Dependencies

- `tree-sitter` - AST parsing library
- `pyyaml` - YAML configuration parsing
- Language-specific parsers:
  - `tree-sitter-python`
  - `tree-sitter-php`
  - `tree-sitter-javascript`
  - `tree-sitter-java`

## Report Output Examples

### JSON Format
```json
{
  "tool": "authentication_jwt_detector",
  "version": "1.0.0",
  "timestamp": "2024-11-30T10:30:00",
  "summary": {
    "total_findings": 3,
    "by_language": {"python": 2, "javascript": 1},
    "by_severity": {"HIGH": 3}
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
      "message": "JWT authentication operation detected"
    }
  ]
}
```

### SARIF Format
- Compliant with SARIF 2.1.0 standard
- Integration with security dashboards and tools
- Includes tool metadata, rules, and execution properties

## Extension Points

### Adding New Languages

1. Create query directory: `languages/golang/queries/`
2. Write tree-sitter queries: `jwt_sinks.scm`
3. Update `config/languages.yaml`:
```yaml
golang:
  extensions: ['.go']
  tree_sitter_module: "tree_sitter_go"
  query_file: "jwt_sinks.scm"
  priority: 5
```
4. Install tree-sitter parser: `pip install tree-sitter-go`

### Custom Query Patterns

Modify query files to detect additional patterns:
```scheme
; New pattern for custom JWT library
(call
  function: (attribute
    object: (identifier) @lib
    attribute: (identifier) @method)
  (#match? @lib "custom_jwt")
) @jwt_sink
```

## Performance Characteristics

- File scanning: O(file_size)
- Directory scanning: O(total_code_size)
- Query execution: Optimized by tree-sitter
- Memory: Depends on AST size

## Security Considerations

- Read-only operation (no code modification)
- No network communication
- Local file system access only
- No credentials or sensitive data required

## Integration Examples

### GitHub Actions
```yaml
- name: Run JWT detector
  run: python cli.py . --output report.sarif

- name: Upload SARIF
  uses: github/codeql-action/upload-sarif@v2
  with:
    sarif_file: report.sarif
```

### Pre-commit Hook
```yaml
- repo: local
  hooks:
    - id: jwt-detector
      name: JWT Detector
      entry: python cli.py
      language: system
      types: [python, php, javascript, java]
      pass_filenames: false
```

## Future Enhancements

1. Semantic analysis for reduced false positives
2. Configuration-aware validation (checking if verification is actually performed)
3. Performance improvements with parallel processing
4. Additional language support (Go, Rust, C#)
5. IDE plugin integration
6. Machine learning-based pattern detection
7. Database of known JWT vulnerabilities

## Limitations

- Syntactic analysis only (no semantic understanding)
- Tree-sitter grammar limitations
- Requires language parser installation
- Large files may have performance impact

## Troubleshooting

### ImportError for language parser
Solution: Install the missing parser
```bash
pip install tree-sitter-python
```

### No findings detected
- Verify language parser is installed
- Check if file extensions match config
- Ensure query files exist in language directories
- Use `--verbose` flag for debugging

## Contributing

Contributions welcome in:
- New language support
- Query pattern improvements
- Performance optimizations
- Bug fixes
- Documentation enhancements

## Author Notes

This tool provides a foundation for JWT security analysis. It's designed to be:
- **Extensible**: Easy to add new languages and patterns
- **Accurate**: Uses AST-based pattern matching
- **Practical**: Integrates with CI/CD pipelines
- **Maintainable**: Clean architecture with separation of concerns
