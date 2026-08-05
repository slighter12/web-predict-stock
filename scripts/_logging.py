"""Shared logging setup for command-line scripts."""

from __future__ import annotations

import logging
import os


_LOG_LEVELS = {
    "CRITICAL": logging.CRITICAL,
    "ERROR": logging.ERROR,
    "WARNING": logging.WARNING,
    "INFO": logging.INFO,
    "DEBUG": logging.DEBUG,
    "NOTSET": logging.NOTSET,
}


def configure_cli_logging() -> None:
    """Configure the process root logger for a command-line entrypoint."""

    logging.basicConfig(
        level=_LOG_LEVELS.get(os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
