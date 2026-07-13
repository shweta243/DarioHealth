"""Shared helpers: logging, filesystem, and JSON persistence."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from . import config


def get_logger(name: str = "steam_insights") -> logging.Logger:
    """Return a configured module logger (idempotent)."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
            datefmt="%H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


def ensure_directories() -> None:
    """Create the data directories if they do not yet exist."""
    for directory in (config.RAW_DIR, config.PROCESSED_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def save_json(data: Any, path: Path) -> None:
    """Persist a Python object to disk as pretty-printed JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False, default=str)


def load_json(path: Path) -> Any:
    """Load a JSON file from disk."""
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)
