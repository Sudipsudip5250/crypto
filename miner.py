#!/usr/bin/env python3
"""
miner.py  —  XMR Miner Controller  (entry point)
=================================================
Single entry point for all platforms: Linux, Windows, macOS.
For education and research purposes only.

Usage
-----
    python miner.py              # start mining  (reads config.json)
    python miner.py --setup      # interactive config wizard
    python miner.py --info       # print system info and exit

Press Ctrl+C to stop the miner at any time.

Project layout
--------------
    miner.py            ← you are here
    config.json         ← all user settings
    core/
        config.py       — load / save / wizard for config.json
        logger.py       — logging setup
        requirements.py — auto-install missing pip packages
    platforms/
        detect.py       — OS detection, routes to the right module
        linux.py        — Linux:   download static binary, PTY launch
        windows.py      — Windows: download zip binary, plain launch
        macos.py        — macOS:   download arm64/x64 binary, PTY launch
    hardware/
        cpu.py          — CPU info, thread count, affinity, XMRig cmd builder
        gpu.py          — GPU detection (OpenCL / CUDA stubs for future use)
    controller/
        process.py      — start / stop / health-check XMRig
        thermal.py      — temperature monitoring, suspend / resume / kill
        duty_cycle.py   — timed mine-N-min → rest-M-min cycles
"""

# ── Step 1: check and auto-install required packages ────────────────────────
# This must happen before any module that imports psutil / keyboard.
from core.requirements import check_and_install
check_and_install()

# ── stdlib ──────────────────────────────────────────────────────────────────
import argparse
import signal
import sys
import threading

# ── project modules ─────────────────────────────────────────────────────────
from core.config  import load_config, run_setup
from core.logger  import setup_logging, get_logger

from platforms.detect import get_platform_module, info as platform_info

from hardware.cpu import build_cmd, log_cpu_info
from hardware.gpu import log_gpu_info

from controller.process    import start_miner, stop_miner
from controller.thermal    import thermal_loop
from controller.duty_cycle import duty_cycle_loop


# ---------------------------------------------------------------------------
# CLI argument parsing
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="miner.py",
        description="XMR Miner Controller — cross-platform Monero mining automation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python miner.py            # mine using config.json\n"
            "  python miner.py --setup    # interactive config wizard\n"
            "  python miner.py --info     # show system info and exit\n"
        ),
    )
    parser.add_argument(
        "--setup", action="store_true",
        help="Run the interactive config wizard to create/update config.json",
    )
    parser.add_argument(
        "--info", action="store_true",
        help="Detect and print system info (OS, CPU, GPU) then exit",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# System info (--info mode)
# ---------------------------------------------------------------------------

def print_system_info() -> None:
    # Logging not yet configured here, use print
    pinfo = platform_info()
    print("\n── Platform ──────────────────────────────────")
    for k, v in pinfo.items():
        print(f"  {k:<12} {v}")

    from hardware.cpu import get_cpu_info
    cinfo = get_cpu_info()
    print("\n── CPU ───────────────────────────────────────")
    for k, v in cinfo.items():
        print(f"  {k:<12} {v}")

    from hardware.gpu import detect_gpu
    ginfo = detect_gpu()
    print("\n── GPU ───────────────────────────────────────")
    for k, v in ginfo.items():
        if k != "details":
            print(f"  {k:<12} {v}")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()

    # ── --setup ─────────────────────────────────────────────────────────────
    if args.setup:
        run_setup()
        return

    # ── --info ──────────────────────────────────────────────────────────────
    if args.info:
        print_system_info()
        return

    # ── load config ─────────────────────────────────────────────────────────
    cfg = load_config()
    log = setup_logging(cfg["log_to_file"])

    log.info("━━━  XMR Miner Controller  ━━━  for education purposes only  ━━━")

    # ── OS detection ────────────────────────────────────────────────────────
    pinfo = platform_info()
    log.info("Platform: %s %s  |  Python %s", pinfo["os"], pinfo["arch"], pinfo["python"])

    platform_mod = get_platform_module()   # linux / windows / macos

    # ── hardware info ───────────────────────────────────────────────────────
    log_cpu_info()
    log_gpu_info()

    # ── get xmrig binary ────────────────────────────────────────────────────
    xmrig_bin = platform_mod.ensure_xmrig(cfg["xmrig_version"])
    log.info("XMRig binary: %s", xmrig_bin)

    # ── signal handling (Ctrl+C / SIGTERM) ──────────────────────────────────
    stop_event = threading.Event()
    _proc_ref: list = []   # mutable container so closure can mutate it

    def shutdown(*_) -> None:
        log.info("Shutdown signal received — stopping miner …")
        stop_event.set()
        if _proc_ref:
            stop_miner(_proc_ref[0])
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, shutdown)

    # ── start mining ─────────────────────────────────────────────────────────
    if cfg["duty_cycle_enabled"]:
        log.info(
            "Mode: DUTY CYCLE — mine %d min / rest %d min",
            cfg["mine_duration_min"], cfg["rest_duration_min"],
        )
        duty_cycle_loop(
            xmrig_path   = str(xmrig_bin),
            cfg          = cfg,
            platform_mod = platform_mod,
            build_cmd_fn = build_cmd,
            stop_event   = stop_event,
        )
    else:
        log.info(
            "Mode: CONTINUOUS — pool=%s  worker=%s",
            cfg["pool_address"], cfg["worker_name"],
        )
        proc, fwd_stop = start_miner(
            xmrig_path   = str(xmrig_bin),
            cfg          = cfg,
            platform_mod = platform_mod,
            build_cmd_fn = build_cmd,
        )
        _proc_ref.append(proc)

        # thermal_loop blocks until miner exits or stop_event is set
        thermal_loop(proc, cfg, stop_event)

        stop_miner(proc, fwd_stop)


if __name__ == "__main__":
    main()
