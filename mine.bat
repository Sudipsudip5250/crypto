@echo off
REM =============================================================================
REM  mine.bat — XMR Miner CLI  (Windows Command Prompt)
REM =============================================================================
REM  Usage:
REM    mine [command]
REM
REM  Commands:
REM    start     Start mining in the foreground  (default)
REM    bg        Start mining in the background
REM    stop      Stop a background miner
REM    restart   Stop + start in the background
REM    status    Show running state + last 5 log lines
REM    logs      Open the miner log in Notepad
REM    donate    Show donation info and wallet address
REM    setup     Run the interactive config wizard
REM    info      Print OS / CPU / GPU info
REM    version   Show cached + latest XMRig version
REM    update    Update XMRig to the latest GitHub release
REM    reset     Delete cached XMRig binary (re-downloaded on next start)
REM    config    Open config.json in Notepad
REM    install   Install / update Python dependencies
REM    help      Show this help message
REM =============================================================================

setlocal EnableDelayedExpansion

set SCRIPT_DIR=%~dp0
set SCRIPT_DIR=%SCRIPT_DIR:~0,-1%
set PID_FILE=%SCRIPT_DIR%\.miner.pid
set LOG_FILE=%SCRIPT_DIR%\logs\miner.log
set CONFIG_FILE=%SCRIPT_DIR%\config.json
set XMRIG_DIR=%SCRIPT_DIR%\tools\xmrig
set XMRIG_BIN=%XMRIG_DIR%\xmrig.exe
set VERSION_FILE=%SCRIPT_DIR%\tools\.xmrig_version
set PYTHON=python
set DONATE_WALLET=4B3WoA2P3fQNancXvdPVvnVcWZfeyC97dRj56pbq6RJdNGS39V4ME4WKHxn7e9KAFeJ87dNxgAdrP8dF5r8bFVxhPDS49gU

REM ── Command dispatch ─────────────────────────────────────────────────────

if "%~1"==""         goto :cmd_start
if "%~1"=="start"    goto :cmd_start
if "%~1"=="bg"       goto :cmd_bg
if "%~1"=="stop"     goto :cmd_stop
if "%~1"=="restart"  goto :cmd_restart
if "%~1"=="status"   goto :cmd_status
if "%~1"=="logs"     goto :cmd_logs
if "%~1"=="donate"   goto :cmd_donate
if "%~1"=="setup"    goto :cmd_setup
if "%~1"=="info"     goto :cmd_info
if "%~1"=="version"  goto :cmd_version
if "%~1"=="update"   goto :cmd_update
if "%~1"=="reset"    goto :cmd_reset
if "%~1"=="config"   goto :cmd_config
if "%~1"=="install"  goto :cmd_install
if "%~1"=="help"     goto :cmd_help
if "%~1"=="--help"   goto :cmd_help
if "%~1"=="-h"       goto :cmd_help

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
echo     start      Start mining in the foreground  (default)
echo     bg         Start mining in the background
echo     stop       Stop a background miner
echo     restart    Stop + start in the background
echo     status     Show running state + last 5 log lines
echo     logs       Open the miner log in Notepad
echo     donate     Show donation info and wallet address
echo     setup      Interactive config wizard
echo     info       Print OS / CPU / GPU detection
echo     version    Show cached + latest XMRig version
echo     update     Update XMRig to the latest release
echo     reset      Delete cached XMRig binary (re-downloaded on next start)
echo     config     Open config.json in Notepad
echo     install    Install / update Python dependencies
echo     help       Show this message
echo.
echo   Examples:
echo     mine setup      configure wallet, pool, temperature limits
echo     mine bg         mine in background
echo     mine donate     show wallet address / how to support the project
echo     mine update     upgrade XMRig binary
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

:cmd_version
cd /d "%SCRIPT_DIR%"
%PYTHON% miner.py --version
goto :end

:cmd_update
if exist "%PID_FILE%" (
    set /p CHECK_PID=<"%PID_FILE%"
    tasklist /FI "PID eq !CHECK_PID!" 2>nul | find /I "python.exe" >nul 2>&1
    if !errorlevel! == 0 (
        echo [mine] Miner is running. Stop it first:  mine stop
        goto :end
    )
)
cd /d "%SCRIPT_DIR%"
echo [mine] Checking for XMRig updates ...
%PYTHON% miner.py --update
goto :end

