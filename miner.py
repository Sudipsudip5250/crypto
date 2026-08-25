#!/usr/bin/env python3
"""
miner.py  —  XMR Miner Controller  (single entry point for all platforms)
==========================================================================
FOR EDUCATIONAL AND RESEARCH PURPOSES ONLY.
See DISCLAIMER.md and LICENSE for the full legal notice, including the
cloud-platform Terms of Service warning.

DO NOT run on AWS, GCP, Azure, DigitalOcean, Replit, Heroku, GitHub Actions,
or any other cloud / shared-hosting platform — it violates their ToS.

Usage
-----
    python miner.py [command] [options]

Commands
--------
    start        Start mining in the foreground  (default)
    bg           Start mining in the background (daemon)
    stop         Stop a background miner
    restart      Stop + start in the background
    status       Show running state + last 5 log lines
    logs         Tail the miner log in real time
    setup        Interactive config wizard
    info         Print OS / CPU / GPU detection
    version      Show cached + latest XMRig version
    update       Update XMRig to the latest release
    donate       Show donation info and wallet address
    donate-mode  Mine to project Monero wallet for N min (no config change)
    config       Open config.json in your editor
    install      Install / upgrade Python dependencies
    reset        Delete cached XMRig binary (re-downloaded on next start)
    check        Validate config and print a redacted command plan
    help         Show this message

Options (for donate-mode and update)
--------------------------------------
    --donate-time MINUTES   Minutes to mine in donate-mode  (default: 10)
    --force-update          Re-download XMRig even if up-to-date

Legacy flags (still accepted for backward compatibility)
---------------------------------------------------------
    --setup  --info  --update  --force-update  --version
    --donate  --donate-mode  --donate-time

Project layout
--------------
    miner.py            ← you are here
    config.json         ← all user settings
    core/
        config.py       — load / save / wizard for config.json
        daemon.py       — cross-platform bg / stop / status / logs / …
        logger.py       — logging setup
        requirements.py — auto-install missing pip packages
        updater.py      — XMRig version check and update
        download.py     — verified release downloads and safe extraction
    platforms/
        detect.py       — OS detection, routes to the right module
        linux.py        — Linux:   download static binary, PTY launch
        windows.py      — Windows: download zip binary, plain launch
        macos.py        — macOS:   download arm64/x64 binary, PTY launch
    hardware/
        cpu.py          — CPU info, thread count, affinity, XMRig cmd builder
        gpu.py          — GPU capability detection and reporting
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
import time

# ── project modules ─────────────────────────────────────────────────────────
from core.config  import COIN_PRESETS, load_config, run_setup, PROJECT_WALLET, set_config_path
from core.logger  import setup_logging, get_logger

from platforms.detect import get_platform_module, info as platform_info

from hardware.cpu import build_cmd, log_cpu_info
from hardware.gpu import log_gpu_info

from controller.process    import start_miner, stop_miner
from controller.thermal    import thermal_loop
from controller.duty_cycle import duty_cycle_loop


# ---------------------------------------------------------------------------
# Donation wallet (single source of truth — referenced by donate / donate-mode)
# ---------------------------------------------------------------------------

DONATE_WALLET = PROJECT_WALLET


# ---------------------------------------------------------------------------
# CLI argument parsing
# ---------------------------------------------------------------------------

_COMMANDS = [
    "start", "bg", "stop", "restart", "status", "logs",
    "setup", "info", "version", "update",
    "donate", "donate-mode",
    "config", "install", "reset", "check", "profiles", "tui", "help",
]

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="miner.py",
        description=(
            "XMRig Miner Controller — cross-platform configurable mining automation\n"
            "FOR EDUCATIONAL AND RESEARCH PURPOSES ONLY. See DISCLAIMER.md."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False,   # we handle 'help' as a command + keep -h
    )

    # ── Positional command (preferred style) ────────────────────────────────
    parser.add_argument(
        "command", nargs="?", default=None,
        metavar="COMMAND",
        help=f"One of: {', '.join(_COMMANDS)}",
    )
    parser.add_argument(
        "donate_minutes", nargs="?", type=int, default=None,
        metavar="MINUTES",
        help="Duration for donate-mode (only used with donate-mode)",
    )

    # ── Options ─────────────────────────────────────────────────────────────
    parser.add_argument("--donate-time", type=int, default=10, metavar="MINUTES",
                        help="Minutes to mine in donate-mode (default: 10)")
    parser.add_argument("--force-update", action="store_true",
                        help="Re-download XMRig even if already up-to-date")
    parser.add_argument("--config", default=None, metavar="PATH",
                        help="Use a separate local config file for this worker")

    # ── Legacy flags (hidden from help but still work) ───────────────────────
    for flag in ("--setup", "--info", "--update", "--version",
                 "--donate", "--donate-mode"):
        parser.add_argument(flag, action="store_true", help=argparse.SUPPRESS)

    # ── -h / --help ─────────────────────────────────────────────────────────
    parser.add_argument("-h", "--help", action="store_true", help=argparse.SUPPRESS)

    return parser.parse_args()


def _resolve_command(args: argparse.Namespace) -> str:
    """
    Return the canonical command string.

    Positional `command` takes priority; legacy --flags map to commands for
    backward compatibility.
    """
    if args.command:
        return args.command.lower()
    # Legacy flag resolution (first match wins)
    if getattr(args, "setup",        False): return "setup"
    if getattr(args, "info",         False): return "info"
    if getattr(args, "update",       False) or args.force_update: return "update"
    if getattr(args, "version",      False): return "version"
    if getattr(args, "donate",       False): return "donate"
    if getattr(args, "donate_mode",  False): return "donate-mode"
    if getattr(args, "help",         False): return "help"
    return "start"


# ---------------------------------------------------------------------------
# help
# ---------------------------------------------------------------------------

def print_help() -> None:
    print("""
