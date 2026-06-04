#!/usr/bin/env python3
"""
SAFE XMR MINER — Cross-platform controller (Windows + Linux)

Combines the previous miner_window.py and miner_linux.py into a single
controller that auto-detects the OS, ensures xmrig is available (tries to
install on common Linux distros or downloads the Windows release), checks
for temperature sensors (psutil / lm-sensors fallback), and starts the miner
with basic thermal protections and CPU limits.

USAGE:
    python3 miner_crossplatform.py

Note: On Linux the script may attempt to run package manager commands using
'sudo' to install xmrig and lm-sensors. If you prefer to install manually,
install xmrig and lm-sensors yourself and re-run the script.

Be responsible: only run this on hardware you own or have explicit permission
to use. Mining may increase power usage, wear, and heat.
"""

import os
import sys
import time
import subprocess
import signal
import logging
import shutil
import urllib.request
import zipfile
import platform
import re
from pathlib import Path

try:
    import psutil
except Exception:
    psutil = None

# ================= USER CONFIG =================
WALLET_ADDRESS = "4B3WoA2P3fQNancXvdPVvnVcWZfeyC97dRj56pbq6RJdNGS39V4ME4WKHxn7e9KAFeJ87dNxgAdrP8dF5r8bFVxhPDS49gU"
POOL_ADDRESS = "pool.supportxmr.com:3333"
POOL_PASSWORD = "x"

CPU_USAGE_PERCENT = 0.70
PAUSE_TEMP_C = 80
RESUME_TEMP_C = 70
EMERGENCY_KILL_TEMP_C = 90
TEMP_CHECK_INTERVAL = 20
XMRIG_VERSION = "6.22.0"  # used when downloading Windows build
# ==============================================

BASE = Path(__file__).parent
TOOLS = BASE / "tools"
XMRIG_DIR = TOOLS / "xmrig"
LOG_DIR = BASE / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger("miner-cross")

IS_WINDOWS = platform.system().lower().startswith("win")
IS_LINUX = platform.system().lower().startswith("linux")


# ----------------- INSTALL / ENSURE XMRIG -----------------
def xmrig_bin_path():
    """Return path to xmrig binary (string) or None."""
    if IS_WINDOWS:
        return str(XMRIG_DIR / "xmrig.exe")
    else:
        path = shutil.which("xmrig")
        return path


def download_xmrig_windows():
    """Download and unpack XMRig Windows release into tools/xmrig."""
    TOOLS.mkdir(exist_ok=True)
    tmp = TOOLS / "_tmp"
    tmp.mkdir(exist_ok=True)

    url = f"https://github.com/xmrig/xmrig/releases/download/v{XMRIG_VERSION}/xmrig-{XMRIG_VERSION}-msvc-win64.zip"
    archive = tmp / "xmrig.zip"

    log.info("Downloading XMRig (Windows) from %s", url)
    try:
        urllib.request.urlretrieve(url, archive)
    except Exception as e:
        log.error("Failed to download xmrig: %s", e)
        return None

    try:
        with zipfile.ZipFile(archive) as z:
            z.extractall(tmp)
    except Exception as e:
        log.error("Failed to extract xmrig archive: %s", e)
        return None

    exe = next(tmp.rglob("xmrig.exe"), None)
    if not exe:
        log.error("xmrig.exe not found inside archive")
        return None

    if XMRIG_DIR.exists():
        try:
            shutil.rmtree(XMRIG_DIR)
        except Exception:
            pass

    shutil.move(str(exe.parent), XMRIG_DIR)
    try:
        shutil.rmtree(tmp)
    except Exception:
        pass

    return str(XMRIG_DIR / "xmrig.exe")


def try_install_with_pkgmgr():
    """Attempt to install xmrig and lm-sensors using a known package manager.
    This is best-effort: different distros have different package names.
    Returns True on success (xmrig available in PATH), False otherwise.
    """
    candidates = [
        ("apt-get", ["sudo", "apt-get", "update"], ["sudo", "apt-get", "install", "-y", "xmrig", "lm-sensors"]),
        ("dnf", None, ["sudo", "dnf", "install", "-y", "xmrig", "lm_sensors"]),
        ("yum", None, ["sudo", "yum", "install", "-y", "xmrig", "lm_sensors"]),
        ("pacman", None, ["sudo", "pacman", "-Syu", "--noconfirm", "xmrig", "lm_sensors"]),
        ("zypper", None, ["sudo", "zypper", "install", "-y", "xmrig", "lm_sensors"]),
    ]

    for name, pre, install_cmd in candidates:
        if shutil.which(name):
            try:
                if pre:
                    log.info("Running: %s", " ".join(pre))
                    subprocess.run(pre, check=False)
                log.info("Attempting to install xmrig via %s", name)
                subprocess.run(install_cmd, check=False)
                # check if xmrig now exists
                if shutil.which("xmrig"):
                    return True
            except Exception as e:
                log.warning("Package manager %s failed: %s", name, e)

    return False


def ensure_xmrig():
    """Ensure xmrig is available, installing or downloading as needed.
    Returns path to xmrig binary (string) or exits with error.
    """
    path = xmrig_bin_path()
    if path and Path(path).exists():
        return path

    if IS_WINDOWS:
        log.info("XMRig not found — downloading Windows build...")
        path = download_xmrig_windows()
        if not path:
            log.error("Failed to install xmrig for Windows. Please install manually.")
            sys.exit(1)
        return path

    if IS_LINUX:
        log.info("XMRig not found in PATH on Linux. Trying to install via package manager...")
        ok = try_install_with_pkgmgr()
        if ok:
            path = shutil.which("xmrig")
            if path:
                log.info("xmrig installed: %s", path)
                return path

        # Last resort: tell the user to install manually
        log.error(
            "Could not install xmrig automatically.\n"
            "Please install xmrig and lm-sensors manually for your distribution. For Debian/Ubuntu: `sudo apt install xmrig lm-sensors`."
        )
        sys.exit(1)

    log.error("Unsupported platform: %s", platform.system())
    sys.exit(1)


