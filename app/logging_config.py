"""Structured logging for DE-Guardian."""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        """
        Format a LogRecord into a JSON-encoded string representing a structured log entry.
        
        Constructs a payload containing a UTC ISO8601 timestamp, the record's level, logger name, and message, and includes any of the optional attributes `run_id`, `event`, `armed_mode`, `attempt`, and `status_code` if present on the record. If exception information is present on the record, includes a formatted `exc_info` entry.
        
        Parameters:
            record (logging.LogRecord): The log record to format.
        
        Returns:
            str: JSON string of the structured log payload.
        """
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key in ("run_id", "event", "armed_mode", "attempt", "status_code"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging() -> None:
    """
    Configure the root logger to emit JSON-formatted logs to standard output.
    
    Adds a StreamHandler that writes JSON via JsonFormatter and sets the root logger level to INFO.
    If the root logger already has any handlers, no changes are made.
    """
    root = logging.getLogger()
    if root.handlers:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    root.setLevel(logging.INFO)


def get_logger(name: str) -> logging.Logger:
    """
    Obtain a logger associated with the given name.
    
    Parameters:
        name (str): The logger name used to retrieve or create the logger.
    
    Returns:
        logging.Logger: Logger instance for the specified name.
    """
    return logging.getLogger(name)
