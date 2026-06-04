#!/usr/bin/env python3
"""
XMR Miner Controller — Cross-platform (Linux · Windows · macOS)

For education and research purposes only.
Run on hardware you own or have explicit permission to use.

Usage:
    python miner.py              # start mining (reads config.json)
    python miner.py --setup      # interactively set up config.json

Controls while running:
    Ctrl+C   — graceful shutdown
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import platform
import re
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import urllib.request
import zipfile
from pathlib import Path

# ---------------------------------------------------------------------------
# PATHS
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
TOOLS_DIR = BASE_DIR / "tools"
XMRIG_DIR = TOOLS_DIR / "xmrig"
LOG_DIR = BASE_DIR / "logs"
CONFIG_PATH = BASE_DIR / "config.json"

LOG_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# DEFAULTS (used when key is missing from config.json)
# ---------------------------------------------------------------------------

DEFAULTS: dict = {
    "wallet_address": "",
    "worker_name": "myrig",
    "pool_address": "pool.supportxmr.com:3333",
    "pool_password": "x",
    "cpu_usage_percent": 0.70,
    "randomx_mode": "auto",
    "cpu_priority": 2,
    "pause_temp_c": 80,
    "resume_temp_c": 70,
    "emergency_kill_temp_c": 90,
    "temp_check_interval_sec": 20,
    "duty_cycle_enabled": False,
    "mine_duration_min": 15,
    "rest_duration_min": 5,
    "xmrig_version": "6.22.2",
    "log_to_file": True,
}

# ---------------------------------------------------------------------------
# LOGGING
# ---------------------------------------------------------------------------

def setup_logging(log_to_file: bool) -> logging.Logger:
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if log_to_file:
        handlers.append(logging.FileHandler(LOG_DIR / "miner.log", encoding="utf-8"))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=handlers,
    )
    return logging.getLogger("xmr-miner")


log = logging.getLogger("xmr-miner")

# ---------------------------------------------------------------------------
# CONFIG LOADING
# ---------------------------------------------------------------------------

def load_config() -> dict:
    if not CONFIG_PATH.exists():
        log.error("config.json not found at %s", CONFIG_PATH)
        log.error("Run:  python miner.py --setup  to create it interactively.")
        sys.exit(1)
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        log.error("Invalid config.json: %s", exc)
        sys.exit(1)

    cfg = {**DEFAULTS, **{k: v for k, v in data.items() if not k.startswith("_")}}

    if not cfg["wallet_address"]:
        log.error("wallet_address is empty in config.json. Please edit it first.")
        sys.exit(1)

    return cfg


# ---------------------------------------------------------------------------
# INTERACTIVE SETUP
# ---------------------------------------------------------------------------

def run_setup() -> None:
    print("\n=== XMR Miner Setup ===")
    print("Press Enter to keep the current/default value.\n")

    existing: dict = {}
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                existing = {k: v for k, v in json.load(f).items() if not k.startswith("_")}
        except Exception:
            pass

    def ask(key: str, prompt: str, current=None) -> str | float | bool:
        default = current if current is not None else existing.get(key, DEFAULTS.get(key, ""))
        answer = input(f"  {prompt} [{default}]: ").strip()
        return answer if answer else default

    wallet   = ask("wallet_address",        "Wallet address (XMR)")
    worker   = ask("worker_name",           "Worker / rig name")
    pool     = ask("pool_address",          "Pool address")
    password = ask("pool_password",         "Pool password")
    cpu_pct  = ask("cpu_usage_percent",     "CPU usage fraction (0.1 – 1.0)")
    rx_mode  = ask("randomx_mode",          "RandomX mode  [auto / light / hard]")
    priority = ask("cpu_priority",          "CPU priority  (0=lowest … 5=highest)")
    pause_t  = ask("pause_temp_c",          "Suspend temp (°C)")
    resume_t = ask("resume_temp_c",         "Resume temp  (°C)")
    kill_t   = ask("emergency_kill_temp_c", "Emergency kill temp (°C)")
    interval = ask("temp_check_interval_sec","Temp-check interval (seconds)")
    duty_raw = ask("duty_cycle_enabled",    "Enable duty-cycle mode? (true/false)")
    mine_dur = ask("mine_duration_min",     "  Mining duration per cycle (minutes)")
    rest_dur = ask("rest_duration_min",     "  Rest duration per cycle  (minutes)")
    version  = ask("xmrig_version",         "XMRig version to download")
    log_file = ask("log_to_file",           "Save log to logs/miner.log? (true/false)")

    def to_bool(v: str | bool) -> bool:
        if isinstance(v, bool):
            return v
        return str(v).lower() in ("true", "yes", "1", "y")

    cfg = {
        "_comment": "Edit this file to configure your miner.",
        "wallet_address":          str(wallet),
        "worker_name":             str(worker),
        "pool_address":            str(pool),
        "pool_password":           str(password),
        "cpu_usage_percent":       float(cpu_pct),
        "randomx_mode":            str(rx_mode),
        "cpu_priority":            int(priority),
        "pause_temp_c":            int(pause_t),
        "resume_temp_c":           int(resume_t),
        "emergency_kill_temp_c":   int(kill_t),
        "temp_check_interval_sec": int(interval),
        "duty_cycle_enabled":      to_bool(duty_raw),
        "mine_duration_min":       int(mine_dur),
        "rest_duration_min":       int(rest_dur),
        "xmrig_version":           str(version),
        "log_to_file":             to_bool(log_file),
    }

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    print(f"\n✓ Config saved to {CONFIG_PATH}")
    print("Run  python miner.py  to start mining.\n")


# ---------------------------------------------------------------------------
# OS DETECTION
# ---------------------------------------------------------------------------

_SYS = platform.system().lower()
IS_WINDOWS = _SYS.startswith("win")
IS_LINUX   = _SYS.startswith("linux")
IS_MACOS   = _SYS.startswith("darwin")
ARCH = platform.machine().lower()


# ---------------------------------------------------------------------------
# XMRIG DOWNLOAD / INSTALL
# ---------------------------------------------------------------------------

def _xmrig_download_url(version: str) -> str:
    if IS_WINDOWS:
        return f"https://github.com/xmrig/xmrig/releases/download/v{version}/xmrig-{version}-msvc-win64.zip"
    if IS_LINUX:
        return f"https://github.com/xmrig/xmrig/releases/download/v{version}/xmrig-{version}-linux-static-x64.tar.gz"
    if IS_MACOS:
        if "arm" in ARCH or "aarch" in ARCH:
            return f"https://github.com/xmrig/xmrig/releases/download/v{version}/xmrig-{version}-macos-arm64.tar.gz"
        return f"https://github.com/xmrig/xmrig/releases/download/v{version}/xmrig-{version}-macos-x64.tar.gz"
    raise RuntimeError(f"Unsupported OS for auto-download: {platform.system()}")


def _show_progress(block_num: int, block_size: int, total_size: int) -> None:
    downloaded = block_num * block_size
    if total_size > 0:
        pct = min(100, int(downloaded * 100 / total_size))
        mb = downloaded / 1_048_576
        total_mb = total_size / 1_048_576
        print(f"\r  Downloading… {pct}%  ({mb:.1f} / {total_mb:.1f} MB)", end="", flush=True)


def _download_and_unpack(version: str) -> str:
    url = _xmrig_download_url(version)
    log.info("Downloading XMRig v%s from GitHub…", version)
    log.info("  %s", url)

    TOOLS_DIR.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=TOOLS_DIR) as tmp_str:
        tmp = Path(tmp_str)
        archive = tmp / ("xmrig.zip" if url.endswith(".zip") else "xmrig.tar.gz")

        try:
            urllib.request.urlretrieve(url, archive, reporthook=_show_progress)
            print()
        except Exception as exc:
            raise RuntimeError(f"Download failed: {exc}") from exc

        if archive.suffix == ".zip":
            with zipfile.ZipFile(archive, "r") as z:
                z.extractall(tmp)
        else:
            with tarfile.open(archive, "r:gz") as t:
                t.extractall(tmp, filter="data")

        bin_name = "xmrig.exe" if IS_WINDOWS else "xmrig"
        binary = next((p for p in tmp.rglob(bin_name) if p.is_file()), None)
        if binary is None:
            raise RuntimeError(f"Binary '{bin_name}' not found inside archive")

        extracted_dir = binary.parent
        if XMRIG_DIR.exists():
            shutil.rmtree(XMRIG_DIR)
        shutil.move(str(extracted_dir), XMRIG_DIR)

    if not IS_WINDOWS:
        xmrig_bin = XMRIG_DIR / "xmrig"
        xmrig_bin.chmod(0o755)

    final = XMRIG_DIR / ("xmrig.exe" if IS_WINDOWS else "xmrig")
    if not final.exists():
        raise RuntimeError("Installation incomplete — binary missing after extraction")

    log.info("XMRig installed at %s", final)
    return str(final)


def _try_pkg_manager() -> str | None:
    """Attempt to install xmrig via the system package manager (Linux only)."""
    candidates = [
        ("apt-get", ["sudo", "apt-get", "update"], ["sudo", "apt-get", "install", "-y", "xmrig", "lm-sensors"]),
        ("dnf",     None,                           ["sudo", "dnf",     "install", "-y", "xmrig", "lm_sensors"]),
        ("yum",     None,                           ["sudo", "yum",     "install", "-y", "xmrig", "lm_sensors"]),
        ("pacman",  None,                           ["sudo", "pacman",  "-Syu", "--noconfirm", "xmrig", "lm_sensors"]),
        ("zypper",  None,                           ["sudo", "zypper",  "install", "-y", "xmrig", "lm_sensors"]),
        ("brew",    None,                           ["brew", "install", "xmrig"]),
    ]
    for mgr, pre, install_cmd in candidates:
        if shutil.which(mgr):
            try:
                if pre:
                    subprocess.run(pre, check=False, capture_output=True)
                log.info("Trying to install xmrig via %s…", mgr)
                subprocess.run(install_cmd, check=False)
                path = shutil.which("xmrig")
                if path:
                    return path
            except Exception as exc:
                log.warning("Package manager '%s' failed: %s", mgr, exc)
    return None


def ensure_xmrig(version: str) -> str:
    """Return path to xmrig binary, downloading/installing if needed."""
    if IS_WINDOWS:
        bundled = XMRIG_DIR / "xmrig.exe"
        if bundled.exists():
            return str(bundled)
        return _download_and_unpack(version)

    # Linux / macOS: check local download first, then PATH
    bundled = XMRIG_DIR / "xmrig"
    if bundled.exists():
        return str(bundled)

    system_path = shutil.which("xmrig")
    if system_path:
        return system_path

    # Try to install via package manager before downloading
    if IS_LINUX:
        pkg_path = _try_pkg_manager()
        if pkg_path:
            return pkg_path

    # Fall back to static binary download
    return _download_and_unpack(version)


# ---------------------------------------------------------------------------
# TEMPERATURE READING
# ---------------------------------------------------------------------------

try:
    import psutil as _psutil
except ImportError:
    _psutil = None  # type: ignore


def cpu_temp() -> float | None:
    """Return the peak CPU temperature in °C, or None if unavailable."""
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

    try:
        out = subprocess.check_output(["sensors"], stderr=subprocess.DEVNULL, text=True)
        nums = [float(n) for n in re.findall(r"([-+]?\d+\.?\d*)°C", out)]
        if nums:
            return max(nums)
    except Exception:
        pass

    return None


# ---------------------------------------------------------------------------
# THREAD CALCULATION
# ---------------------------------------------------------------------------

def calculate_threads(cpu_usage_percent: float) -> int:
    try:
        total = (_psutil.cpu_count(logical=True) if _psutil else None) or os.cpu_count() or 1
    except Exception:
        total = os.cpu_count() or 1
    return max(1, min(total, int(total * cpu_usage_percent)))


# ---------------------------------------------------------------------------
# MINER PROCESS LAUNCH
# ---------------------------------------------------------------------------

def _build_cmd(xmrig_path: str, cfg: dict) -> list[str]:
    threads = calculate_threads(cfg["cpu_usage_percent"])
    cmd = [
        xmrig_path,
        "-o", cfg["pool_address"],
        "-u", cfg["wallet_address"],
        "-p", cfg["worker_name"] if cfg["pool_password"] in ("x", "") else cfg["pool_password"],
        "--rig-id", cfg["worker_name"],
        "--print-time", "10",
        f"--cpu-priority={cfg['cpu_priority']}",
    ]

    if IS_LINUX or IS_MACOS:
        cmd += ["--threads", str(threads), f"--randomx-mode={cfg['randomx_mode']}"]

    return cmd


def _set_process_priority(pid: int, cfg: dict) -> None:
    if _psutil is None:
        return
    try:
        p = _psutil.Process(pid)
        if IS_WINDOWS:
            p.nice(_psutil.BELOW_NORMAL_PRIORITY_CLASS)
        else:
            p.nice(10)
        threads = calculate_threads(cfg["cpu_usage_percent"])
        total = _psutil.cpu_count(logical=True) or 1
        p.cpu_affinity(list(range(min(threads, total))))
    except Exception as exc:
        log.warning("Could not set process priority/affinity: %s", exc)


def start_miner(xmrig_path: str, cfg: dict) -> tuple[subprocess.Popen, threading.Event]:
    """Launch XMRig and return (Popen, stop_event).
    On Linux/macOS a PTY is used so XMRig outputs colour and banners correctly.
    """
    cmd = _build_cmd(xmrig_path, cfg)
    log.info("Starting XMRig (pid=pending) — pool=%s  threads=%d",
             cfg["pool_address"], calculate_threads(cfg["cpu_usage_percent"]))

    stop_evt = threading.Event()

    if IS_LINUX or IS_MACOS:
        try:
            import pty
            master_fd, slave_fd = pty.openpty()
            proc = subprocess.Popen(
                cmd,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                close_fds=True,
            )
            os.close(slave_fd)

            def _forward():
                try:
                    while not stop_evt.is_set():
                        data = os.read(master_fd, 4096)
                        if not data:
                            break
                        sys.stdout.buffer.write(data)
                        sys.stdout.buffer.flush()
                except OSError:
                    pass

            threading.Thread(target=_forward, daemon=True).start()
        except Exception as exc:
            log.warning("PTY failed (%s), using plain pipes", exc)
            proc = subprocess.Popen(cmd, stdout=sys.stdout, stderr=sys.stderr)
    else:
        proc = subprocess.Popen(cmd, stdout=sys.stdout, stderr=sys.stderr)

    log.info("XMRig started (pid=%d)", proc.pid)
    _set_process_priority(proc.pid, cfg)
    return proc, stop_evt


# ---------------------------------------------------------------------------
# THERMAL CONTROL
# ---------------------------------------------------------------------------

def _get_psutil_proc(pid: int):
    if _psutil is None:
        return None
    try:
        return _psutil.Process(pid)
    except Exception:
        return None


def thermal_loop(proc: subprocess.Popen, cfg: dict, stop_evt: threading.Event) -> None:
    """Monitor temperature and suspend/resume/kill the miner accordingly."""
    pause_t   = cfg["pause_temp_c"]
    resume_t  = cfg["resume_temp_c"]
    kill_t    = cfg["emergency_kill_temp_c"]
    interval  = cfg["temp_check_interval_sec"]
    ps_proc   = _get_psutil_proc(proc.pid)
    suspended = False
    warned    = False

    while not stop_evt.is_set():
        if proc.poll() is not None:
            log.error("XMRig exited unexpectedly (code=%d)", proc.returncode)
            stop_evt.set()
            return

        temp = cpu_temp()
        if temp is None:
            if not warned:
                log.warning(
                    "CPU temperature unavailable — thermal protection disabled. "
                    "On Linux install lm-sensors and run: sudo sensors-detect"
                )
                warned = True
            time.sleep(interval)
            continue

        log.info("CPU temp: %.1f°C", temp)

        if temp >= kill_t:
            log.critical("EMERGENCY temp (%.1f°C >= %d°C) — killing miner!", temp, kill_t)
            proc.kill()
            stop_evt.set()
            return

        if ps_proc:
            if temp >= pause_t and not suspended:
                try:
                    ps_proc.suspend()
                    suspended = True
                    log.warning("Miner SUSPENDED (temp %.1f°C >= %d°C)", temp, pause_t)
                except Exception as exc:
                    log.warning("Could not suspend miner: %s", exc)

            elif suspended and temp <= resume_t:
                try:
                    ps_proc.resume()
                    suspended = False
                    log.info("Miner RESUMED (temp %.1f°C <= %d°C)", temp, resume_t)
                except Exception as exc:
                    log.warning("Could not resume miner: %s", exc)

        time.sleep(interval)


# ---------------------------------------------------------------------------
# DUTY CYCLE
# ---------------------------------------------------------------------------

def duty_cycle_loop(xmrig_path: str, cfg: dict, stop_evt: threading.Event) -> None:
    """Alternates between mining and rest periods."""
    mine_sec = cfg["mine_duration_min"] * 60
    rest_sec = cfg["rest_duration_min"] * 60
    cycle = 1

    while not stop_evt.is_set():
        log.info("=== Cycle %d — Mining for %d minutes ===", cycle, cfg["mine_duration_min"])
        proc, _ = start_miner(xmrig_path, cfg)

        # mine for the configured duration (or until stop)
        deadline = time.monotonic() + mine_sec
        while time.monotonic() < deadline and not stop_evt.is_set():
            if proc.poll() is not None:
                log.error("XMRig crashed during cycle %d", cycle)
                break

            temp = cpu_temp()
            if temp is not None:
                log.info("CPU temp: %.1f°C", temp)
                if temp >= cfg["emergency_kill_temp_c"]:
                    log.critical("EMERGENCY temp — stopping miner and exiting duty cycle!")
                    proc.kill()
                    stop_evt.set()
                    return

            time.sleep(cfg["temp_check_interval_sec"])

        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except Exception:
                proc.kill()
        log.info("Cycle %d done. Resting for %d minutes…", cycle, cfg["rest_duration_min"])

        rest_deadline = time.monotonic() + rest_sec
        while time.monotonic() < rest_deadline and not stop_evt.is_set():
            time.sleep(5)

        cycle += 1


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="XMR Miner Controller")
    parser.add_argument("--setup", action="store_true", help="Interactively create/update config.json")
    args = parser.parse_args()

    if args.setup:
        run_setup()
        return

    cfg = load_config()
    global log
    log = setup_logging(cfg["log_to_file"])

    log.info("XMR Miner Controller — for education purposes only")
    log.info("OS: %s  Arch: %s", platform.system(), platform.machine())
    log.info("Pool: %s  Worker: %s", cfg["pool_address"], cfg["worker_name"])
    log.info("Duty-cycle mode: %s", "ON" if cfg["duty_cycle_enabled"] else "OFF")

    xmrig_path = ensure_xmrig(cfg["xmrig_version"])
    log.info("Using XMRig: %s", xmrig_path)

    stop_evt = threading.Event()
    proc: subprocess.Popen | None = None

    def shutdown(*_) -> None:
        log.info("Shutdown signal received — stopping miner…")
        stop_evt.set()
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except Exception:
                proc.kill()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, shutdown)

    if cfg["duty_cycle_enabled"]:
        duty_cycle_loop(xmrig_path, cfg, stop_evt)
    else:
        proc, fwd_stop = start_miner(xmrig_path, cfg)
        thermal_loop(proc, cfg, fwd_stop)


if __name__ == "__main__":
    main()
