# JWT Detector - Quick Reference

## Installation

```bash
cd /home/wangzekai/TOP14/authentication_jwt_detector
pip install -r requirements.txt
```

## Basic Usage

```bash
# Scan current directory
python cli.py .

# Scan specific directory
python cli.py /path/to/project

# Save to JSON file
python cli.py /path/to/project --output report.json

# Generate SARIF report
python cli.py /path/to/project --output report.sarif

# Verbose output
python cli.py /path/to/project -v

# Scan specific language only
python cli.py /path/to/project --lang python
```

## Detected Operations

| Language | Pattern | Example |
|----------|---------|---------|
| Python | jwt.decode() | `jwt.decode(token, secret)` |
| Python | PyJWT().decode() | `PyJWT().decode(token, key)` |
| PHP | JWT::decode() | `JWT::decode($token, $key)` |
| PHP | $obj->decode() | `$jwt->decode($token)` |
| JS | jwt.verify() | `jwt.verify(token, secret)` |
| JS | jsonwebtoken.verify() | `jwt.verify(token, key, cb)` |
| Java | Jwts.parser() | `Jwts.parser().setSigningKey(key).parseClaimsJws(token)` |
| Java | JWTVerifier.verify() | `verifier.verify(token)` |

## Output Formats

### JSON (Default)
```bash
python cli.py /path --output report.json
```

Includes:
- Tool metadata
- Timestamp
- Summary statistics (by language, severity)
- Detailed findings with code snippets

### SARIF
```bash
python cli.py /path --output report.sarif
```

SARIF 2.1.0 compliant format for:
- GitHub Code Scanning
- Azure DevOps
- Other SAST integrations

## File Structure

```
authentication_jwt_detector/
├── cli.py                    # Main entry point
├── config/                   # Configuration
├── core/                     # Core scanning logic
├── languages/                # Language-specific queries
├── reports/                  # Report generators
├── tests/                    # Test suite
└── README.md                 # Full documentation
```

## Exit Codes

- `0` - Success, no findings
- `1` - Success, findings detected
- `2` - Error occurred

## Configuration

Edit `config/languages.yaml` to:
- Add/remove language support
- Change file extensions
- Modify tree-sitter modules
- Adjust scanner behavior

## Running Tests

```bash
python -m unittest tests.test_scanner -v
```

## Common Issues

| Issue | Solution |
|-------|----------|
| `ImportError: tree_sitter_python not found` | `pip install tree-sitter-python` |
| No findings detected | Install language parser, check file extensions |
| Slow scanning | Large files/directories take longer, consider subdirectories |

## Integration Examples

### Pre-commit
```yaml
- repo: local
  hooks:
    - id: jwt-detector
      name: JWT Detector
      entry: python cli.py
      language: system
      types: [python, php, javascript]
```

### GitHub Actions
```yaml
- name: Scan with JWT Detector
  run: python cli.py . --output report.json

- name: Upload results
  run: |
    cat report.json
```

### GitLab CI
```yaml
jwt-scan:
  script:
    - python cli.py . --output report.json
  artifacts:
    reports:
      sast: report.json
```

## Key Classes

### Finding
```python
Finding(
    file: str,
    line: int,
    column: int,
    function_name: str,
    code_snippet: str,
    severity: str = "HIGH",
    language: str = "",
    message: str = ""
)
```

### JWTSinkScanner
```python
scanner = JWTSinkScanner()
findings = scanner.scan_directory("/path/to/code")
summary = scanner.get_summary()
```

### JSONReporter / SARIFReporter
```python
from reports.json_reporter import JSONReporter

reporter = JSONReporter()
reporter.add_findings(findings)
reporter.write_report("output.json")
```

## Query Examples

### Python Pattern
```scheme
(call
  function: (attribute
    object: (identifier) @obj
    attribute: (identifier) @method)
  (#match? @method "^(decode|verify)$")
) @jwt_sink
```

### JavaScript Pattern
```scheme
(call
  callee: (member_expression
    object: (identifier) @obj
    property: (identifier) @method)
  (#match? @method "^(verify|decode)$")
) @jwt_sink
```

## Extending for New Languages

1. Create `languages/newlang/queries/jwt_sinks.scm`
2. Update `config/languages.yaml`
3. Install tree-sitter parser: `pip install tree-sitter-newlang`
4. Test with sample files

## Performance Tips

- Scan specific directories instead of entire projects
- Exclude build/vendor directories in code before scanning
- Use `--lang` flag to limit language detection overhead
- Large monorepos may benefit from splitting scans

## Documentation

- **README.md** - Full user guide and documentation
- **IMPLEMENTATION.md** - Architecture and design details
- **This file** - Quick reference and common tasks

## Support

For issues and questions:
1. Check README.md for detailed documentation
2. Review test cases for usage examples
3. Check query files for supported patterns
