@echo off
REM =============================================================================
REM  mine.bat — XMR Miner launcher for Windows (Command Prompt)
REM =============================================================================
REM  All logic lives in miner.py.  This script finds Python and hands off.
REM
REM  Usage:  mine [command] [options]
REM  Run:    mine help   for the full command list.
REM
REM  FOR EDUCATIONAL AND RESEARCH PURPOSES ONLY.
REM  Do NOT run on cloud platforms -- see DISCLAIMER.md.
REM =============================================================================

cd /d "%~dp0"

where python >nul 2>&1
if errorlevel 1 (
    echo [mine] Python not found.
    echo        Install Python 3.10 or later from https://python.org
    exit /b 1
)

python miner.py %*
