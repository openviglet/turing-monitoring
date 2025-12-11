@echo off
REM URL Checker - Command Line Interface
REM Usage: run-cli.bat [url-name] [options]
REM
REM Examples:
REM   run-cli.bat                          - Interactive menu
REM   run-cli.bat prod-publish            - Use prod-publish URL
REM   run-cli.bat stage-author --verbose  - Use stage-author URL with verbose logging
REM   run-cli.bat prod-publish --no-email - Use prod-publish without sending email

echo ================================================================================
echo   URL CHECKER - TURING ES
echo   Command Line Interface
echo ================================================================================
echo.

REM Check Python version
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.8 or higher.
    echo Download from: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/3] Checking Python installation...
python --version

REM Create virtual environment if it doesn't exist
if not exist "venv\Scripts\activate.bat" (
    echo.
    echo [2/3] Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment
        pause
        exit /b 1
    )
    echo Virtual environment created successfully
) else (
    echo.
    echo [2/3] Virtual environment already exists
)

REM Activate virtual environment and install dependencies
echo.
echo [3/3] Installing/updating dependencies...
call venv\Scripts\activate.bat
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

if errorlevel 1 (
    echo [ERROR] Failed to install dependencies
    pause
    exit /b 1
)

echo Dependencies installed successfully
echo.
echo ================================================================================
echo   STARTING URL CHECKER (CLI MODE)
echo ================================================================================
echo.

REM Run the application with arguments (CLI mode)
python run.py --cli %*

REM Deactivate virtual environment
deactivate
