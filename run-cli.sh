#!/bin/bash
# URL Checker - Command Line Interface
# Usage: ./run-cli.sh [url-name] [options]
#
# Examples:
#   ./run-cli.sh                          - Interactive menu
#   ./run-cli.sh prod-publish            - Use prod-publish URL
#   ./run-cli.sh stage-author --verbose  - Use stage-author URL with verbose logging
#   ./run-cli.sh prod-publish --no-email - Use prod-publish without sending email

echo "================================================================================"
echo "  URL CHECKER - TURING ES"
echo "  Command Line Interface"
echo "================================================================================"
echo ""

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python 3 not found. Please install Python 3.8 or higher."
    exit 1
fi

echo "[1/3] Checking Python installation..."
python3 --version

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo ""
    echo "[2/3] Creating virtual environment..."
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo "[ERROR] Failed to create virtual environment"
        exit 1
    fi
    echo "Virtual environment created successfully"
else
    echo ""
    echo "[2/3] Virtual environment already exists"
fi

# Activate virtual environment and install dependencies
echo ""
echo "[3/3] Installing/updating dependencies..."
source venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

if [ $? -ne 0 ]; then
    echo "[ERROR] Failed to install dependencies"
    exit 1
fi

echo "Dependencies installed successfully"
echo ""
echo "================================================================================"
echo "  STARTING URL CHECKER (CLI MODE)"
echo "================================================================================"
echo ""

# Run the application with arguments (CLI mode)
if [ -n "$1" ] && [ ! "${1:0:2}" = "--" ]; then
    python3 run.py --cli --url-name "$@"
else
    python3 run.py --cli "$@"
fi

# Deactivate virtual environment
deactivate
