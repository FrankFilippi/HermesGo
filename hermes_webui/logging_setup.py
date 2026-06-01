"""Logging configuration.

All logs land under ``%LOCALAPPDATA%\\hermes\\logs\\hermeswebui\\`` so that when a
"normal user" reports a problem, you can ask them for one folder and get the full
picture: the shell launcher log, plus the captured stdout/stderr of the Hermes
dashboard subprocess (written separately by :mod:`hermes_webui.hermes_manager`).

We use a rotating file handler (5 files x 2 MB) so logs never grow unbounded, and
also echo to stderr which is handy in a developer checkout.
"""

from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path

from . import paths

_CONFIGURED = False


def setup() -> Path:
    """Configure root logging once. Returns the path of the main log file."""
    global _CONFIGURED
    log_file = paths.logs_dir() / "hermeswebui.log"
    if _CONFIGURED:
        return log_file

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    fmt = logging.Formatter(
        "%(asctime)s %(levelname)-7s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=2 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

    # stderr is detached in a windowed (no-console) PyInstaller build, so guard it.
    if sys.stderr is not None:
        stream = logging.StreamHandler(sys.stderr)
        stream.setFormatter(fmt)
        root.addHandler(stream)

    # Quiet down chatty third parties.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    _CONFIGURED = True
    logging.getLogger("hermes_webui").info("Logging initialised -> %s", log_file)
    return log_file


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