\033[1mXMR Miner CLI\033[0m  —  for education and research purposes only

\033[1mUsage:\033[0m  python miner.py [command] [options]
        ./mine.sh  [command] [options]   (Linux / macOS)
        mine       [command] [options]   (Windows)

\033[1mCommands:\033[0m
  \033[36mstart\033[0m        Start mining in the foreground   (Ctrl+C to stop)
  \033[36mbg\033[0m           Start mining in the background   (daemon mode)
  \033[36mstop\033[0m         Stop a background miner
  \033[36mrestart\033[0m      Stop + start in the background
  \033[36mstatus\033[0m       Show running state + last 5 log lines
  \033[36mlogs\033[0m         Tail the miner log in real time  (Ctrl+C to exit)
  \033[36msetup\033[0m        Interactive config wizard
  \033[36minfo\033[0m         Print OS / CPU / GPU detection
  \033[36mversion\033[0m      Show cached + latest XMRig version
  \033[36mupdate\033[0m       Update XMRig to the latest release
  \033[36mdonate\033[0m       Show donation info and wallet address
  \033[36mdonate-mode\033[0m  Mine to project wallet for N min  (no config change)
  \033[36mconfig\033[0m       Open config.json in your editor
  \033[36minstall\033[0m      Install / upgrade Python dependencies
  \033[36mreset\033[0m        Delete cached XMRig binary  (re-downloaded on next start)
  \033[36mcheck\033[0m        Validate config and print the planned XMRig command
  \033[36mprofiles\033[0m     List supported profiles and backend constraints
  \033[36mtui\033[0m          Open the local terminal interface
  \033[36mhelp\033[0m         Show this message

\033[1mOptions:\033[0m
  --donate-time MINUTES   Duration for donate-mode  (default: 10)
  --force-update          Re-download XMRig even if up-to-date
  --config PATH            Use a separate local config file for this worker

\033[1mExamples:\033[0m
  python miner.py setup            configure wallet, pool, temp limits
  python miner.py bg               mine in background
  python miner.py logs             watch live output
  python miner.py donate-mode 30   donate 30 min of CPU
  python miner.py update           upgrade XMRig binary
  python miner.py stop             stop background miner

\033[1mLegal:\033[0m  See DISCLAIMER.md — do NOT run on cloud platforms.
""")


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
# check (configuration only; never starts mining)
# ---------------------------------------------------------------------------

def check_config() -> None:
    """Validate the local configuration and print a redacted command plan."""
    cfg = load_config()
    pinfo = platform_info()
    cmd = build_cmd("<xmrig>", cfg)
    redacted = list(cmd)
    try:
        redacted[redacted.index("--user") + 1] = "<wallet configured>"
        redacted[redacted.index("--pass") + 1] = "<pool password configured>"
    except (ValueError, IndexError):
        pass

    print("Configuration is valid.")
    print(f"  OS / architecture : {pinfo['os']} / {pinfo['arch']}")
    print(f"  Coin / algorithm  : {cfg.get('coin') or '(algorithm-only)'} / {cfg.get('algorithm') or '(coin alias)'}")
    print(f"  Backend           : {cfg.get('backend', 'cpu')}")
    print(f"  Pool              : {cfg['pool_address']}")
    print("  Planned command   : " + " ".join(redacted))


# ---------------------------------------------------------------------------
# profiles (read-only)
# ---------------------------------------------------------------------------

def print_profiles() -> None:
    print("\nSupported XMRig profiles")
    print("-------------------------")
    for name, preset in COIN_PRESETS.items():
        coin = str(preset["coin"]) or "(algorithm-only)"
        backends = ", ".join(str(value) for value in preset["backends"])
        print(f"  {name:<12} {str(preset['label']):<12} {str(preset['algorithm']):<14} {coin:<16} {backends}")
    print("  custom       User-defined XMRig coin alias or algorithm")
    print()


# ---------------------------------------------------------------------------
# donate (info only)
# ---------------------------------------------------------------------------

def print_donate_info() -> None:
    print()
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║              Support & Donate  —  XMR Miner                 ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()
    print("  Option 1 — Mine for the project (explicit Monero donation session)")
    print("  The normal config.json wallet is empty until you run setup.")
    print("  Run this command to donate CPU time without changing your config:")
    print()
    print("    python miner.py donate-mode                 donate 10 min (no config change)")
    print("    python miner.py donate-mode --donate-time 30  donate 30 min")
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
# donate-mode  (actually mines to the project wallet for N minutes)
# ---------------------------------------------------------------------------

def run_donate_mode(minutes: int) -> None:
    """Start XMRig pointed at the project wallet for *minutes* minutes.

    The user's config.json is never touched — we clone the loaded config dict
    and override wallet_address + worker_name in memory only.
    """
    import copy

    log = setup_logging(False)
    log.info("━━━  DONATE MODE  ━━━  mining to project wallet for %d minute(s)  ━━━", minutes)

    print()
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║          Donate Mode  —  Thank you!  ♥                      ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print(f"  Mining to project wallet for {minutes} minute(s).")
    print("  Your config.json is NOT changed.")
    print("  Press Ctrl+C at any time to stop early.")
    print()

    cfg = load_config(require_wallet=False)
    donate_cfg = copy.deepcopy(cfg)
    donate_cfg["coin"]               = "monero"
    donate_cfg["algorithm"]          = "rx/0"
    donate_cfg["backend"]            = "cpu"
    donate_cfg["wallet_address"]     = DONATE_WALLET
    donate_cfg["pool_address"]       = "pool.supportxmr.com:3333"
    donate_cfg["pool_password"]      = "x"
    donate_cfg["worker_name"]        = "donate"
    donate_cfg["duty_cycle_enabled"]  = False  # always continuous in donate mode
    donate_cfg["log_to_file"]         = False

    if cfg.get("duty_cycle_enabled"):
        print("  Note: duty-cycle is disabled for this donate session.")
        print("        Thermal protection (suspend/resume/kill) is still active.")
        print()

    platform_mod = get_platform_module()
    log_cpu_info()

    xmrig_bin = platform_mod.ensure_xmrig(
        donate_cfg["xmrig_version"], donate_cfg.get("xmrig_path", "")
    )
    log.info("XMRig binary: %s", xmrig_bin)

    stop_event = threading.Event()
    _proc_ref: list = []

    def shutdown(*_) -> None:
        log.info("Donate session interrupted — stopping miner …")
        stop_event.set()
        # Give start_miner up to 2 s to populate _proc_ref if racing
        for _ in range(20):
            if _proc_ref:
                break
            time.sleep(0.1)
        for p in _proc_ref:
            try:
                stop_miner(p)
            except Exception:
                pass
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, shutdown)

    # Timer thread: stop automatically after N minutes
    def _timer() -> None:
        stop_event.wait(timeout=minutes * 60)
        if not stop_event.is_set():
            log.info("Donate session complete (%d min) — stopping miner …", minutes)
            stop_event.set()
            for p in _proc_ref:
                try:
                    stop_miner(p)
                except Exception:
                    pass

    threading.Thread(target=_timer, daemon=True).start()

    proc, fwd_stop = start_miner(
        xmrig_path   = str(xmrig_bin),
        cfg          = donate_cfg,
        platform_mod = platform_mod,
        build_cmd_fn = build_cmd,
    )
    _proc_ref.append(proc)
    thermal_loop(proc, donate_cfg, stop_event)
    stop_miner(proc, fwd_stop)

    print()
    print("  Donate session finished. Thank you for supporting the project!")
    print(f"  Pool dashboard: https://supportxmr.com/#/dashboard?addr={DONATE_WALLET}")
    print()


# ---------------------------------------------------------------------------
# version
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
            print("→ Update available!  Run: python miner.py update")
        elif cached:
            print("→ You are up-to-date.")
    else:
        print("Could not reach GitHub — check your internet connection.")


# ---------------------------------------------------------------------------
# start — the actual mining loop
# ---------------------------------------------------------------------------

def _do_mine() -> None:
    """Load config and run the main mining loop (foreground)."""
    cfg = load_config()
    log = setup_logging(cfg["log_to_file"])

    log.info("━━━  XMR Miner Controller  ━━━  educational use only  ━━━")

    pinfo = platform_info()
    log.info("Platform: %s %s  |  Python %s", pinfo["os"], pinfo["arch"], pinfo["python"])

    platform_mod = get_platform_module()
    log_cpu_info()
    log_gpu_info()

    xmrig_bin = platform_mod.ensure_xmrig(
        cfg["xmrig_version"], cfg.get("xmrig_path", "")
    )
    log.info("XMRig binary: %s", xmrig_bin)

    stop_event = threading.Event()
    _proc_ref: list = []

    def shutdown(*_) -> None:
        log.info("Shutdown signal received — stopping miner …")
        stop_event.set()
        # Wait briefly for _proc_ref to be populated if signal races start_miner
        for _ in range(20):
            if _proc_ref:
                break
            time.sleep(0.1)
        for p in _proc_ref:
            try:
                stop_miner(p)
            except Exception:
                pass
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, shutdown)

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


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()
    if args.config:
        set_config_path(args.config)
    cmd  = _resolve_command(args)

    # ── Commands that delegate to core/daemon.py ────────────────────────────
    if cmd == "bg":
        from core.daemon import cmd_bg;       cmd_bg();      return
    if cmd == "stop":
        from core.daemon import cmd_stop;     cmd_stop();    return
    if cmd == "restart":
        from core.daemon import cmd_restart;  cmd_restart(); return
    if cmd == "status":
        from core.daemon import cmd_status;   cmd_status();  return
    if cmd == "logs":
        from core.daemon import cmd_logs;     cmd_logs();    return
    if cmd == "config":
        from core.daemon import cmd_config;   cmd_config();  return
    if cmd == "install":
        from core.daemon import cmd_install;  cmd_install(); return
    if cmd == "reset":
        from core.daemon import cmd_reset;    cmd_reset();   return

    # ── Informational commands ───────────────────────────────────────────────
    if cmd in ("help", "-h", "--help"):
        print_help(); return
    if cmd == "check":
        check_config(); return
    if cmd == "profiles":
        print_profiles(); return
    if cmd == "tui":
        from tui import run_tui
        run_tui(); return
    if cmd == "donate":
        print_donate_info(); return
    if cmd == "info":
        print_system_info(); return
    if cmd == "version":
        print_xmrig_version(); return

    # ── donate-mode — also accept minutes as a bare positional after command ─
    # e.g. "python miner.py donate-mode 30"  or  "./mine.sh donate-mode 30"
    if cmd == "donate-mode":
        minutes = args.donate_minutes if args.donate_minutes is not None else args.donate_time
        if not 1 <= minutes <= 1440:
            print("[miner] donate-mode duration must be between 1 and 1440 minutes.", file=sys.stderr)
            sys.exit(2)
        run_donate_mode(minutes)
        return

    # ── setup ────────────────────────────────────────────────────────────────
    if cmd == "setup":
        run_setup(); return

    # ── update ───────────────────────────────────────────────────────────────
    if cmd == "update":
        cfg = load_config()
        setup_logging(cfg["log_to_file"])
        from core.updater import update_xmrig
        update_xmrig(cfg, force=args.force_update)
        return

    # ── start (default) ──────────────────────────────────────────────────────
    if cmd in ("start", ""):
        _do_mine()
        return

    # Unknown command
    print(f"[miner] Unknown command: '{cmd}'")
    print("        Run  python miner.py help  to see all commands.")
    sys.exit(1)


if __name__ == "__main__":
    main()
