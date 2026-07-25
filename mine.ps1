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
#    restart   Stop + start in the background
#    status    Show running state + last 5 log lines
#    logs      Tail the miner log in real time
#    donate    Show donation info and wallet address
#    donate-mode  Mine to project wallet for N min (no config change)
#    setup     Run the interactive config wizard
#    info      Print OS / CPU / GPU info
#    version   Show cached + latest XMRig version
#    update    Update XMRig to the latest GitHub release
#    reset     Delete the cached XMRig binary (re-downloaded on next start)
#    config    Open config.json in Notepad
#    install   Install / update Python dependencies
#    help      Show this help message
# =============================================================================

param(
    [Parameter(Position=0)]
    [string]$Command = "start"
)

# ── Paths ─────────────────────────────────────────────────────────────────────
$ScriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Definition
$PidFile     = Join-Path $ScriptDir ".miner.pid"
$LogFile     = Join-Path $ScriptDir "logs\miner.log"
$ConfigFile  = Join-Path $ScriptDir "config.json"
$XmrigDir    = Join-Path $ScriptDir "tools\xmrig"
$XmrigBin    = Join-Path $XmrigDir "xmrig.exe"
$VersionFile = Join-Path $ScriptDir "tools\.xmrig_version"
$Python      = "python"
$DonateWallet = "4B3WoA2P3fQNancXvdPVvnVcWZfeyC97dRj56pbq6RJdNGS39V4ME4WKHxn7e9KAFeJ87dNxgAdrP8dF5r8bFVxhPDS49gU"

# ── Colour helpers ────────────────────────────────────────────────────────────
function Write-Info    { param($msg) Write-Host "[mine] $msg" -ForegroundColor Cyan }
function Write-Ok      { param($msg) Write-Host "[mine] $msg" -ForegroundColor Green }
function Write-Warn    { param($msg) Write-Host "[mine] $msg" -ForegroundColor Yellow }
function Write-Err     { param($msg) Write-Host "[mine] $msg" -ForegroundColor Red }