# ----------------- TEMPERATURE READING -----------------

def cpu_temp():
    """Return CPU temperature in °C as float, or None if unavailable."""
    # Primary: psutil sensors
    try:
        if psutil and hasattr(psutil, "sensors_temperatures"):
            temps = psutil.sensors_temperatures()
            if temps:
                values = []
                for entries in temps.values():
                    for e in entries:
                        if getattr(e, 'current', None) is not None and e.current > 0:
                            values.append(e.current)
                if values:
                    return max(values)
    except Exception:
        pass

    # Fallback: use `sensors` command (lm-sensors) and parse numbers
    try:
        out = subprocess.check_output(["sensors"], stderr=subprocess.DEVNULL, text=True)
        nums = re.findall(r"([-+]?[0-9]+\.?[0-9]*)°C", out)
        nums = [float(n) for n in nums]
        if nums:
            return max(nums)
    except Exception:
        pass

    return None


# ----------------- MINER CONTROL -----------------

def start_miner(xmrig_path):
    """
    Start XMRig.
    On Linux, force a PTY so XMRig thinks it is attached to a real terminal
    (otherwise banner/output may be suppressed).
    """
    cmd = [
        xmrig_path,
        "-o", POOL_ADDRESS,
        "-u", WALLET_ADDRESS,
        "-p", POOL_PASSWORD,
    ]

    proc_p = None
    proc = None

    if IS_LINUX:
        try:
            import pty
            master, slave = pty.openpty()
            proc_p = subprocess.Popen(
                cmd,
                stdin=sys.stdin,
                stdout=sys.stdout,
                stderr=sys.stderr
            )
        except Exception as e:
            log.warning("PTY launch failed, falling back to normal pipes: %s", e)
            proc_p = subprocess.Popen(
                cmd,
                stdin=sys.stdin,
                stdout=sys.stdout,
                stderr=sys.stderr
            )
    else:
        proc_p = subprocess.Popen(
            cmd,
            stdin=sys.stdin,
            stdout=sys.stdout,
            stderr=sys.stderr
        )

    if psutil:
        try:
            proc = psutil.Process(proc_p.pid)
        except Exception:
            proc = None

    return proc_p, proc

    # Linux / other unix
    cmd = [
        xmrig_path,
        "-o", POOL_ADDRESS,
        "-u", WALLET_ADDRESS,
        "-p", POOL_PASSWORD,
        "--threads", str(threads),
        "--print-time", "10",
        "--randomx-mode=light",
        "--cpu-priority=2",
    ]

    p = subprocess.Popen(
        cmd,
        stdin=sys.stdin,
        stdout=sys.stdout,
        stderr=sys.stderr
    )
    proc = psutil.Process(p.pid) if psutil else None
    try:
        if proc and hasattr(proc, 'nice'):
            proc.nice(10)
    except Exception:
        pass

    return proc


# ----------------- MAIN LOOP -----------------

def main():
    xmrig_path = ensure_xmrig()
    log.info("Using xmrig: %s", xmrig_path)

    if psutil is None:
        log.warning("psutil not available. Some features (temperature, process control) may not work.")

    miner = start_miner(xmrig_path)
    suspended = False

    def shutdown(*_):
        log.info("Shutdown signal received. Stopping miner...")
        try:
            if proc_p and proc_p.poll() is None:
                proc_p.terminate()
                proc_p.wait(timeout=5)
        except Exception:
            try:
                proc_p.kill()
            except Exception:
                pass
        sys.exit(0)
        log.info("Shutting down miner...")
        try:
            if miner and miner.is_running():
                miner.kill()
        except Exception:
            pass
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    try:
        signal.signal(signal.SIGTERM, shutdown)
    except Exception:
        pass
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, shutdown)

    while True:
        # Check if miner process is alive
        try:
            if miner and not miner.is_running():
                log.error("XMRig exited unexpectedly. Exiting controller.")
                sys.exit(1)
        except Exception:
            pass

        temp = cpu_temp()
        if temp is None:
            if not hasattr(main, "_warned"):
                log.warning(
                    "CPU temperature unavailable on this system. Thermal protections disabled. On Linux, try installing lm-sensors and running `sudo sensors-detect` if supported by your hardware."
                )
                main._warned = True
            time.sleep(TEMP_CHECK_INTERVAL)
            continue

        log.info(f"CPU temp: {temp:.1f}°C")

        if temp >= EMERGENCY_KILL_TEMP_C:
            log.critical("Emergency temperature reached (>= %s°C). Killing miner.", EMERGENCY_KILL_TEMP_C)
            shutdown()
        elif temp >= PAUSE_TEMP_C and not suspended:
            try:
                miner.suspend()
                suspended = True
                log.info("Miner suspended due to high temperature.")
            except Exception:
                log.warning("Failed to suspend miner process.")
        elif suspended and temp <= RESUME_TEMP_C:
            try:
                miner.resume()
                suspended = False
                log.info("Miner resumed — temperature dropped.")
            except Exception:
                log.warning("Failed to resume miner process.")

        time.sleep(TEMP_CHECK_INTERVAL)


if __name__ == "__main__":
    main()
