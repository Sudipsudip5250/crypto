"""
platforms/macos.py
------------------
Everything macOS-specific:
  • Locating / downloading / installing XMRig  (arm64 or x64 tar.gz)
  • Launching XMRig (PTY like Linux for colour output)
"""

from __future__ import annotations

import logging
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
import urllib.request
from pathlib import Path

log = logging.getLogger("xmr-miner")

BASE_DIR  = Path(__file__).resolve().parent.parent
TOOLS_DIR = BASE_DIR / "tools"
XMRIG_DIR = TOOLS_DIR / "xmrig"
BINARY    = XMRIG_DIR / "xmrig"

_ARCH = platform.machine().lower()
_IS_ARM = any(tag in _ARCH for tag in ("arm", "aarch64"))

def _release_url(version: str) -> str:
    suffix = "arm64" if _IS_ARM else "x64"
    return (
        f"https://github.com/xmrig/xmrig/releases/download"
        f"/v{version}/xmrig-{version}-macos-{suffix}.tar.gz"
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
    """Download the macOS release (arm64 or x64) from GitHub."""
    url = _release_url(version)
    log.info("Downloading XMRig v%s for macOS (%s) …", version, "arm64" if _IS_ARM else "x64")
    log.info("  %s", url)

    TOOLS_DIR.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(dir=TOOLS_DIR) as tmp_str:
        tmp     = Path(tmp_str)
        archive = tmp / "xmrig.tar.gz"

        try:
            urllib.request.urlretrieve(url, archive, reporthook=_show_progress)
            print()
        except Exception as exc:
            raise RuntimeError(f"Download failed: {exc}") from exc

        with tarfile.open(archive, "r:gz") as tf:
            tf.extractall(tmp, filter="data")

        binary = next((p for p in tmp.rglob("xmrig") if p.is_file()), None)
        if binary is None:
            raise RuntimeError("xmrig binary not found inside downloaded archive")

        if XMRIG_DIR.exists():
            shutil.rmtree(XMRIG_DIR)
        shutil.move(str(binary.parent), XMRIG_DIR)

    BINARY.chmod(0o755)
    log.info("XMRig installed → %s", BINARY)

    from core.updater import write_cached_version
    write_cached_version(version)

    return BINARY


def try_brew() -> Path | None:
    """Try installing xmrig via Homebrew. Returns path on success, None otherwise."""
    if not shutil.which("brew"):
        return None
    try:
        log.info("Installing xmrig via Homebrew …")
        result = subprocess.run(["brew", "install", "xmrig"], check=False)
        if result.returncode == 0:
            path = shutil.which("xmrig")
            if path:
                log.info("xmrig installed via brew: %s", path)
                return Path(path)
    except Exception as exc:
        log.warning("brew install failed: %s", exc)
    return None


def ensure_xmrig(version: str) -> Path:
    """
    Return a Path to xmrig binary on macOS.
    Priority:
      1. Already-downloaded binary in tools/xmrig/
      2. System-installed binary in PATH
      3. Homebrew install
      4. Direct download from GitHub
    """
    if BINARY.exists():
        log.info("Using cached XMRig: %s", BINARY)
        return BINARY

    system = shutil.which("xmrig")
    if system:
        log.info("Using system XMRig: %s", system)
        return Path(system)

    brew = try_brew()
    if brew:
        return brew

    return download_xmrig(version)


# ---------------------------------------------------------------------------
# Process launch  (PTY for colour output — same pattern as Linux)
# ---------------------------------------------------------------------------

def launch_process(cmd: list[str]) -> tuple[subprocess.Popen, threading.Event]:
    """
    Launch XMRig on macOS with a PTY.

    Returns
    -------
    proc       : subprocess.Popen
    stop_event : threading.Event
    """
    stop_event = threading.Event()

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

        def _forward() -> None:
            try:
                while not stop_event.is_set():
                    data = os.read(master_fd, 4096)
                    if not data:
                        break
                    sys.stdout.buffer.write(data)
                    sys.stdout.buffer.flush()
            except OSError:
                pass
            finally:
                try:
                    os.close(master_fd)
                except OSError:
                    pass

        threading.Thread(target=_forward, daemon=True).start()

    except Exception as exc:
        log.warning("PTY launch failed (%s) — using plain pipes", exc)
        proc = subprocess.Popen(cmd, stdout=sys.stdout, stderr=sys.stderr)

    return proc, stop_event
