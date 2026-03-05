#!/bin/bash
# vikunja.sh - Main controller script for Vikunja skill
# Wraps the Python CLI and handles virtual environment activation

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/../.venv"
PYTHON_CMD="$VENV_DIR/bin/python"

# Check if venv exists
if [ ! -d "$VENV_DIR" ]; then
    echo "ERROR: Virtual environment not found. Please run ./setup.sh first."
    exit 1
fi

# Check if Python exists in venv
if [ ! -f "$PYTHON_CMD" ]; then
    echo "ERROR: Python not found in virtual environment. Please run ./setup.sh again."
    exit 1
fi

# Run the Python CLI with all arguments
exec "$PYTHON_CMD" "$SCRIPT_DIR/../src/vikunja.py" "$@"
