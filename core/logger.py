"""
core/logger.py
--------------
Centralised logging setup.  Call setup_logging() once at startup; every other
module then uses  logging.getLogger("xmr-miner")  to get the same logger.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

LOGGER_NAME = "xmr-miner"


def setup_logging(log_to_file: bool = True, log_dir: Path | None = None) -> logging.Logger:
    """
    Configure and return the root project logger.

    Parameters
    ----------
    log_to_file : bool
        When True, also writes to <log_dir>/miner.log.
    log_dir : Path | None
        Directory for the log file.  Defaults to ./logs/ relative to CWD.
    """
    if log_dir is None:
        log_dir = Path.cwd() / "logs"
    log_dir.mkdir(exist_ok=True)

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    handlers: list[logging.Handler] = []

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    handlers.append(console)

    if log_to_file:
        fh = logging.FileHandler(log_dir / "miner.log", encoding="utf-8")
        fh.setFormatter(fmt)
        handlers.append(fh)

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)

    # Avoid duplicate handlers if called more than once
    if not logger.handlers:
        for h in handlers:
            logger.addHandler(h)

    return logger


def get_logger() -> logging.Logger:
    """Convenience: return the project logger (must call setup_logging first)."""
    return logging.getLogger(LOGGER_NAME)
