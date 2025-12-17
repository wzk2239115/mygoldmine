# Authentication JWT Detector - Project Index

Welcome to the JWT Authentication Detector! This document helps you navigate the project structure and get started quickly.

## Quick Navigation

### For First-Time Users
1. **Start here**: [README.md](README.md) - Complete user guide and installation instructions
2. **Quick commands**: [QUICK_REFERENCE.md](QUICK_REFERENCE.md) - Common usage patterns
3. **Try it out**: `python cli.py /path/to/code`

### For Developers
1. **Architecture**: [IMPLEMENTATION.md](IMPLEMENTATION.md) - Technical design and components
2. **Code**: [core/scanner.py](core/scanner.py) - Main scanning engine
3. **Tests**: `python -m unittest tests.test_scanner -v`

### For Integration
1. **API Usage**: See [IMPLEMENTATION.md](IMPLEMENTATION.md#5-cli-interface) for integration examples
2. **CI/CD**: Check README.md for GitHub Actions, GitLab CI examples
3. **Configuration**: Edit [config/languages.yaml](config/languages.yaml)

## File Organization

```
.
├── README.md                          ← START HERE: Full documentation
├── QUICK_REFERENCE.md                 ← Common commands & patterns
├── IMPLEMENTATION.md                  ← Technical architecture
├── PROJECT_SUMMARY.md                 ← Completion summary
├── INDEX.md                           ← This file
│
├── cli.py                             Main command-line entry point
├── requirements.txt                   Python dependencies
│
├── config/
│   └── languages.yaml                Language definitions & config
│
├── core/                             Core scanning logic
│   ├── parser_manager.py             Parser initialization & lifecycle
│   ├── scanner.py                    JWT sink detection engine
│   └── __init__.py
│
├── languages/                        Language-specific queries
│   ├── python/queries/jwt_sinks.scm  Python pattern detection
│   ├── php/queries/jwt_sinks.scm     PHP pattern detection
│   ├── javascript/queries/jwt_verify.scm  JavaScript pattern detection
│   ├── java/queries/jwt_verify.scm   Java pattern detection
│   └── __init__.py
│
├── reports/                          Report generation
│   ├── json_reporter.py              JSON report generation
│   ├── sarif_reporter.py             SARIF report generation
│   └── __init__.py
│
└── tests/                            Test suite
    ├── test_scanner.py               Unit tests
    ├── fixtures/python/jwt_fixtures.py   Python test samples
    ├── fixtures/php/jwt_calls.php    PHP test samples
    └── __init__.py
```

## Common Tasks

### Installation
```bash
pip install -r requirements.txt
```

### Scan Code
```bash
# Basic scan
python cli.py /path/to/code

# Save to JSON
python cli.py /path/to/code --output report.json

# Generate SARIF
python cli.py /path/to/code --output report.sarif

# Verbose mode
python cli.py /path/to/code --verbose
```

### Run Tests
```bash
python -m unittest tests.test_scanner -v
```

### Add New Language
1. Create `languages/newlang/queries/jwt_sinks.scm`
2. Update `config/languages.yaml`
3. Install parser: `pip install tree-sitter-newlang`
4. Test with sample files

### Customize Patterns
1. Edit language query files in `languages/*/queries/`
2. Restart scanner to load new patterns
3. Test with relevant code samples

## Key Classes & Functions

### Core Classes

**JWTSinkScanner** (`core/scanner.py`)
```python
scanner = JWTSinkScanner(config_path=None)
findings = scanner.scan_file(file_path)
findings = scanner.scan_directory(directory)
summary = scanner.get_summary()
```

**Finding** (`core/scanner.py`)
```python
Finding(
    file: str,
    line: int,
    column: int,
    function_name: str,
    code_snippet: str,
    severity: str,
    language: str,
    message: str
)
```

**ParserManager** (`core/parser_manager.py`)
```python
manager = ParserManager(config_path=None)
parser = manager.get_parser(language)
extensions = manager.get_extensions(language)
```

### Report Classes

**JSONReporter** (`reports/json_reporter.py`)
```python
reporter = JSONReporter(output_file=None)
reporter.add_findings(findings)
reporter.write_report(output_file)
report_dict = reporter.generate_report()
```

**SARIFReporter** (`reports/sarif_reporter.py`)
```python
reporter = SARIFReporter(output_file=None)
reporter.add_findings(findings)
reporter.write_report(output_file)
report_dict = reporter.generate_report()
```

## Detected Patterns

### Python
- `jwt.decode(token, secret)`
- `PyJWT().decode(token, secret)`
- `token.verify(secret)`

### PHP
- `JWT::decode($token, $key)`
- `Firebase\JWT\JWT::decode()`
- `$jwt->decode()`

### JavaScript
- `jwt.verify(token, secret)`
- `jsonwebtoken.verify(token, key)`
- `token.decode()`

### Java
- `Jwts.parser().setSigningKey().parseClaimsJws()`
- `JWTVerifier.verify()`
- `parser.parseClaimsJws()`

## Configuration

Edit `config/languages.yaml` to:
- Enable/disable languages
- Change file extensions
- Modify tree-sitter modules
- Adjust scanner settings

## Integration Examples

### GitHub Actions
```yaml
- name: Scan with JWT Detector
  run: python cli.py . --output report.sarif

- name: Upload to Code Scanning
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
      types: [python, php, javascript]
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `ImportError: tree_sitter_python not found` | `pip install tree-sitter-python` |
| No findings detected | Check file extensions match config, install language parser |
| Slow scanning | Scan smaller directories, large files take longer |
| Parser error | Enable `--verbose` flag for debugging |

## Exit Codes
- `0` - Success, no findings
- `1` - Success, findings detected
- `2` - Error occurred

## Performance Tips

- Scan specific subdirectories instead of entire projects
- Use `--lang` flag to limit language detection
- Large monorepos may benefit from split scans
- Exclude build/vendor directories

## Documentation Structure

1. **README.md** (7.7 KB)
   - Installation
   - Usage guide
   - Output formats
   - Configuration
   - Troubleshooting

2. **IMPLEMENTATION.md** (9.5 KB)
   - Architecture overview
   - Component descriptions
   - Extension points
   - Integration examples

3. **QUICK_REFERENCE.md** (4.8 KB)
   - Common commands
   - Pattern table
   - Common issues
   - Integration examples

4. **PROJECT_SUMMARY.md**
   - Completion summary
   - File statistics
   - Feature list
   - Quality metrics

## Next Steps

1. **Install**: `pip install -r requirements.txt`
2. **Run**: `python cli.py /path/to/code`
3. **Explore**: Check output and [README.md](README.md) for details
4. **Integrate**: Add to your CI/CD pipeline
5. **Extend**: Customize queries for your needs

## Support Resources

- **Full Guide**: [README.md](README.md)
- **Technical Details**: [IMPLEMENTATION.md](IMPLEMENTATION.md)
- **Quick Help**: [QUICK_REFERENCE.md](QUICK_REFERENCE.md)
- **Test Examples**: [tests/fixtures/](tests/fixtures/)

## Project Statistics

- **Total Files**: 21
- **Python Code**: ~800 lines
- **Documentation**: ~25 KB
- **Test Cases**: Comprehensive unit tests
- **Languages Supported**: 4
- **Output Formats**: 2 (JSON, SARIF)

## Key Features Summary

✓ **Tree-sitter AST Analysis** - Accurate syntax-aware pattern matching
✓ **Multi-language Support** - Python, PHP, JavaScript, Java
✓ **Multiple Output Formats** - JSON and SARIF standard compliance
✓ **Easy Integration** - CI/CD ready with examples
✓ **Extensible Architecture** - Add languages/patterns easily
✓ **Well-Tested** - Full test suite with fixtures
✓ **Production-Ready** - Enterprise-grade code quality
✓ **Comprehensive Docs** - Multiple documentation levels

---

**Last Updated**: November 30, 2024
**Version**: 1.0.0
**Status**: Production Ready ✓
