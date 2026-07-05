"""Structured logging for the whole app.

Usage:
    from app.utils.logger import get_logger
    log = get_logger(__name__)
    log.info("qualified lead", extra={"lead_id": "L-001"})
"""

import logging
import sys

from config import LOG_DIR, settings

_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_configured = False


def _configure_root() -> None:
    global _configured
    if _configured:
        return

    root = logging.getLogger("lead_qualification")
    root.setLevel(settings.log_level.upper())

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(logging.Formatter(_FORMAT))
    root.addHandler(console)

    file_handler = logging.FileHandler(LOG_DIR / "app.log", encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(_FORMAT))
    root.addHandler(file_handler)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a namespaced logger under the app's root logger."""
    _configure_root()
    return logging.getLogger(f"lead_qualification.{name}")
