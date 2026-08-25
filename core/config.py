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
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = Path(os.environ.get("CRYPTO_CONFIG", str(BASE_DIR / "config.json"))).expanduser().resolve()


def set_config_path(path: str | Path) -> Path:
    """Select a local config file for one worker or an authorized group member."""
    global CONFIG_PATH
    CONFIG_PATH = Path(path).expanduser().resolve()
    os.environ["CRYPTO_CONFIG"] = str(CONFIG_PATH)
    return CONFIG_PATH

# Project donation wallet — used only by the explicit donate-mode command.
PROJECT_WALLET = (
    "4B3WoA2P3fQNancXvdPVvnVcWZfeyC97dRj56pbq6RJdNGS39V4ME4WKHxn7e9KAFeJ87dNxgAdrP8dF5r8bFVxhPDS49gU"
)

# XMRig supports multiple algorithms and coin aliases. Presets only select
# the algorithm identity; pool endpoints and wallets remain user-provided so
# the project does not ship stale or misleading third-party service details.
COIN_PRESETS: dict[str, dict[str, object]] = {
    # `coin` is only set where XMRig documents a useful coin alias. Other
    # profiles use the explicit algorithm flag to avoid passing an unsupported
    # coin alias to XMRig.
    "monero":    {"label": "Monero",    "coin": "monero", "algorithm": "rx/0",          "backends": ("cpu",)},
    "arqma":     {"label": "ArQmA",     "coin": "arqma",  "algorithm": "rx/arq",       "backends": ("cpu",)},
    "wownero":   {"label": "Wownero",   "coin": "",       "algorithm": "rx/wow",       "backends": ("cpu",)},
    "keva":      {"label": "Keva",      "coin": "",       "algorithm": "rx/keva",      "backends": ("cpu",)},
    "safex":     {"label": "Safex",     "coin": "",       "algorithm": "rx/sfx",       "backends": ("cpu",)},
    "conceal":   {"label": "Conceal",   "coin": "",       "algorithm": "cn/ccx",       "backends": ("cpu",)},
    "uplexa":    {"label": "Uplexa",    "coin": "",       "algorithm": "cn/upx2",      "backends": ("cpu",)},
    "talleo":    {"label": "Talleo",    "coin": "",       "algorithm": "cn-pico/tlo",  "backends": ("cpu",)},
    "raptoreum": {"label": "Raptoreum", "coin": "",       "algorithm": "gr",           "backends": ("cpu",)},
    "ravencoin": {"label": "Ravencoin", "coin": "",       "algorithm": "kawpow",       "backends": ("cuda", "opencl")},
}
BACKENDS = ("cpu", "cuda", "opencl", "cpu+cuda", "cpu+opencl")


def _backend_parts(backend: str) -> set[str]:
    return {part for part in backend.split("+") if part}

# ---------------------------------------------------------------------------
# Schema & defaults
# ---------------------------------------------------------------------------

DEFAULTS: dict = {
    # --- Coin / algorithm ---
    "profile":                 "monero",
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
    "randomx_mode":            "auto", # auto | fast | light
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
    "xmrig_path":              "",      # optional native/system binary path

    # --- Logging ---
    "log_to_file":             True,
}

