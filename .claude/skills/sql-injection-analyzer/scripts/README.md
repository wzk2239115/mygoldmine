# SQL Injection Sink Detector

A static code analysis tool designed to detect SQL injection sinks across multiple programming languages with **zero false negatives** (may tolerate false positives).

## ⚠️ Important Caveat

This is a **pre-filter/screening tool**. All detected sinks require **manual verification** to confirm:
- Whether the detected sink actually receives user input
- Whether proper sanitization/parameterization is in place
- Whether the detection is a true positive or false positive

## Supported Languages

- PHP (mysqli, PDO)
- Python (raw SQL, SQLAlchemy, Django ORM)
- Java (JDBC, Spring)
- JavaScript/TypeScript (MySQL, PostgreSQL, ORM libraries)

## Architecture

### Core Components

- **Scanner**: Tree-sitter based static analysis engine
- **Parser Manager**: Language-specific query manager
- **Config**: YAML-based sink definitions
- **Reporter**: JSON output with detailed location info

## Usage

```bash
python cli.py --path <directory> --languages php,python,java,javascript --output report.json
```

## Output Format

```json
{
  "sinks": [
    {
      "file": "app.php",
      "line": 42,
      "column": 10,
      "sink_type": "mysqli_query",
      "sink_category": "direct_execution",
      "function_name": "mysqli_query",
      "parameters": ["$query"],
      "context": "mysqli_query($conn, $query)"
    }
  ],
  "summary": {
    "total_sinks": 150,
    "by_type": {},
    "by_file": {}
  }
}
```

## Detection Strategy

### Why Zero False Negatives?

The tool uses **comprehensive matching patterns** for each language:

1. **Function calls** - Direct database execution functions
2. **Method calls** - Instance/class methods on DB connections
3. **ORM misuse** - Unsafe patterns in ORM frameworks
4. **Template injection** - Raw SQL in template engines

### Philosophy

- **Prefer false positives** over false negatives
- If unsure, flag it
- Manual review is the final validation step