# ── Helpers ───────────────────────────────────────────────────────────────────
function Get-MinerPid {
    if (Test-Path $PidFile) {
        return [int](Get-Content $PidFile -Raw).Trim()
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
    if (-not (Test-Path $ConfigFile)) {
        Write-Warn "config.json not found."
        Write-Host "  Run: .\mine.ps1 setup"
        exit 1
    }
}

function Get-CachedVersion {
    if (Test-Path $VersionFile) {
        return (Get-Content $VersionFile -Raw).Trim()
    }
    return $null
}

# ── Commands ──────────────────────────────────────────────────────────────────

function Invoke-Help {
    Write-Host ""
    Write-Host "  XMR Miner CLI  --  for education and research purposes" -ForegroundColor White
    Write-Host ""
    Write-Host "  Usage:  .\mine.ps1 [command]" -ForegroundColor White
    Write-Host ""
    Write-Host "  Commands:" -ForegroundColor White
    @(
        @("start",   "Start mining in the foreground  (default)"),
        @("bg",      "Start mining in the background"),
        @("stop",    "Stop a background miner"),
        @("restart", "Stop + start in the background"),
        @("status",  "Show running state + last 5 log lines"),
        @("logs",    "Tail the miner log in real time"),
        @("donate",      "Show donation info and wallet address"),
        @("donate-mode", "Mine to project wallet for N min (default 10, no config change)"),
        @("setup",       "Interactive config wizard"),
        @("info",    "Print OS / CPU / GPU detection"),
        @("version", "Show cached + latest XMRig version"),
        @("update",  "Update XMRig to the latest release"),
        @("reset",   "Delete cached XMRig binary (re-downloaded on next start)"),
        @("config",  "Open config.json in Notepad"),
        @("install", "Install / update Python dependencies"),
        @("help",    "Show this message")
    ) | ForEach-Object {
        Write-Host ("    {0,-10} {1}" -f $_[0], $_[1]) -ForegroundColor Cyan
    }
    Write-Host ""
    Write-Host "  Examples:" -ForegroundColor White
    Write-Host "    .\mine.ps1 setup     configure wallet, pool, temperature limits"
    Write-Host "    .\mine.ps1 bg        mine in background"
    Write-Host "    .\mine.ps1 donate    show wallet address / how to support the project"
    Write-Host "    .\mine.ps1 update    upgrade XMRig binary"
    Write-Host "    .\mine.ps1 stop      stop background miner"
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

function Invoke-Version {
    Set-Location $ScriptDir
    & $Python miner.py --version
}

function Invoke-Update {
    if (Test-MinerRunning) {
        Write-Warn "Miner is running. Stop it first:  .\mine.ps1 stop"
        exit 1
    }
    Set-Location $ScriptDir
    Write-Info "Checking for XMRig updates ..."
    & $Python miner.py --update
}

function Invoke-Reset {
    if (Test-MinerRunning) {
        Write-Warn "Miner is running. Stop it first:  .\mine.ps1 stop"
        exit 1
    }
    if (Test-Path $XmrigDir) {
        Remove-Item $XmrigDir -Recurse -Force
        Write-Ok "Cached XMRig binary removed. It will be re-downloaded on next start."
    } else {
        Write-Info "No cached binary found — nothing to remove."
    }
}

function Invoke-Config {
    if (-not (Test-Path $ConfigFile)) {
        Write-Warn "config.json not found. Run: .\mine.ps1 setup"
        exit 1
    }
    Write-Info "Opening config.json in Notepad ..."
    Start-Process notepad $ConfigFile
}

function Invoke-DonateMode {
    param([int]$Minutes = 10)
    Confirm-Config
    Set-Location $ScriptDir
    Write-Info "Starting donate session — mining to project wallet for $Minutes minute(s) ..."
    Write-Info "Your config.json is NOT modified.  Press Ctrl+C to stop early."
    Write-Host ""
    & $Python miner.py --donate-mode --donate-time $Minutes
}

function Invoke-Donate {
    Write-Host ""
    Write-Host "  ============================================================" -ForegroundColor White
    Write-Host "    Support & Donate  --  XMR Miner" -ForegroundColor White
    Write-Host "  ============================================================" -ForegroundColor White
    Write-Host ""
    Write-Host "  Option 1 -- Mine for the project (donate CPU time)" -ForegroundColor White
    Write-Host "  The default config already points to the project wallet."
    Write-Host "  Leave wallet_address unchanged in config.json and start mining."
    Write-Host ""
    Write-Host "    .\mine.ps1 start              foreground session" -ForegroundColor Cyan
    Write-Host "    .\mine.ps1 bg                 background daemon" -ForegroundColor Cyan
    Write-Host "    .\mine.ps1 donate-mode        donate 10 min  (no config change)" -ForegroundColor Cyan
    Write-Host "    .\mine.ps1 donate-mode 30     donate 30 min  (no config change)" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Option 2 -- Send XMR directly" -ForegroundColor White
    Write-Host "  Monero (XMR) wallet address:" -ForegroundColor White
    Write-Host ""
    Write-Host "    $DonateWallet" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Pool dashboard (verify donations in real time):" -ForegroundColor White
    Write-Host "    https://supportxmr.com/#/dashboard?addr=$DonateWallet" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  See DONATE.md for full details." -ForegroundColor White
    Write-Host ""
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
        Write-Host "  Status: .\mine.ps1 status"
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
    # Read version from file — avoids running the binary (blocked in some environments)
    $cachedVer = Get-CachedVersion

    if (Test-MinerRunning) {
        $mpid = Get-MinerPid
        Write-Ok "Miner is RUNNING  (PID $mpid)"
        if ($cachedVer) { Write-Host "  XMRig version : v$cachedVer" }

        if (Test-Path $LogFile) {
            Write-Host ""
            Write-Host "  Recent log:" -ForegroundColor White
            Get-Content $LogFile -Tail 5 | ForEach-Object { Write-Host "    $_" }
        }
    } else {
        Write-Warn "Miner is NOT running."
        if ($cachedVer) {
            Write-Host "  Cached XMRig : v$cachedVer  (.\mine.ps1 update to upgrade)"
        }
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
    "donate"      { Invoke-Donate }
    "donate-mode" {
        $mins = if ($args.Count -ge 1 -and $args[0] -match '^\d+$') { [int]$args[0] } else { 10 }
        Invoke-DonateMode -Minutes $mins
    }
    "setup"   { Invoke-Setup }
    "info"    { Invoke-Info }
    "version" { Invoke-Version }
    "update"  { Invoke-Update }
    "reset"   { Invoke-Reset }
    "config"  { Invoke-Config }
    "install" { Invoke-Install }
    "help"    { Invoke-Help }
    default {
        Write-Err "Unknown command: '$Command'"
        Write-Host "  Run  .\mine.ps1 help  to see all commands."
        exit 1
    }
}
