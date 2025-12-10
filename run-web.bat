@echo off
echo ========================================
echo URL Checker - Streamlit Web Interface
echo ========================================
echo.

REM Check if virtual environment exists
if not exist "venv\" (
    echo Virtual environment not found. Creating...
    python -m venv venv
    if errorlevel 1 (
        echo Error creating virtual environment!
        pause
        exit /b 1
    )
    echo Virtual environment created successfully!
    echo.
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Install/Update dependencies
echo.
echo Installing dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo Error installing dependencies!
    pause
    exit /b 1
)

REM Run Streamlit app
echo.
echo ========================================
echo Starting Streamlit application...
echo Open your browser at: http://localhost:8501
echo ========================================
echo.
streamlit run app.py

pause
