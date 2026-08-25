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

# Project donation wallet — used only by the explicit donate-mode command.
PROJECT_WALLET = (
    "4B3WoA2P3fQNancXvdPVvnVcWZfeyC97dRj56pbq6RJdNGS39V4ME4WKHxn7e9KAFeJ87dNxgAdrP8dF5r8bFVxhPDS49gU"
)

# XMRig supports multiple algorithms and coin aliases. Presets only select
# the algorithm identity; pool endpoints and wallets remain user-provided so
# the project does not ship stale or misleading third-party service details.
COIN_PRESETS: dict[str, dict[str, str]] = {
    "monero":    {"coin": "monero",    "algorithm": "rx/0"},
    "ravencoin": {"coin": "ravencoin", "algorithm": "kawpow"},
    "raptoreum": {"coin": "raptoreum", "algorithm": "ghostrider"},
}
BACKENDS = ("cpu", "cuda", "opencl", "cpu+cuda", "cpu+opencl")

# ---------------------------------------------------------------------------
# Schema & defaults
# ---------------------------------------------------------------------------

DEFAULTS: dict = {
    # --- Coin / algorithm ---
    "coin":                    "monero",
    "algorithm":               "rx/0",
    "backend":                 "cpu",
    "cuda_devices":            "",
    "opencl_devices":          "",

    # --- Pool / identity ---
    "wallet_address":          "",       # mining requires explicit user configuration
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
    "xmrig_version":           "6.26.0",

    # --- Logging ---
    "log_to_file":             True,
}

_DESCRIPTIONS: dict[str, str] = {
    "wallet_address":          "Your wallet address for the selected coin",
    "coin":                    "Coin alias / preset",
    "algorithm":               "XMRig algorithm (for custom setups)",
    "backend":                 "Backend: cpu, cuda, opencl, cpu+cuda, or cpu+opencl",
    "cuda_devices":            "CUDA device indexes (optional, comma-separated)",
    "opencl_devices":          "OpenCL device indexes (optional, comma-separated)",
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

def load_config(*, require_wallet: bool = True) -> dict:
    """Load config.json, merge defaults, and optionally require a wallet."""
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

    cfg["coin"] = str(cfg.get("coin", "monero")).strip().lower() or "monero"
    cfg["algorithm"] = str(cfg.get("algorithm", "rx/0")).strip().lower() or "rx/0"
    cfg["backend"] = str(cfg.get("backend", "cpu")).strip().lower() or "cpu"
    if cfg["backend"] not in BACKENDS:
        print(f"[config] Unsupported backend {cfg['backend']!r}. Choose from: {', '.join(BACKENDS)}")
        sys.exit(1)

    if require_wallet and not cfg["wallet_address"]:
        print("[config] wallet_address is empty. Edit config.json or run: python miner.py setup")
        sys.exit(1)
    if cfg["coin"] != "monero" and cfg["wallet_address"] == PROJECT_WALLET:
        print("[config] The published wallet is Monero-only. Set your own wallet for another coin.")
        sys.exit(1)

    # RandomX mode is only meaningful for RandomX; keep invalid legacy values
    # from producing an XMRig command that the selected release cannot parse.
    if str(cfg.get("randomx_mode", "auto")).lower() not in {"auto", "fast", "light"}:
        cfg["randomx_mode"] = "auto"
    cfg["randomx_mode"] = str(cfg["randomx_mode"]).lower()

    for key in ("cpu_priority", "pause_temp_c", "resume_temp_c",
                "emergency_kill_temp_c", "temp_check_interval_sec",
                "mine_duration_min", "rest_duration_min"):
        try:
            cfg[key] = int(cfg[key])
        except (TypeError, ValueError):
            cfg[key] = DEFAULTS[key]
    cfg["cpu_priority"] = max(0, min(5, cfg["cpu_priority"]))
    cfg["temp_check_interval_sec"] = max(1, cfg["temp_check_interval_sec"])
    cfg["mine_duration_min"] = max(1, cfg["mine_duration_min"])
    cfg["rest_duration_min"] = max(1, cfg["rest_duration_min"])
    cfg["worker_name"] = str(cfg.get("worker_name", "myrig")).strip() or "myrig"
    cfg["pool_address"] = str(cfg.get("pool_address", "")).strip()
    cfg["pool_password"] = str(cfg.get("pool_password", "x"))
    if require_wallet and not cfg["pool_address"]:
        print("[config] pool_address is empty. Edit config.json or run: python miner.py setup")
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
            "The normal wallet_address is intentionally empty until configured. "
            "Use explicit donate-mode to mine to the Monero project wallet."
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

    current_coin = str(current("coin")).strip().lower()
    current_algorithm = str(current("algorithm")).strip().lower()
    current_preset = next(
        (name for name, values in COIN_PRESETS.items()
         if values["coin"] == current_coin and values["algorithm"] == current_algorithm),
        "custom",
    )
    print("  Mining preset: monero, ravencoin, raptoreum, or custom")
    preset_name = input(f"  Preset [{current_preset}]: ").strip().lower() or current_preset
    if preset_name in COIN_PRESETS:
        selected = COIN_PRESETS[preset_name]
        coin = selected["coin"]
        algorithm = selected["algorithm"]
    else:
        print("  Custom mode selected. Enter a coin alias, or leave it blank to use an algorithm directly.")
        coin = input("  Coin alias [blank for algorithm-only]: ").strip().lower()
        algorithm = input("  Algorithm [for example kawpow or rx/0]: ").strip().lower()
        if not coin and not algorithm:
            print("[config] Custom mode requires a coin alias or an algorithm.")
            sys.exit(1)

    wallet = ask("wallet_address")
    if coin != "monero" and wallet == PROJECT_WALLET:
        print("  The published donation wallet is valid for Monero only.")
        wallet = input("  Enter your wallet address for the selected coin (required): ").strip()
        if not wallet:
            print("[config] A non-Monero wallet is required for this preset.")
            sys.exit(1)

    backend = ask("backend").lower()
    while backend not in BACKENDS:
        print(f"  Choose one of: {', '.join(BACKENDS)}")
        backend = input("  Backend [cpu]: ").strip().lower() or "cpu"

    cfg = {
        "coin":                    coin,
        "algorithm":               algorithm,
        "backend":                 backend,
        "cuda_devices":            ask("cuda_devices"),
        "opencl_devices":          ask("opencl_devices"),
        "wallet_address":          wallet,
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
