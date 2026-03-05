#!/bin/bash
# setup.sh - One-time setup script for Vikunja skill
# Creates Python virtual environment and installs dependencies

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"

echo "Setting up Vikunja skill..."

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed"
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

# Activate virtual environment
echo "Activating virtual environment..."
source "$VENV_DIR/bin/activate"

# Upgrade pip
echo "Upgrading pip..."
pip install --quiet --upgrade pip

# Install dependencies
echo "Installing dependencies..."
pip install --quiet -r "$SCRIPT_DIR/requirements.txt"

echo "Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit config.yaml to set your Vikunja base URL"
echo "2. Ensure your credentials are configured in the admin skill"
echo "3. Run './vikunja.sh --help' to get started"
