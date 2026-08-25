"""Small cross-platform terminal interface for the local miner controller.

The TUI is intentionally built with the Python standard library so it works on
Ubuntu Server, Raspberry Pi OS Lite, Windows, and macOS without curses or a
network service. It never starts mining automatically; starting a daemon is an
explicit menu action and uses the existing daemon safeguards.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _clear() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def _pause() -> None:
    try:
        input("\nPress Enter to return to the menu…")
    except (EOFError, KeyboardInterrupt):
        pass


def _run_cli(command: str) -> None:
    """Run an existing command in a child process, preserving CRYPTO_CONFIG."""
    subprocess.run([sys.executable, str(BASE_DIR / "miner.py"), command], check=False)
    _pause()


def _menu() -> None:
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║             Crypto Miner Controller — local TUI             ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print("  No action runs until you choose it. Use only authorized hardware.\n")
    print("  1  Validate config (no download, no mining)")
    print("  2  Run setup wizard")
    print("  3  Start background miner")
    print("  4  Stop background miner")
    print("  5  Restart background miner")
    print("  6  Show status")
    print("  7  Show logs")
    print("  8  Show system information")
    print("  9  Show donation information")
    print("  q  Quit")


def run_tui() -> None:
    """Run the explicit local TUI until the user chooses quit."""
    from core import config as config_module
    from core import daemon

    while True:
        _clear()
        _menu()
        try:
            choice = input("\n  Select an option: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting TUI.")
            return

        if choice == "q":
            print("Exiting TUI.")
            return
        if choice == "1":
            _run_cli("check")
        elif choice == "2":
            config_module.run_setup()
            _pause()
        elif choice == "3":
            daemon.cmd_bg()
            _pause()
        elif choice == "4":
            daemon.cmd_stop()
            _pause()
        elif choice == "5":
            daemon.cmd_restart()
            _pause()
        elif choice == "6":
            daemon.cmd_status()
            _pause()
        elif choice == "7":
            try:
                daemon.cmd_logs()
            except KeyboardInterrupt:
                pass
            _pause()
        elif choice == "8":
            _run_cli("info")
        elif choice == "9":
            _run_cli("donate")
        else:
            print("\nUnknown option. Choose 1–9 or q.")
            _pause()
