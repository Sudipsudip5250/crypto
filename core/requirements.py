"""
core/requirements.py
--------------------
Auto-checks and pip-installs any missing Python packages before the rest of
the project imports them.  Called at the very top of miner.py so every other
module can assume its dependencies are present.

For educational and research purposes only — see DISCLAIMER.md.
"""
# ── Educational / research use only ─────────────────────────────────────────
# See DISCLAIMER.md and LICENSE for full legal notices.
# ────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import importlib.util
import subprocess
import sys

# Map  import-name  →  pip install-spec
REQUIRED: dict[str, str] = {
    "psutil": "psutil>=5.9",
}


def _is_importable(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def _pip_install(pip_spec: str) -> bool:
    """Attempt a quiet pip install. Returns True on success."""
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
    missing = [
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
        if not _pip_install(spec):
            failed.append(spec)

    if failed:
        print(f"[setup] ERROR: Could not install: {', '.join(failed)}")
        print("        Please run:  pip install " + " ".join(failed))
        sys.exit(1)

    if not silent:
        print("[setup] All requirements satisfied.\n")
