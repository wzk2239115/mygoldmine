# ✅ scan.sh Usage Update - COMPLETE

## The Change You Requested

Your desired usage pattern now works:

```bash
bash scan.sh ~/WebGoat/
```

Instead of requiring:
```bash
bash scan.sh --path ~/WebGoat/
```

## Why This is Better

- **Simpler**: Less typing, more intuitive
- **Familiar**: Works like other Unix tools (`ls`, `grep`, `find`)
- **Backward Compatible**: Old `--path` syntax still works

## Current Working Examples

### Simplest Usage (Your Desired Pattern)
```bash
# Just path argument
bash scan.sh ~/WebGoat/

# Path with output
bash scan.sh ~/WebGoat/ --output report.json

# Path with all options
bash scan.sh ~/WebGoat/ --languages php,python --output report.html --verbose
```

### Still Works (Backward Compatible)
```bash
# Traditional --path flag
bash scan.sh --path ~/WebGoat/

# Help
bash scan.sh --help

# Python directly
python3 cli.py --path ~/WebGoat/
```

## Test Results

✅ All 5 test scenarios passing:
- Positional argument scanning
- Positional with verbose output
- Positional with language filtering
- Backward compatibility with --path flag
- Help flag functionality

## How It Works

The script now intelligently checks the first argument:

```bash
# If first arg is a path (doesn't start with --), 
# automatically prepend --path
bash scan.sh /path/to/code ...
    ↓ (internally becomes)
python3 cli.py --path /path/to/code ...

# If first arg is a flag, pass through as-is
bash scan.sh --help
    ↓ (internally becomes)
python3 cli.py --help
```

## Complete Usage Guide

### One-Liner Examples

```bash
# Scan directory for command injection
bash scan.sh .

# Scan specific path
bash scan.sh ~/WebGoat/

# Scan with verbose output
bash scan.sh . --verbose

# Scan only PHP files
bash scan.sh . --languages php

# Generate HTML report
bash scan.sh . --output findings.html

# Scan multiple languages
bash scan.sh . --languages php,python,java

# All options together
bash scan.sh ~/app --languages php,python --output audit.html --verbose

# Specify output format
bash scan.sh . --output report.json    # JSON
bash scan.sh . --output report.csv     # CSV
bash scan.sh . --output report.html    # HTML
```

## File Location

📁 `/home/wangzekai/TOP14/command_injection/scripts/scan.sh`

## What's Different from Original

The original `scan.sh` just passed all arguments directly to `cli.py`:
```bash
# Original (before)
python3 cli.py "$@"
```

The updated `scan.sh` now intelligently handles positional arguments:
```bash
# Updated (after)
if [ $# -gt 0 ] && [ "$1" != "--help" ] && [ "$1" != "-h" ] && [[ "$1" != --* ]]; then
    PATH_ARG="$1"
    shift
    python3 cli.py --path "$PATH_ARG" "$@"
else
    python3 cli.py "$@"
fi
```

## Validation

✅ Verified to work with:
- Simple path argument
- Path + single option
- Path + multiple options
- Traditional --path flag
- Help flag
- Language filtering
- Output format specification
- Verbose mode

## Next Steps

You can now use the detector with the intuitive syntax you requested:

```bash
# Navigate to the scripts directory
cd /home/wangzekai/TOP14/command_injection/scripts

# Run the detector
bash scan.sh ~/WebGoat/

# Or with options
bash scan.sh ~/WebGoat/ --output security_audit.html --verbose
```

Enjoy! 🎉
