#! python3
# SAFE XMR MINER – WINDOWS

import sys, time, subprocess, signal, logging, shutil
from pathlib import Path
import psutil, platform, urllib.request, zipfile

# ================= USER CONFIG =================
WALLET_ADDRESS = "4B3WoA2P3fQNancXvdPVvnVcWZfeyC97dRj56pbq6RJdNGS39V4ME4WKHxn7e9KAFeJ87dNxgAdrP8dF5r8bFVxhPDS49gU"
POOL_ADDRESS = "pool.supportxmr.com:3333"
POOL_PASSWORD = "x"

CPU_USAGE_PERCENT = 0.70
PAUSE_TEMP_C = 80
RESUME_TEMP_C = 70
EMERGENCY_KILL_TEMP_C = 90
TEMP_CHECK_INTERVAL = 20
XMRIG_VERSION = "6.22.0"
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
log = logging.getLogger("miner-win")

def xmrig_bin():
    return XMRIG_DIR / "xmrig.exe"

def ensure_xmrig():
    if xmrig_bin().exists():
        return

    TOOLS.mkdir(exist_ok=True)
    tmp = TOOLS / "_tmp"
    tmp.mkdir(exist_ok=True)

    url = f"https://github.com/xmrig/xmrig/releases/download/v{XMRIG_VERSION}/xmrig-{XMRIG_VERSION}-msvc-win64.zip"
    archive = tmp / "xmrig.zip"

    log.info("Downloading XMRig (Windows)")
    urllib.request.urlretrieve(url, archive)

    with zipfile.ZipFile(archive) as z:
        z.extractall(tmp)

    exe = next(tmp.rglob("xmrig.exe"), None)
    if not exe:
        sys.exit("xmrig.exe not found")

    if XMRIG_DIR.exists():
        shutil.rmtree(XMRIG_DIR)

    shutil.move(str(exe.parent), XMRIG_DIR)
    shutil.rmtree(tmp)

def cpu_temp():
    if not hasattr(psutil, "sensors_temperatures"):
        return None

    try:
        temps = psutil.sensors_temperatures()
        if not temps:
            return None

        values = []
        for entries in temps.values():
            for e in entries:
                if e.current is not None:
                    values.append(e.current)

        return max(values) if values else None
    except Exception:
        return None


def start_miner():
    total = psutil.cpu_count()
    threads = max(1, int(total * CPU_USAGE_PERCENT))

    cmd = [
        str(xmrig_bin()),
        "-o", POOL_ADDRESS,
        "-u", WALLET_ADDRESS,
        "-p", POOL_PASSWORD
    ]

    p = subprocess.Popen(cmd)
    proc = psutil.Process(p.pid)
    proc.cpu_affinity(list(range(threads)))
    proc.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    return proc

def main():
    ensure_xmrig()
    miner = start_miner()
    suspended = False

    def shutdown(*_):
        miner.kill()
        sys.exit()

    signal.signal(signal.SIGINT, shutdown)

    while True:
        temp = cpu_temp()
        if temp is None:
            if not hasattr(main, "_warned"):
                log.warning(
                    "CPU temperature unavailable on this system. "
                    "Thermal throttling disabled."
                )
                main._warned = True

            time.sleep(TEMP_CHECK_INTERVAL)
            continue

        log.info(f"CPU temp: {temp:.1f}°C")

        if temp >= EMERGENCY_KILL_TEMP_C:
            shutdown()
        elif temp >= PAUSE_TEMP_C and not suspended:
            miner.suspend(); suspended = True
        elif suspended and temp <= RESUME_TEMP_C:
            miner.resume(); suspended = False

        time.sleep(TEMP_CHECK_INTERVAL)

if __name__ == "__main__":
    main()
