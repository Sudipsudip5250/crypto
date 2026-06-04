"""
hardware/cpu.py
---------------
CPU-related utilities:
  • Detect CPU info (model, core count, architecture)
  • Calculate safe thread count from config
  • Set process affinity and niceness / priority class
  • Build the XMRig command-line arguments for CPU mining
"""

from __future__ import annotations

import logging
import os
import platform
import subprocess
from pathlib import Path

log = logging.getLogger("xmr-miner")

try:
    import psutil as _psutil
except ImportError:
    _psutil = None  # type: ignore

IS_WINDOWS = platform.system().lower().startswith("win")
IS_LINUX   = platform.system().lower().startswith("linux")
IS_MACOS   = platform.system().lower().startswith("darwin")


# ---------------------------------------------------------------------------
# CPU information
# ---------------------------------------------------------------------------

def get_cpu_info() -> dict:
    """Return a dict with basic CPU information."""
    logical  = (_psutil.cpu_count(logical=True)  if _psutil else None) or os.cpu_count() or 1
    physical = (_psutil.cpu_count(logical=False) if _psutil else None) or logical

    model = "Unknown"
    try:
        if IS_LINUX:
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if line.startswith("model name"):
                        model = line.split(":", 1)[1].strip()
                        break
        elif IS_MACOS:
            out = subprocess.check_output(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                text=True, stderr=subprocess.DEVNULL,
            )
            model = out.strip()
        elif IS_WINDOWS:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"HARDWARE\DESCRIPTION\System\CentralProcessor\0",
            )
            model = winreg.QueryValueEx(key, "ProcessorNameString")[0].strip()
    except Exception:
        pass

    return {
        "model":    model,
        "logical":  logical,
        "physical": physical,
        "arch":     platform.machine(),
    }


def log_cpu_info() -> dict:
    """Log detected CPU info and return the info dict."""
    info = get_cpu_info()
    log.info(
        "CPU  %s  |  %d logical / %d physical cores  |  arch: %s",
        info["model"], info["logical"], info["physical"], info["arch"],
    )
    return info


# ---------------------------------------------------------------------------
# Thread calculation
# ---------------------------------------------------------------------------

def calculate_threads(cpu_usage_percent: float) -> int:
    """Return how many CPU threads XMRig should use."""
    total = get_cpu_info()["logical"]
    threads = max(1, min(total, int(total * cpu_usage_percent)))
    return threads


# ---------------------------------------------------------------------------
# Process affinity and priority
# ---------------------------------------------------------------------------

def set_affinity_and_priority(pid: int, threads: int, cpu_priority: int) -> None:
    """
    Pin the process to `threads` CPU cores and set its scheduling priority.

    On Linux/macOS: uses nice values (10 = low priority).
    On Windows: uses BELOW_NORMAL or NORMAL priority class + cpu_affinity.
    """
    if _psutil is None:
        log.debug("psutil not available — skipping affinity/priority setup")
        return

    try:
        proc  = _psutil.Process(pid)
        total = get_cpu_info()["logical"]
        cores = list(range(min(threads, total)))

        if hasattr(proc, "cpu_affinity"):
            proc.cpu_affinity(cores)
            log.info("CPU affinity → cores %s", cores)

        if IS_WINDOWS:
            nice = (
                _psutil.BELOW_NORMAL_PRIORITY_CLASS
                if cpu_priority <= 2
                else _psutil.NORMAL_PRIORITY_CLASS
            )
        else:
            # Linux/macOS nice value: higher number = lower priority
            # cpu_priority 0→19, 5→0 (invert and scale)
            nice = max(0, 19 - int(cpu_priority * 3.8))

        proc.nice(nice)
        log.info("Process priority set (nice=%s)", nice)

    except Exception as exc:
        log.warning("Could not set affinity/priority: %s", exc)


# ---------------------------------------------------------------------------
# XMRig command-line builder
# ---------------------------------------------------------------------------

def build_cmd(xmrig_path: str | Path, cfg: dict) -> list[str]:
    """
    Build the XMRig command-line argument list from the loaded config.

    The command is the same on all platforms; platform-specific flags
    (like --randomx-mode) are added only where supported.
    """
    threads = calculate_threads(cfg["cpu_usage_percent"])

    cmd: list[str] = [
        str(xmrig_path),
        "--url",        cfg["pool_address"],
        "--user",       cfg["wallet_address"],
        "--pass",       cfg["pool_password"],
        "--rig-id",     cfg["worker_name"],
        "--print-time", "10",
        f"--cpu-priority={cfg['cpu_priority']}",
    ]

    # Thread and RandomX flags — XMRig on Windows picks threads automatically
    # so we only pass them explicitly on Linux/macOS
    if IS_LINUX or IS_MACOS:
        cmd += [
            "--threads",       str(threads),
            f"--randomx-mode={cfg['randomx_mode']}",
        ]

    log.info(
        "XMRig command: threads=%d  randomx=%s  priority=%d",
        threads, cfg["randomx_mode"], cfg["cpu_priority"],
    )
    return cmd
