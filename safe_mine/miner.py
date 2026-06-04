#! python3
# ============================================================
# SAFE XMR MINER CONTROLLER
# Windows + Linux (Ubuntu tested design)
# ============================================================

import os
import sys
import time
import subprocess
import platform
import shutil
import signal
import logging
from pathlib import Path

import psutil
import urllib.request
import zipfile
import tarfile

# ============================================================
# USER CONFIG (EDIT ONLY THIS SECTION)
# ============================================================

WALLET_ADDRESS = "4B3WoA2P3fQNancXvdPVvnVcWZfeyC97dRj56pbq6RJdNGS39V4ME4WKHxn7e9KAFeJ87dNxgAdrP8dF5r8bFVxhPDS49gU"
POOL_ADDRESS = "pool.supportxmr.com:3333"
POOL_PASSWORD = "x"

# Resource safety
CPU_USAGE_PERCENT = 0.70
PAUSE_TEMP_C = 80
RESUME_TEMP_C = 70
EMERGENCY_KILL_TEMP_C = 90
TEMP_CHECK_INTERVAL = 20  # seconds

XMRIG_VERSION = "6.22.0"

# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
TOOLS_DIR = BASE_DIR / "tools"
XMRIG_DIR = TOOLS_DIR / "xmrig"
TMP_DIR = TOOLS_DIR / "_tmp"
LOG_DIR = BASE_DIR / "logs"
LOG_FILE = LOG_DIR / "miner.log"

# ============================================================
# LOGGING
# ============================================================

LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger("safe-xmr")

# ============================================================
# UTILITIES
# ============================================================

def is_windows():
    return platform.system().lower().startswith("win")

def xmrig_binary():
    return XMRIG_DIR / ("xmrig.exe" if is_windows() else "xmrig")

# ============================================================
# XMRIG INSTALLER (FIXED)
# ============================================================

def ensure_xmrig():
    if xmrig_binary().exists():
        log.info("XMRig already installed.")
        return

    TOOLS_DIR.mkdir(exist_ok=True)
    TMP_DIR.mkdir(exist_ok=True)

    if is_windows():
        url = f"https://github.com/xmrig/xmrig/releases/download/v{XMRIG_VERSION}/xmrig-{XMRIG_VERSION}-msvc-win64.zip"
        archive = TMP_DIR / "xmrig.zip"

        log.info("Downloading XMRig for Windows...")
        urllib.request.urlretrieve(url, archive)

        with zipfile.ZipFile(archive, "r") as z:
            z.extractall(TMP_DIR)

        # 🔴 REAL FIX: find xmrig.exe, not folder names
        xmrig_exe = None
        for path in TMP_DIR.rglob("xmrig.exe"):
            xmrig_exe = path
            break

        if not xmrig_exe:
            log.error("xmrig.exe not found after extraction.")
            sys.exit(1)

        extracted_dir = xmrig_exe.parent

    else:
        url = f"https://github.com/xmrig/xmrig/releases/download/v{XMRIG_VERSION}/xmrig-{XMRIG_VERSION}-linux-static-x64.tar.gz"
        archive = TMP_DIR / "xmrig.tar.gz"

        log.info("Downloading XMRig for Linux...")
        urllib.request.urlretrieve(url, archive)

        with tarfile.open(archive, "r:gz") as t:
            t.extractall(TMP_DIR)

        xmrig_bin = None
        for path in TMP_DIR.rglob("xmrig"):
            if path.is_file():
                xmrig_bin = path
                break

        if not xmrig_bin:
            log.error("xmrig binary not found after extraction.")
            sys.exit(1)

        extracted_dir = xmrig_bin.parent
        os.chmod(xmrig_bin, 0o755)

    # Clean previous install
    if XMRIG_DIR.exists():
        shutil.rmtree(XMRIG_DIR)

    shutil.move(str(extracted_dir), XMRIG_DIR)

    shutil.rmtree(TMP_DIR, ignore_errors=True)

    if not xmrig_binary().exists():
        log.error("XMRig installation incomplete.")
        sys.exit(1)

    log.info("XMRig installed successfully.")

# ============================================================
# TEMPERATURE MONITORING
# ============================================================

def max_cpu_temp():
    try:
        temps = psutil.sensors_temperatures()
        values = []
        for entries in temps.values():
            for e in entries:
                if e.current:
                    values.append(e.current)
        return max(values) if values else None
    except Exception:
        return None

# ============================================================
# MINER CONTROL
# ============================================================

def start_miner():
    total = psutil.cpu_count(logical=True)
    allowed = max(1, int(total * CPU_USAGE_PERCENT))

    cmd = [
        str(xmrig_binary()),
        "-o", POOL_ADDRESS,
        "-u", WALLET_ADDRESS,
        "-p", POOL_PASSWORD
    ]

    log.info(f"Starting miner using {allowed}/{total} CPU threads")
    proc = subprocess.Popen(cmd, stdout=sys.stdout, stderr=sys.stderr)
    p = psutil.Process(proc.pid)

    try:
        p.cpu_affinity(list(range(allowed)))
        if is_windows():
            p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
        else:
            p.nice(10)
    except Exception as e:
        log.warning(f"CPU control unavailable: {e}")

    return p

# ============================================================
# MAIN LOOP
# ============================================================

def main():
    ensure_xmrig()
    miner = start_miner()
    suspended = False

    def shutdown(*_):
        log.warning("Shutting down miner...")
        try:
            miner.kill()
        except Exception:
            pass
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    while True:
        temp = max_cpu_temp()

        if temp is None:
            if not hasattr(main, "_warned"):
                log.info("CPU temperature unavailable. Mining continues normally.")
                main._warned = True
            time.sleep(TEMP_CHECK_INTERVAL)
            continue


        log.info(f"CPU temperature: {temp:.1f}°C")

        if temp >= EMERGENCY_KILL_TEMP_C:
            log.critical("EMERGENCY temperature reached.")
            shutdown()

        if temp >= PAUSE_TEMP_C and not suspended:
            log.warning("High temp – suspending miner.")
            miner.suspend()
            suspended = True

        elif suspended and temp <= RESUME_TEMP_C:
            log.info("Temp safe – resuming miner.")
            miner.resume()
            suspended = False

        time.sleep(TEMP_CHECK_INTERVAL)

# ============================================================
if __name__ == "__main__":
    main()
