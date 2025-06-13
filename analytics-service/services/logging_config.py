"""logging_config.py

Unified JSON logging for all modules.

Usage
-----
>>> from logging_config import get_logger
>>> log = get_logger(__name__)
>>> log.info("Fall detected", event="fall", trace_id="abc123", session_id=7,
...          data={"person_id": 3, "confidence": 0.92})

The output is a single‑line JSON object, easy to ingest into ELK / Loki / Splunk.
"""
from __future__ import annotations

import logging
import sys
from typing import Any, Dict, Optional

import structlog

# ---------------------------------------------------------------------------
# Helper processors
# ---------------------------------------------------------------------------

def _add_module(logger: structlog.BoundLogger, method: str, event_dict: Dict[str, Any]):
    """Ensure the module name (logger name) is present in every record."""
    if "module" not in event_dict:
        event_dict["module"] = logger.name or "root"
    return event_dict


# ---------------------------------------------------------------------------
# Global configuration (called on import)
# ---------------------------------------------------------------------------

def _configure() -> None:
    """Configure std logging + structlog once."""

    # 1) Base Python logging → INFO to stdout (stderr is noisy under gunicorn)
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stdout,
        format="%(message)s",  # structlog will render JSON; keep raw format here
    )

    # 2) structlog processors pipeline
    processors = [
        structlog.processors.TimeStamper(fmt="iso", utc=True, key="ts"),
        _add_module,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),  # final JSON dump
    ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.PrintLoggerFactory(stream=sys.stdout),
        cache_logger_on_first_use=True,
    )


# run once at import
_configure()


# ---------------------------------------------------------------------------
# Public helper
# ---------------------------------------------------------------------------

def get_logger(name: Optional[str] = None) -> structlog.BoundLogger:  # type: ignore[name-defined]
    """Return a structlog logger; call at module level.

    Parameters
    ----------
    name : Optional[str]
        Usually pass `__name__` to set the module field.
    """
    return structlog.get_logger(name)
