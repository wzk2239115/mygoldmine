# Quick Start Guide

## Installation

```bash
# Install core dependencies
pip install -r requirements.txt

# Install optional tree-sitter language bindings
# (only for languages you want to scan)
pip install tree-sitter-python
pip install tree-sitter-php
pip install tree-sitter-javascript
pip install tree-sitter-java
```

## First Scan

### 1. Scan a File

```bash
# Scan a Python file
python cli.py tests/fixtures/python/django_sqlalchemy_examples.py

# Scan a PHP file
python cli.py tests/fixtures/php/model_updates.php
```

### 2. Generate Reports

```bash
# Generate JSON report
python cli.py --output json --report findings.json /path/to/code

# Generate SARIF report for IDE integration
python cli.py --output sarif --report findings.sarif /path/to/code
```

### 3. Run Tests

```bash
# Run automated tests
python -m unittest tests.test_scanner -v

# Or with pytest
pytest tests/test_scanner.py -v
```

## Common Usage Patterns

### Django Project Scan

```bash
python cli.py --lang python --output json --report django_findings.json /path/to/django_app
```

### Laravel Project Scan

```bash
python cli.py --lang php --output json --report laravel_findings.json /path/to/laravel_project
```

### Node.js/TypeScript Project Scan

```bash
python cli.py --lang javascript --output sarif --report node_findings.sarif /path/to/nodejs_project
```

### Spring Boot Project Scan

```bash
python cli.py --lang java --output json --report spring_findings.json /path/to/spring_project
```

## Understanding Reports

### JSON Report Fields

- **file**: Path to the vulnerable file
- **line**: Line number where vulnerability detected
- **column**: Column number for precise location
- **type**: Vulnerability type (MASS_ASSIGNMENT)
- **code**: Actual code snippet
- **message**: Description of the issue
- **severity**: Risk level (HIGH, MEDIUM, LOW)

### SARIF Report

SARIF (Static Analysis Results Interchange Format) is compatible with:
- GitHub Code Scanning
- GitLab SAST
- Azure DevOps
- SonarQube
- Most modern IDEs

## Troubleshooting

### Module Not Found Errors

Install missing language bindings:
```bash
pip install tree-sitter-python tree-sitter-php tree-sitter-javascript tree-sitter-java
```

### No Findings Detected

1. Verify file language is supported
2. Check file extension is in config
3. Run with verbose output for debugging

### Permission Errors

```bash
# Make CLI executable
chmod +x cli.py

# Run with python explicitly
python cli.py /path/to/code
```

## Next Steps

1. Customize patterns in `languages/<lang>/queries/sinks.scm`
2. Add your own test fixtures in `tests/fixtures/`
3. Integrate into CI/CD pipeline (use SARIF output)
4. Configure IDE integration for real-time warnings
