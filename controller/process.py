"""
controller/process.py
---------------------
XMRig process lifecycle management.

Provides a thin wrapper around the platform-specific launch_process() so that
miner.py and duty_cycle.py don't need to import platform modules directly.

Functions
---------
start_miner(xmrig_path, cfg, platform_mod, build_cmd_fn)
    → (subprocess.Popen, threading.Event)

stop_miner(proc, fwd_stop, timeout)
    Terminate XMRig gracefully, then forcefully if needed.

is_alive(proc)
    True if the process is still running.
"""

from __future__ import annotations

import logging
import subprocess
import threading

log = logging.getLogger("xmr-miner")


def start_miner(
    xmrig_path: str,
    cfg: dict,
    platform_mod,    # platforms.linux / platforms.windows / platforms.macos
    build_cmd_fn,    # hardware.cpu.build_cmd
) -> tuple[subprocess.Popen, threading.Event]:
    """
    Build the XMRig command, launch it via the platform module, and set
    process affinity / priority.

    Returns
    -------
    proc       : subprocess.Popen
    fwd_stop   : threading.Event  (set to stop the PTY-forward thread)
    """
    from hardware.cpu import set_affinity_and_priority, calculate_threads

    cmd = build_cmd_fn(xmrig_path, cfg)
    log.info("Launching XMRig …")

    proc, fwd_stop = platform_mod.launch_process(cmd)
    log.info("XMRig running (pid=%d)", proc.pid)

    threads = calculate_threads(cfg["cpu_usage_percent"])
    set_affinity_and_priority(proc.pid, threads, cfg["cpu_priority"])

    return proc, fwd_stop


def stop_miner(
    proc: subprocess.Popen,
    fwd_stop: threading.Event | None = None,
    timeout: int = 10,
) -> None:
    """
    Gracefully terminate XMRig.

    1. Set the PTY forward-thread stop event (if provided).
    2. Send SIGTERM and wait up to `timeout` seconds.
    3. Send SIGKILL if still alive.
    """
    if fwd_stop is not None:
        fwd_stop.set()

    if proc.poll() is not None:
        return  # already exited

    log.info("Stopping XMRig (pid=%d) …", proc.pid)
    proc.terminate()
    try:
        proc.wait(timeout=timeout)
        log.info("XMRig stopped.")
    except subprocess.TimeoutExpired:
        log.warning("XMRig did not stop within %ds — sending SIGKILL", timeout)
        proc.kill()
        proc.wait()


def is_alive(proc: subprocess.Popen) -> bool:
    """Return True if the process is still running."""
    return proc.poll() is None
