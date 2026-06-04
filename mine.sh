#!/usr/bin/env bash
# =============================================================================
#  mine.sh — XMR Miner CLI  (Linux / macOS)
# =============================================================================
#  Usage:
#    ./mine.sh [command]
#
#  Commands:
#    start       Start mining in the foreground  (default when no command given)
#    bg          Start mining in the background (daemon mode)
#    stop        Stop a background miner
#    restart     Stop + start in the background
#    status      Show whether the miner is running
#    logs        Tail the miner log  (Ctrl+C to exit)
#    setup       Run the interactive config wizard
#    info        Print OS / CPU / GPU info
#    install     Install / update Python dependencies
#    help        Show this help message
# =============================================================================

set -euo pipefail

# ── Colours ────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GRN='\033[0;32m'
YLW='\033[0;33m'
BLU='\033[0;34m'
CYN='\033[0;36m'
BLD='\033[1m'
RST='\033[0m'

# Disable colours if not a terminal
[ -t 1 ] || { RED=''; GRN=''; YLW=''; BLU=''; CYN=''; BLD=''; RST=''; }

# ── Paths ───────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$SCRIPT_DIR/.miner.pid"
LOG_FILE="$SCRIPT_DIR/logs/miner.log"

# ── Helpers ─────────────────────────────────────────────────────────────────
info()    { echo -e "${BLU}[mine]${RST} $*"; }
success() { echo -e "${GRN}[mine]${RST} $*"; }
warn()    { echo -e "${YLW}[mine]${RST} $*"; }
error()   { echo -e "${RED}[mine]${RST} $*" >&2; }

find_python() {
    for py in python3 python python3.12 python3.11 python3.10; do
        if command -v "$py" &>/dev/null; then
            # Make sure it's Python 3
            version=$("$py" -c "import sys; print(sys.version_info.major)" 2>/dev/null || echo 0)
            if [ "$version" = "3" ]; then
                echo "$py"
                return 0
            fi
        fi
    done
    error "Python 3 not found. Please install Python 3.10 or later."
    exit 1
}

PYTHON=$(find_python)

check_config() {
    if [ ! -f "$SCRIPT_DIR/config.json" ]; then
        warn "config.json not found."
        echo -e "  Run ${CYN}./mine.sh setup${RST} to create it.\n"
        exit 1
    fi
}

is_running() {
    if [ -f "$PID_FILE" ]; then
        pid=$(cat "$PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            return 0   # running
        else
            rm -f "$PID_FILE"
        fi
    fi
    return 1   # not running
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
  ${CYN}status${RST}     Show whether the miner is running
  ${CYN}logs${RST}       Tail the miner log               (Ctrl+C to exit)
  ${CYN}setup${RST}      Interactive config wizard
  ${CYN}info${RST}       Print OS / CPU / GPU detection
  ${CYN}install${RST}    Install / update Python dependencies
  ${CYN}help${RST}       Show this message

${BLD}Examples:${RST}
  ./mine.sh setup       # configure wallet, pool, temperature limits
  ./mine.sh bg          # mine in background
  ./mine.sh logs        # watch live output
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
        echo -e "  Logs: ${CYN}./mine.sh logs${RST}"
        echo -e "  Stop: ${CYN}./mine.sh stop${RST}"
    else
        rm -f "$PID_FILE"
        error "Miner failed to start. Check logs: $LOG_FILE"
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
            exit 0
        fi
    done

    warn "Process did not stop gracefully — sending SIGKILL …"
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
    if is_running; then
        pid=$(cat "$PID_FILE")
        success "Miner is RUNNING  (PID $pid)"

        # show last few log lines if available
        if [ -f "$LOG_FILE" ]; then
            echo ""
            echo -e "${BLD}Recent log:${RST}"
            tail -5 "$LOG_FILE" | sed 's/^/  /'
        fi
    else
        warn "Miner is NOT running."
    fi
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
    setup)   cmd_setup   ;;
    info)    cmd_info    ;;
    install) cmd_install ;;
    help|--help|-h) cmd_help ;;
    *)
        error "Unknown command: '$COMMAND'"
        echo -e "  Run ${CYN}./mine.sh help${RST} to see all commands."
        exit 1
        ;;
esac