_DESCRIPTIONS: dict[str, str] = {
    "profile":                 "Coin profile / preset",
    "wallet_address":          "Your wallet address for the selected coin",
    "coin":                    "XMRig coin alias (optional)",
    "algorithm":               "XMRig algorithm (for custom setups)",
    "backend":                 "Backend: cpu, cuda, opencl, cpu+cuda, or cpu+opencl",
    "cuda_devices":            "CUDA device indexes (optional, comma-separated)",
    "opencl_devices":          "OpenCL device indexes (optional, comma-separated)",
    "worker_name":             "Rig / worker label shown on the pool",
    "pool_address":            "Pool host:port  (e.g. pool.supportxmr.com:3333)",
    "pool_password":           "Pool password   (usually 'x')",
    "cpu_usage_percent":       "CPU fraction to use  (0.1 – 1.0)",
    "randomx_mode":            "RandomX mode    (auto | fast | light)",
    "cpu_priority":            "Process priority (0=lowest … 5=highest)",
    "pause_temp_c":            "Suspend miner above this CPU temp (°C)",
    "resume_temp_c":           "Resume miner below this CPU temp  (°C)",
    "emergency_kill_temp_c":   "Kill miner + exit above this temp  (°C)",
    "temp_check_interval_sec": "Temperature polling interval (seconds)",
    "duty_cycle_enabled":      "Enable duty-cycle mode?  (true / false)",
    "mine_duration_min":       "  ↳ Mine for this many minutes per cycle",
    "rest_duration_min":       "  ↳ Rest for this many minutes per cycle",
    "xmrig_version":           "XMRig version to auto-download from GitHub",
    "xmrig_path":              "Optional native XMRig binary path (useful on ARM64)",
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

    cfg["coin"] = str(cfg.get("coin", "monero")).strip().lower()
    cfg["algorithm"] = str(cfg.get("algorithm", "rx/0")).strip().lower()
    raw_profile = str(user.get("profile", "")).strip().lower()
    if not raw_profile:
        raw_profile = next(
            (name for name, values in COIN_PRESETS.items()
             if str(values["coin"]) == cfg["coin"]
             and str(values["algorithm"]) == cfg["algorithm"]),
            "custom",
        )
    cfg["profile"] = raw_profile
    if not cfg["coin"] and not cfg["algorithm"]:
        cfg["coin"], cfg["algorithm"] = "monero", "rx/0"
    cfg["backend"] = str(cfg.get("backend", "cpu")).strip().lower() or "cpu"
    if cfg["backend"] not in BACKENDS:
        print(f"[config] Unsupported backend {cfg['backend']!r}. Choose from: {', '.join(BACKENDS)}")
        sys.exit(1)
    if cfg["profile"] in COIN_PRESETS:
        preset = COIN_PRESETS[cfg["profile"]]
        allowed = set(preset["backends"])
        if not _backend_parts(cfg["backend"]).issubset(allowed):
            print(
                f"[config] Profile {cfg['profile']!r} supports only: "
                f"{', '.join(sorted(allowed))}. Choose another backend or run setup."
            )
            sys.exit(1)

    if require_wallet and not cfg["wallet_address"]:
        print("[config] wallet_address is empty. Edit config.json or run: python miner.py setup")
        sys.exit(1)
    if cfg["profile"] != "monero" and cfg["wallet_address"] == PROJECT_WALLET:
        print("[config] The published wallet is Monero-only. Set your own wallet for another profile.")
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
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
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

    current_profile = str(current("profile")).strip().lower()
    print("  Profiles: " + ", ".join(COIN_PRESETS) + ", custom")
    preset_name = input(f"  Profile [{current_profile}]: ").strip().lower() or current_profile
    if preset_name in COIN_PRESETS:
        selected = COIN_PRESETS[preset_name]
        profile = preset_name
        coin = str(selected["coin"])
        algorithm = str(selected["algorithm"])
        allowed_backends = tuple(str(v) for v in selected["backends"])
        print(f"  {selected['label']}: algorithm={algorithm}; allowed backends={', '.join(allowed_backends)}")
    else:
        profile = "custom"
        print("  Custom mode selected. Enter a coin alias, or leave it blank to use an algorithm directly.")
        coin = input("  Coin alias [blank for algorithm-only]: ").strip().lower()
        algorithm = input("  Algorithm [for example kawpow or rx/0]: ").strip().lower()
        allowed_backends = BACKENDS
        if not coin and not algorithm:
            print("[config] Custom mode requires a coin alias or an algorithm.")
            sys.exit(1)

    wallet = ask("wallet_address")
    if profile != "monero" and wallet == PROJECT_WALLET:
        print("  The published donation wallet is valid for Monero only.")
        wallet = input("  Enter your wallet address for the selected coin (required): ").strip()
        if not wallet:
            print("[config] A non-Monero wallet is required for this preset.")
            sys.exit(1)

    backend_default = str(current("backend")).lower()
    if backend_default not in BACKENDS or not _backend_parts(backend_default).issubset(set(allowed_backends)):
        backend_default = allowed_backends[0]
    backend = input(f"  {_DESCRIPTIONS['backend']}  [{backend_default}]: ").strip().lower() or backend_default
    while backend not in BACKENDS or not _backend_parts(backend).issubset(set(allowed_backends)):
        print(f"  Choose a compatible backend: {', '.join(allowed_backends)}")
        backend = input(f"  Backend [{backend_default}]: ").strip().lower() or backend_default

    cfg = {
        "profile":                 profile,
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
        "xmrig_path":              ask("xmrig_path"),
        "log_to_file":             ask_bool("log_to_file"),
    }

    save_config(cfg)
    print("\n✓ Config saved. Run  python miner.py  to start mining.\n")
