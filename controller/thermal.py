"""
controller/thermal.py
---------------------
CPU temperature monitoring.

Provides:
  • cpu_temp()       — read current peak CPU temperature (°C)
  • thermal_loop()   — background loop that suspends/resumes/kills the miner
                       based on temperature thresholds in config
"""

from __future__ import annotations

import logging
import re
import subprocess
import time

log = logging.getLogger("xmr-miner")

try:
    import psutil as _psutil
except ImportError:
    _psutil = None  # type: ignore


# ---------------------------------------------------------------------------
# Temperature reading
# ---------------------------------------------------------------------------

def _read_psutil() -> float | None:
    """Read max CPU temperature via psutil.sensors_temperatures()."""
    try:
        if _psutil and hasattr(_psutil, "sensors_temperatures"):
            sensors = _psutil.sensors_temperatures()
            if sensors:
                values = [
                    e.current
                    for entries in sensors.values()
                    for e in entries
                    if getattr(e, "current", None) and e.current > 0
                ]
                if values:
                    return max(values)
    except Exception:
        pass
    return None


def _read_lm_sensors() -> float | None:
    """Read max CPU temperature via the `sensors` command (lm-sensors, Linux)."""
    try:
        out = subprocess.check_output(
            ["sensors"], stderr=subprocess.DEVNULL, text=True, timeout=5
        )
        nums = [float(n) for n in re.findall(r"([-+]?\d+\.?\d*)°C", out)]
        if nums:
            return max(nums)
    except Exception:
        pass
    return None


def _read_sysfs() -> float | None:
    """Read max CPU temperature from Linux /sys thermal zones (fallback)."""
    try:
        import glob as _glob
        values = []
        for path in _glob.glob("/sys/class/thermal/thermal_zone*/temp"):
            with open(path) as f:
                raw = f.read().strip()
            temp = int(raw) / 1000.0   # millidegrees → degrees
            if temp > 0:
                values.append(temp)
        if values:
            return max(values)
    except Exception:
        pass
    return None


def cpu_temp() -> float | None:
    """
    Return the peak CPU temperature in °C, or None if all methods fail.

    Tries (in order):
      1. psutil.sensors_temperatures()
      2. `sensors` command  (lm-sensors, Linux)
      3. /sys/class/thermal/thermal_zone*/temp  (Linux sysfs)
    """
    return _read_psutil() or _read_lm_sensors() or _read_sysfs()


# ---------------------------------------------------------------------------
# Thermal control loop
# ---------------------------------------------------------------------------

def thermal_loop(
    proc,          # subprocess.Popen
    cfg: dict,
    stop_event,    # threading.Event
) -> None:
    """
    Monitor temperature every `temp_check_interval_sec` seconds.

    Behaviour
    ---------
    temp >= emergency_kill_temp_c  → kill miner immediately, set stop_event
    temp >= pause_temp_c           → suspend (SIGSTOP) the miner
    temp <= resume_temp_c          → resume (SIGCONT) the miner
    miner exited unexpectedly      → log error, set stop_event
    """
    pause_t  = cfg["pause_temp_c"]
    resume_t = cfg["resume_temp_c"]
    kill_t   = cfg["emergency_kill_temp_c"]
    interval = cfg["temp_check_interval_sec"]

    ps_proc   = None
    suspended = False
    warned    = False   # warn once if no temperature source available

    if _psutil:
        try:
            ps_proc = _psutil.Process(proc.pid)
        except Exception:
            pass

    while not stop_event.is_set():
        # ── health check ────────────────────────────────────────────────────
        if proc.poll() is not None:
            log.error("XMRig exited unexpectedly (code=%s).", proc.returncode)
            stop_event.set()
            return

        # ── temperature ─────────────────────────────────────────────────────
        temp = cpu_temp()

        if temp is None:
            if not warned:
                log.warning(
                    "CPU temperature unavailable — thermal protection disabled.\n"
                    "  Linux: install lm-sensors → sudo sensors-detect\n"
                    "  macOS:  temperature reading via psutil (usually works)\n"
                    "  Windows: temperature requires psutil + WMI permissions"
                )
                warned = True
            time.sleep(interval)
            continue

        log.info("CPU temp: %.1f°C", temp)

        # ── emergency kill ───────────────────────────────────────────────────
        if temp >= kill_t:
            log.critical(
                "EMERGENCY: %.1f°C >= %d°C — killing miner NOW!", temp, kill_t
            )
            try:
                proc.kill()
            except Exception:
                pass
            stop_event.set()
            return

        # ── suspend / resume (requires psutil) ──────────────────────────────
        if ps_proc:
            if temp >= pause_t and not suspended:
                try:
                    ps_proc.suspend()
                    suspended = True
                    log.warning(
                        "Miner SUSPENDED (%.1f°C >= %d°C). "
                        "Will resume below %d°C.",
                        temp, pause_t, resume_t,
                    )
                except Exception as exc:
                    log.warning("Could not suspend miner: %s", exc)

            elif suspended and temp <= resume_t:
                try:
                    ps_proc.resume()
                    suspended = False
                    log.info(
                        "Miner RESUMED (%.1f°C <= %d°C).", temp, resume_t
                    )
                except Exception as exc:
                    log.warning("Could not resume miner: %s", exc)

        time.sleep(interval)
