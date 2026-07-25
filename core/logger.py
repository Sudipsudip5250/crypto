"""
core/logger.py
--------------
Centralised logging setup.

Call setup_logging() once at startup; every other module then uses
    logging.getLogger("xmr-miner")
to get the same logger.

The log directory defaults to <project_root>/logs/ — resolved from this
file's location so it is correct regardless of the current working directory.

For educational and research purposes only — see DISCLAIMER.md.
"""
# ── Educational / research use only ─────────────────────────────────────────
# See DISCLAIMER.md and LICENSE for full legal notices.
# ────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import logging
import sys
from pathlib import Path

LOGGER_NAME = "xmr-miner"

# Project-root-relative default log directory (does not depend on CWD)
_DEFAULT_LOG_DIR = Path(__file__).resolve().parent.parent / "logs"


def setup_logging(
    log_to_file: bool = True,
    log_dir: Path | None = None,
) -> logging.Logger:
    """
    Configure and return the root project logger.

    Parameters
    ----------
    log_to_file : bool
        When True, also writes to <log_dir>/miner.log.
    log_dir : Path | None
        Directory for the log file.
        Defaults to <project_root>/logs/ — NOT relative to CWD.
    """
    if log_dir is None:
        log_dir = _DEFAULT_LOG_DIR

    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        # Non-fatal: just skip file logging if the directory can't be created
        print(f"[logger] Warning: could not create log directory {log_dir}: {exc}",
              file=sys.stderr)
        log_to_file = False

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    handlers: list[logging.Handler] = []

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    handlers.append(console)

    if log_to_file:
        try:
            fh = logging.FileHandler(log_dir / "miner.log", encoding="utf-8")
            fh.setFormatter(fmt)
            handlers.append(fh)
        except OSError as exc:
            print(f"[logger] Warning: could not open log file: {exc}", file=sys.stderr)

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)

    # Avoid duplicate handlers if called more than once
    if not logger.handlers:
        for h in handlers:
            logger.addHandler(h)

    return logger


def get_logger() -> logging.Logger:
    """Convenience: return the project logger (call setup_logging first)."""
    return logging.getLogger(LOGGER_NAME)
