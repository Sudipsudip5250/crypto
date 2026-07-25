"""
controller/duty_cycle.py
------------------------
Duty-cycle controller: alternate between mining and resting on a fixed schedule.

Flow per cycle
--------------
  1. Start XMRig via the platform module
  2. Mine for `mine_duration_min` minutes (polling temp every interval)
  3. Stop XMRig gracefully
  4. Rest for `rest_duration_min` minutes
  5. Repeat until stop_event is set

For educational and research purposes only — see DISCLAIMER.md.
"""
# ── Educational / research use only ─────────────────────────────────────────
# See DISCLAIMER.md and LICENSE for full legal notices.
# ────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import logging
import subprocess
import time

from controller.thermal import cpu_temp

log = logging.getLogger("xmr-miner")


def duty_cycle_loop(
    xmrig_path: str,
    cfg: dict,
    platform_mod,    # platforms.linux / platforms.windows / platforms.macos
    build_cmd_fn,    # hardware.cpu.build_cmd
    stop_event,      # threading.Event
) -> None:
    """
    Run the mine → rest duty cycle until stop_event is set.

    Parameters
    ----------
    xmrig_path   : str          path to xmrig binary
    cfg          : dict         loaded config
    platform_mod :              platform module (has launch_process())
    build_cmd_fn :              callable(xmrig_path, cfg) → list[str]
    stop_event   : Event        set externally to stop the loop
    """
    mine_sec = cfg["mine_duration_min"] * 60
    rest_sec = cfg["rest_duration_min"] * 60
    interval = cfg["temp_check_interval_sec"]
    kill_t   = cfg["emergency_kill_temp_c"]
    cycle    = 1

    while not stop_event.is_set():
        log.info(
            "━━━  Cycle %d  — mining for %d min  ━━━",
            cycle, cfg["mine_duration_min"],
        )

        cmd  = build_cmd_fn(xmrig_path, cfg)
        proc, fwd_stop = platform_mod.launch_process(cmd)

        mine_end = time.monotonic() + mine_sec
        while time.monotonic() < mine_end and not stop_event.is_set():
            if proc.poll() is not None:
                log.error("XMRig crashed during cycle %d (code=%s).", cycle, proc.returncode)
                break

            temp = cpu_temp()
            if temp is not None:
                log.info("CPU temp: %.1f°C", temp)
                if temp >= kill_t:
                    log.critical("EMERGENCY temp %.1f°C — stopping duty cycle!", temp)
                    try:
                        proc.kill()
                    except Exception:
                        pass
                    fwd_stop.set()
                    stop_event.set()
                    return

            remaining = int(mine_end - time.monotonic())
            log.debug("Mining … %d s remaining in cycle %d", remaining, cycle)
            time.sleep(interval)

        # ── stop miner ──────────────────────────────────────────────────────
        fwd_stop.set()
        if proc.poll() is None:
            log.info("Stopping miner after cycle %d …", cycle)
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                log.warning("XMRig did not stop in 10 s — force-killing …")
                try:
                    proc.kill()
                    proc.wait(timeout=5)
                except (subprocess.TimeoutExpired, OSError):
                    pass

        if stop_event.is_set():
            return

        # ── rest ────────────────────────────────────────────────────────────
        log.info(
            "Cycle %d done. Resting for %d min …",
            cycle, cfg["rest_duration_min"],
        )
        rest_end = time.monotonic() + rest_sec
        while time.monotonic() < rest_end and not stop_event.is_set():
            time.sleep(5)

        cycle += 1
