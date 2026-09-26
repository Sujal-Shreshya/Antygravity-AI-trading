"""
Structured logging module for AI Trading Engine.
Supports standardized JSON log output in production and colored console output in development.
"""

import json
import logging
import sys
from contextvars import ContextVar
from typing import Any

# ContextVar for distributed request tracing and order correlation
correlation_id_ctx: ContextVar[str | None] = ContextVar("correlation_id", default=None)


class JSONFormatter(logging.Formatter):
    """Formats log records as structured JSON strings."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "line": record.lineno,
        }

        corr_id = correlation_id_ctx.get()
        if corr_id:
            log_obj["correlation_id"] = corr_id

        if hasattr(record, "extra") and isinstance(record.extra, dict):
            log_obj["extra"] = record.extra

        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_obj)


def configure_logging(level: str = "INFO", json_format: bool = False) -> None:
    """Configures the root logger with the chosen formatter."""
    root_logger = logging.getLogger()
    root_logger.setLevel(level.upper())

    # Clear existing handlers
    root_logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    if json_format:
        formatter = JSONFormatter(datefmt="%Y-%m-%dT%H:%M:%S%z")
    else:
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    handler.setFormatter(formatter)
    root_logger.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """Returns a named logger instance."""
    return logging.getLogger(name)
