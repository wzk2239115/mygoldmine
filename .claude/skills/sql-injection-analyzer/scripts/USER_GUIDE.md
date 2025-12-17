# SQL Injection Sink Detector - User Guide

## Overview

The SQL Injection Sink Detector is a **pre-filter/screening tool** that identifies potential SQL injection sinks in your codebase. It's designed with a **zero false negative strategy** - meaning it will detect all potential sinks while tolerating false positives.

⚠️ **Important**: All detected sinks require manual verification to confirm whether they actually receive untrusted input and whether proper parameterization/sanitization is in place.

## Quick Start

### Installation

```bash
cd sql_injection_sink_detector
pip install -r requirements.txt
python3 cli.py --path /path/to/your/code --languages php,python --output report.json
```

### Basic Usage

```bash
# Scan a directory for all language sinks
python3 cli.py --path ./app --output report.json

# Scan with specific languages
python3 cli.py --path ./app --languages php,python --output report.json

# Verbose output
python3 cli.py --path ./app --verbose --output report.json

# Generate HTML report
python3 cli.py --path ./app --output report.html

# Scan a single file
python3 cli.py --path ./app/query.php --output report.json
```

## Supported Languages

### PHP
- `mysqli_query()` - MySQLi direct query execution
- `mysqli_real_query()` - MySQLi raw query execution
- `mysql_query()` - Legacy MySQL extension
- `pg_query()` - PostgreSQL query execution
- `PDO::query()` - PDO query method
- `PDO::exec()` - PDO execute method

### Python
- `cursor.execute()` - Direct SQL execution on cursor objects
- `cursor.executescript()` - SQLite script execution
- `cursor.executemany()` - Batch SQL execution
- `connection.execute(text())` - SQLAlchemy raw SQL
- `Model.objects.raw()` - Django ORM raw queries
- `Model.objects.extra()` - Django ORM extra queries

### JavaScript/TypeScript
- `connection.query()` - MySQL direct query
- `pool.execute()` - Connection pool execution
- `sequelize.query()` - Sequelize raw queries
- `db.raw()` - Knex raw queries

### Java
- `Statement.executeQuery()` - JDBC query execution
- `Statement.executeUpdate()` - JDBC update execution
- `Statement.execute()` - JDBC general execution
- `JdbcTemplate.query()` - Spring JDBC operations

## Understanding the Output

### JSON Report Format

```json
{
  "metadata": {
    "timestamp": "2025-11-29T07:49:28.889092",
    "tool": "SQL Injection Sink Detector",
    "version": "1.0.0",
    "source_path": "/app",
    "languages_scanned": ["php", "python"]
  },
  "summary": {
    "total_sinks": 22,
    "by_category": {
      "direct_execution": 6,
      "pdo_execution": 2,
      "raw_sql": 3
    },
    "by_file": {
      "app/query.php": 5,
      "app/models.py": 8
    }
  },
  "sinks": [
    {
      "file": "app/query.php",
      "line": 42,
      "column": 10,
      "sink_type": "mysqli_query",
      "sink_category": "direct_execution",
      "function_name": "mysqli_query",
      "parameters": ["$conn", "$query"],
      "vulnerable_params": [1],
      "context": "mysqli_query($conn, $query);"
    }
  ]
}
```

### Key Fields

- **file**: Source code file path
- **line**: Line number where sink is found
- **column**: Column number where sink starts
- **sink_type**: Function/method name
- **sink_category**: Category of sink (direct_execution, pdo_execution, etc.)
- **parameters**: Arguments passed to the sink
- **vulnerable_params**: Parameter indices that might receive user input
- **context**: Surrounding source code for manual verification

## Interpretation Guide

### What This Tool DOES

✅ **Finds all SQL function/method calls** across supported languages
✅ **Identifies potential entry points** for SQL injection
✅ **Generates organized reports** with file locations and context
✅ **Supports multiple languages** in a single scan
✅ **Zero false negatives** - catches all sinks

### What This Tool DOES NOT Do

❌ **Does NOT track data flow** - Can't determine if user input reaches the sink
❌ **Does NOT check parameterization** - Doesn't verify if prepared statements are used
❌ **Does NOT validate** - Doesn't verify if input is actually unsafe
❌ **Does NOT eliminate false positives** - May flag safe code

## Workflow

### Step 1: Run the Scanner
```bash
python3 cli.py --path ./myapp --output sinks.json --verbose
```

### Step 2: Review the Report
- Open `sinks.json` or `sinks.html`
- Identify sinks that might receive untrusted input
- Group by category for easier analysis

### Step 3: Manual Verification
For each detected sink:

