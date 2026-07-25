"""
core/config.py
--------------
Load, validate, and interactively create config.json.

All user-tunable settings live in config.json in the project root.
This module owns the schema (DEFAULTS) and is the single place to add
new config keys in the future.

For educational and research purposes only — see DISCLAIMER.md.
"""
# ── Educational / research use only ─────────────────────────────────────────
# See DISCLAIMER.md and LICENSE for full legal notices.
# ────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import json
import sys
from pathlib import Path

BASE_DIR    = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config.json"

# Project donation wallet — used as the default so clones that run without
# changing wallet_address automatically donate mining power to the project.
PROJECT_WALLET = (
    "4B3WoA2P3fQNancXvdPVvnVcWZfeyC97dRj56pbq6RJdNGS39V4ME4WKHxn7e9KAFeJ87dNxgAdrP8dF5r8bFVxhPDS49gU"
)

# ---------------------------------------------------------------------------
# Schema & defaults
# ---------------------------------------------------------------------------

DEFAULTS: dict = {
    # --- Pool / identity ---
    "wallet_address":          PROJECT_WALLET,  # default = project donation wallet
    "worker_name":             "myrig",
    "pool_address":            "pool.supportxmr.com:3333",
    "pool_password":           "x",

    # --- CPU resource limits ---
    "cpu_usage_percent":       0.70,   # fraction of logical cores (0.1–1.0)
    "randomx_mode":            "auto", # auto | light | hard
    "cpu_priority":            2,      # 0 (lowest) … 5 (highest)

    # --- Thermal protection ---
    "pause_temp_c":            80,     # suspend miner above this °C
    "resume_temp_c":           70,     # resume miner below this °C
    "emergency_kill_temp_c":   90,     # kill + exit above this °C
    "temp_check_interval_sec": 20,     # how often to poll temperature

    # --- Duty-cycle mode ---
    "duty_cycle_enabled":      False,
    "mine_duration_min":       15,     # minutes to mine per cycle
    "rest_duration_min":       5,      # minutes to rest per cycle

    # --- XMRig binary ---
    "xmrig_version":           "6.22.2",

    # --- Logging ---
    "log_to_file":             True,
}

