@echo off
REM Windows execution script for URL Checker
REM Automatically creates virtual environment, installs dependencies, and runs the application

echo ========================================
echo URL Checker - Turing ES
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found!
    echo Please install Python 3.8 or higher
    echo Download from: https://www.python.org/downloads/
    pause
    exit /b 1
)

REM Check Python version
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo Python version: %PYTHON_VERSION%
echo.

REM Create virtual environment if it doesn't exist
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment
        pause
        exit /b 1
    )
    echo Virtual environment created successfully!
    echo.
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Failed to activate virtual environment
    pause
    exit /b 1
)

REM Install dependencies
echo.
echo Installing dependencies...
pip install -q -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)

REM Run application
echo.
echo ========================================
echo Running URL Checker...
echo ========================================
echo.
python main.py %*

REM Check exit code
if errorlevel 1 (
    echo.
    echo ========================================
    echo Execution completed with errors
    echo ========================================
    pause
    exit /b 1
) else (
    echo.
    echo ========================================
    echo Execution completed successfully
    echo ========================================
    pause
    exit /b 0
)