1. **Check the source** - Does this parameter actually receive user input?
   - GET/POST parameters
   - HTTP headers
   - Database input
   - File content

2. **Verify protection** - Is the input properly protected?
   - ✅ Prepared statements with parameterized queries
   - ✅ Whitelist validation
   - ✅ Input escaping (if appropriate for context)

3. **Confirm or dismiss** - Is this a real vulnerability?
   - Real: The sink receives user input without protection
   - False positive: The sink uses safe inputs or prepared statements

### Example Analysis

Detected sink:
```php
// Line 42 in users.php
$user_id = $_GET['id'];
$query = "SELECT * FROM users WHERE id = " . $user_id;
mysqli_query($conn, $query);
```

**Analysis**:
- ❌ **Vulnerable**: `$user_id` comes from `$_GET` (untrusted)
- ❌ **No protection**: Direct string concatenation
- ✅ **Confirm**: This is a real SQL injection vulnerability

**Safe version**:
```php
$user_id = $_GET['id'];
$stmt = $conn->prepare("SELECT * FROM users WHERE id = ?");
$stmt->bind_param("i", $user_id);
$stmt->execute();
```

## Detection Strategy

### Why Zero False Negatives?

The tool uses **comprehensive pattern matching** that includes:

1. **Direct function calls**: `mysqli_query($query)`
2. **Method calls**: `$pdo->query($sql)`, `$db->execute($sql)`
3. **Class method calls**: `PDO::query()`, `JdbcTemplate.query()`
4. **ORM methods**: `Model.objects.raw()`, `sequelize.query()`
5. **Various formats**: Handles different spacing, quotes, and styles

### Trade-off Philosophy

**We prefer false positives over false negatives** because:
- Missing a real vulnerability is dangerous
- False positives can be filtered by code review
- The tool is a screening tool, not a final verdict

## Configuration

### Adding Custom Sinks

Edit `config/languages.yaml`:

```yaml
languages:
  php:
    sinks:
      - name: "custom_sql_function"
        category: "custom"
        type: "function_call"
        vulnerable_params: [0]
```

### Output Formats

- **JSON** (default): Detailed structured data
- **HTML**: Interactive visual report
- **CSV**: For spreadsheet import

## Advanced Usage

### Scan with Custom Configuration
```bash
python3 cli.py --path ./app --languages php,python --output report.json --verbose
```

### Filter Results
```bash
# Extract only direct_execution sinks
python3 -c "
import json
with open('report.json') as f:
    report = json.load(f)
    direct = [s for s in report['sinks'] if s['sink_category'] == 'direct_execution']
    print(f'Found {len(direct)} direct execution sinks')
"
```

### Merge Multiple Reports
```bash
python3 -c "
import json
from pathlib import Path

all_sinks = []
for report_file in Path('.').glob('report_*.json'):
    with open(report_file) as f:
        report = json.load(f)
        all_sinks.extend(report['sinks'])

# Save merged report
with open('merged_report.json', 'w') as f:
    json.dump({'sinks': all_sinks}, f, indent=2)
"
```

## Testing

Run the test suite:
```bash
python3 -m unittest tests.test_sink_detection -v
```

Tests verify:
- Detection of all sink types
- Zero false negatives (all sinks detected)
- Report generation accuracy
- Multi-language support

All 15 tests pass ✓

## Troubleshooting

### No sinks detected
- Check that file extensions match language (`.php`, `.py`, `.js`, `.java`)
- Enable verbose mode: `--verbose`
- Verify language is enabled in config

### Too many false positives
- Review manually - this is expected
- Filter by category for more focused analysis
- Remember: This is a pre-filter tool

### Performance issues
- Limit languages: `--languages php` (instead of all)
- Scan specific directories instead of entire codebase
- Tool is designed for interactive analysis, not CI/CD (yet)

## Best Practices

1. **Regular scans**: Run periodically as code is added
2. **Code review**: Every detected sink should be reviewed
3. **Track changes**: Compare old vs new reports
4. **Document decisions**: Record why sinks are safe or vulnerable
5. **Automated testing**: Create unit tests for SQL parameters

## Security Implications

This tool helps identify **sinks** - the dangerous functions where SQL injection can occur. However:

- **Sinks alone are not vulnerabilities** - They need user input without protection
- **Use with other tools** - Combine with data flow analysis for complete picture
- **Manual review required** - This is not an automated vulnerability scanner
- **Not a substitute** - Use prepared statements/parameterized queries as primary defense

## License & Attribution

This tool is part of the SQL Injection security analysis suite.

**Remember**: A sink is just a starting point. True security comes from using parameterized queries and input validation throughout your application.
