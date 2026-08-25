"""
platforms/windows.py
--------------------
Everything Windows-specific:
  • Locating / downloading / installing XMRig  (MSVC zip from GitHub)
  • Launching XMRig (plain subprocess — no PTY needed on Windows)
"""

from __future__ import annotations

import logging
import platform
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from core.download import download_verified, safe_extract_zip

log = logging.getLogger("xmr-miner")

BASE_DIR  = Path(__file__).resolve().parent.parent
TOOLS_DIR = BASE_DIR / "tools"
XMRIG_DIR = TOOLS_DIR / "xmrig"
BINARY    = XMRIG_DIR / "xmrig.exe"

RELEASE_BASE = "https://github.com/xmrig/xmrig/releases/download"

_MACHINE = platform.machine().lower()
_ARCH = "arm64" if any(tag in _MACHINE for tag in ("arm64", "aarch64", "arm")) else "x64"


def _release_asset(version: str) -> str:
    """Return the asset name used by the selected XMRig release."""
    try:
        parts = tuple(int(part) for part in version.split(".")[:3])
    except ValueError:
        parts = (0,)
    if parts < (6, 23, 0):
        if _ARCH != "x64":
            raise RuntimeError("XMRig versions before 6.23.0 have no Windows ARM64 asset")
        return f"xmrig-{version}-msvc-win64.zip"
    return f"xmrig-{version}-windows-{_ARCH}.zip"


# ---------------------------------------------------------------------------
# XMRig discovery and installation
# ---------------------------------------------------------------------------

def _show_progress(block: int, block_size: int, total: int) -> None:
    done = block * block_size
    if total > 0:
        pct = min(100, int(done * 100 / total))
        mb  = done / 1_048_576
        tot = total / 1_048_576
        print(f"\r  Downloading … {pct:3d}%  ({mb:.1f} / {tot:.1f} MB)", end="", flush=True)


def download_xmrig(version: str) -> Path:
    """Download the official Windows x64 or ARM64 release from GitHub."""
    asset_name = _release_asset(version)
    url = f"{RELEASE_BASE}/v{version}/{asset_name}"
    log.info("Downloading XMRig v%s for Windows (%s) …", version, _ARCH)
    log.info("  %s", url)

    TOOLS_DIR.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(dir=TOOLS_DIR) as tmp_str:
        tmp     = Path(tmp_str)
        archive = tmp / "xmrig.zip"

        try:
            download_verified(
                url,
                archive,
                version=version,
                asset_name=asset_name,
                reporthook=_show_progress,
            )
            print()
        except Exception as exc:
            raise RuntimeError(f"Download failed: {exc}") from exc

        safe_extract_zip(archive, tmp)

        exe = next((p for p in tmp.rglob("xmrig.exe") if p.is_file()), None)
        if exe is None:
            raise RuntimeError("xmrig.exe not found inside downloaded archive")

        if XMRIG_DIR.exists():
            shutil.rmtree(XMRIG_DIR)
        shutil.move(str(exe.parent), XMRIG_DIR)

    log.info("XMRig installed → %s", BINARY)

    from core.updater import write_cached_version
    write_cached_version(version)

    return BINARY


def ensure_xmrig(version: str, native_path: str = "") -> Path:
    """
    Return a Path to xmrig.exe, using a configured native path first.
    Priority:
      1. Already-downloaded binary in tools/xmrig/
      2. System-installed binary in PATH
      3. Download from GitHub
    """
    if native_path:
        path = Path(native_path).expanduser().resolve()
        if not path.is_file():
            raise RuntimeError(f"Configured XMRig path is not a file: {path}")
        log.info("Using configured native XMRig: %s", path)
        return path

    if BINARY.exists():
        log.info("Using cached XMRig: %s", BINARY)
        return BINARY

    system = shutil.which("xmrig")
    if system:
        log.info("Using system XMRig: %s", system)
        return Path(system)

    return download_xmrig(version)


# ---------------------------------------------------------------------------
# Process launch
# ---------------------------------------------------------------------------

def launch_process(cmd: list[str]) -> tuple[subprocess.Popen, threading.Event]:
    """
    Launch XMRig on Windows.

    Returns
    -------
    proc       : subprocess.Popen
    stop_event : threading.Event  (unused on Windows but kept for API consistency)
    """
    stop_event = threading.Event()

    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.DEVNULL,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )

    return proc, stop_event
