"""
core/daemon.py
--------------
Cross-platform background-process management for the miner.

Implements the bg / stop / restart / status / logs / config / install / reset
commands so that miner.py (and any thin shell launcher) can delegate to one
place rather than duplicating logic across mine.sh, mine.bat, and mine.ps1.

All paths are resolved relative to the project root so the module works
regardless of the current working directory when it is called.
"""
# ── Educational / research use only ─────────────────────────────────────────
# See DISCLAIMER.md and LICENSE for full legal notices.
# Do NOT run on cloud platforms, VPSes, CI/CD runners, or any machine you do
# not personally own — it violates their Terms of Service.
# ────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import os
import platform
import subprocess
import sys
import time
from pathlib import Path

BASE_DIR  = Path(__file__).resolve().parent.parent
PID_FILE  = BASE_DIR / ".miner.pid"
LOG_DIR   = BASE_DIR / "logs"
LOG_FILE  = LOG_DIR  / "miner.log"
CONFIG    = BASE_DIR / "config.json"
TOOLS_DIR = BASE_DIR / "tools"
XMRIG_DIR = TOOLS_DIR / "xmrig"

IS_WINDOWS = platform.system().lower().startswith("win")

# ── ANSI colours (auto-disabled on plain Windows consoles) ───────────────────
_USE_COLOR = (not IS_WINDOWS) or bool(
    os.environ.get("WT_SESSION") or os.environ.get("ANSICON") or os.environ.get("TERM")
)
GRN = "\033[0;32m" if _USE_COLOR else ""
YLW = "\033[0;33m" if _USE_COLOR else ""
CYN = "\033[0;36m" if _USE_COLOR else ""
BLD = "\033[1m"    if _USE_COLOR else ""
RST = "\033[0m"    if _USE_COLOR else ""


def _info(msg: str) -> None:
    print(f"{CYN}[mine]{RST} {msg}")

def _ok(msg: str) -> None:
    print(f"{GRN}[mine]{RST} {msg}")

def _warn(msg: str) -> None:
    print(f"{YLW}[mine]{RST} {msg}")


# ---------------------------------------------------------------------------
# PID / process helpers
# ---------------------------------------------------------------------------

def get_pid() -> int | None:
    """Return the PID of the running miner daemon, or None."""
    if not PID_FILE.exists():
        return None

    try:
        pid = int(PID_FILE.read_text(encoding="utf-8").strip())
    except (ValueError, OSError):
        PID_FILE.unlink(missing_ok=True)
        return None

    # Verify the process is actually alive
    alive = False
    try:
        if IS_WINDOWS:
            try:
                import psutil
                alive = psutil.pid_exists(pid)
            except ImportError:
                # psutil unavailable — use tasklist as fallback
                result = subprocess.run(
                    ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                    capture_output=True, text=True,
                )
                alive = str(pid) in result.stdout
        else:
            os.kill(pid, 0)   # signal 0 = existence check only
            alive = True
    except (ProcessLookupError, PermissionError):
        alive = False
    except OSError:
        alive = False

    if not alive:
        PID_FILE.unlink(missing_ok=True)
        return None

    return pid


def is_running() -> bool:
    """Return True if a miner daemon is currently running."""
    return get_pid() is not None


# ---------------------------------------------------------------------------
# bg — start daemon
# ---------------------------------------------------------------------------

