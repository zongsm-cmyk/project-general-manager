@echo off
setlocal enabledelayedexpansion

title Project General Manager - Orchestrator
cd /d "%~dp0"

echo ===================================================
echo   Project General Manager - Orchestrator Server
echo ===================================================
echo.

:: 1. Check if port 8799 is already in use
netstat -ano | findstr /R /C:":8799 " | findstr /C:"LISTENING" >nul 2>&1
if %errorlevel% equ 0 (
    echo [WARNING] Orchestrator is ALREADY RUNNING on port 8799.
    echo To stop the running instance, run stop_gm.bat.
    echo.
    pause
    exit /b 0
)

:: 2. Check for virtual environment (.venv)
if not exist ".venv\Scripts\python.exe" (
    echo [INFO] Virtual environment not found. Setting up .venv...
    where python >nul 2>&1
    if %errorlevel% neq 0 (
        echo [ERROR] Python was not found on your system PATH.
        echo Please install Python 3.10+ and re-run this script.
        pause
        exit /b 1
    )
    python -m venv .venv
    if not exist ".venv\Scripts\python.exe" (
        echo [ERROR] Failed to create virtual environment in .venv.
        pause
        exit /b 1
    )
    echo [INFO] Installing dependencies into .venv...
    ".venv\Scripts\pip.exe" install -r requirements.txt
)

:: 3. Verify websockets package is ready
".venv\Scripts\python.exe" -c "import websockets, sqlite3" >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Re-installing missing dependencies in .venv...
    ".venv\Scripts\pip.exe" install -r requirements.txt
)

:: 4. Start Orchestrator
echo [INFO] Starting Orchestrator on ws://127.0.0.1:8799 ...
echo [INFO] Logs will be mirrored to orchestrator.log
echo [INFO] Press Ctrl+C or run stop_gm.bat to stop.
echo.

".venv\Scripts\python.exe" orchestrator.py 2>&1 | powershell -NoProfile -Command "$input | Tee-Object -FilePath 'orchestrator.log' -Append"

pause
