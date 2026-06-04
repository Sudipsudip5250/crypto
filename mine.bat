@echo off
REM =============================================================================
REM  mine.bat — XMR Miner CLI  (Windows)
REM =============================================================================
REM  Usage:
REM    mine [command]
REM
REM  Commands:
REM    start     Start mining in the foreground  (default)
REM    bg        Start mining in the background
REM    stop      Stop a background miner
REM    status    Show whether the miner is running
REM    logs      Open the miner log in Notepad
REM    setup     Run the interactive config wizard
REM    info      Print OS / CPU / GPU info
REM    install   Install / update Python dependencies
REM    help      Show this help message
REM =============================================================================

setlocal EnableDelayedExpansion

set SCRIPT_DIR=%~dp0
set SCRIPT_DIR=%SCRIPT_DIR:~0,-1%
set PID_FILE=%SCRIPT_DIR%\.miner.pid
set LOG_FILE=%SCRIPT_DIR%\logs\miner.log
set PYTHON=python

REM ── Command dispatch ─────────────────────────────────────────────────────

if "%~1"==""        goto :cmd_start
if "%~1"=="start"   goto :cmd_start
if "%~1"=="bg"      goto :cmd_bg
if "%~1"=="stop"    goto :cmd_stop
if "%~1"=="status"  goto :cmd_status
if "%~1"=="logs"    goto :cmd_logs
if "%~1"=="setup"   goto :cmd_setup
if "%~1"=="info"    goto :cmd_info
if "%~1"=="install" goto :cmd_install
if "%~1"=="help"    goto :cmd_help
if "%~1"=="--help"  goto :cmd_help
if "%~1"=="-h"      goto :cmd_help

echo [mine] Unknown command: %~1
echo        Run  mine help  to see all commands.
exit /b 1

REM ── Commands ─────────────────────────────────────────────────────────────

:cmd_help
echo.
echo   XMR Miner CLI  --  for education and research purposes
echo.
echo   Usage:  mine [command]
echo.
echo   Commands:
echo     start     Start mining in the foreground  (default)
echo     bg        Start mining in the background  (hidden window)
echo     stop      Stop a background miner
echo     status    Show whether the miner is running
echo     logs      Open the miner log in Notepad
echo     setup     Interactive config wizard
echo     info      Print OS / CPU / GPU detection
echo     install   Install / update Python dependencies
echo     help      Show this message
echo.
echo   Examples:
echo     mine setup      configure wallet, pool, temperature limits
echo     mine bg         mine in background
echo     mine status     check if running
echo     mine stop       stop background miner
echo.
goto :end

:cmd_install
echo [mine] Installing Python dependencies ...
%PYTHON% -m pip install --upgrade pip --quiet
%PYTHON% -m pip install -r "%SCRIPT_DIR%\requirements.txt" --quiet
echo [mine] Dependencies installed.
goto :end

:cmd_setup
cd /d "%SCRIPT_DIR%"
%PYTHON% miner.py --setup
goto :end

:cmd_info
cd /d "%SCRIPT_DIR%"
%PYTHON% miner.py --info
goto :end

:cmd_start
if not exist "%SCRIPT_DIR%\config.json" (
    echo [mine] config.json not found. Run:  mine setup
    exit /b 1
)
echo [mine] Starting miner (foreground) ...  Press Ctrl+C to stop.
cd /d "%SCRIPT_DIR%"
%PYTHON% miner.py
goto :end

:cmd_bg
if not exist "%SCRIPT_DIR%\config.json" (
    echo [mine] config.json not found. Run:  mine setup
    exit /b 1
)

REM Check if already running
if exist "%PID_FILE%" (
    set /p EXISTING_PID=<"%PID_FILE%"
    tasklist /FI "PID eq !EXISTING_PID!" 2>nul | find /I "python.exe" >nul 2>&1
    if !errorlevel! == 0 (
        echo [mine] Miner is already running  (PID !EXISTING_PID!). Run:  mine stop
        goto :end
    ) else (
        del "%PID_FILE%"
    )
)

if not exist "%SCRIPT_DIR%\logs" mkdir "%SCRIPT_DIR%\logs"

echo [mine] Starting miner in background ...
cd /d "%SCRIPT_DIR%"
start /B /MIN "" %PYTHON% miner.py >> "%LOG_FILE%" 2>&1

REM Give it a moment then grab the python PID
timeout /t 2 /nobreak >nul
for /f "tokens=2 delims=," %%P in ('tasklist /FI "IMAGENAME eq python.exe" /FO CSV /NH 2^>nul') do (
    set NEW_PID=%%~P
    goto :bg_found
)

:bg_found
if defined NEW_PID (
    echo !NEW_PID!> "%PID_FILE%"
    echo [mine] Miner started  (PID !NEW_PID!)
    echo        Logs:   mine logs
    echo        Stop:   mine stop
) else (
    echo [mine] Could not confirm miner started. Check: %LOG_FILE%
)
goto :end

:cmd_stop
if not exist "%PID_FILE%" (
    echo [mine] Miner is not running.
    goto :end
)
set /p STOP_PID=<"%PID_FILE%"
echo [mine] Stopping miner  (PID %STOP_PID%) ...
taskkill /PID %STOP_PID% /F >nul 2>&1
del "%PID_FILE%"
echo [mine] Miner stopped.
goto :end

:cmd_status
if exist "%PID_FILE%" (
    set /p STATUS_PID=<"%PID_FILE%"
    tasklist /FI "PID eq !STATUS_PID!" 2>nul | find /I "python.exe" >nul 2>&1
    if !errorlevel! == 0 (
        echo [mine] Miner is RUNNING  (PID !STATUS_PID!)
        if exist "%LOG_FILE%" (
            echo.
            echo Recent log:
            powershell -Command "Get-Content '%LOG_FILE%' -Tail 5 | ForEach-Object { '  ' + $_ }"
        )
    ) else (
        del "%PID_FILE%"
        echo [mine] Miner is NOT running.
    )
) else (
    echo [mine] Miner is NOT running.
)
goto :end

:cmd_logs
if not exist "%LOG_FILE%" (
    echo [mine] No log file yet: %LOG_FILE%
    echo        Start the miner first:  mine bg
    goto :end
)
echo [mine] Opening log in Notepad ...
start notepad "%LOG_FILE%"
goto :end

:end
endlocal
