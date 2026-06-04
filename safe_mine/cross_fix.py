#! python3
"""
SAFE XMR MINER — Single cross-platform controller (Windows + Linux)

- Auto-detects OS.
- Ensures xmrig is available: tries package managers on Linux or downloads the
  Windows build into ./tools/xmrig/.
- Reads CPU temperature via psutil (preferred) or lm-sensors (`sensors`) fallback.
- Starts xmrig with reasonable thread limits, uses a PTY on Linux to preserve
  banner/interactive output, and configures process affinity / niceness on Windows.
- Implements thermal protections: suspend/resume and emergency kill.
- Robust signal handling and orderly shutdown.

USAGE:
    python3 miner_crossplatform.py

Be responsible: only run this on hardware you own or have explicit permission
to use. Mining may increase power usage, wear, and heat.
"""

from __future__ import annotations
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

# Fraction of logical CPUs to use (0.0..1.0)
CPU_USAGE_PERCENT = 0.70

# Thermal thresholds (°C)
PAUSE_TEMP_C = 80
RESUME_TEMP_C = 70
EMERGENCY_KILL_TEMP_C = 90
TEMP_CHECK_INTERVAL = 20  # seconds

# Windows XMRig release version (only used for automatic Windows download)
XMRIG_VERSION = "6.22.0"
# ==============================================

BASE = Path(__file__).parent.resolve()
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


# ----------------- HELPERS -----------------
def xmrig_bin_path() -> str | None:
    """Return path to xmrig binary (string) or None."""
    if IS_WINDOWS:
        candidate = XMRIG_DIR / "xmrig.exe"
        return str(candidate) if candidate.exists() else None
    else:
        return shutil.which("xmrig")


def download_xmrig_windows() -> str | None:
    """Download and unpack XMRig Windows release into tools/xmrig."""
    TOOLS.mkdir(exist_ok=True)
    tmp = TOOLS / "_tmp"
    if tmp.exists():
        shutil.rmtree(tmp, ignore_errors=True)
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
        with zipfile.ZipFile(archive, "r") as z:
            z.extractall(tmp)
    except Exception as e:
        log.error("Failed to extract xmrig archive: %s", e)
        return None

    exe = next(tmp.rglob("xmrig.exe"), None)
    if not exe:
        log.error("xmrig.exe not found inside archive")
        return None

    if XMRIG_DIR.exists():
        shutil.rmtree(XMRIG_DIR, ignore_errors=True)

    shutil.move(str(exe.parent), XMRIG_DIR)
    shutil.rmtree(tmp, ignore_errors=True)
    log.info("Downloaded xmrig to %s", XMRIG_DIR)
    return str(XMRIG_DIR / "xmrig.exe")


def try_install_with_pkgmgr() -> bool:
    """Try installing xmrig and lm-sensors via common Linux package managers."""
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
                if shutil.which("xmrig"):
                    return True
            except Exception as e:
                log.warning("Package manager %s failed: %s", name, e)
    return False