_DESCRIPTIONS: dict[str, str] = {
    "wallet_address":          "Your XMR wallet address",
    "worker_name":             "Rig / worker label shown on the pool",
    "pool_address":            "Pool host:port  (e.g. pool.supportxmr.com:3333)",
    "pool_password":           "Pool password   (usually 'x')",
    "cpu_usage_percent":       "CPU fraction to use  (0.1 – 1.0)",
    "randomx_mode":            "RandomX mode    (auto | light | hard)",
    "cpu_priority":            "Process priority (0=lowest … 5=highest)",
    "pause_temp_c":            "Suspend miner above this CPU temp (°C)",
    "resume_temp_c":           "Resume miner below this CPU temp  (°C)",
    "emergency_kill_temp_c":   "Kill miner + exit above this temp  (°C)",
    "temp_check_interval_sec": "Temperature polling interval (seconds)",
    "duty_cycle_enabled":      "Enable duty-cycle mode?  (true / false)",
    "mine_duration_min":       "  ↳ Mine for this many minutes per cycle",
    "rest_duration_min":       "  ↳ Rest for this many minutes per cycle",
    "xmrig_version":           "XMRig version to auto-download from GitHub",
    "log_to_file":             "Save logs to logs/miner.log?  (true / false)",
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_config() -> dict:
    """Load config.json, merge with defaults, and validate required fields."""
    if not CONFIG_PATH.exists():
        print(f"[config] config.json not found at {CONFIG_PATH}")
        print("[config] Run:  python miner.py setup  to create it.\n")
        sys.exit(1)

    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except json.JSONDecodeError as exc:
        print(f"[config] Invalid config.json: {exc}")
        sys.exit(1)

    # Strip comment keys (start with '_'), merge with defaults
    user = {k: v for k, v in raw.items() if not k.startswith("_")}
    cfg  = {**DEFAULTS, **user}

    if not cfg["wallet_address"]:
        print("[config] wallet_address is empty. Edit config.json or run: python miner.py setup")
        sys.exit(1)

    # Clamp cpu_usage_percent to a sane range
    try:
        cfg["cpu_usage_percent"] = max(0.05, min(1.0, float(cfg["cpu_usage_percent"])))
    except (TypeError, ValueError):
        cfg["cpu_usage_percent"] = DEFAULTS["cpu_usage_percent"]

    return cfg


def save_config(cfg: dict) -> None:
    """Write cfg to config.json (strips internal _ keys, adds comment header)."""
    out: dict = {
        "_comment":  "Edit this file to configure your miner. See README.md.",
        "_donate":   (
            "The default wallet_address is the project donation wallet. "
            "Change it to your own address to mine for yourself."
        ),
    }
    out.update({k: v for k, v in cfg.items() if not k.startswith("_")})
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print(f"[config] Saved → {CONFIG_PATH}")


def run_setup() -> None:
    """Interactive wizard to create or update config.json."""
    print("\n╔══════════════════════════════╗")
    print("║   XMR Miner — Setup Wizard   ║")
    print("╚══════════════════════════════╝")
    print("Press Enter to keep the value shown in [brackets].\n")

    # Load existing values so the wizard shows current choices
    existing: dict = {}
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                existing = {
                    k: v for k, v in json.load(f).items()
                    if not k.startswith("_")
                }
        except Exception:
            pass

    def current(key: str):
        return existing.get(key, DEFAULTS[key])

    def ask(key: str) -> str:
        default = current(key)
        prompt  = f"  {_DESCRIPTIONS[key]}  [{default}]: "
        answer  = input(prompt).strip()
        return answer if answer else str(default)

    def ask_bool(key: str) -> bool:
        default = current(key)
        prompt  = f"  {_DESCRIPTIONS[key]}  [{'true' if default else 'false'}]: "
        answer  = input(prompt).strip().lower()
        if answer in ("true",  "yes", "1", "y"):
            return True
        if answer in ("false", "no",  "0", "n"):
            return False
        return bool(default)

    def ask_float(key: str) -> float:
        """Prompt for a float, re-asking on invalid input."""
        while True:
            raw = ask(key)
            try:
                return float(raw)
            except ValueError:
                print(f"  ✗  Expected a decimal number (e.g. 0.75). Please try again.")

    def ask_int(key: str) -> int:
        """Prompt for an integer, re-asking on invalid input."""
        while True:
            raw = ask(key)
            try:
                return int(raw)
            except ValueError:
                print(f"  ✗  Expected a whole number (e.g. 80). Please try again.")

    cfg = {
        "wallet_address":          ask("wallet_address"),
        "worker_name":             ask("worker_name"),
        "pool_address":            ask("pool_address"),
        "pool_password":           ask("pool_password"),
        "cpu_usage_percent":       ask_float("cpu_usage_percent"),
        "randomx_mode":            ask("randomx_mode"),
        "cpu_priority":            ask_int("cpu_priority"),
        "pause_temp_c":            ask_int("pause_temp_c"),
        "resume_temp_c":           ask_int("resume_temp_c"),
        "emergency_kill_temp_c":   ask_int("emergency_kill_temp_c"),
        "temp_check_interval_sec": ask_int("temp_check_interval_sec"),
        "duty_cycle_enabled":      ask_bool("duty_cycle_enabled"),
        "mine_duration_min":       ask_int("mine_duration_min"),
        "rest_duration_min":       ask_int("rest_duration_min"),
        "xmrig_version":           ask("xmrig_version"),
        "log_to_file":             ask_bool("log_to_file"),
    }

    save_config(cfg)
    print("\n✓ Config saved. Run  python miner.py  to start mining.\n")
