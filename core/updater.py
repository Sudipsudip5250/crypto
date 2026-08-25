"""
core/updater.py
---------------
XMRig auto-update utilities.

  get_latest_version()     → query GitHub API for the latest XMRig release tag
  get_cached_version()     → read version from the local version file
  needs_update(cfg)        → True if a newer version is available
  update_xmrig(cfg)        → download + replace the cached binary

For educational and research purposes only — see DISCLAIMER.md.
"""
# ── Educational / research use only ─────────────────────────────────────────
# See DISCLAIMER.md and LICENSE for full legal notices.
# ────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import json
import logging
import platform
import re
import shutil
import subprocess
from pathlib import Path
import urllib.request
import urllib.error

log = logging.getLogger("xmr-miner")

GITHUB_LATEST = "https://api.github.com/repos/xmrig/xmrig/releases/latest"

BASE_DIR     = Path(__file__).resolve().parent.parent
TOOLS_DIR    = BASE_DIR / "tools"
XMRIG_DIR    = TOOLS_DIR / "xmrig"
VERSION_FILE = TOOLS_DIR / ".xmrig_version"   # written after every download

_SYS        = platform.system().lower()
IS_WINDOWS  = _SYS.startswith("win")


def _cached_binary() -> Path | None:
    """Return path to the cached XMRig binary, or None if not present."""
    binary = XMRIG_DIR / ("xmrig.exe" if IS_WINDOWS else "xmrig")
    return binary if binary.exists() else None


def write_cached_version(version: str) -> None:
    """Persist the version string to tools/.xmrig_version after a download."""
    TOOLS_DIR.mkdir(exist_ok=True)
    # Strip any pre-release suffix before storing (e.g. "6.26.0-beta" → "6.26.0")
    clean = re.split(r"[^0-9.]", version.strip())[0]
    VERSION_FILE.write_text(clean, encoding="utf-8")


def get_cached_version() -> str | None:
    """
    Return the installed XMRig version string (e.g. "6.26.0").

    Reads from tools/.xmrig_version (written after every download).
    Falls back to trying the binary's --version flag if that file is absent.
    Returns None if neither method works.
    """
    # Primary: version file written by the downloader
    if VERSION_FILE.exists():
        try:
            ver = VERSION_FILE.read_text(encoding="utf-8").strip()
            if re.match(r"\d+\.\d+\.\d+", ver):
                return ver
        except OSError:
            pass

    # Fallback: try running the binary (may be blocked in sandboxes)
    binary = _cached_binary()
    if binary is None:
        return None
    try:
        out = subprocess.check_output(
            [str(binary), "--version"],
            stderr=subprocess.STDOUT,
            text=True,
            timeout=10,
        )
        match = re.search(r"(\d+\.\d+\.\d+)", out)
        if match:
            ver = match.group(1)
            write_cached_version(ver)   # cache it for next time
            return ver
    except Exception:
        pass

    return None


def get_latest_version() -> str | None:
    """
    Query the GitHub releases API and return the latest XMRig version string
    (e.g. "6.26.0"), or None on network / parse failure.
    """
    try:
        req = urllib.request.Request(
            GITHUB_LATEST,
            headers={"User-Agent": "xmr-miner-updater/1.0"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8", errors="replace")

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            log.warning("GitHub API returned unexpected JSON: %s", exc)
            return None

        tag = data.get("tag_name", "")          # e.g. "v6.26.0"
        match = re.search(r"(\d+\.\d+\.\d+)", tag)
        if match:
            return match.group(1)

        log.warning("Could not parse version tag from GitHub response: %r", tag)

    except urllib.error.URLError as exc:
        log.warning("Could not reach GitHub API: %s", exc)
    except Exception as exc:
        log.warning("Unexpected error checking for updates: %s", exc)

    return None


def _version_tuple(ver: str) -> tuple[int, ...]:
    """
    Convert a version string to a comparable tuple of ints.

    Handles plain releases ("6.26.0") and pre-release suffixes ("6.26.0-beta",
    "6.26.0-rc1") by stripping everything after the first non-numeric,
    non-dot character.
    """
    # Keep only the numeric dotted part
    clean = re.split(r"[^0-9.]", ver.strip())[0]
    parts = [p for p in clean.split(".") if p.isdigit()]
    if not parts:
        return (0,)
    return tuple(int(p) for p in parts)


def needs_update(cfg: dict) -> tuple[bool, str | None, str | None]:
    """
    Check whether a newer XMRig is available.

    Returns
    -------
    (should_update, cached_version, latest_version)
    """
    cached = get_cached_version() or cfg.get("xmrig_version", "0.0.0")
    latest = get_latest_version()

    if latest is None:
        log.warning("Could not determine latest version — skipping update check.")
        return False, cached, None

    try:
        should = _version_tuple(latest) > _version_tuple(cached)
    except Exception:
        should = False

    return should, cached, latest


def update_xmrig(cfg: dict, force: bool = False) -> bool:
    """
    Download and install the latest XMRig release if a newer version exists.

    Parameters
    ----------
    cfg   : dict   loaded config (used for fallback version and OS)
    force : bool   if True, download even if already up-to-date

    Returns
    -------
    True if the binary was (re)installed, False otherwise.
    """
    log.info("Checking for XMRig updates …")
    should_update, cached, latest = needs_update(cfg)

    if latest is None:
        log.warning("Update check failed — keeping current version.")
        return False

    if not force and not should_update:
        log.info("XMRig is up-to-date  (v%s).", cached)
        return False

    log.info(
        "Update available: v%s → v%s — downloading …",
        cached or "?", latest,
    )

    # Remove old binary dir so the platform download starts fresh
    if XMRIG_DIR.exists():
        shutil.rmtree(XMRIG_DIR)

    # Delegate to the correct platform downloader
    from platforms.detect import get_platform_module
    platform_mod = get_platform_module()
    new_bin = platform_mod.ensure_xmrig(latest)

    log.info("XMRig updated to v%s → %s", latest, new_bin)

    # Persist new version in config.json
    try:
        from core.config import load_config, save_config
        cfg2 = load_config()
        cfg2["xmrig_version"] = latest
        save_config(cfg2)
        log.info("config.json updated: xmrig_version=%s", latest)
    except Exception as exc:
        log.warning("Could not update config.json: %s", exc)

    return True
