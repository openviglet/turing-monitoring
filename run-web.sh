#!/bin/bash

echo "========================================"
echo "URL Checker - Streamlit Web Interface"
echo "========================================"
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Virtual environment not found. Creating..."
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo "Error creating virtual environment!"
        exit 1
    fi
    echo "Virtual environment created successfully!"
    echo ""
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install/Update dependencies
echo ""
echo "Installing dependencies..."
pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "Error installing dependencies!"
    exit 1
fi

# Run Streamlit app
echo ""
echo "========================================"
echo "Starting Streamlit application..."
echo "Open your browser at: http://localhost:8501"
echo "========================================"
echo ""
streamlit run app.py
