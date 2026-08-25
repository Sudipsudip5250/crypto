"""
platforms/detect.py
-------------------
OS and architecture detection.
Returns the correct platform handler module and a summary dict used by
other modules to make OS-specific decisions without re-running detection.
"""

from __future__ import annotations

import platform
import sys
from pathlib import Path
from types import ModuleType


# ---------------------------------------------------------------------------
# Raw detection
# ---------------------------------------------------------------------------

_SYS   = platform.system().lower()
_MACH  = platform.machine().lower()

IS_WINDOWS = _SYS.startswith("win")
IS_LINUX   = _SYS.startswith("linux")
IS_MACOS   = _SYS.startswith("darwin")
IS_ARM     = any(tag in _MACH for tag in ("arm", "aarch64"))
IS_X86_64  = any(tag in _MACH for tag in ("x86_64", "amd64"))

OS_NAME    = platform.system()          # "Linux" / "Windows" / "Darwin"
OS_VERSION = platform.version()
ARCH       = platform.machine()         # "x86_64" / "aarch64" / "AMD64" …
PYTHON_VER = platform.python_version()


def _raspberry_pi_model() -> str | None:
    """Return the Linux device-tree model when running on a Raspberry Pi."""
    if not IS_LINUX:
        return None
    try:
        model = Path("/proc/device-tree/model").read_text(encoding="utf-8", errors="replace").strip("\x00\n")
    except OSError:
        return None
    return model or None


RPI_MODEL = _raspberry_pi_model()


def info() -> dict:
    """Return a dict summarising the detected environment."""
    return {
        "os":         OS_NAME,
        "os_version": OS_VERSION,
        "arch":       ARCH,
        "is_windows": IS_WINDOWS,
        "is_linux":   IS_LINUX,
        "is_macos":   IS_MACOS,
        "is_arm":     IS_ARM,
        "is_x86_64":  IS_X86_64,
        "python":     PYTHON_VER,
        "is_raspberry_pi": bool(RPI_MODEL),
        "raspberry_pi_model": RPI_MODEL or "",
    }


def get_platform_module() -> ModuleType:
    """
    Import and return the OS-specific platform module.

    Returns
    -------
    platforms.linux   on Linux
    platforms.windows on Windows
    platforms.macos   on macOS / Darwin
    """
    if IS_LINUX:
        from platforms import linux
        return linux
    if IS_WINDOWS:
        from platforms import windows
        return windows
    if IS_MACOS:
        from platforms import macos
        return macos

    print(f"[detect] Unsupported OS: {OS_NAME}. Only Linux, Windows, and macOS are supported.")
    sys.exit(1)
