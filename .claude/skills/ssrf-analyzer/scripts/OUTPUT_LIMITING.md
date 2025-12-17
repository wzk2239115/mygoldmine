# Output Limiting Feature

## Overview

The SSRF Sink Detector now includes output limiting features to handle large scan results effectively. When scanning large projects (like WebGoat with 267+ results), you can now control how results are displayed.

## Features

### 1. Summary Mode (`--summary`)

Shows only aggregated counts by language and severity level, not individual findings.

**Use when:** You want a quick overview of vulnerability distribution without detailed listings.

```bash
bash scan.sh --summary /path/to/code
```

**Example output:**
```
Found 267 potential SSRF sinks

By Severity:
  HIGH: 267

By Language:
  cpp: 45
  java: 89
  javascript: 78
  php: 15
  python: 40
```

### 2. Result Limiting (`--limit N`)

Shows only the first N results, with a note indicating total count.

**Use when:** You want to see sample findings without massive output.

```bash
bash scan.sh --limit 50 /path/to/code
```

**Example output:**
```
Found 267 potential SSRF sinks (showing first 50):

file: path/to/file1.js,line: 45,column: 12,sink_name: fetch,language: javascript,severity: high,snippet: "..."
file: path/to/file2.java,line: 78,column: 8,sink_name: HttpGet,language: java,severity: high,snippet: "..."
...
(50 results shown)
...
Note: Showing 50 of 267 results. Use --limit to see more.
```

### 3. Default Mode (no options)

Shows all results (default behavior for backwards compatibility).

```bash
bash scan.sh /path/to/code
```

## Recommended Usage Patterns

### For Quick Analysis
```bash
# Get overview of vulnerabilities
bash scan.sh --summary ~/WebGoat/
```

### For Detailed Investigation (Limited)
```bash
# See first 50 findings
bash scan.sh --limit 50 ~/WebGoat/

# See first 100 findings
bash scan.sh --limit 100 ~/WebGoat/
```

### For Complete Analysis
```bash
# Generate full JSON report for processing
python3 cli.py --output json ~/WebGoat/ > full_report.json

# Then analyze with external tools as needed
```

## Combining with Other Options

The output limiting options work in the scan.sh wrapper script. The underlying CLI still supports full options:

```bash
# Use CLI directly for more control
python3 cli.py --lang java --output json /path/to/code
```

## Performance Impact

- **--summary mode**: Fastest - scans entire codebase but displays summary only
- **--limit N mode**: Same speed as default, just truncates display output
- **Default mode**: No performance impact, just displays all results

## Example: Scanning WebGoat

The previous scan of WebGoat found 267 results. Now you can handle it efficiently:

```bash
# Quick overview (1 second)
bash scan.sh --summary ~/WebGoat/

# See first 50 findings (2-3 seconds)
bash scan.sh --limit 50 ~/WebGoat/

# Generate structured report for analysis
python3 cli.py --output json ~/WebGoat/ > webgoat_report.json
```

## File Size Considerations

When scanning large projects:
- Text output can be very long (267 results = ~50KB+ text)
- JSON output is more efficient for programmatic processing
- Summary mode produces minimal output (~200 bytes)

## Help Command

```bash
bash scan.sh --help
```

Shows all available options and examples.
