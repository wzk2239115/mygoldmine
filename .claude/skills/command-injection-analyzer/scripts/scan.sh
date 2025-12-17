#!/bin/bash
# Command Injection Sink Detector - Convenient scanning script

set -e

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is required"
    exit 1
fi

# Check if pyyaml is installed
python3 -c "import yaml" 2>/dev/null || {
    echo "Installing required dependencies..."
    pip3 install -q -r requirements.txt
}

# Default output file
OUTPUT_FILE=""
DISPLAY_ONLY=true

# Parse arguments to check if output file is specified
TEMP_ARGS=()
SKIP_NEXT=false

for arg in "$@"; do
    if [ "$SKIP_NEXT" = true ]; then
        OUTPUT_FILE="$arg"
        DISPLAY_ONLY=false
        SKIP_NEXT=false
        continue
    fi

    if [ "$arg" = "--output" ] || [ "$arg" = "-o" ]; then
        SKIP_NEXT=true
        continue
    fi

    TEMP_ARGS+=("$arg")
done

# Handle positional argument for path
if [ ${#TEMP_ARGS[@]} -gt 0 ] && [ "${TEMP_ARGS[0]}" != "--help" ] && [ "${TEMP_ARGS[0]}" != "-h" ] && [[ "${TEMP_ARGS[0]}" != --* ]]; then
    # First argument is a path (not a flag)
    PATH_ARG="${TEMP_ARGS[0]}"
    unset 'TEMP_ARGS[0]'
    TEMP_ARGS=("${TEMP_ARGS[@]}")

    if [ "$DISPLAY_ONLY" = true ]; then
        # Use temporary JSON file for displaying results
        TEMP_JSON=$(mktemp --suffix=.json)

        # Run scan directly - let it print normally
        python3 cli.py --path "$PATH_ARG" --output "$TEMP_JSON" "${TEMP_ARGS[@]}"

        echo ""  # Blank line for spacing

        # Check if JSON file was created and has content
        if [ -s "$TEMP_JSON" ]; then
            # Display the results
            python3 display_results.py "$TEMP_JSON"
        else
            echo "Error: Scanning failed"
        fi

        # Clean up
        rm -f "$TEMP_JSON"
    else
        # Output file specified, use regular mode
        python3 cli.py --path "$PATH_ARG" --output "$OUTPUT_FILE" "${TEMP_ARGS[@]}"
    fi
else
    # No positional argument or it's a flag
    if [ "$DISPLAY_ONLY" = true ]; then
        python3 cli.py "${TEMP_ARGS[@]}"
    else
        python3 cli.py "${TEMP_ARGS[@]}" --output "$OUTPUT_FILE"
    fi
fi
