"""
EN02 v3 — Lightweight Structured Logger
Zero extra dependencies — uses stdlib logging only.
Structured JSON-style output for easy parsing in production.
"""

import logging
import time
import json
import sys

from ai.config import LOG_LEVEL

# ── Formatter: emit one JSON line per record ──────────────────────────────────
class _JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts":      self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level":   record.levelname,
            "module":  record.name,
            "msg":     record.getMessage(),
        }
        if hasattr(record, "extra"):
            payload.update(record.extra)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def get_logger(name: str = "en02") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:          # avoid duplicate handlers on re-import
        return logger

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JSONFormatter())
    logger.addHandler(handler)
    logger.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))
    logger.propagate = False
    return logger


# ── Convenience: log with extra structured fields ─────────────────────────────
def log_request(logger: logging.Logger, endpoint: str, filename: str) -> float:
    """Call at request start; returns start timestamp."""
    t = time.perf_counter()
    r = logging.LogRecord("en02", logging.INFO, "", 0, "request received", (), None)
    r.extra = {"endpoint": endpoint, "file": filename}
    logger.handle(r)
    return t


def log_result(logger: logging.Logger, start_t: float,
               detected: bool, emission_kghr: float, severity: str) -> float:
    """Call after processing; returns elapsed ms."""
    elapsed_ms = round((time.perf_counter() - start_t) * 1000, 1)
    r = logging.LogRecord("en02", logging.INFO, "", 0, "prediction complete", (), None)
    r.extra = {
        "elapsed_ms":    elapsed_ms,
        "detected":      detected,
        "emission_kghr": emission_kghr,
        "severity":      severity,
    }
    logger.handle(r)
    return elapsed_ms


def log_error(logger: logging.Logger, endpoint: str, error: str) -> None:
    r = logging.LogRecord("en02", logging.ERROR, "", 0, "request failed", (), None)
    r.extra = {"endpoint": endpoint, "error": error}
    logger.handle(r)
