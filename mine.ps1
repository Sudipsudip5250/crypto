# =============================================================================
#  mine.ps1 — XMR Miner launcher for Windows (PowerShell)
# =============================================================================
#  All logic lives in miner.py.  This script finds Python and hands off.
#
#  Usage:  .\mine.ps1 [command] [options]
#  Run:    .\mine.ps1 help   for the full command list.
#
#  FOR EDUCATIONAL AND RESEARCH PURPOSES ONLY.
#  Do NOT run on cloud platforms -- see DISCLAIMER.md.
# =============================================================================

param(
    [Parameter(Position = 0, ValueFromRemainingArguments = $true)]
    [string[]]$PassThrough
)

Set-Location (Split-Path -Parent $MyInvocation.MyCommand.Definition)

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "[mine] Python not found." -ForegroundColor Red
    Write-Host "       Install Python 3.10 or later from https://python.org"
    exit 1
}

& python miner.py @PassThrough
