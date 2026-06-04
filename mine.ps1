# =============================================================================
#  mine.ps1 — XMR Miner CLI  (Windows PowerShell)
# =============================================================================
#  Usage:
#    .\mine.ps1 [command]
#
#  Commands:
#    start     Start mining in the foreground  (default)
#    bg        Start mining in the background
#    stop      Stop a background miner
#    status    Show whether the miner is running
#    logs      Tail the miner log in real time
#    setup     Run the interactive config wizard
#    info      Print OS / CPU / GPU info
#    install   Install / update Python dependencies
#    help      Show this help message
# =============================================================================

param(
    [Parameter(Position=0)]
    [string]$Command = "start"
)

# ── Paths ─────────────────────────────────────────────────────────────────────
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$PidFile   = Join-Path $ScriptDir ".miner.pid"
$LogFile   = Join-Path $ScriptDir "logs\miner.log"
$Python    = "python"

# ── Colour helpers ────────────────────────────────────────────────────────────
function Write-Info    { param($msg) Write-Host "[mine] $msg" -ForegroundColor Cyan }
function Write-Ok      { param($msg) Write-Host "[mine] $msg" -ForegroundColor Green }
function Write-Warn    { param($msg) Write-Host "[mine] $msg" -ForegroundColor Yellow }
function Write-Err     { param($msg) Write-Host "[mine] $msg" -ForegroundColor Red }

# ── Helpers ───────────────────────────────────────────────────────────────────
function Get-MinerPid {
    if (Test-Path $PidFile) {
        $pid = (Get-Content $PidFile).Trim()
        return [int]$pid
    }
    return $null
}

function Test-MinerRunning {
    $mpid = Get-MinerPid
    if ($null -eq $mpid) { return $false }
    $proc = Get-Process -Id $mpid -ErrorAction SilentlyContinue
    if ($null -ne $proc) { return $true }
    Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
    return $false
}

function Confirm-Config {
    if (-not (Test-Path (Join-Path $ScriptDir "config.json"))) {
        Write-Warn "config.json not found."
        Write-Host "  Run: .\mine.ps1 setup"
        exit 1
    }
}

# ── Commands ──────────────────────────────────────────────────────────────────

function Invoke-Help {
    Write-Host ""
    Write-Host "  XMR Miner CLI  --  for education and research purposes" -ForegroundColor White
    Write-Host ""
    Write-Host "  Usage:  .\mine.ps1 [command]" -ForegroundColor White
    Write-Host ""
    Write-Host "  Commands:" -ForegroundColor White
    Write-Host "    start     Start mining in the foreground  (default)" -ForegroundColor Cyan
    Write-Host "    bg        Start mining in the background"            -ForegroundColor Cyan
    Write-Host "    stop      Stop a background miner"                   -ForegroundColor Cyan
    Write-Host "    status    Show whether the miner is running"         -ForegroundColor Cyan
    Write-Host "    logs      Tail the miner log in real time"           -ForegroundColor Cyan
    Write-Host "    setup     Interactive config wizard"                  -ForegroundColor Cyan
    Write-Host "    info      Print OS / CPU / GPU detection"            -ForegroundColor Cyan
    Write-Host "    install   Install / update Python dependencies"      -ForegroundColor Cyan
    Write-Host "    help      Show this message"                         -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Examples:" -ForegroundColor White
    Write-Host "    .\mine.ps1 setup      # configure wallet, pool, temperature limits"
    Write-Host "    .\mine.ps1 bg         # mine in background"
    Write-Host "    .\mine.ps1 logs       # watch live output"
    Write-Host "    .\mine.ps1 stop       # stop background miner"
    Write-Host ""
}

function Invoke-Install {
    Write-Info "Installing Python dependencies ..."
    & $Python -m pip install --upgrade pip --quiet
    & $Python -m pip install -r (Join-Path $ScriptDir "requirements.txt") --quiet
    Write-Ok "Dependencies installed."
}

function Invoke-Setup {
    Set-Location $ScriptDir
    & $Python miner.py --setup
}

function Invoke-Info {
    Set-Location $ScriptDir
    & $Python miner.py --info
}

function Invoke-Start {
    Confirm-Config
    Set-Location $ScriptDir
    Write-Info "Starting miner (foreground) ...  Press Ctrl+C to stop."
    & $Python miner.py
}

function Invoke-Bg {
    Confirm-Config

    if (Test-MinerRunning) {
        $mpid = Get-MinerPid
        Write-Warn "Miner is already running (PID $mpid).  Run: .\mine.ps1 stop"
        return
    }

    $logsDir = Join-Path $ScriptDir "logs"
    if (-not (Test-Path $logsDir)) { New-Item -ItemType Directory -Path $logsDir | Out-Null }

    Set-Location $ScriptDir
    Write-Info "Starting miner in background ..."

    $proc = Start-Process `
        -FilePath $Python `
        -ArgumentList "miner.py" `
        -WorkingDirectory $ScriptDir `
        -RedirectStandardOutput $LogFile `
        -RedirectStandardError  $LogFile `
        -WindowStyle Hidden `
        -PassThru

    $proc.Id | Set-Content $PidFile
    Start-Sleep -Seconds 1

    if (-not $proc.HasExited) {
        Write-Ok "Miner started  (PID $($proc.Id))"
        Write-Host "  Logs:   .\mine.ps1 logs"
        Write-Host "  Stop:   .\mine.ps1 stop"
    } else {
        Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
        Write-Err "Miner failed to start. Check: $LogFile"
        exit 1
    }
}

function Invoke-Stop {
    if (-not (Test-MinerRunning)) {
        Write-Warn "Miner is not running."
        return
    }

    $mpid = Get-MinerPid
    Write-Info "Stopping miner (PID $mpid) ..."

    Stop-Process -Id $mpid -Force -ErrorAction SilentlyContinue
    Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
    Write-Ok "Miner stopped."
}

function Invoke-Restart {
    Invoke-Stop
    Start-Sleep -Seconds 1
    Invoke-Bg
}

function Invoke-Status {
    if (Test-MinerRunning) {
        $mpid = Get-MinerPid
        Write-Ok "Miner is RUNNING  (PID $mpid)"
        if (Test-Path $LogFile) {
            Write-Host ""
            Write-Host "  Recent log:" -ForegroundColor White
            Get-Content $LogFile -Tail 5 | ForEach-Object { Write-Host "    $_" }
        }
    } else {
        Write-Warn "Miner is NOT running."
    }
}

function Invoke-Logs {
    if (-not (Test-Path $LogFile)) {
        Write-Warn "No log file yet: $LogFile"
        Write-Host "  Start the miner first:  .\mine.ps1 bg"
        return
    }
    Write-Info "Tailing $LogFile  (Ctrl+C to stop) ..."
    Write-Host ""
    Get-Content $LogFile -Wait -Tail 20
}

# ── Dispatch ──────────────────────────────────────────────────────────────────
switch ($Command.ToLower()) {
    "start"   { Invoke-Start }
    "bg"      { Invoke-Bg }
    "stop"    { Invoke-Stop }
    "restart" { Invoke-Restart }
    "status"  { Invoke-Status }
    "logs"    { Invoke-Logs }
    "setup"   { Invoke-Setup }
    "info"    { Invoke-Info }
    "install" { Invoke-Install }
    "help"    { Invoke-Help }
    default {
        Write-Err "Unknown command: '$Command'"
        Write-Host "  Run  .\mine.ps1 help  to see all commands."
        exit 1
    }
}
