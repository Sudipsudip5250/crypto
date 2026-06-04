#!/usr/bin/env python3
# SAFE XMR MINER – LINUX (ARM / x86_64)

import os
import sys
import time
import subprocess
import signal
import logging
import shutil
from pathlib import Path
import psutil

# ================= USER CONFIG =================
WALLET_ADDRESS = "4B3WoA2P3fQNancXvdPVvnVcWZfeyC97dRj56pbq6RJdNGS39V4ME4WKHxn7e9KAFeJ87dNxgAdrP8dF5r8bFVxhPDS49gU"
POOL_ADDRESS = "pool.supportxmr.com:3333"
POOL_PASSWORD = "x"

CPU_USAGE_PERCENT = 0.70
PAUSE_TEMP_C = 80
RESUME_TEMP_C = 70
EMERGENCY_KILL_TEMP_C = 90
TEMP_CHECK_INTERVAL = 20
# ==============================================

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("miner-linux")


# ----------------- UTILITIES -----------------
def xmrig_bin():
    path = shutil.which("xmrig")
    if not path:
        log.error("xmrig not found. Install it with: sudo apt install xmrig")
        sys.exit(1)
    return path


def cpu_temp():
    try:
        if not hasattr(psutil, "sensors_temperatures"):
            return None
        temps = psutil.sensors_temperatures()
        if not temps:
            return None
        values = [e.current for entries in temps.values() for e in entries if e.current is not None and e.current > 0]
        return max(values) if values else None
    except Exception:
        return None


# ----------------- MINER CONTROL -----------------
def start_miner():
    total = psutil.cpu_count(logical=True)
    threads = max(1, int(total * CPU_USAGE_PERCENT))

    cmd = [
        xmrig_bin(),
        "-o", POOL_ADDRESS,
        "-u", WALLET_ADDRESS,
        "-p", POOL_PASSWORD,
        "--threads", str(threads),
        "--print-time", "10",
        "--randomx-mode=light",  # safer on ARM / low memory
        "--cpu-priority=2"
    ]

    p = subprocess.Popen(
        cmd,
        stdin=sys.stdin,
        stdout=sys.stdout,
        stderr=sys.stderr
    )

    proc = psutil.Process(p.pid)
    try:
        proc.nice(10)
    except Exception:
        pass

    return proc


# ----------------- MAIN LOOP -----------------
def main():
    miner = start_miner()
    log.info("Miner process PID: %s", miner.pid)
    suspended = False

    def shutdown(*_):
        log.info("Shutting down miner...")
        try:
            if miner.is_running():
                miner.kill()
        except psutil.NoSuchProcess:
            pass
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    while True:
        # Check if miner is alive
        if not miner.is_running():
            log.error("XMRig exited unexpectedly. Exiting controller.")
            sys.exit(1)

        # Check CPU temperature
        temp = cpu_temp()
        if temp is None:
            if not hasattr(main, "_warned"):
                log.warning(
                    "CPU temperature unavailable. Thermal protection disabled; using CPU limits only."
                )
                main._warned = True
            time.sleep(TEMP_CHECK_INTERVAL)
            continue

        log.info(f"CPU temp: {temp:.1f}°C")

        if temp >= EMERGENCY_KILL_TEMP_C:
            shutdown()
        elif temp >= PAUSE_TEMP_C and not suspended:
            miner.suspend()
            suspended = True
        elif suspended and temp <= RESUME_TEMP_C:
            miner.resume()
            suspended = False

        time.sleep(TEMP_CHECK_INTERVAL)


if __name__ == "__main__":
    main()
