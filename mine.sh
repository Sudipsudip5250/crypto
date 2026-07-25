#!/usr/bin/env bash
# =============================================================================
#  mine.sh — XMR Miner launcher for Linux / macOS
# =============================================================================
#  All logic lives in miner.py.  This script finds Python 3.10+ and hands off.
#
#  Usage:  ./mine.sh [command] [options]
#  Run:    ./mine.sh help   for the full command list.
#
#  FOR EDUCATIONAL AND RESEARCH PURPOSES ONLY.
#  Do NOT run on cloud platforms — see DISCLAIMER.md.
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

find_python() {
    for py in python3 python python3.13 python3.12 python3.11 python3.10; do
        if command -v "$py" &>/dev/null; then
            ver=$("$py" -c "import sys; print(sys.version_info.major)" 2>/dev/null || echo 0)
            [ "$ver" = "3" ] && { echo "$py"; return 0; }
        fi
    done
    echo "Error: Python 3.10 or later is required." >&2
    echo "       Install from https://python.org or via your package manager." >&2
    exit 1
}

cd "$SCRIPT_DIR"
exec "$(find_python)" miner.py "$@"
