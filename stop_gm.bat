@echo off
setlocal enabledelayedexpansion

title Project General Manager - Stop Server
cd /d "%~dp0"

echo ===================================================
echo   Project General Manager - Stop Orchestrator
echo ===================================================
echo.

set PORT=8799
set TARGET_PID=

for /f "tokens=5" %%a in ('netstat -aon ^| findstr /R /C:":%PORT% " ^| findstr /C:"LISTENING"') do (
    set TARGET_PID=%%a
)

if "%TARGET_PID%"=="" (
    echo [INFO] No Orchestrator process found listening on port %PORT%.
    echo The server is already stopped.
    goto :done
)

echo [INFO] Found process with PID: %TARGET_PID% listening on port %PORT%.
taskkill /F /PID %TARGET_PID% >nul 2>&1
if %errorlevel% equ 0 (
    echo [SUCCESS] Orchestrator (PID %TARGET_PID%) stopped successfully.
) else (
    echo [WARNING] Could not terminate PID %TARGET_PID%. It may have already exited.
)

:done
echo.
pause
