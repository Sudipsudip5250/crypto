#!/usr/bin/env bash
# =============================================================================
#  mine.sh — XMR Miner CLI  (Linux / macOS)
# =============================================================================
#  Usage:
#    ./mine.sh [command]
#
#  Commands:
#    start       Start mining in the foreground  (default)
#    bg          Start mining in the background (daemon mode)
#    stop        Stop a background miner
#    restart     Stop + start in the background
#    status      Show whether the miner is running + last 5 log lines
#    logs        Tail the miner log in real time (Ctrl+C to exit)
#    donate      Show donation info and wallet address
#    setup       Run the interactive config wizard
#    info        Print OS / CPU / GPU info
#    version     Show cached + latest XMRig version
#    update      Update XMRig to the latest GitHub release
#    reset       Delete the cached XMRig binary (re-downloaded on next start)
#    config      Open config.json in your editor ($EDITOR, nano, or vi)
#    install     Install / update Python dependencies
#    help        Show this help message
# =============================================================================

set -euo pipefail

# ── Colours ────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GRN='\033[0;32m'; YLW='\033[0;33m'
BLU='\033[0;34m'; CYN='\033[0;36m'; BLD='\033[1m';  RST='\033[0m'
[ -t 1 ] || { RED=''; GRN=''; YLW=''; BLU=''; CYN=''; BLD=''; RST=''; }

# ── Paths ───────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$SCRIPT_DIR/.miner.pid"
LOG_FILE="$SCRIPT_DIR/logs/miner.log"
CONFIG_FILE="$SCRIPT_DIR/config.json"
XMRIG_DIR="$SCRIPT_DIR/tools/xmrig"

# ── Helpers ─────────────────────────────────────────────────────────────────
info()    { echo -e "${BLU}[mine]${RST} $*"; }
success() { echo -e "${GRN}[mine]${RST} $*"; }
warn()    { echo -e "${YLW}[mine]${RST} $*"; }
error()   { echo -e "${RED}[mine]${RST} $*" >&2; }
bold()    { echo -e "${BLD}$*${RST}"; }

find_python() {
    for py in python3 python python3.13 python3.12 python3.11 python3.10; do
        if command -v "$py" &>/dev/null; then
            ver=$("$py" -c "import sys; print(sys.version_info.major)" 2>/dev/null || echo 0)
            [ "$ver" = "3" ] && { echo "$py"; return 0; }
        fi
    done
    error "Python 3 not found. Please install Python 3.10 or later."
    exit 1
}
PYTHON=$(find_python)

check_config() {
    if [ ! -f "$CONFIG_FILE" ]; then
        warn "config.json not found."
        echo -e "  Run ${CYN}./mine.sh setup${RST} to create it."
        exit 1
    fi
}

