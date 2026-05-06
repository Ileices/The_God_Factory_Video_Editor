"""
Logging setup — file + console, with crash-dump support.
"""

import logging
import sys
import traceback
from datetime import datetime
from pathlib import Path

from god_factory_editor.config import LOGS_DIR, APP_NAME

_LOG_FILE = LOGS_DIR / f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

# ── Root logger ───────────────────────────────────────────────────────────────
def get_logger(name: str = APP_NAME) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )

    # File handler (always DEBUG level)
    fh = logging.FileHandler(_LOG_FILE, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    # Console handler (INFO+ only)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    return logger


log = get_logger()


# ── Crash handler ─────────────────────────────────────────────────────────────
def install_crash_handler():
    """Redirect uncaught exceptions to the log file."""
    def _handler(exc_type, exc_value, exc_tb):
        crash_file = LOGS_DIR / f"crash_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        msg = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        log.critical(f"UNCAUGHT EXCEPTION:\n{msg}")
        try:
            crash_file.write_text(msg, encoding="utf-8")
        except Exception:
            pass
        sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = _handler
