"""
Centralized logging configuration.
Provides a structured logger with rotating file handler and console handler.
"""
import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional

from app.core.config import settings


_FORMATTER = logging.Formatter(
    fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)


def _build_file_handler(log_path: Path) -> logging.handlers.RotatingFileHandler:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        filename=str(log_path),
        maxBytes=settings.LOG_ROTATION_BYTES,
        backupCount=settings.LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.setFormatter(_FORMATTER)
    return handler


def _build_console_handler() -> logging.StreamHandler:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_FORMATTER)
    return handler


def get_logger(name: str, log_file: Optional[str] = None) -> logging.Logger:
    """
    Return a named logger with rotating file + console handlers.

    Args:
        name:     Logger name (use __name__ of the calling module).
        log_file: Optional override for the log file name (inside LOGS_DIR).
                  Defaults to 'platform.log'.
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        # Already configured – return as-is to prevent duplicate handlers.
        return logger

    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    logger.setLevel(level)

    file_name = log_file or "platform.log"
    log_path = settings.LOGS_DIR / file_name

    logger.addHandler(_build_file_handler(log_path))
    logger.addHandler(_build_console_handler())
    logger.propagate = False
    return logger


# Module-level platform logger used across the application.
platform_logger = get_logger("ai_platform")