is_running() {
    if [ -f "$PID_FILE" ]; then
        pid=$(cat "$PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then return 0; fi
        rm -f "$PID_FILE"
    fi
    return 1
}

# ── Commands ─────────────────────────────────────────────────────────────────

cmd_help() {
    echo -e "
${BLD}XMR Miner CLI${RST}  —  for education and research purposes

${BLD}Usage:${RST}  ./mine.sh [command]

${BLD}Commands:${RST}
  ${CYN}start${RST}      Start mining in the foreground   (Ctrl+C to stop)
  ${CYN}bg${RST}         Start mining in the background   (daemon mode)
  ${CYN}stop${RST}       Stop a background miner
  ${CYN}restart${RST}    Stop + start in the background
  ${CYN}status${RST}     Show running state + last 5 log lines
  ${CYN}logs${RST}       Tail the miner log in real time  (Ctrl+C to exit)
  ${CYN}setup${RST}      Interactive config wizard
  ${CYN}info${RST}       Print OS / CPU / GPU detection
  ${CYN}version${RST}    Show cached + latest XMRig version
  ${CYN}update${RST}     Update XMRig to the latest release
  ${CYN}donate${RST}     Show donation info and wallet address
  ${CYN}reset${RST}      Delete cached XMRig binary  (re-downloaded on next start)
  ${CYN}config${RST}     Open config.json in \$EDITOR / nano / vi
  ${CYN}install${RST}    Install / update Python dependencies
  ${CYN}help${RST}       Show this message

${BLD}Examples:${RST}
  ./mine.sh setup       # configure wallet, pool, temperature limits
  ./mine.sh bg          # mine in background
  ./mine.sh logs        # watch live output
  ./mine.sh donate      # show wallet address / how to support the project
  ./mine.sh update      # upgrade XMRig binary
  ./mine.sh stop        # stop background miner
"
}

cmd_install() {
    info "Installing Python dependencies …"
    "$PYTHON" -m pip install --upgrade pip --quiet
    "$PYTHON" -m pip install -r "$SCRIPT_DIR/requirements.txt" --quiet
    success "Dependencies installed."
}

cmd_setup() {
    cd "$SCRIPT_DIR"
    "$PYTHON" miner.py --setup
}

cmd_info() {
    cd "$SCRIPT_DIR"
    "$PYTHON" miner.py --info
}

cmd_version() {
    cd "$SCRIPT_DIR"
    "$PYTHON" miner.py --version
}

cmd_update() {
    if is_running; then
        warn "Miner is running. Stop it first:  ./mine.sh stop"
        exit 1
    fi
    cd "$SCRIPT_DIR"
    info "Checking for XMRig updates …"
    "$PYTHON" miner.py --update
}

cmd_reset() {
    if is_running; then
        warn "Miner is running. Stop it first:  ./mine.sh stop"
        exit 1
    fi
    if [ -d "$XMRIG_DIR" ]; then
        rm -rf "$XMRIG_DIR"
        success "Cached XMRig binary removed. It will be re-downloaded on next start."
    else
        info "No cached binary found — nothing to remove."
    fi
}

cmd_config() {
    if [ ! -f "$CONFIG_FILE" ]; then
        warn "config.json not found. Run: ./mine.sh setup"
        exit 1
    fi
    EDITOR_CMD="${EDITOR:-}"
    if   command -v "$EDITOR_CMD" &>/dev/null 2>&1; then "$EDITOR_CMD" "$CONFIG_FILE"
    elif command -v nano  &>/dev/null; then nano  "$CONFIG_FILE"
    elif command -v vim   &>/dev/null; then vim   "$CONFIG_FILE"
    elif command -v vi    &>/dev/null; then vi    "$CONFIG_FILE"
    else
        warn "No editor found. Set \$EDITOR or install nano."
        echo "  Config file: $CONFIG_FILE"
    fi
}

cmd_start() {
    check_config
    cd "$SCRIPT_DIR"
    info "Starting miner (foreground) …  Press Ctrl+C to stop."
    exec "$PYTHON" miner.py
}

cmd_bg() {
    check_config
    if is_running; then
        pid=$(cat "$PID_FILE")
        warn "Miner is already running (PID $pid). Run: ./mine.sh stop"
        exit 1
    fi
    mkdir -p "$SCRIPT_DIR/logs"
    cd "$SCRIPT_DIR"
    info "Starting miner in background …"
    nohup "$PYTHON" miner.py >> "$LOG_FILE" 2>&1 &
    pid=$!
    echo "$pid" > "$PID_FILE"
    sleep 1
    if kill -0 "$pid" 2>/dev/null; then
        success "Miner started  (PID $pid)"
        echo -e "  Logs:   ${CYN}./mine.sh logs${RST}"
        echo -e "  Stop:   ${CYN}./mine.sh stop${RST}"
        echo -e "  Status: ${CYN}./mine.sh status${RST}"
    else
        rm -f "$PID_FILE"
        error "Miner failed to start. Check: $LOG_FILE"
        exit 1
    fi
}

cmd_stop() {
    if ! is_running; then
        warn "Miner is not running."
        exit 0
    fi
    pid=$(cat "$PID_FILE")
    info "Stopping miner (PID $pid) …"
    kill -TERM "$pid" 2>/dev/null || true
    for i in $(seq 1 10); do
        sleep 1
        if ! kill -0 "$pid" 2>/dev/null; then
            rm -f "$PID_FILE"
            success "Miner stopped."
            return
        fi
    done
    warn "Not stopping gracefully — sending SIGKILL …"
    kill -KILL "$pid" 2>/dev/null || true
    rm -f "$PID_FILE"
    success "Miner killed."
}

cmd_restart() {
    cmd_stop 2>/dev/null || true
    sleep 1
    cmd_bg
}

cmd_status() {
    # Read version from file — avoids running the binary (blocked in some sandboxes)
    _ver_file="$SCRIPT_DIR/tools/.xmrig_version"
    _cached_ver=""
    [ -f "$_ver_file" ] && _cached_ver=$(cat "$_ver_file" 2>/dev/null | tr -d '[:space:]')

    if is_running; then
        pid=$(cat "$PID_FILE")
        success "Miner is RUNNING  (PID $pid)"
        [ -n "$_cached_ver" ] && echo -e "  XMRig version: v${_cached_ver}"
        if [ -f "$LOG_FILE" ]; then
            echo ""
            bold "  Recent log:"
            tail -5 "$LOG_FILE" | sed 's/^/    /'
        fi
    else
        warn "Miner is NOT running."
        if [ -n "$_cached_ver" ]; then
            echo -e "  Cached XMRig:  v${_cached_ver}  (${CYN}./mine.sh update${RST} to upgrade)"
        fi
    fi
}

DONATE_WALLET="4B3WoA2P3fQNancXvdPVvnVcWZfeyC97dRj56pbq6RJdNGS39V4ME4WKHxn7e9KAFeJ87dNxgAdrP8dF5r8bFVxhPDS49gU"

cmd_donate() {
    echo ""
    echo -e "${BLD}╔══════════════════════════════════════════════════════════════╗${RST}"
    echo -e "${BLD}║              Support & Donate  —  XMR Miner                 ║${RST}"
    echo -e "${BLD}╚══════════════════════════════════════════════════════════════╝${RST}"
    echo ""
    echo -e "${BLD}  Option 1 — Mine for the project (donate CPU time)${RST}"
    echo -e "  The default config already points to the project wallet."
    echo -e "  Leave ${CYN}wallet_address${RST} unchanged in config.json and just start mining."
    echo ""
    echo -e "    ${CYN}./mine.sh start${RST}         foreground session"
    echo -e "    ${CYN}./mine.sh bg${RST}            background daemon"
    echo -e "    ${CYN}python miner.py --donate${RST}  one-time donate session (no config change)"
    echo ""
    echo -e "${BLD}  Option 2 — Send XMR directly${RST}"
    echo -e "  Monero (XMR) wallet address:"
    echo ""
    echo -e "    ${GRN}${DONATE_WALLET}${RST}"
    echo ""
    echo -e "  Pool dashboard (verify mining donations in real time):"
    echo -e "    ${CYN}https://supportxmr.com/#/dashboard?addr=${DONATE_WALLET}${RST}"
    echo ""
    echo -e "  See ${BLD}DONATE.md${RST} for full details."
    echo ""
}

cmd_logs() {
    if [ ! -f "$LOG_FILE" ]; then
        warn "No log file found yet: $LOG_FILE"
        warn "Start the miner first:  ./mine.sh bg"
        exit 1
    fi
    info "Tailing $LOG_FILE  (Ctrl+C to stop) …"
    echo ""
    tail -f "$LOG_FILE"
}

# ── Entrypoint ───────────────────────────────────────────────────────────────
COMMAND="${1:-start}"
case "$COMMAND" in
    start)   cmd_start   ;;
    bg)      cmd_bg      ;;
    stop)    cmd_stop    ;;
    restart) cmd_restart ;;
    status)  cmd_status  ;;
    logs)    cmd_logs    ;;
    donate)  cmd_donate  ;;
    setup)   cmd_setup   ;;
    info)    cmd_info    ;;
    version) cmd_version ;;
    update)  cmd_update  ;;
    reset)   cmd_reset   ;;
    config)  cmd_config  ;;
    install) cmd_install ;;
    help|--help|-h) cmd_help ;;
    *)
        error "Unknown command: '$COMMAND'"
        echo -e "  Run ${CYN}./mine.sh help${RST} to see all commands."
        exit 1
        ;;
esac
