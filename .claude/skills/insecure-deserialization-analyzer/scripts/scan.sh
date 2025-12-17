#!/bin/bash

################################################################################
# Insecure Deserialization Sink Detector - Scanning Script
#
# Usage:
#   bash scan.sh <target_directory> [options]
#   bash scan.sh ~/WebGoat/
#   bash scan.sh ~/WebGoat/ --lang python
#   bash scan.sh ~/WebGoat/ --output json --report findings.json
#
# Options:
#   --lang LANGUAGE      Programming language (php, python, java, javascript)
#   --output FORMAT      Output format (json, sarif) [default: json]
#   --report FILE        Output report file path
#   --verbose            Enable verbose output
#   --help               Show this help message
#
################################################################################

set -e

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DETECTOR_DIR="$SCRIPT_DIR"

# Default options
TARGET_DIR=""
LANGUAGE=""
OUTPUT_FORMAT="text"
REPORT_FILE=""
VERBOSE=false
SHOW_HELP=false

################################################################################
# Functions
################################################################################

print_help() {
    cat << 'EOF'
Insecure Deserialization Sink Detector - Scanning Script

Usage:
  bash scan.sh <target_directory> [options]

Examples:
  bash scan.sh ~/WebGoat/
  bash scan.sh ~/WebGoat/ --lang python
  bash scan.sh ~/WebGoat/ --output json --report findings.json
  bash scan.sh ~/WebGoat/ --verbose --output sarif --report report.sarif

Options:
  --lang LANGUAGE        Programming language to scan
                        Choices: php, python, java, javascript, typescript, c, cpp, go, rust
                        If not specified, all languages are scanned

  --output FORMAT        Output format for report
                        Choices: text (default), json, sarif

  --report FILE          Save report to file instead of stdout
                        Example: --report findings.txt

  --verbose              Show detailed scanning information

  --help                 Show this help message

Output Formats:
  text                   Plain text format with compact sink information
  json                   Standard JSON with statistics summary
  sarif                  OASIS SARIF format for tool integration

Detected Vulnerabilities:

  PHP:
    - unserialize()
    - __wakeup(), __destruct(), __unserialize()
    - json_decode(), simplexml_load_string()

  Python:
    - pickle.loads(), pickle.load()
    - yaml.load(), yaml.unsafe_load(), yaml.full_load()
    - dill.loads(), cloudpickle.loads()
    - marshal.loads()
    - shelve operations

  Java:
    - ObjectInputStream.readObject(), readUnshared()
    - Jackson ObjectMapper.readValue()
    - XStream.fromXML()
    - SnakeYAML Yaml.load()
    - Class.forName()

  JavaScript:
    - eval()
    - new Function()
    - vm.runInContext(), vm.runInNewContext()
    - setTimeout/setInterval with string code
    - dynamic require() and import()

  TypeScript:
    - eval()
    - new Function()
    - vm.runInContext(), vm.runInNewContext()
    - dynamic require() and import()

  C:
    - memcpy(), memmove(), strcpy()
    - fread(), recv(), read()
    - Unsafe buffer operations

  C++:
    - std::memcpy(), std::memmove()
    - Stream read operations
    - Unsafe pointer casts

  Go:
    - encoding/gob Decode()
    - encoding/json Unmarshal()
    - encoding/xml Unmarshal()
    - encoding/yaml Unmarshal()
    - unsafe.Pointer operations

  Rust:
    - serde deserialize()
    - serde_json from_str(), from_slice()
    - bincode decode()
    - unsafe transmute()
    - unsafe memory operations


EOF
}

print_info() {
    if [ "$VERBOSE" = true ]; then
        echo "[*] $1"
    fi
}

print_success() {
    echo "[+] $1"
}

print_warning() {
    echo "[!] $1"
}

print_error() {
    echo "[ERROR] $1"
}

check_dependencies() {
    print_info "Checking dependencies..."

    # Check Python
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is not installed"
        exit 1
    fi
    print_info "Python 3: $(python3 --version)"

    # Check detector exists
    if [ ! -d "$DETECTOR_DIR" ]; then
        print_error "Detector directory not found: $DETECTOR_DIR"
        exit 1
    fi
    print_info "Detector found: $DETECTOR_DIR"

    # Check if cli.py exists
    if [ ! -f "$DETECTOR_DIR/cli.py" ]; then
        print_error "CLI script not found: $DETECTOR_DIR/cli.py"
        exit 1
    fi
    print_info "CLI script found"
}

validate_language() {
    if [ -n "$LANGUAGE" ]; then
        case "$LANGUAGE" in
            php|python|java|javascript|typescript|c|cpp|go|rust)
                print_info "Language: $LANGUAGE"
                ;;
            *)
                print_error "Invalid language: $LANGUAGE"
                echo "Valid options: php, python, java, javascript, typescript, c, cpp, go, rust"
                exit 1
                ;;
        esac
    else
        print_info "Language: auto-detect (all supported languages)"
    fi
}

