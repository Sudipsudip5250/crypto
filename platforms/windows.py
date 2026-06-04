"""
platforms/windows.py
--------------------
Everything Windows-specific:
  • Locating / downloading / installing XMRig  (MSVC zip from GitHub)
  • Launching XMRig (plain subprocess — no PTY needed on Windows)
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys
import tempfile
import threading
import urllib.request
import zipfile
from pathlib import Path

log = logging.getLogger("xmr-miner")

BASE_DIR  = Path(__file__).resolve().parent.parent
TOOLS_DIR = BASE_DIR / "tools"
XMRIG_DIR = TOOLS_DIR / "xmrig"
BINARY    = XMRIG_DIR / "xmrig.exe"

RELEASE_URL = (
    "https://github.com/xmrig/xmrig/releases/download"
    "/v{version}/xmrig-{version}-msvc-win64.zip"
)


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
    """Download the MSVC Win64 release from GitHub and unpack to XMRIG_DIR."""
    url = RELEASE_URL.format(version=version)
    log.info("Downloading XMRig v%s for Windows …", version)
    log.info("  %s", url)

    TOOLS_DIR.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(dir=TOOLS_DIR) as tmp_str:
        tmp     = Path(tmp_str)
        archive = tmp / "xmrig.zip"

        try:
            urllib.request.urlretrieve(url, archive, reporthook=_show_progress)
            print()
        except Exception as exc:
            raise RuntimeError(f"Download failed: {exc}") from exc

        with zipfile.ZipFile(archive, "r") as zf:
            zf.extractall(tmp)

        exe = next((p for p in tmp.rglob("xmrig.exe") if p.is_file()), None)
        if exe is None:
            raise RuntimeError("xmrig.exe not found inside downloaded archive")

        if XMRIG_DIR.exists():
            shutil.rmtree(XMRIG_DIR)
        shutil.move(str(exe.parent), XMRIG_DIR)

    log.info("XMRig installed → %s", BINARY)
    return BINARY


def ensure_xmrig(version: str) -> Path:
    """
    Return a Path to xmrig.exe.
    Priority:
      1. Already-downloaded binary in tools/xmrig/
      2. System-installed binary in PATH
      3. Download from GitHub
    """
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
