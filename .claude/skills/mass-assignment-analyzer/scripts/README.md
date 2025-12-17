# Mass Assignment Sink Detector

A comprehensive static analysis tool for detecting mass assignment vulnerabilities across multiple programming languages using tree-sitter.

## Overview

Mass assignment vulnerabilities occur when an application blindly assigns all user input to model properties without proper validation. This can lead to:

- **Privilege Escalation**: Users modifying admin flags or role attributes
- **Data Manipulation**: Bypassing business logic restrictions
- **Information Disclosure**: Accessing unauthorized fields

## Supported Languages

- **PHP**: Laravel, Yii, Symfony
- **Python**: Django ORM, SQLAlchemy, Pydantic
- **Java**: Spring Data JPA, Hibernate, MapStruct, ModelMapper
- **JavaScript/TypeScript**: Sequelize, Mongoose, TypeORM, Prisma

## Project Structure

```
mass_assignment_sink_detector/
├── config/
│   └── languages.yaml              # Language configuration
├── core/
│   ├── scanner.py                  # Main scanning engine
│   └── parser_manager.py           # Tree-sitter parser management
├── languages/
│   ├── php/queries/sinks.scm       # PHP patterns
│   ├── python/queries/sinks.scm    # Python patterns
│   ├── java/queries/sinks.scm      # Java patterns
│   └── javascript/queries/sinks.scm # JavaScript patterns
├── reports/
│   ├── json_reporter.py            # JSON output
│   └── sarif_reporter.py           # SARIF output
├── tests/
│   ├── fixtures/                   # Test samples
│   └── test_scanner.py             # Unit tests
├── cli.py                          # Command-line interface
└── README.md                       # This file
```

## Installation

### Requirements

- Python 3.7+
- tree-sitter bindings for target languages

### Setup

```bash
# Install dependencies
pip install tree-sitter pyyaml

# Install language-specific tree-sitter bindings
pip install tree-sitter-python tree-sitter-php tree-sitter-javascript tree-sitter-java
```

## Usage

### Basic Scanning

```bash
# Scan a single file (language auto-detected)
python cli.py /path/to/code.py

# Scan a directory
python cli.py /path/to/project

# Specify language explicitly
python cli.py --lang python /path/to/code
```

### Output Formats

```bash
# JSON output (default)
python cli.py --output json /path/to/code

# SARIF output (for integration with IDE/CI tools)
python cli.py --output sarif /path/to/code

# Save report to file
python cli.py --output json --report results.json /path/to/code
python cli.py --output sarif --report results.sarif /path/to/code
```

### Examples

```bash
# Scan Django project
python cli.py --lang python --output json --report django_report.json /home/user/django_project

# Scan PHP Laravel application
python cli.py --lang php --output sarif /var/www/laravel_app

# Scan TypeScript Node.js project
python cli.py --lang javascript --output json /path/to/nodejs_project
```

## Detection Patterns

### PHP

Detects:
- `Model::create($request->all())`
- `$model->fill($data)`
- `$model->setAttributes($data)`
- `Model::firstOrCreate($data)`
- `Model::updateOrCreate($data)`

### Python

Detects:
- `Model.objects.create(**request.POST.dict())`
- `Model.objects.update_or_create(**data)`
- `session.add(Model(**data))`
- `Model(**data)` instantiation
- `Model.parse_obj(data)`

### Java

Detects:
- `BeanUtils.copyProperties(source, target)`
- `entity.setProperty()` patterns
- `repository.save()` with mapper
- `ModelMapper.map()` usage
- Loop-based property assignment

### JavaScript

Detects:
- `Model.create(req.body)`
- `Model.findByIdAndUpdate(id, data)`
- `session.add(new Model(data))`
- `Object.assign(target, source)`
- Direct property assignment in loops

## How It Works

1. **File Detection**: Auto-detects file language from extension
2. **Parsing**: Uses tree-sitter to parse code into abstract syntax trees
3. **Pattern Matching**: Applies language-specific queries to detect vulnerable patterns
4. **Reporting**: Generates findings in JSON or SARIF format

## Testing

Run automated tests:

```bash
python -m pytest tests/
# or
python tests/test_scanner.py
```

Test fixtures are located in `tests/fixtures/` and include both vulnerable and safe examples.

## Output Examples

### JSON Report

```json
{
  "metadata": {
    "tool": "mass_assignment_sink_detector",
    "version": "1.0.0",
    "timestamp": "2024-01-15T10:30:00",
    "total_findings": 3
  },
  "findings": [
    {
      "file": "/app/controllers/UserController.php",
      "line": 15,
      "column": 20,
      "type": "MASS_ASSIGNMENT",
      "code": "User::create($request->all());",
      "message": "Potential mass assignment vulnerability using 'create'",
      "severity": "HIGH"
    }
  ]
}
```

### SARIF Report

Compliant with [SARIF 2.1.0](https://docs.oasis-open.org/sarif/sarif/v2.1.0/sarif-v2.1.0.html) standard for tool integration with IDEs and CI/CD systems.

## Configuration

Modify `config/languages.yaml` to:
- Enable/disable languages
- Customize file extensions
- Adjust scanner priority

```yaml
languages:
  php:
    extensions:
      - .php
    tree_sitter_module: tree_sitter_php
    priority: 1
```

## Limitations

- Requires tree-sitter language bindings to be installed
- Pattern-based detection may have false positives/negatives
- Cannot perform data flow analysis
- Context-aware analysis requires additional configuration

## Best Practices

### Remediation

When findings are detected, follow these remediation steps:

1. **Use Allowlists**: Explicitly define which fields can be mass-assigned
   ```php
   // PHP Laravel example
   protected $fillable = ['name', 'email'];
   ```

2. **Input Validation**: Always validate user input before assignment
   ```python
   # Django example
   user = User.objects.create(**validated_data)
   ```

3. **Use DTOs**: Transfer objects with explicit fields
   ```java
   // Java example
   User user = mapper.map(userDto, User.class);
   ```

4. **Review Permissions**: Ensure only authorized fields can be modified

## Contributing

To extend the detector:

1. Add new language patterns in `languages/<lang>/queries/sinks.scm`
2. Add test fixtures in `tests/fixtures/<lang>/`
3. Update language config in `config/languages.yaml`

## License

MIT License

## References

- [OWASP: Mass Assignment](https://owasp.org/www-community/Mass_Assignment)
- [CWE-915: Improperly Controlled Multiple Inheritance](https://cwe.mitre.org/data/definitions/915.html)
- [Tree-sitter Documentation](https://tree-sitter.github.io/)
- [SARIF Standard](https://docs.oasis-open.org/sarif/sarif/v2.1.0/sarif-v2.1.0.html)
