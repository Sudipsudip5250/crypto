"""
platforms/linux.py
------------------
Everything Linux-specific:
  • Locating / downloading / installing XMRig
  • Launching XMRig with a PTY so colour and banner output is preserved

For educational and research purposes only — see DISCLAIMER.md.
"""
# ── Educational / research use only ─────────────────────────────────────────
# See DISCLAIMER.md and LICENSE for full legal notices.
# ────────────────────────────────────────────────────────────────────────────

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
from pathlib import Path

from core.download import download_verified

log = logging.getLogger("xmr-miner")

BASE_DIR  = Path(__file__).resolve().parent.parent
TOOLS_DIR = BASE_DIR / "tools"
XMRIG_DIR = TOOLS_DIR / "xmrig"
BINARY    = XMRIG_DIR / "xmrig"

RELEASE_URL = (
    "https://github.com/xmrig/xmrig/releases/download"
    "/v{version}/xmrig-{version}-linux-static-x64.tar.gz"
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


def _safe_extractall(tf: tarfile.TarFile, dest: Path) -> None:
    """
    Extract a tar archive safely.

    Uses the ``filter="data"`` argument added in Python 3.11.4 / 3.12 to
    block path-traversal and setuid/setgid members.  Falls back to a manual
    member-by-member safe extraction on older Python versions.
    """
    if sys.version_info >= (3, 11, 4):
        tf.extractall(dest, filter="data")
        return

    # Manual safe extraction for Python < 3.11.4
    for member in tf.getmembers():
        # Block absolute paths and path traversal
        if os.path.isabs(member.name) or ".." in member.name.split(os.sep):
            log.warning("Skipping unsafe tar member: %s", member.name)
            continue
        # Block setuid / setgid bits
        member.mode = member.mode & 0o755
        tf.extract(member, dest)


def download_xmrig(version: str) -> Path:
    """Download the official Linux static x64 release and unpack it."""
    machine = platform.machine().lower()
    if machine not in {"x86_64", "amd64"}:
        raise RuntimeError(
            f"No official static Linux x64 archive matches {machine!r}. "
            "Install a native XMRig binary or build XMRig for this architecture."
        )

    url = RELEASE_URL.format(version=version)
    asset_name = f"xmrig-{version}-linux-static-x64.tar.gz"
    log.info("Downloading XMRig v%s for Linux …", version)
    log.info("  %s", url)

    TOOLS_DIR.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(dir=TOOLS_DIR) as tmp_str:
        tmp     = Path(tmp_str)
        archive = tmp / "xmrig.tar.gz"

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

        with tarfile.open(archive, "r:gz") as tf:
            _safe_extractall(tf, tmp)

        binary = next(
            (p for p in tmp.rglob("xmrig") if p.is_file()),
            None,
        )
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


def try_package_manager() -> Path | None:
    """
    Attempt to install xmrig via the system package manager.
    Returns the path to xmrig if successful, None otherwise.
    """
    candidates = [
        ("apt-get",
         ["sudo", "apt-get", "update", "-qq"],
         ["sudo", "apt-get", "install", "-y", "xmrig", "lm-sensors"]),
        ("dnf",    None, ["sudo", "dnf",    "install", "-y", "xmrig", "lm_sensors"]),
        ("yum",    None, ["sudo", "yum",    "install", "-y", "xmrig", "lm_sensors"]),
        ("pacman", None, ["sudo", "pacman", "-Syu", "--noconfirm", "xmrig", "lm_sensors"]),
        ("zypper", None, ["sudo", "zypper", "install", "-y", "xmrig", "lm_sensors"]),
    ]

    for mgr, pre_cmd, install_cmd in candidates:
        if not shutil.which(mgr):
            continue
        try:
            if pre_cmd:
                subprocess.run(pre_cmd, check=False, capture_output=True)
            log.info("Installing xmrig via %s …", mgr)
            subprocess.run(install_cmd, check=False)
            path = shutil.which("xmrig")
            if path:
                log.info("xmrig installed via %s: %s", mgr, path)
                return Path(path)
        except Exception as exc:
            log.warning("Package manager '%s' failed: %s", mgr, exc)

    return None


def ensure_xmrig(version: str, native_path: str = "") -> Path:
    """
    Return a Path to a working xmrig binary.
    Priority order:
      1. Already-downloaded binary in tools/xmrig/
      2. System-installed binary in PATH
      3. System package manager install
      4. Direct download of static binary from GitHub
    """
    if native_path:
        path = Path(native_path).expanduser().resolve()
        if not path.is_file() or not os.access(path, os.X_OK):
            raise RuntimeError(f"Configured XMRig path is not an executable file: {path}")
        log.info("Using configured native XMRig: %s", path)
        return path

    if BINARY.exists():
        log.info("Using cached XMRig: %s", BINARY)
        return BINARY

    system = shutil.which("xmrig")
    if system:
        log.info("Using system XMRig: %s", system)
        return Path(system)

    pkg = try_package_manager()
    if pkg:
        return pkg

    return download_xmrig(version)


# ---------------------------------------------------------------------------
# Process launch  (PTY so XMRig thinks it's attached to a real terminal)
# ---------------------------------------------------------------------------

def launch_process(cmd: list[str]) -> tuple[subprocess.Popen, threading.Event]:
    """
    Launch XMRig with a PTY.

    Returns
    -------
    proc       : subprocess.Popen
    stop_event : threading.Event — set this to signal the output-forward thread to stop
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
