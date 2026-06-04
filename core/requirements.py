"""
core/requirements.py
--------------------
Auto-checks and pip-installs any missing Python packages before the rest of
the project imports them.  Called at the very top of miner.py so every other
module can assume its dependencies are present.
"""

from __future__ import annotations

import importlib
import importlib.util
import subprocess
import sys

# Map  import-name  →  pip install-name
REQUIRED: dict[str, str] = {
    "psutil": "psutil>=5.9",
}

# Optional extras (nice-to-have, not fatal if they fail)
OPTIONAL: dict[str, str] = {
    "keyboard": "keyboard",   # for future keypress controls on Windows
}


def _is_importable(module_name: str) -> bool:
    spec = importlib.util.find_spec(module_name)
    return spec is not None


def _pip_install(pip_spec: str) -> bool:
    """Return True on success."""
    print(f"  [setup] Installing {pip_spec} …")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--quiet", pip_spec],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def check_and_install(*, silent: bool = False) -> None:
    """
    Verify every package in REQUIRED is importable.
    If not, attempt a silent pip install.
    Raises SystemExit if a required package cannot be installed.
    """
    missing: list[tuple[str, str]] = [
        (mod, spec)
        for mod, spec in REQUIRED.items()
        if not _is_importable(mod)
    ]

    if not missing:
        return

    if not silent:
        print("[setup] Some required packages are missing — installing now…")

    failed: list[str] = []
    for mod, spec in missing:
        ok = _pip_install(spec)
        if not ok:
            failed.append(spec)

    if failed:
        print(f"[setup] ERROR: Could not install: {', '.join(failed)}")
        print("        Please run:  pip install " + " ".join(failed))
        sys.exit(1)

    if not silent:
        print("[setup] All requirements satisfied.\n")

    # Also try optionals — failures are warnings only
    for mod, spec in OPTIONAL.items():
        if not _is_importable(mod):
            _pip_install(spec)
