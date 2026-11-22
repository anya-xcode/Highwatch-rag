"""
Logging configuration.

- LOG_FORMAT=console: human-readable logs for local development.
- LOG_FORMAT=json: one JSON object per line with `severity` and `message`
  fields. Google Cloud Logging parses this format automatically when the app
  runs on Cloud Run (no SDK or extra cost); locally it is just stdout.
"""

import logging
import sys

import structlog

_SEVERITY = {
    "debug": "DEBUG",
    "info": "INFO",
    "warning": "WARNING",
    "warn": "WARNING",
    "error": "ERROR",
    "exception": "ERROR",
    "critical": "CRITICAL",
}


def _add_severity(_logger, method_name, event_dict):
    level = str(event_dict.get("level", method_name)).lower()
    event_dict["severity"] = _SEVERITY.get(level, "DEFAULT")
    return event_dict


def configure_logging(level: str = "info", fmt: str = "console") -> None:
    """Configure structlog for console or Cloud Logging-compatible JSON output."""
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    shared = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]

    if fmt == "json":
        processors = shared + [
            _add_severity,
            structlog.processors.format_exc_info,
            structlog.processors.EventRenamer("message"),
            structlog.processors.JSONRenderer(),
        ]
    else:
        processors = shared + [
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.dev.ConsoleRenderer(),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=False,
    )
