@echo off
echo ===================================================
echo   General Manager Orchestrator - Startup Script
echo ===================================================
echo.

:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in your PATH.
    echo Please install Python 3.10 or higher.
    pause
    exit /b 1
)

:: Install required dependencies (will skip if already installed)
echo [INFO] Checking dependencies...
pip install -r requirements.txt >nul

:: Start the Python WebSocket server
echo [INFO] Starting Orchestrator on ws://127.0.0.1:8799...
echo [INFO] Leave this window open to keep the server running.
echo.
python orchestrator.py

pause