validate_output_format() {
    case "$OUTPUT_FORMAT" in
        json|sarif|text)
            print_info "Output format: $OUTPUT_FORMAT"
            ;;
        *)
            print_error "Invalid output format: $OUTPUT_FORMAT"
            echo "Valid options: json, sarif, text"
            exit 1
            ;;
    esac
}

validate_target() {
    if [ -z "$TARGET_DIR" ]; then
        print_error "Target directory not specified"
        print_help
        exit 1
    fi

    if [ ! -e "$TARGET_DIR" ]; then
        print_error "Target path does not exist: $TARGET_DIR"
        exit 1
    fi

    # Expand ~ and convert to absolute path
    TARGET_DIR=$(cd "$TARGET_DIR" 2>/dev/null && pwd) || TARGET_DIR="$TARGET_DIR"

    print_info "Target: $TARGET_DIR"

    if [ ! -d "$TARGET_DIR" ]; then
        print_warning "Target is a file, not a directory"
    fi
}

run_scan() {
    print_info "Starting scan..."

    # Build command
    local cmd="python3 $DETECTOR_DIR/cli.py"

    # Add language option if specified
    if [ -n "$LANGUAGE" ]; then
        cmd="$cmd --lang $LANGUAGE"
    fi

    # Add output format
    cmd="$cmd --output $OUTPUT_FORMAT"

    # Add report file if specified
    if [ -n "$REPORT_FILE" ]; then
        cmd="$cmd --report $REPORT_FILE"
    fi

    # Add verbose flag if enabled
    if [ "$VERBOSE" = true ]; then
        cmd="$cmd --verbose"
    fi

    # Add target directory
    cmd="$cmd $TARGET_DIR"

    print_info "Executing: $cmd"
    echo ""

    # Run the scan
    cd "$DETECTOR_DIR"
    if eval "$cmd"; then
        local exit_code=0
    else
        local exit_code=$?
    fi

    return $exit_code
}

print_results_summary() {
    if [ -n "$REPORT_FILE" ] && [ -f "$REPORT_FILE" ]; then
        print_success "Report saved to: $REPORT_FILE"

        if command -v python3 &> /dev/null; then
            # Extract statistics from JSON
            if [ "$OUTPUT_FORMAT" = "json" ]; then
                local total=$(python3 -c "import json; data=json.load(open('$REPORT_FILE')); print(data.get('summary', {}).get('total_sinks', 0))" 2>/dev/null)
                if [ -n "$total" ] && [ "$total" -gt 0 ]; then
                    print_warning "Found $total deserialization sinks"
                else
                    print_success "No deserialization sinks found"
                fi
            fi
        fi
    else
        # When output to stdout, show brief summary
        if [ "$VERBOSE" = false ]; then
            echo ""
        fi
    fi
}

################################################################################
# Main Script
################################################################################

# Parse command-line arguments
# Support both positional and flag arguments
# Examples: scan.sh ~/WebGoat/
#           scan.sh ~/WebGoat/ --lang python
#           scan.sh --lang python ~/WebGoat/ --report findings.json
while [[ $# -gt 0 ]]; do
    case $1 in
        --help|-h)
            SHOW_HELP=true
            shift
            ;;
        --lang)
            LANGUAGE="$2"
            shift 2
            ;;
        --output|-o)
            OUTPUT_FORMAT="$2"
            shift 2
            ;;
        --report|-r)
            REPORT_FILE="$2"
            shift 2
            ;;
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        -*)
            print_error "Unknown option: $1"
            print_help
            exit 1
            ;;
        *)
            # First non-flag argument is the target directory
            if [ -z "$TARGET_DIR" ]; then
                TARGET_DIR="$1"
            fi
            shift
            ;;
    esac
done

# Show help if requested
if [ "$SHOW_HELP" = true ]; then
    print_help
    exit 0
fi

# Print header
echo "======================================================================"
echo "  Insecure Deserialization Sink Detector - Scan Script"
echo "======================================================================"
echo ""

# Run validation checks
check_dependencies
echo ""

validate_target
validate_language
validate_output_format

# Only print detailed info if verbose
if [ "$VERBOSE" = true ]; then
    echo ""
fi

# Run the scan
print_success "Scan configuration ready"
if [ "$VERBOSE" = true ]; then
    echo ""
fi

run_scan
SCAN_EXIT_CODE=$?

echo ""
print_results_summary

if [ $SCAN_EXIT_CODE -eq 0 ]; then
    print_success "Scan completed successfully"
    exit 0
else
    print_warning "Scan completed with findings (exit code: $SCAN_EXIT_CODE)"
    exit $SCAN_EXIT_CODE
fi