def cmd_bg() -> None:
    """Start the miner as a detached background daemon."""
    if is_running():
        pid = get_pid()
        _warn(f"Miner is already running (PID {pid}).  Run: python miner.py stop")
        return

    if not CONFIG.exists():
        _warn("config.json not found.  Run: python miner.py setup")
        sys.exit(1)

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    with open(LOG_FILE, "a", encoding="utf-8") as log_handle:
        if IS_WINDOWS:
            DETACHED_PROCESS      = 0x00000008
            CREATE_NEW_PROC_GROUP = 0x00000200
            proc = subprocess.Popen(
                [sys.executable, str(BASE_DIR / "miner.py"), "start"],
                stdout=log_handle,
                stderr=log_handle,
                creationflags=DETACHED_PROCESS | CREATE_NEW_PROC_GROUP,
                close_fds=True,
            )
        else:
            proc = subprocess.Popen(
                [sys.executable, str(BASE_DIR / "miner.py"), "start"],
                stdout=log_handle,
                stderr=log_handle,
                start_new_session=True,   # detach from controlling terminal
                close_fds=True,
            )

    PID_FILE.write_text(str(proc.pid), encoding="utf-8")
    time.sleep(1)

    if proc.poll() is None:
        _ok(f"Miner started  (PID {proc.pid})")
        print(f"  Logs:   {CYN}python miner.py logs{RST}")
        print(f"  Stop:   {CYN}python miner.py stop{RST}")
        print(f"  Status: {CYN}python miner.py status{RST}")
    else:
        PID_FILE.unlink(missing_ok=True)
        print(f"[mine] Miner failed to start. Check: {LOG_FILE}", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# stop
# ---------------------------------------------------------------------------

def cmd_stop() -> None:
    """Stop the background miner daemon."""
    pid = get_pid()
    if pid is None:
        _warn("Miner is not running.")
        return

    _info(f"Stopping miner (PID {pid}) …")

    try:
        if IS_WINDOWS:
            subprocess.run(["taskkill", "/PID", str(pid), "/F"],
                           capture_output=True)
        else:
            import signal as _signal
            os.kill(pid, _signal.SIGTERM)
    except Exception as exc:
        _warn(f"Could not send stop signal: {exc}")

    # Wait up to 10 s for graceful exit
    for _ in range(10):
        time.sleep(1)
        if get_pid() is None:
            _ok("Miner stopped.")
            return

    # Force kill
    _warn("Not stopping gracefully — force-killing …")
    try:
        if IS_WINDOWS:
            subprocess.run(["taskkill", "/PID", str(pid), "/F", "/T"],
                           capture_output=True)
        else:
            os.kill(pid, 9)
    except Exception:
        pass

    PID_FILE.unlink(missing_ok=True)
    _ok("Miner killed.")


# ---------------------------------------------------------------------------
# restart
# ---------------------------------------------------------------------------

def cmd_restart() -> None:
    """Stop the running daemon (if any) then start a new one."""
    cmd_stop()
    time.sleep(1)
    cmd_bg()


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------

def cmd_status() -> None:
    """Print running state, XMRig version, and last 5 log lines."""
    from core.updater import get_cached_version
    pid = get_pid()
    ver = get_cached_version()

    if pid:
        _ok(f"Miner is RUNNING  (PID {pid})")
        if ver:
            print(f"  XMRig version : v{ver}")
        if LOG_FILE.exists():
            print(f"\n  {BLD}Recent log:{RST}")
            try:
                lines = LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()
                for line in lines[-5:]:
                    print(f"    {line}")
            except OSError:
                pass
    else:
        _warn("Miner is NOT running.")
        if ver:
            print(
                f"  Cached XMRig : v{ver}  "
                f"({CYN}python miner.py update{RST} to upgrade)"
            )


# ---------------------------------------------------------------------------
# logs — tail the log file
# ---------------------------------------------------------------------------

def cmd_logs() -> None:
    """Stream the miner log file in real time (Ctrl+C to stop)."""
    if not LOG_FILE.exists():
        _warn(f"No log file yet: {LOG_FILE}")
        _warn("Start the miner first:  python miner.py bg")
        return

    _info(f"Tailing {LOG_FILE}  (Ctrl+C to stop) …")
    print()

    # On Unix, replace this process with tail -f for efficient streaming
    if not IS_WINDOWS:
        tail_bin = "/usr/bin/tail"
        if not os.path.exists(tail_bin):
            tail_bin = "tail"
        try:
            os.execvp(tail_bin, [tail_bin, "-f", str(LOG_FILE)])
        except (FileNotFoundError, PermissionError):
            pass  # fall through to Python fallback

    # Cross-platform / Windows fallback: read and poll
    try:
        with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as fh:
            # Show the last 20 lines first
            content = fh.read()
            tail_lines = content.splitlines()[-20:]
            print("\n".join(tail_lines))
            # Then stream new lines
            while True:
                line = fh.readline()
                if line:
                    print(line, end="", flush=True)
                else:
                    time.sleep(0.25)
    except KeyboardInterrupt:
        print()


# ---------------------------------------------------------------------------
# config — open config.json in an editor
# ---------------------------------------------------------------------------

def cmd_config() -> None:
    """Open config.json in the user's preferred editor."""
    if not CONFIG.exists():
        _warn("config.json not found.  Run: python miner.py setup")
        sys.exit(1)

    if IS_WINDOWS:
        try:
            os.startfile(str(CONFIG))   # type: ignore[attr-defined]
        except (AttributeError, OSError):
            subprocess.Popen(["notepad.exe", str(CONFIG)])
        return

    # Unix: honour $EDITOR, then try common editors
    for ed in [os.environ.get("EDITOR", ""), "nano", "vim", "vi"]:
        if not ed:
            continue
        try:
            result = subprocess.run(
                ["which", ed], capture_output=True, text=True
            )
            if result.returncode == 0:
                os.execvp(ed, [ed, str(CONFIG)])
                return   # unreachable if execvp succeeds
        except Exception:
            continue

    _warn("No editor found. Set $EDITOR or install nano.")
    print(f"  Config file: {CONFIG}")


# ---------------------------------------------------------------------------
# install — pip install dependencies
# ---------------------------------------------------------------------------

def cmd_install() -> None:
    """Install / upgrade all Python dependencies from requirements.txt."""
    req = BASE_DIR / "requirements.txt"
    _info("Upgrading pip …")
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "--upgrade", "pip", "--quiet"],
        check=False,
    )
    _info("Installing dependencies from requirements.txt …")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", str(req)],
        check=False,
    )
    if result.returncode == 0:
        _ok("Dependencies installed.")
    else:
        print("[mine] pip install failed.", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# reset — delete cached XMRig binary
# ---------------------------------------------------------------------------

def cmd_reset() -> None:
    """Delete the cached XMRig binary so it is re-downloaded on next start."""
    if is_running():
        _warn("Miner is running. Stop it first:  python miner.py stop")
        sys.exit(1)

    if XMRIG_DIR.exists():
        import shutil
        shutil.rmtree(XMRIG_DIR)
        _ok("Cached XMRig binary removed. It will be re-downloaded on next start.")
    else:
        _info("No cached binary found — nothing to remove.")
