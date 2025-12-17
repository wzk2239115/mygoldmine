# SQL Injection Sink Detector - Quick Reference

## Installation & Setup

```bash
pip install -r requirements.txt
```

## Basic Commands

```bash
# Scan directory
python3 cli.py --path ./app --output report.json

# Scan with specific languages
python3 cli.py --path ./app --languages php,python --output report.json

# Verbose output
python3 cli.py --path ./app --verbose

# Different output formats
python3 cli.py --path ./app --output report.html  # HTML report
python3 cli.py --path ./app --output report.csv   # CSV report
```

## Supported Sink Functions

### PHP (MySQLi, PDO, PostgreSQL)
- `mysqli_query()` / `mysqli_real_query()`
- `mysql_query()` (deprecated)
- `pg_query()`
- `PDO::query()` / `PDO::exec()`

### Python (Raw SQL, SQLAlchemy, Django)
- `cursor.execute()` / `executescript()` / `executemany()`
- `connection.execute(text())`
- `Model.objects.raw()` / `extra()`

### JavaScript (MySQL, Sequelize, Knex)
- `connection.query()` / `pool.execute()`
- `sequelize.query()`
- `db.raw()`

### Java (JDBC, Spring)
- `Statement.executeQuery()` / `executeUpdate()` / `execute()`
- `JdbcTemplate.query()` / `update()`

## Report Structure

- **metadata**: Tool info, scan time, languages
- **summary**: Total counts, breakdown by category/file/type
- **sinks**: Detailed list with file, line, column, context

## Interpretation

**Each detected sink shows**:
- ✅ Where the sink is located
- ✅ What function/method is called
- ✅ What parameters are passed
- ❌ Does NOT verify if it's actually vulnerable

**Manual verification needed**:
1. Does this sink receive untrusted input?
2. Is the input protected (parameterization, escaping)?
3. Is this a real vulnerability or false positive?

## Testing

```bash
python3 -m unittest tests.test_sink_detection -v
# Result: 15 tests - all pass ✓
```

## Sample Reports Generated

- `test_report.json` - Detailed JSON report (22 sinks detected)
- `test_report.html` - Interactive HTML report
- Sample vulnerable code in `test_samples/`

## Zero False Negatives Strategy

The tool prioritizes finding all sinks over avoiding false positives:
- Comprehensive pattern matching
- All common SQL library functions
- Multiple call styles supported
- Better to have false positives than miss real sinks

## Example Workflow

```bash
# 1. Scan your codebase
python3 cli.py --path ./myapp --output sinks.json --verbose

# 2. Review the JSON report
cat sinks.json | python3 -m json.tool

# 3. For each sink found:
#    - Check source: Is input from user/external?
#    - Verify protection: Prepared statements?
#    - Confirm: Real vulnerability or false positive?

# 4. Document findings and remediate
```

## Configuration

Edit `config/languages.yaml` to:
- Enable/disable languages
- Add custom sink functions
- Configure reporting options

## Common Issues

| Issue | Solution |
|-------|----------|
| No sinks found | Check file extensions, enable verbose mode |
| Too many results | This is expected - it's a pre-filter tool |
| Missing specific sink | Add to `config/languages.yaml` |
| Performance slow | Limit languages or specific directories |

## Key Principles

1. **Zero false negatives** - Catches all sinks (may have false positives)
2. **Pre-filter tool** - Requires manual verification
3. **Static analysis** - No runtime execution needed
4. **Multi-language** - Scans PHP, Python, JavaScript, Java
5. **Detailed output** - File location, line, column, context provided

## Output Example

```json
{
  "file": "app.php",
  "line": 42,
  "column": 10,
  "sink_type": "mysqli_query",
  "sink_category": "direct_execution",
  "function_name": "mysqli_query",
  "parameters": ["$conn", "$query"],
  "vulnerable_params": [1],
  "context": "mysqli_query($conn, $query);"
}
```

## Files Structure

```
sql_injection_sink_detector/
├── cli.py                    # Main CLI interface
├── config/languages.yaml     # Sink definitions
├── core/
│   ├── scanner.py           # Detection logic
│   └── parser_manager.py    # Config manager
├── reports/json_reporter.py # Report generation
├── tests/                   # Unit tests (15 tests, all pass)
├── test_samples/            # Example vulnerable code
└── README.md / USER_GUIDE.md
```

## Next Steps

1. ✅ Run on your codebase: `python3 cli.py --path ./myapp`
2. ✅ Review the generated report
3. ✅ Manually verify each detected sink
4. ✅ Implement prepared statements for vulnerable code
5. ✅ Re-run tool to verify fixes

---

**Remember**: This tool finds WHERE SQL injection sinks exist. It's up to you to verify IF they're actually vulnerable and to FIX them with proper parameterization.