def ensure_xmrig() -> str:
    """
    Ensure xmrig is available.
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

        log.error(
            "Could not install xmrig automatically.\n"
            "Please install xmrig and lm-sensors manually for your distribution. For Debian/Ubuntu: `sudo apt install xmrig lm-sensors`."
        )
        sys.exit(1)

    log.error("Unsupported platform: %s", platform.system())
    sys.exit(1)


# ----------------- TEMPERATURE READING -----------------
def cpu_temp() -> float | None:
    """Return CPU temperature in °C as float, or None if unavailable."""
    # Primary: psutil sensors
    try:
        if psutil and hasattr(psutil, "sensors_temperatures"):
            temps = psutil.sensors_temperatures()
            if temps:
                values = []
                for entries in temps.values():
                    for e in entries:
                        current = getattr(e, "current", None)
                        if current is not None and current > 0:
                            values.append(current)
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


# ----------------- MINER START / CONTROL -----------------
def calculate_threads() -> int:
    """Return number of threads to request to xmrig based on CPU_USAGE_PERCENT."""
    try:
        total = psutil.cpu_count(logical=True) if psutil else os.cpu_count()
    except Exception:
        total = os.cpu_count()
    total = total or 1
    threads = max(1, int(total * CPU_USAGE_PERCENT))
    # limit threads to total
    return min(threads, total)


def start_miner(xmrig_path):
    """
    Start XMRig.
    Linux path is UNCHANGED.
    Windows is optimized for max hashrate + safe control.
    """
    proc_p = None
    ps_proc = None

    # ================= LINUX (DO NOT TOUCH) =================
    if IS_LINUX:
        threads = calculate_threads()

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

        import pty
        import threading

        master_fd, slave_fd = pty.openpty()

        proc_p = subprocess.Popen(
            cmd,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            close_fds=True
        )

        os.close(slave_fd)

        def forward_output():
            try:
                while True:
                    data = os.read(master_fd, 1024)
                    if not data:
                        break
                    sys.stdout.buffer.write(data)
                    sys.stdout.flush()
            except OSError:
                pass

        threading.Thread(target=forward_output, daemon=True).start()

    # ================= WINDOWS (FIXED) =================
    else:
        total = psutil.cpu_count(logical=True)
        allowed = max(1, int(total * CPU_USAGE_PERCENT))

        cmd = [
            xmrig_path,
            "-o", POOL_ADDRESS,
            "-u", WALLET_ADDRESS,
            "-p", POOL_PASSWORD,
            "--print-time", "10",
            "--cpu-priority=2",
            "--auto-config",
            "--randomx-no-rdmsr=0",
            "--huge-pages"
        ]

        proc_p = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=sys.stdout,
            stderr=sys.stderr
        )

        ps_proc = psutil.Process(proc_p.pid)

        try:
            # ✅ KEY PERFORMANCE FIX
            ps_proc.cpu_affinity(list(range(allowed)))
            ps_proc.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
        except Exception as e:
            log.warning("Windows CPU control failed: %s", e)

    log.info(
        "Started XMRig (pid=%s) using ~%d%% CPU",
        proc_p.pid,
        int(CPU_USAGE_PERCENT * 100)
    )

    return proc_p, ps_proc



# ----------------- MAIN LOOP -----------------
def main():
    xmrig_path = ensure_xmrig()
    log.info("Using xmrig: %s", xmrig_path)

    if psutil is None:
        log.warning("psutil not available. Some features (temperature reading, process control) may not work. "
                    "On Linux consider: sudo apt install python3-psutil lm-sensors")

    proc_p = None
    ps_proc = None
    suspended = False

    def shutdown(*_):
        log.info("Shutting down miner...")
        # Try graceful terminate first
        try:
            if proc_p:
                if proc_p.poll() is None:
                    proc_p.terminate()
                    try:
                        proc_p.wait(timeout=5)
                    except Exception:
                        proc_p.kill()
        except Exception:
            pass

        # As last fallback, if psutil process exists, kill it
        try:
            if ps_proc and ps_proc.is_running():
                ps_proc.kill()
        except Exception:
            pass

        sys.exit(0)

    # register signal handlers
    signal.signal(signal.SIGINT, shutdown)
    if hasattr(signal, "SIGTERM"):
        try:
            signal.signal(signal.SIGTERM, shutdown)
        except Exception:
            pass

    # Start miner
    proc_p, ps_proc = start_miner(xmrig_path)

    # Warn once if temperatures are unusable
    warned_no_temp = False

    while True:
        # Check process health
        try:
            if proc_p and proc_p.poll() is not None:
                log.error("XMRig exited unexpectedly (returncode=%s). Exiting controller.", proc_p.returncode)
                sys.exit(1)
        except Exception:
            pass

        temp = cpu_temp()
        if temp is None:
            if not warned_no_temp:
                log.warning(
                    "CPU temperature unavailable on this system. Thermal protections disabled. "
                    "On Linux, try installing lm-sensors and running `sudo sensors-detect` if supported by your hardware."
                )
                warned_no_temp = True
            time.sleep(TEMP_CHECK_INTERVAL)
            continue

        log.info("CPU temp: %.1f°C", temp)

        try:
            if temp >= EMERGENCY_KILL_TEMP_C:
                log.critical("Emergency temperature reached (>= %s°C). Killing miner.", EMERGENCY_KILL_TEMP_C)
                shutdown()
            elif temp >= PAUSE_TEMP_C and not suspended:
                # suspend via psutil if available
                if ps_proc:
                    try:
                        ps_proc.suspend()
                        suspended = True
                        log.info("Miner suspended due to high temperature.")
                    except Exception as e:
                        log.warning("Failed to suspend miner process via psutil: %s", e)
                else:
                    log.warning("Thermal threshold reached but cannot suspend: psutil not available.")
            elif suspended and temp <= RESUME_TEMP_C:
                if ps_proc:
                    try:
                        ps_proc.resume()
                        suspended = False
                        log.info("Miner resumed — temperature dropped.")
                    except Exception as e:
                        log.warning("Failed to resume miner process via psutil: %s", e)
        except Exception as e:
            log.exception("Error during thermal/proc handling: %s", e)

        time.sleep(TEMP_CHECK_INTERVAL)


if __name__ == "__main__":
    main()