:cmd_reset
if exist "%PID_FILE%" (
    set /p CHECK_PID=<"%PID_FILE%"
    tasklist /FI "PID eq !CHECK_PID!" 2>nul | find /I "python.exe" >nul 2>&1
    if !errorlevel! == 0 (
        echo [mine] Miner is running. Stop it first:  mine stop
        goto :end
    )
)
if exist "%XMRIG_DIR%" (
    rmdir /S /Q "%XMRIG_DIR%"
    echo [mine] Cached XMRig binary removed. It will be re-downloaded on next start.
) else (
    echo [mine] No cached binary found - nothing to remove.
)
goto :end

:cmd_config
if not exist "%CONFIG_FILE%" (
    echo [mine] config.json not found. Run:  mine setup
    goto :end
)
echo [mine] Opening config.json in Notepad ...
start notepad "%CONFIG_FILE%"
goto :end

:cmd_donate
echo.
echo   ============================================================
echo     Support ^& Donate  --  XMR Miner
echo   ============================================================
echo.
echo   Option 1 -- Mine for the project (donate CPU time)
echo   The default config already points to the project wallet.
echo   Leave wallet_address unchanged in config.json and start mining.
echo.
echo     mine start               foreground session
echo     mine bg                  background daemon
echo     python miner.py --donate one-time donate session (no config change)
echo.
echo   Option 2 -- Send XMR directly
echo   Monero (XMR) wallet address:
echo.
echo     %DONATE_WALLET%
echo.
echo   Pool dashboard (verify donations in real time):
echo     https://supportxmr.com/#/dashboard?addr=%DONATE_WALLET%
echo.
echo   See DONATE.md for full details.
echo.
goto :end

:cmd_start
if not exist "%CONFIG_FILE%" (
    echo [mine] config.json not found. Run:  mine setup
    exit /b 1
)
echo [mine] Starting miner (foreground) ...  Press Ctrl+C to stop.
cd /d "%SCRIPT_DIR%"
%PYTHON% miner.py
goto :end

:cmd_bg
if not exist "%CONFIG_FILE%" (
    echo [mine] config.json not found. Run:  mine setup
    exit /b 1
)
if exist "%PID_FILE%" (
    set /p EXISTING_PID=<"%PID_FILE%"
    tasklist /FI "PID eq !EXISTING_PID!" 2>nul | find /I "python.exe" >nul 2>&1
    if !errorlevel! == 0 (
        echo [mine] Miner already running (PID !EXISTING_PID!). Run:  mine stop
        goto :end
    ) else (
        del "%PID_FILE%"
    )
)
if not exist "%SCRIPT_DIR%\logs" mkdir "%SCRIPT_DIR%\logs"
cd /d "%SCRIPT_DIR%"
echo [mine] Starting miner in background ...
start /B /MIN "" %PYTHON% miner.py >> "%LOG_FILE%" 2>&1
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
    echo        Status: mine status
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
echo [mine] Stopping miner (PID %STOP_PID%) ...
taskkill /PID %STOP_PID% /F >nul 2>&1
del "%PID_FILE%"
echo [mine] Miner stopped.
goto :end

:cmd_restart
if exist "%PID_FILE%" (
    set /p RST_PID=<"%PID_FILE%"
    taskkill /PID !RST_PID! /F >nul 2>&1
    del "%PID_FILE%"
    echo [mine] Miner stopped.
    timeout /t 2 /nobreak >nul
)
goto :cmd_bg

:cmd_status
REM Read version from file — avoids running the binary (blocked in some environments)
set CACHED_VER=
if exist "%VERSION_FILE%" (
    set /p CACHED_VER=<"%VERSION_FILE%"
)

if exist "%PID_FILE%" (
    set /p STATUS_PID=<"%PID_FILE%"
    tasklist /FI "PID eq !STATUS_PID!" 2>nul | find /I "python.exe" >nul 2>&1
    if !errorlevel! == 0 (
        echo [mine] Miner is RUNNING  (PID !STATUS_PID!)
        if not "!CACHED_VER!"=="" echo   XMRig version: v!CACHED_VER!
        if exist "%LOG_FILE%" (
            echo.
            echo   Recent log:
            powershell -Command "Get-Content '%LOG_FILE%' -Tail 5 | ForEach-Object { '    ' + $_ }"
        )
    ) else (
        del "%PID_FILE%"
        echo [mine] Miner is NOT running.
        if not "!CACHED_VER!"=="" echo   Cached XMRig:  v!CACHED_VER!  (run: mine update to upgrade)
    )
) else (
    echo [mine] Miner is NOT running.
    if not "!CACHED_VER!"=="" echo   Cached XMRig:  v!CACHED_VER!  (run: mine update to upgrade)
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
