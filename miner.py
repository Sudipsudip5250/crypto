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
    python miner.py --update     # update XMRig to the latest release
    python miner.py --version    # show cached XMRig version and exit
    python miner.py --donate     # show donation info (wallet address etc.)

Press Ctrl+C to stop the miner at any time.

Project layout
--------------
    miner.py            ← you are here
    config.json         ← all user settings
    core/
        config.py       — load / save / wizard for config.json
        logger.py       — logging setup
        requirements.py — auto-install missing pip packages
        updater.py      — XMRig version check and download
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
            "  python miner.py              mine using config.json\n"
            "  python miner.py --setup      interactive config wizard\n"
            "  python miner.py --info       show system info and exit\n"
            "  python miner.py --update     update XMRig to latest release\n"
            "  python miner.py --version    show cached XMRig version\n"
        ),
    )
    parser.add_argument("--setup",   action="store_true",
                        help="Run the interactive config wizard")
    parser.add_argument("--info",    action="store_true",
                        help="Detect and print system info then exit")
    parser.add_argument("--update",  action="store_true",
                        help="Update XMRig to the latest GitHub release")
    parser.add_argument("--force-update", action="store_true",
                        help="Re-download XMRig even if already up-to-date")
    parser.add_argument("--version", action="store_true",
                        help="Show the cached XMRig version and exit")
    parser.add_argument("--donate", action="store_true",
                        help="Show donation info (wallet address, pool dashboard) and exit")
    return parser.parse_args()


# ---------------------------------------------------------------------------
# --info mode
# ---------------------------------------------------------------------------

def print_system_info() -> None:
    pinfo = platform_info()
    print("\n── Platform ──────────────────────────────────")
    for k, v in pinfo.items():
        print(f"  {k:<14} {v}")

    from hardware.cpu import get_cpu_info
    cinfo = get_cpu_info()
    print("\n── CPU ───────────────────────────────────────")
    for k, v in cinfo.items():
        print(f"  {k:<14} {v}")

    from hardware.gpu import detect_gpu
    ginfo = detect_gpu()
    print("\n── GPU ───────────────────────────────────────")
    for k, v in ginfo.items():
        if k != "details":
            print(f"  {k:<14} {v}")
    print()


# ---------------------------------------------------------------------------
# --donate mode
# ---------------------------------------------------------------------------

DONATE_WALLET = (
    "4B3WoA2P3fQNancXvdPVvnVcWZfeyC97dRj56pbq6RJdNGS39V4ME4WKHxn7e9KAFeJ87dNxgAdrP8dF5r8bFVxhPDS49gU"
)

def print_donate_info() -> None:
    print()
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║              Support & Donate  —  XMR Miner                 ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()
    print("  Option 1 — Mine for the project (donate CPU time)")
    print("  The default config.json already points to the project wallet.")
    print("  Leave wallet_address unchanged and run:")
    print()
    print("    python miner.py               mine in foreground")
    print("    python miner.py --donate      (you are here — info only)")
    print()
    print("  Option 2 — Send XMR directly")
    print("  Monero (XMR) wallet address:")
    print()
    print(f"    {DONATE_WALLET}")
    print()
    print("  Pool dashboard — verify mining donations in real time:")
    print(f"    https://supportxmr.com/#/dashboard?addr={DONATE_WALLET}")
    print()
    print("  See DONATE.md for full details.")
    print()


# ---------------------------------------------------------------------------
# --version mode
# ---------------------------------------------------------------------------

def print_xmrig_version() -> None:
    from core.updater import get_cached_version, get_latest_version
    cached = get_cached_version()
    if cached:
        print(f"Cached XMRig version : v{cached}")
    else:
        print("XMRig not yet downloaded. Run: python miner.py  to auto-download.")

    print("Checking GitHub for latest release …")
    latest = get_latest_version()
    if latest:
        print(f"Latest XMRig version : v{latest}")
        if cached and latest != cached:
            print(f"→ Update available!  Run: python miner.py --update")
        elif cached:
            print("→ You are up-to-date.")
    else:
        print("Could not reach GitHub — check your internet connection.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()

    # ── --donate ────────────────────────────────────────────────────────────
    if args.donate:
        print_donate_info()
        return

    # ── --setup ─────────────────────────────────────────────────────────────
    if args.setup:
        run_setup()
        return

    # ── --info ──────────────────────────────────────────────────────────────
    if args.info:
        print_system_info()
        return

    # ── --version ───────────────────────────────────────────────────────────
    if args.version:
        print_xmrig_version()
        return

    # ── --update / --force-update ────────────────────────────────────────────
    if args.update or args.force_update:
        cfg = load_config()
        log = setup_logging(cfg["log_to_file"])
        from core.updater import update_xmrig
        update_xmrig(cfg, force=args.force_update)
        return

    # ── load config ─────────────────────────────────────────────────────────
    cfg = load_config()
    log = setup_logging(cfg["log_to_file"])

    log.info("━━━  XMR Miner Controller  ━━━  for education purposes only  ━━━")

    # ── OS detection ────────────────────────────────────────────────────────
    pinfo = platform_info()
    log.info("Platform: %s %s  |  Python %s", pinfo["os"], pinfo["arch"], pinfo["python"])

    platform_mod = get_platform_module()

    # ── hardware info ───────────────────────────────────────────────────────
    log_cpu_info()
    log_gpu_info()

    # ── get xmrig binary ────────────────────────────────────────────────────
    xmrig_bin = platform_mod.ensure_xmrig(cfg["xmrig_version"])
    log.info("XMRig binary: %s", xmrig_bin)

    # ── signal handling ──────────────────────────────────────────────────────
    stop_event = threading.Event()
    _proc_ref: list = []

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
        thermal_loop(proc, cfg, stop_event)
        stop_miner(proc, fwd_stop)


if __name__ == "__main__":
    main()
